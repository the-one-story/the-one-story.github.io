"""Send outcomes and the account-hold guard.

Motivated by a real three-day outage (10-12/08/2026): Brevo put the account
under manual review, every campaign create returned 402
`account_under_validation`, and the run still went green - so nobody noticed
the newsletter was dead. These pin the two halves of that: the failure has to
be non-zero, and we must stop firing rejected creates into a review queue.
"""
from __future__ import annotations

import json

import pytest

import send_email


# --------------------------------------------------------------------------- #
# Hold bookkeeping                                                            #
# --------------------------------------------------------------------------- #
def test_no_hold_means_attempt():
    assert send_email._hold_blocks({}, "2026-08-13") is None
    assert send_email._hold_blocks({"date": "2026-08-12"}, "2026-08-13") is None


def test_a_fresh_hold_blocks_todays_attempt():
    state = {"hold": {"code": "account_under_validation",
                      "since": "2026-08-10", "last_attempt": "2026-08-12"}}
    reason = send_email._hold_blocks(state, "2026-08-13")
    assert reason and "account_under_validation" in reason


def test_a_stale_hold_is_re_probed_so_sending_self_heals():
    """The hold must not wedge sending forever - once the review clears, the
    job has to resume without anyone editing state by hand."""
    state = {"hold": {"code": "account_under_validation",
                      "since": "2026-08-10", "last_attempt": "2026-08-10"}}
    due = f"2026-08-{10 + send_email._HOLD_REPROBE_DAYS:02d}"
    assert send_email._hold_blocks(state, due) is None


def test_an_unreadable_hold_does_not_wedge_sending():
    state = {"hold": {"code": "account_under_validation", "since": "not-a-date"}}
    assert send_email._hold_blocks(state, "2026-08-13") is None


# --------------------------------------------------------------------------- #
# End-to-end behaviour of main()                                              #
# --------------------------------------------------------------------------- #
@pytest.fixture
def wired(monkeypatch, isolated_root):
    """A fully configured sender whose only unknown is what the API returns."""
    ranked = {"run_time": "2026-08-13T05:00:00+10:00"}
    monkeypatch.setattr(send_email, "read_json",
                        lambda p, default=None: dict(ranked) if "ranked" in p
                        else (_state.get("v") or default))
    monkeypatch.setattr(send_email, "build_email", lambda r: ("Subject line", "<html></html>"))
    monkeypatch.setattr(send_email, "load_settings", lambda: {
        "ranked_json_path": "data/ranked.json",
        "newsletter": {"enabled": True, "sender_email": "onestory@mail.example.com",
                       "sender_name": "One Story", "list_id": 2,
                       "api_base": "https://api.brevo.com/v3"},
    })
    monkeypatch.setenv("BREVO_API_KEY", "key")
    _state = {"v": {}}
    monkeypatch.setattr(send_email, "write_json",
                        lambda p, obj: _state.__setitem__("v", obj) or p)
    monkeypatch.setattr(send_email.sys, "argv", ["send_email.py"])
    return _state


def _http_error(code, body):
    import urllib.error
    import io
    return urllib.error.HTTPError("u", code, "err", {}, io.BytesIO(body.encode()))


def test_account_under_validation_exits_non_zero_and_records_a_hold(wired, monkeypatch):
    def boom(*a, **k):
        raise _http_error(402, json.dumps(
            {"code": "account_under_validation",
             "message": "Your account is under validation."}))
    monkeypatch.setattr(send_email, "_post", boom)

    assert send_email.main() == 1, "a dead send must not report success"
    hold = wired["v"]["hold"]
    assert hold["code"] == "account_under_validation"
    assert hold["since"] == "2026-08-13"


def test_a_recorded_hold_stops_the_next_days_attempt(wired, monkeypatch):
    wired["v"] = {"hold": {"code": "account_under_validation",
                           "since": "2026-08-12", "last_attempt": "2026-08-12"}}
    calls = []
    monkeypatch.setattr(send_email, "_post", lambda *a, **k: calls.append(a) or (200, {"id": 1}))
    assert send_email.main() == 1
    assert calls == [], "kept hammering the API while the account was under review"


def test_other_http_errors_do_not_record_a_hold(wired, monkeypatch):
    """A one-off 500 must not silence sending for days."""
    monkeypatch.setattr(send_email, "_post",
                        lambda *a, **k: (_ for _ in ()).throw(_http_error(500, "boom")))
    assert send_email.main() == 1
    assert "hold" not in (wired["v"] or {})


def test_a_successful_send_clears_any_hold(wired, monkeypatch):
    wired["v"] = {"hold": {"code": "account_under_validation",
                           "since": "2026-08-01", "last_attempt": "2026-08-01"}}
    monkeypatch.setattr(send_email, "_post", lambda *a, **k: (201, {"id": 42}))
    assert send_email.main() == 0
    assert "hold" not in wired["v"]
    assert wired["v"]["date"] == "2026-08-13"


def test_already_sent_today_is_a_no_op(wired, monkeypatch):
    wired["v"] = {"date": "2026-08-13"}
    calls = []
    monkeypatch.setattr(send_email, "_post", lambda *a, **k: calls.append(a) or (200, {"id": 1}))
    assert send_email.main() == 0
    assert calls == []


# --------------------------------------------------------------------------- #
# The workflow must surface a failed send                                     #
# --------------------------------------------------------------------------- #
def test_workflow_reraises_a_failed_send_after_publishing():
    """continue-on-error keeps publishing unblocked; without a re-raise the run
    shows green and a dead newsletter goes unnoticed (it did, for 3 days)."""
    import pathlib
    import yaml
    wf = yaml.safe_load((pathlib.Path(__file__).resolve().parent.parent
                         / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8"))
    steps = wf["jobs"]["build"]["steps"]
    names = [s.get("name", "") for s in steps]

    send = next(s for s in steps if s.get("id") == "send")
    assert send.get("continue-on-error") is True

    surfacer = next(s for s in steps if "outcome == 'failure'" in str(s.get("if", "")))
    assert "steps.send.outcome" in surfacer["if"]
    assert "exit 1" in surfacer["run"]

    # It must run AFTER the commit, or a failed send would block publishing.
    commit_i = next(i for i, n in enumerate(names) if n.startswith("Commit"))
    assert names.index(surfacer["name"]) > commit_i
