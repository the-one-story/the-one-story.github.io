"""Stage 5 - RENDER.

Turn data/ranked.json into a single, aggressively spartan static index.html:
one large headline, the feed's own short description, one prominent hero link
(the best single write-up), a mechanical coverage line, the timestamp, and a
"next update" note. A collapsed "Why this story?" toggle reveals the runner-up
stories and the component scores that made the winner win.

COPYRIGHT: we render ONLY the headline, the feed-supplied snippet (already
word-capped at fetch time), the source name, a link, and stats we computed
ourselves. No article body, no fabricated "analysis". All feed-supplied text
is HTML-escaped.
"""
from __future__ import annotations

import html
import re
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from common import load_settings, read_json, rel

# Strip a trailing " - Section" or " (tags)" from a feed name for clean display
# e.g. "The Nation (US, left)" -> "The Nation", "The Guardian - World" -> "The Guardian".
_SRC_CLEAN = re.compile(r"\s*[(\-].*$")


def _clean_source(name: str) -> str:
    return _SRC_CLEAN.sub("", name).strip() or name


# Map five-point lean to three display buckets (Ground-News style).
_LEAN_BUCKET = {"left": "Left", "centre-left": "Left", "centre": "Centre",
                "centre-right": "Right", "right": "Right"}


def _fmt_local(iso: str, tzname: str) -> tuple[str, str]:
    dt = datetime.fromisoformat(iso).astimezone(ZoneInfo(tzname))
    return dt.strftime("%d/%m/%Y %H:%M"), dt.tzname() or ""


def _next_update(iso: str, tzname: str, update_hour_utc: int) -> str:
    """Human-readable next scheduled update: the next update_hour_utc:00 UTC
    after the run time, shown in local time (e.g. 'Fri 24 Jul, 06:00 AEST')."""
    run = datetime.fromisoformat(iso).astimezone(timezone.utc)
    nxt = run.replace(hour=update_hour_utc, minute=0, second=0, microsecond=0)
    if nxt <= run:
        nxt += timedelta(days=1)
    local = nxt.astimezone(ZoneInfo(tzname))
    return f"{local.strftime('%a %d %b, %H:%M')} {local.tzname()}"


def _display_snippet(winner: dict) -> str:
    """Prefer the hero's snippet; fall back to the first member that has one."""
    if winner.get("hero", {}).get("snippet"):
        return winner["hero"]["snippet"]
    for m in winner.get("members", []):
        if m.get("snippet"):
            return m["snippet"]
    return ""


_LEAN_ORDER = ["left", "centre-left", "centre", "centre-right", "right"]
_LEAN_NAME = {"left": "the left", "centre-left": "the centre-left",
              "centre": "the centre", "centre-right": "the centre-right",
              "right": "the right"}
_COUNTRY_NAME = {"INT": "Wire services", "GB": "UK", "QA": "Qatar",
                 "AU": "Australia", "US": "USA", "DE": "Germany",
                 "FR": "France", "IN": "India", "JP": "Japan", "CA": "Canada",
                 "IL": "Israel", "CN": "China", "BR": "Brazil", "ZA": "South Africa",
                 "SG": "Singapore", "AE": "UAE", "AR": "Argentina", "NG": "Nigeria"}


def _coverage_block(winner: dict) -> str:
    """A mechanical coverage visual, computed entirely from our own stats:
    a political-spectrum bar (lit where the story is being covered) and a chip
    per covering country. No article content, so no copyright concern."""
    n_out = winner["outlet_count"]
    n_cty = len(winner["countries"])
    present = set(winner["leans"])

    idx = [i for i, l in enumerate(_LEAN_ORDER) if l in present]
    lo, hi = _LEAN_ORDER[idx[0]], _LEAN_ORDER[idx[-1]]
    span = (f"all from {_LEAN_NAME[lo]}" if lo == hi
            else f"from {_LEAN_NAME[lo]} to {_LEAN_NAME[hi]}")

    segs = "".join(
        f'<span class="seg{" on" if l in present else ""}" title="{l}"></span>'
        for l in _LEAN_ORDER)
    chips = "".join(
        f'<span class="chip">{html.escape(_COUNTRY_NAME.get(c, c))}</span>'
        for c in winner["countries"])
    out_w = "outlet" if n_out == 1 else "outlets"
    cty_w = "country" if n_cty == 1 else "countries"

    return f"""<div class="coverage">
      <p class="cov-line">Running across <b>{n_out}</b> {out_w} in
        <b>{n_cty}</b> {cty_w}, spanning the political spectrum {span}.</p>
      <div class="spectrum" role="img"
           aria-label="Political spectrum, covered {span}">{segs}</div>
      <div class="spectrum-ends"><span>Left</span><span>Right</span></div>
      <div class="chips">{chips}</div>
    </div>"""


_WORLDMAP = None


def _worldmap() -> dict:
    global _WORLDMAP
    if _WORLDMAP is None:
        _WORLDMAP = read_json("assets/worldmap.json", default={}) or {}
    return _WORLDMAP


def _coverage_map(winner: dict) -> str:
    """A world map (Natural Earth, equirectangular) with a dot on each country
    running the story. Built from our own coverage stats. Wire services (INT)
    have no home country and are noted rather than plotted."""
    wm = _worldmap()
    cent = wm.get("centroids", {})
    if not wm.get("land"):
        return ""
    plotted = [(c, cent[c]) for c in winner["countries"] if c in cent]
    if not plotted:
        return ""
    vb = wm.get("viewbox", [0, 0, 720, 360])

    # Outlets per country (deduped, clean names) for the hover tooltip.
    outlets_by_country: dict[str, list[str]] = {}
    for m in winner.get("members", []):
        lst = outlets_by_country.setdefault(m["country"], [])
        name = _clean_source(m["source"])
        if name not in lst:
            lst.append(name)

    dots = ""
    for c, (x, y) in plotted:
        cname = _COUNTRY_NAME.get(c, c)
        outlets = ", ".join(outlets_by_country.get(c, []))
        tip = html.escape(f"{cname}: {outlets}" if outlets else cname)
        dots += (f'<g class="mnode"><title>{tip}</title>'
                 f'<circle cx="{x}" cy="{y}" r="12" class="mhalo"/>'
                 f'<circle cx="{x}" cy="{y}" r="4.5" class="mdot"/></g>')
    note = ('<p class="mnote">Wire services (Reuters, AP, AFP) are global and '
            "aren&rsquo;t plotted.</p>" if "INT" in winner["countries"] else "")
    return (f'<div class="covmap"><svg viewBox="{vb[0]} {vb[1]} {vb[2]} {vb[3]}"'
            ' class="wmap" role="img" aria-label="World map with a dot on each'
            f' country covering this story"><path class="wland" '
            f'd="{wm["land"]}"/>{dots}</svg>{note}</div>')


def _sources_section(winner: dict) -> str:
    """A Ground-News-style breakdown of who is covering this story: a coverage
    map, then one row per outlet grouped Left / Centre / Right, each linking to
    that outlet's own write-up. Shows how the headlines differ; marks paywalls."""
    members = winner.get("members", [])
    if not members:
        return ""
    # One row per outlet (keep the first, i.e. newest, article from each).
    by_source: dict[str, dict] = {}
    for m in members:
        by_source.setdefault(m["source"], m)

    buckets: dict[str, list[dict]] = {"Left": [], "Centre": [], "Right": []}
    for m in by_source.values():
        buckets[_LEAN_BUCKET.get(m["lean"], "Centre")].append(m)

    blocks = []
    for label in ("Left", "Centre", "Right"):
        items = sorted(buckets[label], key=lambda x: _clean_source(x["source"]))
        if not items:
            continue
        rows = []
        for m in items:
            url = html.escape(m["url"], quote=True)
            src = html.escape(_clean_source(m["source"]))
            head = html.escape(m["title"])
            lock = (' <span class="lock" title="paywalled">&#128274;</span>'
                    if m.get("paywall", "none") != "none" else "")
            rows.append(
                f'<li><a href="{url}" target="_blank" rel="noopener">{src}</a>'
                f'{lock}<span class="src-head">{head}</span></li>')
        blocks.append(
            f'<div class="bucket"><h4>{label}'
            f'<span class="bcount">{len(items)}</span></h4>'
            f'<ul>{"".join(rows)}</ul></div>')

    n = len(by_source)
    map_html = _coverage_map(winner)
    return f"""
    <details class="sources">
      <summary>Covered by {n} outlet{"s" if n != 1 else ""} &mdash; where &amp; who</summary>
      <div class="sources-body">{map_html}{"".join(blocks)}</div>
    </details>"""


_COMPONENT_DESC = {
    "coverage": "How many distinct outlets are running the story — log-scaled, "
                "so 20 isn't worth twice 10.",
    "diversity": "How widely that coverage is spread across countries and the "
                 "political spectrum — weighted heaviest, to beat a story merely "
                 "loud in one bloc.",
    "recency": "Favours coverage that is still building now over a story already "
               "fading.",
    "novelty": "Penalises a story that already led on a recent day, easing back "
               "over ~4 days, so a repeat must bring bigger coverage to win again.",
}


def _why_section(winner: dict, runners: list[dict]) -> str:
    k = winner["components"]
    comp_rows = "".join(
        f'<li><div class="chead"><span class="cname">{name}</span>'
        f'<span class="cscore">{k[name]:.2f}</span></div>'
        f'<p class="cdesc">{_COMPONENT_DESC[name]}</p></li>'
        for name in ("coverage", "diversity", "recency", "novelty")
    )
    nov = winner.get("novelty_match", {})
    nov_note = ""
    if nov.get("date"):
        nov_note = (f"<p class='note'>Novelty penalty applied: this story also "
                    f"led on {html.escape(nov['date'])} "
                    f"(match {nov['cosine']:.2f}). Day-two coverage must rebuild "
                    f"to hold the top slot.</p>")

    run_items = []
    for r in runners:
        title = html.escape(r["hero"]["title"])
        url = html.escape(r["hero"]["url"], quote=True)
        src = html.escape(r["hero"]["source"])
        run_items.append(
            f"<li><a href='{url}' target='_blank' rel='noopener'>{title}</a>"
            f"<span class='ru-meta'>{src} &middot; score {r['score']:.3f} "
            f"&middot; {r['outlet_count']} outlets, {len(r['countries'])} countries, "
            f"{len(r['leans'])} leans</span></li>"
        )
    runners_html = "".join(run_items) or "<li>No runners-up today.</li>"

    return f"""
    <details class="why">
      <summary>Why this story?</summary>
      <div class="why-body">
        <p>The winner is chosen by a fully deterministic score -
           <code>coverage &times; diversity &times; recency &times; novelty</code> -
           with no editorial judgement. Diversity (spread across countries
           <em>and</em> the political spectrum) carries the most weight, so a
           story that everyone agrees is big rises above one that is simply
           being shouted loudest in a single country's press.</p>
        <ul class="comp">{comp_rows}</ul>
        {nov_note}
        <h3>Today's runners-up</h3>
        <ol class="runners">{runners_html}</ol>
      </div>
    </details>"""


def render_html(ranked: dict, stale: bool = False) -> str:
    winner = ranked["winner"]
    runners = ranked.get("runners_up", [])
    tzname = ranked["timezone"]
    stamp, tzabbr = _fmt_local(ranked["run_time"], tzname)
    next_update = _next_update(ranked["run_time"], tzname,
                               ranked.get("update_hour_utc", 20))

    # Headline, snippet and link all come from the one hero article (the best
    # single write-up) so they read as a coherent unit.
    headline = html.escape(winner["hero"]["title"])
    snippet = html.escape(_display_snippet(winner))
    hero_url = html.escape(winner["hero"]["url"], quote=True)
    hero_src = html.escape(_clean_source(winner["hero"]["source"]))
    coverage_block = _coverage_block(winner)
    sources_block = _sources_section(winner)

    stale_banner = (
        "<div class='stale'>Showing yesterday's story - today's update did "
        "not complete.</div>" if stale else "")

    snippet_html = f'<p class="lede">{snippet}</p>' if snippet else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<meta name="theme-color" content="#14161a">
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<title>One Story</title>
<!-- Link-preview (Open Graph) - how the URL unfurls in WhatsApp, iMessage, Slack, etc. -->
<meta property="og:type" content="website">
<meta property="og:site_name" content="One Story">
<meta property="og:url" content="https://the-one-story.github.io/">
<meta property="og:title" content="One Story">
<meta property="og:description" content="The single most important news story of the last 24 hours - ranked deterministically across the world's press. No feed, no scroll.">
<meta property="og:image" content="https://the-one-story.github.io/assets/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="One Story - the single most important story of the last 24 hours">
<meta name="twitter:card" content="summary_large_image">
<style>
  /* "Ink" - a deliberate single-theme dark look (an overnight wire desk),
     with a burnt-orange accent. Committed to dark by design. */
  :root {{
    --bg: #14161a; --fg: #eae7e1; --muted: #969ba1; --accent: #b5652a;
    --rule: #2a2e34; --card: #191b1e; --land: #2b3038;
  }}
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  html {{ -webkit-text-size-adjust: 100%; }}
  body {{
    margin: 0; background: var(--bg); color: var(--fg);
    font-family: Georgia, 'Times New Roman', serif;
    line-height: 1.5; -webkit-font-smoothing: antialiased;
  }}
  .wrap {{
    max-width: 44rem; margin: 0 auto;
    padding: clamp(2rem, 8vw, 5rem) 1.5rem 4rem;
    min-height: 100vh; display: flex; flex-direction: column;
  }}
  .kicker {{
    font-family: -apple-system, system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: 0.18em; font-size: 0.7rem;
    color: var(--muted); margin: 0 0 2.5rem;
  }}
  .kicker b {{ color: var(--accent); font-weight: 700; }}
  h1 {{
    font-size: clamp(2.1rem, 7.5vw, 3.6rem); line-height: 1.08; font-weight: 700;
    margin: 0 0 1.25rem; letter-spacing: -0.015em;
  }}
  .lede {{
    font-size: clamp(1.05rem, 3.2vw, 1.3rem); color: var(--fg);
    margin: 0 0 2rem; font-style: italic;
  }}
  .hero {{
    display: inline-block; font-family: -apple-system, system-ui, sans-serif;
    font-size: 1rem; font-weight: 600; text-decoration: none;
    color: var(--accent); margin-bottom: 2rem;
    border-bottom: 2px solid var(--accent); padding-bottom: 2px;
  }}
  .hero:hover {{ opacity: 0.7; }}
  .hero .arrow {{ font-weight: 400; }}
  .hero .src {{ color: var(--muted); font-weight: 400; }}
  .coverage {{
    font-family: -apple-system, system-ui, sans-serif; font-size: 0.95rem;
    color: var(--muted); border-top: 1px solid var(--rule);
    border-bottom: 1px solid var(--rule); padding: 1.25rem 0; margin: 0 0 2rem;
  }}
  .cov-line {{ margin: 0 0 1rem; }}
  .cov-line b {{ color: var(--fg); font-weight: 700; }}
  .spectrum {{ display: flex; gap: 4px; margin: 0 0 0.4rem; }}
  .spectrum .seg {{
    flex: 1; height: 7px; border-radius: 4px; background: var(--rule);
  }}
  .spectrum .seg.on {{ background: var(--accent); }}
  .spectrum-ends {{
    display: flex; justify-content: space-between;
    font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.14em;
    color: var(--muted); margin-bottom: 1rem;
  }}
  .chips {{ display: flex; flex-wrap: wrap; gap: 0.4rem; }}
  .chip {{
    font-size: 0.75rem; padding: 0.15rem 0.6rem; border: 1px solid var(--rule);
    border-radius: 1rem; color: var(--muted); white-space: nowrap;
  }}
  .sources {{
    font-family: -apple-system, system-ui, sans-serif; font-size: 0.9rem;
    margin: 0 0 0.5rem;
  }}
  .sources summary {{
    cursor: pointer; color: var(--accent); font-weight: 600;
    padding: 0.5rem 0; user-select: none;
  }}
  .sources-body {{ padding-top: 0.75rem; }}
  .covmap {{ margin: 0 0 1.5rem; }}
  .wmap {{ display: block; width: 100%; height: auto; }}
  .wmap .wland {{ fill: var(--land); stroke: none; }}
  .wmap .mnode {{ cursor: help; }}
  .wmap .mnode:hover .mhalo {{ opacity: 0.4; }}
  .wmap .mdot {{ fill: var(--accent); }}
  .wmap .mhalo {{ fill: var(--accent); opacity: 0.18; transition: opacity 0.15s; }}
  .mnote {{ color: var(--muted); font-size: 0.78rem; margin: 0.5rem 0 0;
    font-style: italic; }}
  .bucket {{ margin-bottom: 1.25rem; }}
  .bucket h4 {{
    margin: 0 0 0.5rem; font-size: 0.72rem; text-transform: uppercase;
    letter-spacing: 0.12em; color: var(--muted); font-weight: 700;
    display: flex; align-items: center; gap: 0.5rem;
  }}
  .bucket .bcount {{
    background: var(--rule); color: var(--fg); border-radius: 1rem;
    padding: 0 0.5rem; font-size: 0.7rem; letter-spacing: 0;
  }}
  .bucket ul {{ list-style: none; margin: 0; padding: 0; }}
  .bucket li {{
    padding: 0.5rem 0; border-top: 1px solid var(--rule);
    display: flex; flex-direction: column; gap: 0.1rem;
  }}
  .bucket li a {{ color: var(--fg); font-weight: 600; text-decoration: none;
    border-bottom: 1px solid var(--accent); align-self: flex-start; }}
  .bucket .src-head {{ color: var(--muted); font-size: 0.82rem; }}
  .lock {{ font-size: 0.7rem; opacity: 0.7; }}
  .why {{
    font-family: -apple-system, system-ui, sans-serif; font-size: 0.9rem;
    margin-top: 0.5rem;
  }}
  .why summary {{
    cursor: pointer; color: var(--accent); font-weight: 600;
    padding: 0.5rem 0; user-select: none;
  }}
  .why-body {{ color: var(--muted); padding-top: 0.5rem; }}
  .why-body p {{ margin: 0 0 1rem; }}
  .why-body code {{ font-size: 0.85em; color: var(--fg); }}
  .why-body em {{ color: var(--fg); font-style: italic; }}
  ul.comp {{ list-style: none; margin: 0 0 1rem; padding: 0; }}
  ul.comp li {{ padding: 0.6rem 0; border-top: 1px solid var(--rule); }}
  .chead {{ display: flex; justify-content: space-between; align-items: baseline;
    gap: 1rem; }}
  .cname {{ color: var(--fg); font-weight: 600; text-transform: capitalize; }}
  .cscore {{ color: var(--accent); font-weight: 700;
    font-variant-numeric: tabular-nums; }}
  .cdesc {{ margin: 0.2rem 0 0; color: var(--muted); font-size: 0.85rem; }}
  .note {{ font-size: 0.85rem; font-style: italic; }}
  h3 {{ color: var(--fg); font-size: 0.95rem; margin: 1.5rem 0 0.5rem; }}
  ol.runners {{ padding-left: 1.2rem; margin: 0; }}
  ol.runners li {{ margin-bottom: 0.9rem; }}
  ol.runners a {{ color: var(--fg); text-decoration: none;
    border-bottom: 1px solid var(--accent); }}
  .ru-meta {{ display: block; color: var(--muted); font-size: 0.78rem;
    margin-top: 0.15rem; }}
  footer {{
    margin-top: auto; padding-top: 3rem;
    font-family: -apple-system, system-ui, sans-serif; font-size: 0.8rem;
    color: var(--muted);
  }}
  .stale {{
    font-family: -apple-system, system-ui, sans-serif; font-size: 0.85rem;
    background: var(--accent); color: var(--bg); padding: 0.6rem 1rem;
    border-radius: 0.4rem; margin-bottom: 2rem;
  }}
  a.hero:focus-visible, .why summary:focus-visible {{
    outline: 2px solid var(--accent); outline-offset: 3px; }}
</style>
</head>
<body>
  <div class="wrap">
    {stale_banner}
    <p class="kicker"><b>One Story</b> &nbsp;&middot;&nbsp; the single most
       important story of the last {ranked['window_hours']} hours</p>
    <h1>{headline}</h1>
    {snippet_html}
    <a class="hero" href="{hero_url}" target="_blank" rel="noopener">
      Read the fullest account <span class="arrow">&rarr;</span>
      <span class="src">{hero_src}</span></a>
    {coverage_block}
    {sources_block}
    {_why_section(winner, runners)}
    <footer>
      Updated {stamp} {tzabbr}.<br>Next update: {next_update}.
    </footer>
  </div>
</body>
</html>
"""


def main() -> int:
    settings = load_settings()
    ranked = read_json(settings["ranked_json_path"])
    stale = "--stale" in sys.argv
    if not ranked:
        print("No ranked data - run rank.py first.")
        return 1
    out_path = rel(settings["output_html"])
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(render_html(ranked, stale=stale))
    print("=" * 60)
    print("STAGE 5 - RENDER")
    print("=" * 60)
    print(f"Winner : {ranked['winner']['members'][0]['title'][:60]}")
    print(f"Hero   : {ranked['winner']['hero']['source']}")
    print(f"Runners: {len(ranked.get('runners_up', []))}")
    print(f"Stale  : {stale}")
    print(f"Wrote  -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
