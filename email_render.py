"""Build the daily email from the ranked winner.

Produces an inbox-safe HTML email (table layout, inline styles, web-safe fonts,
committed dark theme - matches the site and dodges client dark-mode inversion).
Same copyright rules as the site: headline + feed snippet + link + computed
stats only, no article body, nothing generated.

Provider-agnostic: writes email.html and returns (subject, html). No custom
unsubscribe/footer - the sending provider (Brevo) appends the required
unsubscribe link + postal address to every campaign, so we don't duplicate it.
"""
from __future__ import annotations

import html
from datetime import datetime
from zoneinfo import ZoneInfo

from common import load_settings, read_json, rel
from render import _clean_source, _display_snippet, _hyphenate

SITE_URL = "https://one-story.charlietrenorden.com/"
# Intentionally dark (matches the site's Ink theme) so dark-mode clients don't
# invert and mangle it, and light clients get a deliberate dark newsletter.
_BG = "#14161a"; _INK = "#ece9e3"; _MUT = "#8b9096"; _O = "#b5652a"
_SNIP = "#c3bfb7"; _RULE = "#2a2e34"


def _fmt_date(iso: str, tz: str) -> str:
    dt = datetime.fromisoformat(iso).astimezone(ZoneInfo(tz))
    return f"{dt.strftime('%A')} {dt.day} {dt.strftime('%B %Y')}"


def build_email(ranked: dict) -> tuple[str, str]:
    w = ranked["winner"]
    headline = html.escape(_hyphenate(w["hero"]["title"]))
    snippet = html.escape(_hyphenate(_display_snippet(w)))
    hero_url = html.escape(w["hero"]["url"], quote=True)
    hero_src = html.escape(_clean_source(w["hero"]["source"]))
    n_out, n_cty = w["outlet_count"], len(w["countries"])
    date_str = _fmt_date(ranked["run_time"], ranked["timezone"])
    subject = f"One Story - {_hyphenate(w['hero']['title'])}"

    coverage = (f"Running across {n_out} outlet{'s' if n_out != 1 else ''} in "
                f"{n_cty} countr{'ies' if n_cty != 1 else 'y'}.")
    sans = "-apple-system,'Segoe UI',Arial,sans-serif"
    serif = "Georgia,'Times New Roman',serif"
    snippet_row = (f'<p style="margin:0 0 22px;font-family:{serif};font-size:19px;'
                   f'line-height:1.5;font-style:italic;color:{_SNIP};">{snippet}</p>'
                   if snippet else "")

    # Flat, dark, single column - no inner card, no custom footer (Brevo appends
    # the unsubscribe link + badge + postal address). bgcolor attrs for Outlook.
    inner = f"""\
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{snippet or headline}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       bgcolor="{_BG}" style="background-color:{_BG};border-collapse:collapse;">
<tr><td align="center" bgcolor="{_BG}" style="padding:26px 10px;background-color:{_BG};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       bgcolor="{_BG}" style="max-width:560px;margin:0 auto;background-color:{_BG};">
<tr><td bgcolor="{_BG}" style="padding:14px 30px 30px;font-family:{sans};background-color:{_BG};">

  <p style="margin:0 0 6px;font-size:18px;letter-spacing:3px;text-transform:uppercase;
     color:{_O};font-weight:700;">One Story</p>
  <p style="margin:0 0 22px;font-size:14px;color:{_MUT};">{date_str}</p>

  <h1 style="margin:0 0 16px;font-family:{serif};font-size:31px;line-height:1.18;
      font-weight:700;color:{_INK};letter-spacing:-.01em;">{headline}</h1>

  {snippet_row}

  <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:4px 0 28px;">
  <tr><td bgcolor="{_O}" style="background-color:{_O};border-radius:6px;">
    <a href="{hero_url}" style="display:inline-block;padding:12px 22px;font-family:{sans};
       font-size:16px;font-weight:600;color:#ffffff;text-decoration:none;">
      Read the fullest account &rarr; {hero_src}</a>
  </td></tr></table>

  <p style="margin:0 0 10px;font-size:15px;color:{_MUT};
     border-top:1px solid {_RULE};padding-top:20px;">{coverage}</p>
  <p style="margin:0;font-size:15px;">
    <a href="{SITE_URL}" style="color:{_O};text-decoration:none;font-weight:600;">
      See the map, every source, and how it's chosen &rarr;</a></p>

</td></tr></table>
</td></tr></table>"""

    # Full HTML document so Brevo carries our <head> through to the client. The
    # color-scheme meta tells dark-mode clients (notably Gmail) the email is
    # intentionally dark and must NOT be auto-lightened or inverted.
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<meta name="supported-color-schemes" content="dark">
<style>:root{{color-scheme:dark;supported-color-schemes:dark;}}</style>
</head>
<body style="margin:0;padding:0 0 32px;background-color:{_BG};">
{inner}
</body>
</html>"""
    return subject, body


def main() -> int:
    settings = load_settings()
    ranked = read_json(settings["ranked_json_path"])
    if not ranked:
        print("No ranked data - run the pipeline first.")
        return 1
    subject, body = build_email(ranked)
    path = rel("email.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    print(f"Subject: {subject}")
    print(f"Wrote email -> {path} ({len(body)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
