"""The decay ledger - the only persistent state in the project.

It is what stops the same story leading two days running, so a bug here is
invisible on the day and only shows up as repetition.
"""
from __future__ import annotations

from ledger import load_ledger, record_winner
from conftest import article


def _winner(title):
    return {"members": [article(title), article(title + " - later report")]}


def _settings(root, days=7):
    return {"ledger_path": "data/recent_leads.json", "ledger_days": days}


def test_recording_a_winner_round_trips(isolated_root):
    s = _settings(isolated_root)
    record_winner(s, _winner("Cyclone Mara batters Queensland"), "2026-08-01T06:00:00+10:00")
    led = load_ledger(s)
    assert len(led) == 1
    assert led[0]["date"] == "2026-08-01"
    assert "Cyclone Mara" in led[0]["text"]


def test_same_day_rerun_replaces_rather_than_duplicates(isolated_root):
    """A re-run must not double-count the day, or the novelty term sees two
    entries for one lead."""
    s = _settings(isolated_root)
    record_winner(s, _winner("First pick"), "2026-08-01T06:00:00+10:00")
    record_winner(s, _winner("Second pick"), "2026-08-01T18:00:00+10:00")
    led = load_ledger(s)
    assert len(led) == 1
    assert "Second pick" in led[0]["text"]


def test_state_survives_a_restart(isolated_root):
    """Nothing is held in memory: a fresh load must see prior days."""
    s = _settings(isolated_root)
    record_winner(s, _winner("Day one story"), "2026-08-01T06:00:00+10:00")
    record_winner(s, _winner("Day two story"), "2026-08-02T06:00:00+10:00")
    led = load_ledger(s)          # simulates a new process reading from disk
    assert [e["date"] for e in led] == ["2026-08-01", "2026-08-02"]


def test_entries_older_than_the_window_are_pruned(isolated_root):
    s = _settings(isolated_root, days=7)
    record_winner(s, _winner("Ancient story"), "2026-07-01T06:00:00+10:00")
    record_winner(s, _winner("Recent story"), "2026-08-01T06:00:00+10:00")
    dates = [e["date"] for e in load_ledger(s)]
    assert "2026-07-01" not in dates
    assert "2026-08-01" in dates


def test_ledger_is_sorted_by_date(isolated_root):
    s = _settings(isolated_root)
    for d in ("2026-08-03", "2026-08-01", "2026-08-02"):
        record_winner(s, _winner(f"Story {d}"), f"{d}T06:00:00+10:00")
    dates = [e["date"] for e in load_ledger(s)]
    assert dates == sorted(dates)


def test_missing_ledger_reads_as_empty(isolated_root):
    assert load_ledger(_settings(isolated_root)) == []


def test_stored_text_is_headlines_only(isolated_root):
    """Copyright guard: the ledger stores headlines, never article bodies."""
    s = _settings(isolated_root)
    w = {"members": [article("Headline one", snippet="A full paragraph of body text.")]}
    record_winner(s, w, "2026-08-01T06:00:00+10:00")
    stored = load_ledger(s)[0]
    assert "body text" not in stored["text"]
    assert stored["text"] == "Headline one"
