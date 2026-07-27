"""Stage 1 - FETCH.

Pull entries from the RSS feeds in config/feeds.yaml, filter to a rolling
24h window, and normalise each item to a flat record:

    {title, source, country, lean, url, published_at, snippet}

Design rules:
- One dead feed must NEVER kill the run. Every feed is fetched in isolation;
  failures are counted and logged, then we move on.
- COPYRIGHT: we only ever keep the headline, the feed-supplied description
  (hard-capped to settings.snippet_cap_words), the source, and the link.
  No article body is ever fetched or stored.
- published_at is stored as an ISO-8601 UTC string. Items with no parseable
  date are dropped from the window (we cannot verify their recency).
"""
from __future__ import annotations

import calendar
import html
import re
import socket
import sys
from datetime import datetime, timedelta, timezone
from urllib.error import URLError

import feedparser

from common import load_feeds, load_settings, tz_now, write_json

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 OneStoryBot/1.0"
)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
# Non-article formats (podcasts, liveblogs, videos, newsletters, roundups).
# These are excluded: their titles are multi-topic digests (bad headlines) and
# their broad vocabulary bridges unrelated stories together during clustering.
_NOISE_URL = re.compile(
    r"(/podcasts?/|/videos?/|/watch/|/audio/|/galler(?:y|ies)/|/in-pictures/|"
    r"/live/|/liveblog|-live-|/live-updates|/newsletters?/)", re.I)
_NOISE_TITLE = re.compile(
    r"(\blive:|\blive updates?\b|\bliveblog\b|\bpodcast\b|\bnewsletter\b|"
    r"\bup first\b|from the politics desk|in today'?s edition|\bin pictures\b|"
    r"\bwatch:|"
    # Roundups / digests: they bridge unrelated stories during clustering and
    # surface as off-topic "sources" (e.g. "the biggest news you missed this
    # weekend"). Kept conservative to avoid dropping single-story explainers.
    r"\bbiggest news\b|\byou missed\b|\bin case you missed\b|\bicymi\b|"
    r"\bround-?up\b|\bweek in review\b|"
    r"\byour (?:morning|evening|weekend|weekly|daily) (?:briefing|rundown|digest)\b)",
    re.I)
# Emoji / pictographs some feeds prefix to titles (e.g. France 24's red-dot live
# marker) that otherwise render as stray symbols in the source list.
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF"
    "\U0001F1E6-\U0001F1FF️‍⃣]")


def is_noise_format(url: str, title: str) -> bool:
    """True for non-article formats (podcast/liveblog/video/newsletter/roundup)."""
    return bool(_NOISE_URL.search(url or "") or _NOISE_TITLE.search(title or ""))
# Google News site-scoped titles look like "Real headline - Reuters".
_GNEWS_SUFFIX_RE = re.compile(r"\s+-\s+[^-]+$")
# Connecting words we don't want a truncated snippet to end on.
_TRAILING_STOP = {
    "the", "a", "an", "and", "or", "but", "for", "to", "of", "in", "on", "at",
    "by", "with", "as", "that", "this", "from", "its", "their", "his", "her",
    "is", "was", "are", "were", "has", "have", "had", "into", "over", "after",
}


def _clean_snippet(raw: str, cap_words: int) -> str:
    """Strip HTML, collapse whitespace, hard-cap word count (copyright guard),
    and end gracefully - at a sentence boundary if one sits within the cap,
    otherwise trim any dangling connecting word before the ellipsis."""
    if not raw:
        return ""
    text = html.unescape(_TAG_RE.sub(" ", raw))
    text = _WS_RE.sub(" ", text).strip()
    words = text.split(" ")
    if len(words) <= cap_words:
        return text
    capped = words[:cap_words]
    # Prefer the last sentence boundary within the cap, if it keeps >= half.
    for end in range(len(capped) - 1, cap_words // 2, -1):
        if capped[end][-1:] in ".!?":
            return " ".join(capped[:end + 1])
    # Otherwise drop trailing connecting words, then add an ellipsis.
    while capped and capped[-1].lower().strip(".,;:'\"") in _TRAILING_STOP:
        capped.pop()
    return " ".join(capped).rstrip(".,;:") + "…"


def _entry_datetime(entry) -> datetime | None:
    """Return a tz-aware UTC datetime from published/updated struct_time."""
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            return datetime.fromtimestamp(calendar.timegm(st), tz=timezone.utc)
    return None


def _fetch_one(feed_cfg: dict):
    """Fetch and parse a single feed. Raises on hard network failure.

    We let feedparser drive the HTTP fetch (agent + gzip + charset detection
    from HTTP headers / XML declaration / BOM). Passing raw bytes ourselves
    lost the HTTP charset and mangled cp1252-in-UTF-8 smart quotes. The socket
    default timeout (set in fetch_all) bounds the connection.
    """
    parsed = feedparser.parse(feed_cfg["url"], agent=_UA)
    # A URLError etc. is captured by feedparser in .bozo/.bozo_exception rather
    # than raised; surface a genuine fetch failure (no entries + a network-y
    # exception) so it is counted as a failed feed.
    if not parsed.entries and parsed.get("bozo"):
        exc = parsed.get("bozo_exception")
        if isinstance(exc, (URLError, socket.timeout, ConnectionError)):
            raise exc
        status = parsed.get("status")
        if status and status >= 400:
            raise OSError(f"HTTP {status}")
    return parsed.entries


def fetch_all(settings: dict, feeds: list[dict]) -> tuple[list[dict], dict]:
    """Fetch every feed, normalise, window-filter. Returns (articles, report)."""
    now = tz_now(settings)
    window_start = now - timedelta(hours=settings["window_hours"])
    cap = settings["snippet_cap_words"]
    socket.setdefaulttimeout(settings["fetch_timeout_secs"])

    articles: list[dict] = []
    report = {
        "run_time": now.isoformat(),
        "window_start": window_start.isoformat(),
        "per_feed": [],
        "feeds_ok": 0,
        "feeds_failed": 0,
        "dropped_no_date": 0,
        "dropped_out_of_window": 0,
        "dropped_noise": 0,
    }

    for fc in feeds:
        is_gnews = fc.get("via") == "gnews"
        row = {"name": fc["name"], "kept": 0, "seen": 0, "error": None}
        try:
            entries = _fetch_one(fc)
            row["seen"] = len(entries)
            for e in entries:
                pub = _entry_datetime(e)
                if pub is None:
                    report["dropped_no_date"] += 1
                    continue
                if pub < window_start.astimezone(timezone.utc):
                    report["dropped_out_of_window"] += 1
                    continue
                title = _EMOJI_RE.sub("", html.unescape(e.get("title", "")))
                title = _WS_RE.sub(" ", title).strip()
                url = e.get("link", "")
                if not title or not url:
                    continue
                if is_noise_format(url, title):
                    report["dropped_noise"] += 1
                    continue
                if is_gnews:
                    # Strip the " - Source" suffix; the GNews description is a
                    # junk anchor, so drop the snippet entirely.
                    title = _GNEWS_SUFFIX_RE.sub("", title).strip()
                    snippet = ""
                else:
                    snippet = _clean_snippet(e.get("summary", ""), cap)
                articles.append({
                    "title": title,
                    "source": fc["name"],
                    "country": fc["country"],
                    "lean": fc["lean"],
                    "paywall": fc.get("paywall", "none"),
                    "url": url,
                    "published_at": pub.isoformat(),
                    "snippet": snippet,
                })
                row["kept"] += 1
            report["feeds_ok"] += 1
        except Exception as exc:  # noqa: BLE001 - one dead feed must not kill run
            row["error"] = f"{type(exc).__name__}: {exc}"
            report["feeds_failed"] += 1
        report["per_feed"].append(row)

    # Deterministic order: newest first, then source, then title.
    articles.sort(key=lambda a: (a["published_at"], a["source"], a["title"]),
                  reverse=True)
    return articles, report


def _print_report(articles: list[dict], report: dict) -> None:
    print("=" * 70)
    print("STAGE 1 - FETCH")
    print("=" * 70)
    print(f"Run time (local) : {report['run_time']}")
    print(f"Window start     : {report['window_start']}")
    print(f"Feeds OK / failed: {report['feeds_ok']} / {report['feeds_failed']}")
    print(f"Dropped (no date): {report['dropped_no_date']}")
    print(f"Dropped (stale)  : {report['dropped_out_of_window']}")
    print(f"Dropped (noise)  : {report['dropped_noise']}")
    print(f"Articles in window: {len(articles)}")
    print("-" * 70)
    print(f"{'feed':<34}{'seen':>6}{'kept':>6}  status")
    for r in report["per_feed"]:
        status = "ok" if r["error"] is None else r["error"][:60]
        print(f"{r['name']:<34}{r['seen']:>6}{r['kept']:>6}  {status}")
    print("-" * 70)
    print("Sample (up to 12 newest):")
    for a in articles[:12]:
        print(f"  [{a['country']:>3}/{a['lean']:<12}] {a['source']:<20} "
              f"{a['title'][:70]}")
    # Coverage sanity: how balanced is the raw pool?
    from collections import Counter
    print("-" * 70)
    print("Pool by country:", dict(Counter(a["country"] for a in articles)))
    print("Pool by lean   :", dict(Counter(a["lean"] for a in articles)))


def main() -> int:
    settings = load_settings()
    feeds = load_feeds()
    articles, report = fetch_all(settings, feeds)
    _print_report(articles, report)
    path = write_json("data/articles.json",
                      {"report": report, "articles": articles})
    print(f"\nWrote {len(articles)} articles -> {path}")
    return 0 if articles else 1


if __name__ == "__main__":
    sys.exit(main())
