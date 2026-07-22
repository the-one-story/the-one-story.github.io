"""Stage 4 - DECAY LEDGER (state, not a user archive).

A tiny local file (data/recent_leads.json) holding fingerprints of the last
~N days' winning clusters, purely so the SCORE stage can penalise a story that
already led on a recent day (the novelty term).

This is the ONLY persistent state in the whole project. It is NOT a browsable
history - the public site stays ephemeral. We store only:
    date  - ISO date (local tz) the story led
    label - the winning headline (for human-readable debugging of the ledger)
    text  - representative text (member headlines joined) used for the
            cosine novelty match. Headlines only; no article bodies.
"""
from __future__ import annotations

from datetime import date, datetime

from common import load_settings, read_json, write_json


def _dedup_titles(members: list[dict]) -> str:
    seen, out = set(), []
    for m in members:
        t = m["title"].strip()
        key = t.lower()
        if key and key not in seen:
            seen.add(key)
            out.append(t)
    return " ".join(out)


def load_ledger(settings: dict) -> list[dict]:
    return read_json(settings["ledger_path"], default=[]) or []


def record_winner(settings: dict, winner: dict, run_time_iso: str) -> str:
    """Append today's winner and prune to the retention window.

    Idempotent per date: if an entry for today already exists it is replaced,
    so re-running the pipeline on the same day does not double-count.
    """
    run_date = datetime.fromisoformat(run_time_iso).date().isoformat()
    ledger = [e for e in load_ledger(settings) if e.get("date") != run_date]
    ledger.append({
        "date": run_date,
        "label": winner["members"][0]["title"],
        "text": _dedup_titles(winner["members"]),
    })

    # Prune anything older than ledger_days.
    cutoff = date.fromisoformat(run_date).toordinal() - settings["ledger_days"]
    ledger = [e for e in ledger
              if date.fromisoformat(e["date"]).toordinal() >= cutoff]
    ledger.sort(key=lambda e: e["date"])
    return write_json(settings["ledger_path"], ledger)


if __name__ == "__main__":
    s = load_settings()
    led = load_ledger(s)
    print(f"Decay ledger: {len(led)} entr{'y' if len(led)==1 else 'ies'} "
          f"at {s['ledger_path']}")
    for e in led:
        print(f"  {e['date']}  {e['label'][:70]}")
