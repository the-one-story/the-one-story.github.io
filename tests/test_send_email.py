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
def _wire(monkeypatch, newsletter, env):
    """A fully configured sender whose only unknown is what the API returns."""
    ranked = {"run_time": "2026-08-13T05:00:00+10:00"}
    state = {"v": {}}
    monkeypatch.setattr(send_email, "read_json",
                        lambda p, default=None: dict(ranked) if "ranked" in p
                        else (state.get("v") or default))
    monkeypatch.setattr(send_email, "build_email",
                        lambda r, **kw: ("Subject line", "<html></html>"))
    monkeypatch.setattr(send_email, "load_settings", lambda: {
        "ranked_json_path": "data/ranked.json", "newsletter": newsletter})
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(send_email, "write_json",
                        lambda p, obj: state.__setitem__("v", obj) or p)
    monkeypatch.setattr(send_email.sys, "argv", ["send_email.py"])
    return state


@pytest.fixture
def wired(monkeypatch, isolated_root):
    """The retired Brevo path, kept because the code is still shipped."""
    return _wire(monkeypatch, {
        "enabled": True, "provider": "brevo",
        "sender_email": "onestory@mail.example.com", "sender_name": "One Story",
        "list_id": 2, "api_base": "https://api.brevo.com/v3"},
        {"BREVO_API_KEY": "key"})


@pytest.fixture
def resend(monkeypatch, isolated_root):
    return _wire(monkeypatch, {
        "enabled": True, "provider": "resend",
        "sender_email": "onestory@mail.example.com", "sender_name": "One Story",
        "segment_id": "seg-uuid", "api_base": "https://api.resend.com"},
        {"RESEND_API_KEY": "key"})


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
# Resend path                                                                 #
# --------------------------------------------------------------------------- #
def test_resend_sends_a_broadcast_in_one_call(resend, monkeypatch):
    """Brevo needed create-then-sendNow; Resend does it in one POST with
    send:true. A missing send flag would leave the edition sitting as a draft
    and nobody would receive it."""
    calls = []
    monkeypatch.setattr(send_email, "_post",
                        lambda url, key, payload, auth="brevo":
                        calls.append((url, payload, auth)) or (201, {"id": "b-1"}))
    assert send_email.main() == 0
    assert len(calls) == 1, "a broadcast must not take two calls"
    url, payload, auth = calls[0]
    assert url.endswith("/broadcasts")
    assert auth == "resend"
    assert payload["send"] is True
    assert payload["segment_id"] == "seg-uuid"
    assert payload["from"] == "One Story <onestory@mail.example.com>"
    assert resend["v"]["date"] == "2026-08-13"


def test_resend_uses_bearer_auth_not_brevos_api_key_header(monkeypatch):
    """The two providers authenticate differently; sending Brevo's header to
    Resend is a 401."""
    seen = {}

    class _Resp:
        status = 200
        def read(self): return b'{"id":"x"}'
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def _fake_urlopen(req, timeout=None):
        seen.update(dict(req.header_items()))
        return _Resp()

    monkeypatch.setattr(send_email.urllib.request, "urlopen", _fake_urlopen)
    send_email._post("https://api.resend.com/broadcasts", "kk", {}, auth="resend")
    hdrs = {k.lower(): v for k, v in seen.items()}
    assert hdrs.get("Authorization".lower()) == "Bearer kk"
    assert "api-key" not in hdrs

    seen.clear()
    send_email._post("https://api.brevo.com/v3/emailCampaigns", "kk", {})
    hdrs = {k.lower(): v for k, v in seen.items()}
    assert hdrs.get("api-key") == "kk"
    assert "authorization" not in hdrs


def test_post_sends_a_real_user_agent(monkeypatch):
    """Cloudflare fronts both providers' APIs and bans urllib's default
    `Python-urllib/3.x` with 403 error 1010 browser_signature_banned. It reads
    like an auth failure but is purely the agent string - it killed a send on
    13/08/2026 and had already bitten the sibling project."""
    seen = {}

    class _Resp:
        status = 200
        def read(self): return b"{}"
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(send_email.urllib.request, "urlopen",
                        lambda req, timeout=None: seen.update(dict(req.header_items())) or _Resp())
    send_email._post("https://api.resend.com/broadcasts", "k", {}, auth="resend")
    ua = {k.lower(): v for k, v in seen.items()}.get("user-agent", "")
    assert ua and "python-urllib" not in ua.lower(), f"default agent will be blocked: {ua!r}"


def test_resend_test_send_uses_direct_email_not_a_broadcast(resend, monkeypatch):
    """A broadcast can only target a segment, so a --test broadcast would mail
    the live list. It must go through /emails to a named address instead."""
    calls = []
    monkeypatch.setattr(send_email, "_post",
                        lambda url, key, payload, auth="brevo":
                        calls.append((url, payload)) or (200, {"id": "e-1"}))
    monkeypatch.setenv("RESEND_TEST_EMAIL", "me@example.com")
    monkeypatch.setattr(send_email.sys, "argv", ["send_email.py", "--test"])
    assert send_email.main() == 0
    url, payload = calls[0]
    assert url.endswith("/emails"), "a test must not go out as a broadcast"
    assert payload["to"] == ["me@example.com"]
    assert "segment_id" not in payload
    assert resend["v"] == {}, "a test must not touch the per-day guard"


def test_resend_body_carries_the_unsubscribe_placeholder(resend, monkeypatch):
    """Resend appends no footer, so without this the edition ships with no
    unsubscribe link."""
    captured = {}
    monkeypatch.setattr(send_email, "build_email",
                        lambda r, **kw: captured.update(kw) or ("s", "<html></html>"))
    monkeypatch.setattr(send_email, "_post", lambda *a, **k: (201, {"id": "b-1"}))
    assert send_email.main() == 0
    assert captured.get("unsubscribe_url") == send_email._RESEND_UNSUB


def test_brevo_path_passes_no_unsubscribe_url(wired, monkeypatch):
    """Brevo appends its own footer - passing one duplicates it."""
    captured = {}
    monkeypatch.setattr(send_email, "build_email",
                        lambda r, **kw: captured.update(kw) or ("s", "<html></html>"))
    monkeypatch.setattr(send_email, "_post", lambda *a, **k: (201, {"id": 1}))
    assert send_email.main() == 0
    assert captured.get("unsubscribe_url") is None


def test_resend_missing_segment_id_dry_runs_rather_than_erroring(monkeypatch, isolated_root):
    _wire(monkeypatch, {
        "enabled": True, "provider": "resend", "sender_name": "One Story",
        "sender_email": "onestory@mail.example.com", "segment_id": ""},
        {"RESEND_API_KEY": "key"})
    calls = []
    monkeypatch.setattr(send_email, "_post",
                        lambda *a, **k: calls.append(a) or (200, {}))
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
