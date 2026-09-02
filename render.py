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
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from common import load_settings, read_json, rel

# Strip a trailing " - Section" or " (tags)" from a feed name for clean display
# e.g. "The Nation (US, left)" -> "The Nation", "The Guardian - World" -> "The Guardian".
# Strip a trailing " - Region/Section" suffix or a " (Region)" parenthetical,
# but NOT an internal hyphen (so "Agence France-Presse" survives intact).
_SRC_CLEAN = re.compile(r"\s+-\s.*$|\s*\(.*$")

# Cloudflare Web Analytics. Feeds the private stats dashboard, which runs ONE
# account-wide GraphQL query and splits the results by `requestHost` - so this is
# deliberately the same token used across every site in the estate, not a per-site
# one. Cookieless, no personal data, ~10KB deferred so it costs nothing visible.
#
# This belongs in the template and NOT in the built index.html: the daily workflow
# regenerates that file, so a tag pasted into the output disappears on the next run.
# A plain constant rather than inline HTML because the page below is an f-string,
# where the token's braces would otherwise need escaping.
_BEACON = (
    """<script>/* Analytics, gated. Two kinds of visitor are not an audience and never load it: anyone who has opted out with ?nostats=1, and automation, since navigator.webdriver is the one signal true for Playwright, Puppeteer and Selenium alike. Inline and dependency-free on purpose - served from the Worker, a bad deploy there would stop analytics on every site. See site-stats/beacon. */(function(){try{var X="ct.nostats",C="ct_nostats",D=";path=/;domain=.charlietrenorden.com",q=location.search,out=false;if(q.indexOf("nostats=1")>-1){try{localStorage.setItem(X,"1")}catch(e){}document.cookie=C+"=1"+D+";max-age=63072000;samesite=lax";}if(q.indexOf("nostats=0")>-1){try{localStorage.removeItem(X)}catch(e){}document.cookie=C+"="+D+";max-age=0";}try{out=!!localStorage.getItem(X)}catch(e){}if(!out)out=document.cookie.indexOf(C+"=1")>-1;if(out||navigator.webdriver)return;var d=document,s;s=d.createElement("script");s.defer=true;s.src="https://static.cloudflareinsights.com/beacon.min.js";s.setAttribute("data-cf-beacon",'{"token": "32b821209b5441a08df42ccf61c9e6c2"}');d.head.appendChild(s);s=d.createElement("script");s.defer=true;s.src="https://beacon.charlietrenorden.com/b.js";d.head.appendChild(s);}catch(e){}})();</script>"""
)


def _clean_source(name: str) -> str:
    return _SRC_CLEAN.sub("", name).strip() or name


# Group the source list by the actual 5-point lean, so the headers match the
# coverage line's span wording (a centre-left outlet reads as "Centre-left",
# not lumped under "Left").
_LEAN_BUCKET = {"left": "Left", "centre-left": "Centre-left", "centre": "Centre",
                "centre-right": "Centre-right", "right": "Right"}
_BUCKET_ORDER = ["Left", "Centre-left", "Centre", "Centre-right", "Right"]


def _fmt_local(iso: str, tzname: str) -> tuple[str, str]:
    dt = datetime.fromisoformat(iso).astimezone(ZoneInfo(tzname))
    return dt.strftime("%d/%m/%Y %H:%M"), dt.tzname() or ""


def _next_update(iso: str, tzname: str, update_hour_local: int) -> str:
    """Human-readable next scheduled update, e.g. 'Fri 24 Jul, 05:00 AEST'.

    The job is scheduled in LOCAL terms (05:00 Sydney year-round - two UTC crons
    plus a DST gate, see daily.yml), so resolve the next LOCAL occurrence. Built
    from the calendar date rather than by adding a timedelta, so the wall-clock
    hour stays 05:00 even across a daylight-saving transition.
    """
    local = datetime.fromisoformat(iso).astimezone(ZoneInfo(tzname))
    tz = ZoneInfo(tzname)
    at = time(hour=update_hour_local)
    nxt = datetime.combine(local.date(), at, tzinfo=tz)
    if nxt <= local:
        nxt = datetime.combine(local.date() + timedelta(days=1), at, tzinfo=tz)
    return f"{nxt.strftime('%a %d %b, %H:%M')} {nxt.tzname()}"


def _hyphenate(text: str) -> str:
    """House style: no em/en dashes anywhere on the page - collapse them to a
    plain hyphen (also normalises dashes that arrive inside feed text)."""
    return (text or "").replace("—", "-").replace("–", "-")


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
                 "SG": "Singapore", "AE": "UAE", "AR": "Argentina", "NG": "Nigeria",
                 "MX": "Mexico", "EG": "Egypt", "KR": "South Korea",
                 "ID": "Indonesia", "IT": "Italy", "ES": "Spain", "KE": "Kenya"}


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

    buckets: dict[str, list[dict]] = {b: [] for b in _BUCKET_ORDER}
    for m in by_source.values():
        buckets[_LEAN_BUCKET.get(m["lean"], "Centre")].append(m)

    blocks = []
    for label in _BUCKET_ORDER:
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
      <summary>Covered by {n} outlet{"s" if n != 1 else ""} - where &amp; who</summary>
      <div class="sources-body">{map_html}{"".join(blocks)}</div>
    </details>"""


_COMPONENT_DESC = {
    "coverage": "How many distinct outlets are running the story - log-scaled, "
                "so 20 isn't worth twice 10.",
    "diversity": "How widely that coverage is spread across countries and the "
                 "political spectrum - weighted heaviest, so a story merely loud "
                 "in one bloc doesn't dominate.",
    "recency": "Favours stories with fresh, recent coverage over ones already "
               "fading (measured from the average time the coverage was published).",
    "novelty": "Penalises a story that already led on a recent day, easing back "
               "over ~4 days, so a repeat must bring bigger coverage to lead again.",
    "stakes": "Whether the reporting says people were harmed, and how many, read "
              "from the headlines themselves and log-scaled. Never zero: it breaks "
              "ties rather than deciding.",
}

#: What the reader SEES, where that differs from the internal key. Charlie,
#: 02/09/2026: "stakes needs a better term".
#:
#: "stakes" says something is at risk, which is a claim about the future. The
#: number is not that. "harm" was tried and Charlie said it still sounded off,
#: and he was right: harm is a quality, and this is a COUNT - how many people were
#: hurt, log-scaled. "toll" is the newspaper word for that exact quantity, one
#: plain syllable like the other four, and it cannot be read as a bet or a mood.
#:
#: DISPLAY ONLY. The key stays "stakes" in config/weights, in stakes.py and in
#: every stored record, so renaming the label costs no migration and no history.
_COMPONENT_LABEL = {"stakes": "toll"}


def _signup_form(form_url: str) -> str:
    """Signup form (rendered only when an endpoint is configured).

    Posts to our own Cloudflare Worker (workers/subscribe), NOT to the mail
    provider. Brevo hosted a form we could post to directly; Resend does not,
    and its contacts API needs the API key - which can never sit in a public
    page. The Worker holds the key and adds the contact server-side.
    """
    if not form_url:
        return ""
    action = html.escape(form_url, quote=True)
    # Submit into a hidden iframe so the subscriber stays on the page, then swap
    # the note to a success message (single opt-in - no confirmation step).
    return f"""
    <section class="signup">
      <p class="signup-lead">Get it in your inbox each morning.</p>
      <form action="{action}" method="post" target="os-bd-sink"
            class="signup-form" onsubmit="return osSignup(this)">
        <input type="email" name="email" placeholder="you@example.com"
               aria-label="Email address" required>
        <!-- Honeypot: bots fill this, humans never see it. The Worker answers
             200 and silently drops the submission. -->
        <input type="text" name="email_address_check" value="" tabindex="-1"
               autocomplete="off" aria-hidden="true"
               style="position:absolute;left:-5000px;">
        <button type="submit">Subscribe</button>
      </form>
      <p class="signup-note" id="os-signup-note">One email a day. No tracking.
        Unsubscribe anytime.</p>
      <iframe name="os-bd-sink" title="subscription" aria-hidden="true"
              tabindex="-1" style="position:absolute;width:0;height:0;border:0;">
      </iframe>
      <script>
        function osSignup(f) {{
          setTimeout(function () {{
            f.style.display = 'none';
            var n = document.getElementById('os-signup-note');
            if (n) {{
              n.textContent = "Thanks - you're on the list; your first edition arrives tomorrow morning. Heads up: it may land in spam the first time - mark it 'not spam' (or add us to your contacts) and the rest will reach your inbox.";
              n.style.color = 'var(--accent)';
            }}
          }}, 150);
          return true;  // let the POST reach the Worker via the hidden iframe
        }}
      </script>
    </section>"""


def _why_section(winner: dict, runners: list[dict]) -> str:
    k = winner["components"]
    weights = load_settings()["weights"]
    comp_rows = "".join(
        f'<li><div class="chead">'
        f'<span class="cname">{_COMPONENT_LABEL.get(name, name)}'
        f' <span class="cwt">{weights.get(name, 1.0):.1f}&times; weight</span></span>'
        f'<span class="cscore">{k[name]:.2f}</span></div>'
        f'<div class="cbar"><span style="width:{max(0, min(100, round(k[name]*100)))}%">'
        f'</span></div>'
        f'<p class="cdesc">{_COMPONENT_DESC[name]}</p></li>'
        # Driven by what the SCORE actually produced, not a hand-kept list.
        # The list went stale the day stakes was added: the formula line above
        # named five dimensions and this rendered four.
        for name in k if name in _COMPONENT_DESC
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
        <p>The lead story is chosen by a fully deterministic score -
           <code>coverage &times; diversity &times; recency &times; novelty
           &times; toll</code> - with nothing chosen by hand on the day.
           Diversity (spread across countries
           <em>and</em> the political spectrum) carries the most weight, so a
           story that everyone agrees is big rises above one that is simply
           being shouted loudest in a single country's press.</p>
        <p class="comp-intro">Each dimension below scores from <strong>0 to 1</strong>
           (higher is stronger), but they don't count equally: each is raised to the
           weight shown, then the weighted dimensions combine to rank the day's
           stories - so this story comes out top across the combination today.</p>
        <ul class="comp">{comp_rows}</ul>
        {nov_note}
        <h3>Next-highest today</h3>
        <ol class="runners">{runners_html}</ol>
      </div>
    </details>"""


def render_html(ranked: dict, stale: bool = False) -> str:
    winner = ranked["winner"]
    runners = ranked.get("runners_up", [])
    tzname = ranked["timezone"]
    stamp, tzabbr = _fmt_local(ranked["run_time"], tzname)
    next_update = _next_update(ranked["run_time"], tzname,
                               ranked.get("update_hour_local", 5))

    # Headline, snippet and link all come from the one hero article (the best
    # single write-up) so they read as a coherent unit.
    headline = html.escape(_hyphenate(winner["hero"]["title"]))
    snippet = html.escape(_hyphenate(_display_snippet(winner)))
    hero_url = html.escape(winner["hero"]["url"], quote=True)
    hero_src = html.escape(_clean_source(winner["hero"]["source"]))
    coverage_block = _coverage_block(winner)
    sources_block = _sources_section(winner)
    signup_block = _signup_form(ranked.get("signup_form_url", ""))

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
<!-- Favicons. The SVG is the master mark; the PNG/ICO fallbacks exist because
     Safari and older Chrome ignore rel=icon type=image/svg+xml and would
     otherwise show a blank tab. apple-touch-icon is the iOS home-screen icon
     (flattened onto the bone bg - iOS renders transparency as black). -->
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<link rel="icon" href="assets/favicon.ico" sizes="32x32">
<link rel="icon" type="image/png" sizes="16x16" href="assets/favicon-16x16.png">
<link rel="icon" type="image/png" sizes="32x32" href="assets/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="96x96" href="assets/favicon-96x96.png">
<link rel="apple-touch-icon" sizes="180x180" href="assets/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="192x192" href="assets/android-chrome-192x192.png">
<link rel="icon" type="image/png" sizes="512x512" href="assets/android-chrome-512x512.png">
<title>One Story</title>
<!-- Link-preview (Open Graph) - how the URL unfurls in WhatsApp, iMessage, Slack, etc. -->
<meta property="og:type" content="website">
<meta property="og:site_name" content="One Story">
<meta property="og:url" content="https://one-story.charlietrenorden.com/">
<meta property="og:title" content="One Story">
<meta name="description" content="One story a day: the most important thing that happened in the last 24 hours.">
  <meta property="og:description" content="One story a day: the most important thing that happened in the last 24 hours.">
<meta property="og:image" content="https://one-story.charlietrenorden.com/assets/og.png">
<meta property="og:image:secure_url" content="https://one-story.charlietrenorden.com/assets/og.png">
<meta property="og:image:type" content="image/png">
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
  .topbar {{
    display: flex; align-items: baseline; justify-content: space-between;
    /* NOWRAP, deliberately. With wrap, the back-link drops to a line of its own
       as soon as the kicker is a few pixels too wide - which is what the card
       thumbnail kept showing, because it is cropped to the content column and so
       renders much narrower than the 1280 viewport it is shot in. Tuning a
       breakpoint would only move the width at which it breaks. With nowrap the
       kicker shrinks and wraps INSIDE itself instead, and the back-link stays
       beside its first line at every width. */
    flex-wrap: nowrap; gap: 0.5rem 1.25rem; margin: 0 0 2.5rem;
    /* The kicker below is sized in cqi, so this row has to be a container. */
    container-type: inline-size;
  }}
  .kicker {{
    font-family: -apple-system, system-ui, sans-serif;
    text-transform: uppercase; letter-spacing: 0.11em;
    /* Shrinks at narrow widths so the whole kicker AND the back-link fit on one
       line. The card thumbnail is cropped to the content column, so it renders far
       narrower than the 1280 viewport it is shot in - at full size the kicker
       pushed HOURS onto a second line there while looking fine on a desktop. */
    /* cqi, NOT vw. This wrapped for three attempts because vw measures the
       VIEWPORT and the thing that is actually narrow is this max-width column. The
       thumbnail shooter uses a 1280px viewport, so 1.35vw resolved to 17px, sailed
       past the 0.82rem ceiling, and the clamp silently returned its MAXIMUM every
       single time - the tuning was doing nothing at all. cqi measures the container,
       which is the width that was always the constraint.
       1.90 is the largest that still fits on one line with DejaVu Sans standing in
       for the runner's wider sans; 2.05 wraps. Verified 700-1280px viewport, where
       the computed size now correctly stays put because the column does. */
    font-size: clamp(0.58rem, 1.55cqi, 0.82rem);
    /* 1.55, not 1.90. The ceiling is 0.82rem = 13.12px, so for the clamp to BIND
       at all the middle term must come out below that - and the content column in
       the shot card is about 700px, where 1.90cqi is 13.3px and clamp goes
       straight back to its maximum. That is the same mistake as the vw version,
       one step smaller: a clamp whose middle term never dips under the ceiling is
       an expensive way to write a constant. 1.55cqi gives ~10.9px there. */
    color: var(--muted); margin: 0;
    /* Let the LONG item shrink and wrap inside itself, so the short one stays on
       the first line beside it. Without min-width:0 a flex child refuses to go
       below its content width, so the whole kicker stayed intact and pushed the
       back-link onto a line of its own - which is what the card screenshot kept
       showing. */
    flex: 1 1 auto; min-width: 0;
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
  .wmap .mnode {{ cursor: default; }}
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
  .comp-intro {{ color: var(--muted); }}
  .comp-intro strong {{ color: var(--fg); }}
  ul.comp {{ list-style: none; margin: 0 0 1rem; padding: 0; }}
  ul.comp li {{ padding: 0.6rem 0; border-top: 1px solid var(--rule); }}
  .chead {{ display: flex; justify-content: space-between; align-items: baseline;
    gap: 1rem; }}
  .cname {{ color: var(--fg); font-weight: 600; text-transform: capitalize; }}
  .cwt {{ color: var(--muted); font-weight: 400; font-size: 0.72rem;
    text-transform: none; letter-spacing: 0; }}
  .cscore {{ color: var(--accent); font-weight: 700;
    font-variant-numeric: tabular-nums; }}
  .cbar {{ height: 5px; background: var(--rule); border-radius: 3px;
    margin: 0.35rem 0 0.1rem; overflow: hidden; }}
  .cbar span {{ display: block; height: 100%; background: var(--accent);
    border-radius: 3px; }}
  .cdesc {{ margin: 0.2rem 0 0; color: var(--muted); font-size: 0.85rem; }}
  .note {{ font-size: 0.85rem; font-style: italic; }}
  h3 {{ color: var(--fg); font-size: 0.95rem; margin: 1.5rem 0 0.5rem; }}
  ol.runners {{ padding-left: 1.2rem; margin: 0; }}
  ol.runners li {{ margin-bottom: 0.9rem; }}
  ol.runners a {{ color: var(--fg); text-decoration: none;
    border-bottom: 1px solid var(--accent); }}
  .ru-meta {{ display: block; color: var(--muted); font-size: 0.78rem;
    margin-top: 0.15rem; }}
  .signup {{
    margin: 2.5rem 0 0; padding: 1.5rem 0 0; border-top: 1px solid var(--rule);
    font-family: -apple-system, system-ui, sans-serif;
  }}
  .signup-lead {{ margin: 0 0 0.9rem; color: var(--fg); font-size: 1rem;
    font-weight: 600; }}
  .signup-form {{ display: flex; flex-wrap: wrap; gap: 0.5rem; }}
  .signup-form input {{
    flex: 1 1 12rem; min-width: 0; padding: 0.6rem 0.8rem; font-size: 0.95rem;
    color: var(--fg); background: var(--card); border: 1px solid var(--rule);
    border-radius: 0.4rem; font-family: inherit;
  }}
  .signup-form input:focus-visible {{ outline: 2px solid var(--accent);
    outline-offset: 1px; }}
  .signup-form button {{
    padding: 0.6rem 1.2rem; font-size: 0.95rem; font-weight: 600; cursor: pointer;
    color: var(--bg); background: var(--accent); border: none;
    border-radius: 0.4rem; font-family: inherit;
  }}
  .signup-form button:hover {{ opacity: 0.9; }}
  .signup-note {{ margin: 0.7rem 0 0; color: var(--muted); font-size: 0.78rem; }}
  footer {{
    margin-top: auto; padding-top: 1.8rem;
    font-family: -apple-system, system-ui, sans-serif; font-size: 0.8rem;
    color: var(--muted);
  }}
  /* House standard: the back-link sits top right on every property. */
  .byline {{ text-align: right; margin: 0 0 0 auto;
    font-family: -apple-system, system-ui, sans-serif; font-size: 0.85rem;
    /* Never the item that wraps: it is three words and it belongs on the kicker's
       first line. */
    flex: 0 0 auto; white-space: nowrap;
  }}
  .byline a {{ color: var(--accent); font-weight: 600;
    text-decoration: underline; text-underline-offset: 3px;
    text-decoration-thickness: 1px; }}
  .byline a:hover {{ opacity: 0.7; }}
  .byline .ext {{ font-weight: 400; }}
  .stale {{
    font-family: -apple-system, system-ui, sans-serif; font-size: 0.85rem;
    background: var(--accent); color: var(--bg); padding: 0.6rem 1rem;
    border-radius: 0.4rem; margin-bottom: 2rem;
  }}
  a.hero:focus-visible, .why summary:focus-visible {{
    outline: 2px solid var(--accent); outline-offset: 3px; }}
</style>
{_BEACON}
</head>
<body>
  <div class="wrap">
    {stale_banner}
    <header class="topbar">
      <p class="kicker"><b>One Story</b> &nbsp;&middot;&nbsp; the most important
         story of the last {ranked['window_hours']} hours</p>
      <p class="byline"><a href="https://charlietrenorden.com/">&larr;&nbsp;Other projects</a></p>
    </header>
    <h1>{headline}</h1>
    {snippet_html}
    <a class="hero" href="{hero_url}" target="_blank" rel="noopener">
      Read the fullest account <span class="arrow">&rarr;</span>
      <span class="src">{hero_src}</span></a>
    {coverage_block}
    {sources_block}
    {_why_section(winner, runners)}
    {signup_block}
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
