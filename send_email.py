"""Send the daily email to the mailing list (Brevo).

Runs in the daily CI job after the page is built. Safe by default:
- No-ops (dry-run) unless BREVO_API_KEY is set AND the newsletter is fully
  configured (enabled, a verified sender_email, and a list_id) in settings, so it
  never sends from a local run or a half-configured repo.
- A per-day guard (data/last_email.json) means re-running the job the same day
  will NOT send a second email.

Brevo has no single "send this HTML to a list" call, so the flow is two steps:
create the campaign as a draft (POST /v3/emailCampaigns) then send it
(POST /v3/emailCampaigns/{id}/sendNow). --test uses sendTest to a single address
(BREVO_TEST_EMAIL) so it never touches the live list, and leaves the daily guard
untouched.

Usage:
    python send_email.py            # sends if configured, else dry-run
    python send_email.py --dry-run  # force dry-run (build + print, never send)
    python send_email.py --test     # create + send a test to BREVO_TEST_EMAIL only
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

# Brevo can put an account under manual review, after which EVERY campaign
# create returns 402 account_under_validation (it did from 10/08/2026, and three
# editions died silently). Retrying daily into a human review queue achieves
# nothing and looks worse, so a hold is recorded and further attempts are skipped
# - but re-probed occasionally so sending resumes on its own once it is lifted.
_HOLD_CODES = {"account_under_validation"}
_HOLD_REPROBE_DAYS = 3


def _hold_blocks(state: dict, run_date: str) -> str | None:
    """Reason to skip today, or None if we should attempt (or re-probe)."""
    hold = (state or {}).get("hold")
    if not hold:
        return None
    last_try = hold.get("last_attempt") or hold.get("since")
    try:
        from datetime import date
        gap = date.fromisoformat(run_date).toordinal() - date.fromisoformat(last_try).toordinal()
    except (TypeError, ValueError):
        return None                      # unreadable hold - do not let it wedge sending
    if gap >= _HOLD_REPROBE_DAYS:
        return None                      # due a re-probe
    return (f"account on hold ({hold.get('code')}) since {hold.get('since')}; "
            f"next re-probe after {_HOLD_REPROBE_DAYS} days without one "
            f"(last attempt {last_try})")


def _post(url: str, key: str, payload: dict | None) -> tuple[int, dict]:
    """POST JSON to Brevo. payload=None sends an empty-body POST (sendNow)."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"api-key": key,
                 "content-type": "application/json",
                 "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", "replace")
        return resp.status, (json.loads(raw) if raw.strip() else {})


def main() -> int:
    force_dry = "--dry-run" in sys.argv
    force_test = "--test" in sys.argv   # send a test to BREVO_TEST_EMAIL, no guard
    settings = load_settings()
    ranked = read_json(settings["ranked_json_path"])
    if not ranked:
        print("No ranked data - run the pipeline first.")
        return 1

    subject, body = build_email(ranked)
    if force_test:
        # Make each test subject unique so Gmail doesn't thread/de-dupe repeated
        # tests of the same day's edition (which hid earlier template changes).
        subject = f"{subject} [test {datetime.now().strftime('%H:%M:%S')}]"
    run_date = datetime.fromisoformat(ranked["run_time"]).date().isoformat()
    nl = settings.get("newsletter") or {}
    key = os.environ.get("BREVO_API_KEY", "").strip()
    sender_email = str(nl.get("sender_email") or "").strip()
    list_id = nl.get("list_id")

    # Already sent today? (the one-off test ignores this)
    state = read_json(_STATE, default={}) or {}
    last = state.get("date")
    if last == run_date and not force_dry and not force_test:
        print(f"Already emailed for {run_date}; skipping.")
        return 0

    # Account under review at Brevo? Don't keep firing rejected campaign creates
    # into a manual review queue. Still a non-zero exit so the day is not silently
    # counted as fine.
    blocked = None if (force_dry or force_test) else _hold_blocks(state, run_date)
    if blocked:
        print(f"Send SKIPPED: {blocked}", file=sys.stderr)
        return 1

    if force_dry or not (key and nl.get("enabled") and sender_email and list_id):
        why = ("--dry-run" if force_dry else
               "no BREVO_API_KEY" if not key else
               "newsletter disabled" if not nl.get("enabled") else
               "no sender_email in settings" if not sender_email else
               "no list_id in settings")
        print(f"DRY-RUN ({why}) - not sending.")
        print(f"Subject: {subject}")
        print(f"Body: {len(body)} bytes")
        return 0

    api = str(nl.get("api_base") or "https://api.brevo.com/v3").rstrip("/")
    name = f"One Story {run_date}" + (" [test]" if force_test else "")
    campaign = {
        "name": name,
        "subject": subject,
        "sender": {"name": nl.get("sender_name", "One Story"), "email": sender_email},
        "htmlContent": body,
        "recipients": {"listIds": [int(list_id)]},
    }
    try:
        status, data = _post(f"{api}/emailCampaigns", key, campaign)
        campaign_id = data.get("id")
        if not campaign_id:
            print(f"Create returned HTTP {status} but no campaign id: {data}",
                  file=sys.stderr)
            return 1

        if force_test:
            recipients = [e.strip() for e in
                          os.environ.get("BREVO_TEST_EMAIL", "").split(",") if e.strip()]
            if not recipients:
                print("--test needs BREVO_TEST_EMAIL set (comma-separated ok).",
                      file=sys.stderr)
                return 1
            _post(f"{api}/emailCampaigns/{campaign_id}/sendTest", key,
                  {"emailTo": recipients})
            print(f"Test of '{subject[:60]}' sent to {recipients} "
                  f"(campaign {campaign_id}; live list untouched, guard left alone).")
            return 0

        _post(f"{api}/emailCampaigns/{campaign_id}/sendNow", key, None)
        print(f"Sent '{subject[:60]}' -> campaign {campaign_id}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        print(f"Send FAILED: HTTP {e.code} {raw[:400]}", file=sys.stderr)
        try:
            code = (json.loads(raw) or {}).get("code", "")
        except ValueError:
            code = ""
        if code in _HOLD_CODES and not force_test:
            hold = dict(state.get("hold") or {})
            hold.setdefault("since", run_date)
            hold["code"], hold["last_attempt"] = code, run_date
            write_json(_STATE, {**state, "hold": hold})
            print(f"Recorded account hold ({code}) since {hold['since']} - further "
                  f"sends are skipped, with a re-probe every {_HOLD_REPROBE_DAYS} days. "
                  "This is an account-level block at Brevo, not a config problem.",
                  file=sys.stderr)
        return 1

    # A send got through, so any recorded hold is over.
    write_json(_STATE, {"date": run_date, "subject": subject})
    print(f"Recorded send for {run_date}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
