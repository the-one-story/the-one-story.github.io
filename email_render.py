"""Build the daily email from the ranked winner.

Produces an inbox-safe HTML email (table layout, inline styles, web-safe fonts,
light background - dark email backgrounds render badly in many clients). Same
copyright rules as the site: headline + feed snippet + link + computed stats
only, no article body, nothing generated.

Provider-agnostic: writes email.html and returns (subject, html). The Buttondown
template variable {{ unsubscribe_url }} is included in the footer; other
providers ignore it or use their own token - swap in send_email.py if needed.
"""
from __future__ import annotations

import html
from datetime import datetime
from zoneinfo import ZoneInfo

from common import load_settings, read_json, rel
from render import _clean_source, _display_snippet

SITE_URL = "https://the-one-story.github.io/"
_O = "#b5652a"; _INK = "#201d1a"; _MUT = "#6f6a63"; _BG = "#f4efe6"
_CARD = "#ffffff"; _RULE = "#e4ded3"


def _fmt_date(iso: str, tz: str) -> str:
    dt = datetime.fromisoformat(iso).astimezone(ZoneInfo(tz))
    return f"{dt.strftime('%A')} {dt.day} {dt.strftime('%B %Y')}"


def build_email(ranked: dict) -> tuple[str, str]:
    w = ranked["winner"]
    headline = html.escape(w["hero"]["title"])
    snippet = html.escape(_display_snippet(w))
    hero_url = html.escape(w["hero"]["url"], quote=True)
    hero_src = html.escape(_clean_source(w["hero"]["source"]))
    n_out, n_cty = w["outlet_count"], len(w["countries"])
    date_str = _fmt_date(ranked["run_time"], ranked["timezone"])
    subject = f"One Story — {w['hero']['title']}"

    coverage = (f"Running across {n_out} outlet{'s' if n_out != 1 else ''} in "
                f"{n_cty} countr{'ies' if n_cty != 1 else 'y'}.")
    snippet_row = (f'<p style="margin:0 0 22px;font-family:Georgia,serif;'
                   f'font-size:18px;line-height:1.5;font-style:italic;color:{_INK}">'
                   f'{snippet}</p>' if snippet else "")

    body = f"""\
<div style="background:{_BG};margin:0;padding:24px 0;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{snippet or headline}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{_BG};">
<tr><td align="center" style="padding:0 16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="max-width:560px;background:{_CARD};border:1px solid {_RULE};border-radius:10px;">
<tr><td style="padding:34px 36px 30px;">

  <p style="margin:0 0 4px;font-family:-apple-system,Segoe UI,Arial,sans-serif;
     font-size:13px;letter-spacing:2.5px;text-transform:uppercase;color:{_O};
     font-weight:700;">One Story</p>
  <p style="margin:0 0 22px;font-family:-apple-system,Segoe UI,Arial,sans-serif;
     font-size:13px;color:{_MUT};">{date_str}</p>

  <h1 style="margin:0 0 16px;font-family:Georgia,'Times New Roman',serif;
      font-size:30px;line-height:1.15;font-weight:700;color:{_INK};letter-spacing:-.01em;">
    {headline}</h1>

  {snippet_row}

  <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 26px;"><tr>
    <td style="border-radius:6px;background:{_O};">
      <a href="{hero_url}" style="display:inline-block;padding:12px 22px;
         font-family:-apple-system,Segoe UI,Arial,sans-serif;font-size:15px;font-weight:600;
         color:#ffffff;text-decoration:none;border-radius:6px;">
        Read the fullest account &rarr; {hero_src}</a>
    </td>
  </tr></table>

  <p style="margin:0 0 6px;font-family:-apple-system,Segoe UI,Arial,sans-serif;
     font-size:14px;color:{_MUT};border-top:1px solid {_RULE};padding-top:20px;">
     {coverage}</p>
  <p style="margin:0 0 4px;font-family:-apple-system,Segoe UI,Arial,sans-serif;font-size:14px;">
     <a href="{SITE_URL}" style="color:{_O};text-decoration:none;font-weight:600;">
       See the map, every source, and why this story won &rarr;</a></p>

</td></tr></table>

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;">
<tr><td style="padding:20px 36px;font-family:-apple-system,Segoe UI,Arial,sans-serif;
    font-size:12px;line-height:1.6;color:{_MUT};text-align:center;">
  You're receiving this because you subscribed to One Story - the single most important
  story of the last 24 hours, chosen by how widely it's covered, not by an algorithm.<br>
  <a href="{{{{ unsubscribe_url }}}}" style="color:{_MUT};text-decoration:underline;">Unsubscribe</a>
  &nbsp;&middot;&nbsp;
  <a href="{SITE_URL}" style="color:{_MUT};text-decoration:underline;">the-one-story.github.io</a>
</td></tr></table>

</td></tr></table>
</div>"""
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
