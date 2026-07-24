"""Send the daily email to the mailing list (Buttondown).

Runs in the daily CI job after the page is built. Safe by default:
- No-ops (dry-run) unless BUTTONDOWN_API_KEY is set AND newsletter.enabled is
  true in settings, so it never sends from a local run or an unconfigured repo.
- A per-day guard (data/last_email.json) means re-running the job the same day
  will NOT send a second email.

Usage:
    python send_email.py            # sends if configured, else dry-run
    python send_email.py --dry-run  # force dry-run (build + print, never send)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime

from common import load_settings, read_json, rel, write_json
from email_render import build_email

_STATE = "data/last_email.json"


def main() -> int:
    force_dry = "--dry-run" in sys.argv
    settings = load_settings()
    ranked = read_json(settings["ranked_json_path"])
    if not ranked:
        print("No ranked data - run the pipeline first.")
        return 1

    subject, body = build_email(ranked)
    run_date = datetime.fromisoformat(ranked["run_time"]).date().isoformat()
    nl = settings.get("newsletter") or {}
    key = os.environ.get("BUTTONDOWN_API_KEY", "").strip()

    # Already sent today?
    last = (read_json(_STATE, default={}) or {}).get("date")
    if last == run_date and not force_dry:
        print(f"Already emailed for {run_date}; skipping.")
        return 0

    if force_dry or not key or not nl.get("enabled"):
        why = ("--dry-run" if force_dry else
               "no BUTTONDOWN_API_KEY" if not key else "newsletter disabled")
        print(f"DRY-RUN ({why}) - not sending.")
        print(f"Subject: {subject}")
        print(f"Body: {len(body)} bytes")
        return 0

    api = nl.get("api_base", "https://api.buttondown.email/v1").rstrip("/")
    payload = json.dumps({
        "subject": subject,
        "body": body,
        "status": nl.get("send_status", "about_to_send"),
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{api}/emails", data=payload, method="POST",
        headers={"Authorization": f"Token {key}",
                 "Content-Type": "application/json",
                 # Buttondown's one-time-per-key confirmation that an API send
                 # is intentional (required for status 'about_to_send').
                 "X-Buttondown-Live-Dangerously": "true"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"Sent '{subject[:60]}' -> HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"Send FAILED: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:400]}",
              file=sys.stderr)
        return 1

    write_json(_STATE, {"date": run_date, "subject": subject})
    print(f"Recorded send for {run_date}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
