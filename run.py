"""Full pipeline orchestrator + Stage 6 FALLBACK.

    python run.py            # run the whole pipeline once, locally or in CI

Sequence: fetch -> cluster -> score -> render, then record the winner to the
decay ledger. Runs the stages in-process so the data is held in memory and
inspected once.

FALLBACK behaviour (Stage 6):
  * Too little data: the scorer always forces a single winner from whatever
    clusters exist, so even one article yields a page. Only *zero* articles is
    a genuine failure.
  * Whole run fails: we never serve a broken page. If a previous index.html
    exists (it is committed to the repo), we leave its content intact and
    inject a subtle "showing yesterday's story" banner. If there is no prior
    page at all (first run failed), we exit non-zero with nothing to publish.
"""
from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from common import load_feeds, load_settings, rel, write_json
from cluster import build_clusters
from fetch import fetch_all
from ledger import load_ledger, record_winner
from rank import build_ranked_table, score_clusters
from render import render_html

# Marker so the stale-banner injection is idempotent across repeated failures.
# Must be quote-agnostic text present in BOTH the freshly-rendered stale banner
# (render.py) and the injected one below - the banner copy is identical in each.
_STALE_MARKER = "Showing yesterday's story"


class PipelineError(RuntimeError):
    pass


def _inject_stale_banner() -> bool:
    """Add the 'showing yesterday's story' banner to the existing index.html.

    Returns True if a prior page was present (stale fallback served), False if
    there is nothing to fall back to.
    """
    settings = load_settings()
    path = rel(settings["output_html"])
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8") as fh:
        html_doc = fh.read()
    if _STALE_MARKER in html_doc:
        return True  # already flagged on a previous failed run
    banner = ("<div class='stale'>Showing yesterday's story - today's update "
              "did not complete.</div>")
    marker = '<div class="wrap">'
    if marker in html_doc:
        html_doc = html_doc.replace(marker, marker + "\n    " + banner, 1)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html_doc)
    return True


def _todays_incumbent(scored, settings, ledger, run_time_iso):
    """If a winner was already chosen today, return the current scored cluster
    that matches it (cosine over headlines) so the day's story stays fixed.
    Returns None on a fresh day, when daily_lock is off, or if the story faded."""
    if not settings.get("daily_lock"):
        return None
    run_date = datetime.fromisoformat(run_time_iso).date().isoformat()
    todays = [e for e in ledger if e.get("date") == run_date]
    if not todays:
        return None
    incumbent_text = todays[-1]["text"]
    texts = [" ".join(dict.fromkeys(m["title"] for m in c["members"]))
             for c in scored]
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2),
                          sublinear_tf=True)
    tfidf = vec.fit_transform(texts + [incumbent_text])
    sims = linear_kernel(tfidf[:-1], tfidf[-1:]).ravel()
    best = int(sims.argmax())
    if sims[best] >= settings["scoring"]["novelty_match_threshold"]:
        return scored[best]
    return None


def run_pipeline() -> dict:
    """Run all stages. Raises PipelineError on unrecoverable failure."""
    settings = load_settings()
    feeds = load_feeds()

    print("\n>>> FETCH")
    articles, report = fetch_all(settings, feeds)
    print(f"    {len(articles)} articles from "
          f"{report['feeds_ok']}/{report['feeds_ok'] + report['feeds_failed']} feeds")
    write_json("data/articles.json", {"report": report, "articles": articles})
    if not articles:
        raise PipelineError("fetch returned zero articles")

    print(">>> CLUSTER")
    clusters = build_clusters(articles, settings)
    print(f"    {len(clusters)} clusters")

    print(">>> SCORE")
    ledger = load_ledger(settings)
    scored = score_clusters(clusters, settings, feeds, report["run_time"], ledger)

    # Daily lock: if a winner was already chosen today, keep that same story
    # (refreshing its coverage) instead of letting a re-run pick a new one.
    incumbent = _todays_incumbent(scored, settings, ledger, report["run_time"])
    locked = incumbent is not None
    if locked:
        scored = [incumbent] + [c for c in scored if c is not incumbent]
        print("    daily lock: kept today's already-chosen story")

    ranked = build_ranked_table(scored, settings, report)
    write_json(settings["ranked_json_path"], ranked)
    win = ranked["winner"]
    print(f"    winner: {win['hero']['title'][:60]}")
    print(f"    score={win['score']:.4f} outlets={win['outlet_count']} "
          f"countries={len(win['countries'])} leans={len(win['leans'])}")

    print(">>> RENDER")
    out_path = rel(settings["output_html"])
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(render_html(ranked, stale=False))
    print(f"    wrote {out_path}")

    print(">>> LEDGER")
    if locked:
        print("    unchanged (today's winner already recorded)")
    else:
        lpath = record_winner(settings, win, report["run_time"])
        print(f"    recorded new daily winner -> {lpath}")

    return ranked


def main() -> int:
    print("=" * 70)
    print("ONE STORY - full pipeline")
    print("=" * 70)
    try:
        run_pipeline()
        print("\nOK - fresh page generated.")
        return 0
    except Exception as exc:  # noqa: BLE001 - top-level guard, never crash-publish
        print(f"\nPIPELINE FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        if _inject_stale_banner():
            print("FALLBACK - kept previous index.html, flagged as stale.",
                  file=sys.stderr)
            return 0  # publish the stale-flagged page; do not fail the job
        print("FALLBACK - no previous page to fall back to; nothing to publish.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
