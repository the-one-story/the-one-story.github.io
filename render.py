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
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from common import load_settings, read_json, rel


def _fmt_local(iso: str, tzname: str) -> tuple[str, str]:
    dt = datetime.fromisoformat(iso).astimezone(ZoneInfo(tzname))
    return dt.strftime("%d/%m/%Y %H:%M"), dt.tzname() or ""


def _display_snippet(winner: dict) -> str:
    """Prefer the hero's snippet; fall back to the first member that has one."""
    if winner.get("hero", {}).get("snippet"):
        return winner["hero"]["snippet"]
    for m in winner.get("members", []):
        if m.get("snippet"):
            return m["snippet"]
    return ""


def _coverage_line(winner: dict) -> str:
    n_out = winner["outlet_count"]
    n_cty = len(winner["countries"])
    n_lean = len(winner["leans"])
    out_w = "outlet" if n_out == 1 else "outlets"
    cty_w = "country" if n_cty == 1 else "countries"
    lean_w = "side" if n_lean == 1 else "sides"
    return (f"Running across {n_out} {out_w} in {n_cty} {cty_w}, "
            f"spanning {n_lean} {lean_w} of the political spectrum.")


def _why_section(winner: dict, runners: list[dict]) -> str:
    k = winner["components"]
    comp_rows = "".join(
        f"<tr><td>{name}</td><td>{k[name]:.2f}</td></tr>"
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
           with no editorial judgement and no AI. Diversity (spread across
           countries <em>and</em> the political spectrum) is weighted most
           heavily, to stop a story that is merely loud in one national press
           from winning on volume alone.</p>
        <table class="comp">
          <thead><tr><th>Component</th><th>Score (0-1)</th></tr></thead>
          <tbody>{comp_rows}</tbody>
        </table>
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

    # Headline, snippet and link all come from the one hero article (the best
    # single write-up) so they read as a coherent unit.
    headline = html.escape(winner["hero"]["title"])
    snippet = html.escape(_display_snippet(winner))
    hero_url = html.escape(winner["hero"]["url"], quote=True)
    hero_src = html.escape(winner["hero"]["source"])
    coverage = _coverage_line(winner)

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
<title>One Story</title>
<style>
  :root {{
    --bg: #fbfbf9; --fg: #1a1a1a; --muted: #6b6b6b; --accent: #b4472e;
    --rule: #e5e3dd; --card: #ffffff;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #111110; --fg: #ececea; --muted: #9a9a95; --accent: #e0785c;
      --rule: #2a2a28; --card: #191918;
    }}
  }}
  * {{ box-sizing: border-box; }}
  html {{ -webkit-text-size-adjust: 100%; }}
  body {{
    margin: 0; background: var(--bg); color: var(--fg);
    font-family: Georgia, 'Times New Roman', serif;
    line-height: 1.5; -webkit-font-smoothing: antialiased;
  }}
  .wrap {{
    max-width: 40rem; margin: 0 auto;
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
    font-size: clamp(2rem, 7vw, 3.1rem); line-height: 1.1; font-weight: 700;
    margin: 0 0 1.25rem; letter-spacing: -0.01em;
  }}
  .lede {{
    font-size: clamp(1.05rem, 3.2vw, 1.3rem); color: var(--fg);
    margin: 0 0 2rem; font-style: italic;
  }}
  .hero {{
    display: inline-block; font-family: -apple-system, system-ui, sans-serif;
    font-size: 0.95rem; font-weight: 600; text-decoration: none;
    color: var(--bg); background: var(--accent);
    padding: 0.7rem 1.2rem; border-radius: 0.4rem; margin-bottom: 2rem;
  }}
  .hero:hover {{ opacity: 0.9; }}
  .hero .src {{ opacity: 0.8; font-weight: 400; }}
  .coverage {{
    font-family: -apple-system, system-ui, sans-serif; font-size: 0.95rem;
    color: var(--muted); border-top: 1px solid var(--rule);
    border-bottom: 1px solid var(--rule); padding: 1rem 0; margin: 0 0 2rem;
  }}
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
  table.comp {{ border-collapse: collapse; margin: 0 0 1rem; width: 100%;
    max-width: 18rem; }}
  table.comp th, table.comp td {{
    text-align: left; padding: 0.3rem 0.6rem 0.3rem 0;
    border-bottom: 1px solid var(--rule); }}
  table.comp th {{ color: var(--fg); font-weight: 600; }}
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
      Read the fullest account <span class="src">&mdash; {hero_src}</span></a>
    <p class="coverage">{coverage}</p>
    {_why_section(winner, runners)}
    <footer>
      Updated {stamp} {tzabbr}. Next update in ~24 hours.<br>
      One story a day. No feed, no scroll. Ranked deterministically from public
      news feeds - no AI, no editorial hand.
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
