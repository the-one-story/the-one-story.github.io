"""The workflow's schedule gate - extracted from daily.yml and exercised.

This is the piece that actually failed in production (06/08/2026): GitHub
delayed the 19:00 UTC cron to 22:41 UTC, the gate demanded the local hour equal
exactly 5, saw 8, and skipped the build - so no edition and no email that day.
It is YAML-embedded Python, so nothing else can test it; these cases pin the
behaviour, including that exact failure.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "daily.yml"


def _gate_source() -> str:
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    step = next(s for s in wf["jobs"]["gate"]["steps"] if s.get("id") == "check")
    body = step["run"]
    return body.split("<<'PY'", 1)[1].rsplit("PY", 1)[0]


def _run_gate(tmp_path, local_iso, last_sent, event="schedule"):
    """Execute the real gate code with a frozen clock and a given state file."""
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "last_email.json").write_text(
        json.dumps({"date": last_sent} if last_sent else {}), encoding="utf-8")
    out = tmp_path / "gh_output"
    out.write_text("", encoding="utf-8")

    freeze = (
        "import datetime as _d\n"
        "class _DT(_d.datetime):\n"
        "    @classmethod\n"
        f"    def now(cls, tz=None): return _d.datetime.fromisoformat({local_iso!r}).astimezone(tz)\n"
        "_d.datetime = _DT\n"
    )
    env = {**os.environ, "EVENT": event, "WANT_LOCAL_HOUR": "5",
           "GITHUB_OUTPUT": str(out)}
    proc = subprocess.run([sys.executable, "-c", freeze + _gate_source()],
                          cwd=tmp_path, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return out.read_text(encoding="utf-8").strip(), proc.stdout


def _ran(result):
    return result[0] == "run=true"


# --------------------------------------------------------------------------- #
# The regression                                                              #
# --------------------------------------------------------------------------- #
def test_a_cron_delayed_by_hours_still_runs(tmp_path):
    """06/08/2026 verbatim: fired 08:41 local, yesterday's edition on record."""
    assert _ran(_run_gate(tmp_path, "2026-08-07T08:41:00+10:00", "2026-08-06"))


def test_a_very_late_cron_still_runs(tmp_path):
    assert _ran(_run_gate(tmp_path, "2026-08-07T19:30:00+10:00", "2026-08-06"))


# --------------------------------------------------------------------------- #
# Exactly one run per local day, in both DST regimes                          #
# --------------------------------------------------------------------------- #
def test_aest_early_cron_is_too_early(tmp_path):
    """18:00 UTC is 04:00 AEST - before the 05:00 target."""
    assert not _ran(_run_gate(tmp_path, "2026-08-07T04:00:00+10:00", "2026-08-06"))


def test_aest_on_time_cron_runs(tmp_path):
    assert _ran(_run_gate(tmp_path, "2026-08-07T05:00:00+10:00", "2026-08-06"))


def test_aedt_early_cron_runs(tmp_path):
    """In summer 18:00 UTC IS 05:00 local, so it is the live one."""
    assert _ran(_run_gate(tmp_path, "2026-12-07T05:00:00+11:00", "2026-12-06"))


def test_aedt_second_cron_is_stopped_by_the_already_sent_check(tmp_path):
    """19:00 UTC is 06:00 AEDT - late enough, so only the state check prevents
    a second edition."""
    assert not _ran(_run_gate(tmp_path, "2026-12-07T06:00:00+11:00", "2026-12-07"))


@pytest.mark.parametrize("regime,offset,early,late", [
    ("AEST", "+10:00", "2026-08-07T04:00:00", "2026-08-07T05:00:00"),
    ("AEDT", "+11:00", "2026-12-07T04:00:00", "2026-12-07T05:00:00"),
])
def test_exactly_one_of_the_two_crons_survives(tmp_path, regime, offset, early, late):
    sent = None
    fired = 0
    for stamp in (early, late):
        result = _run_gate(tmp_path, stamp + offset, sent)
        if _ran(result):
            fired += 1
            sent = stamp[:10]     # that run would send and record the date
    assert fired == 1, f"{regime}: {fired} runs survived the gate, expected 1"


# --------------------------------------------------------------------------- #
# Manual dispatch                                                             #
# --------------------------------------------------------------------------- #
def test_manual_dispatch_always_runs(tmp_path):
    """Must work at any hour and even when today's edition already went."""
    assert _ran(_run_gate(tmp_path, "2026-08-07T14:00:00+10:00", "2026-08-07",
                          event="workflow_dispatch"))


def test_missing_state_file_does_not_block(tmp_path):
    assert _ran(_run_gate(tmp_path, "2026-08-07T05:00:00+10:00", None))


def test_gate_writes_only_key_value_to_github_output(tmp_path):
    """A stray comment line in GITHUB_OUTPUT can be rejected as malformed."""
    result, _ = _run_gate(tmp_path, "2026-08-07T05:00:00+10:00", "2026-08-06")
    for line in result.splitlines():
        assert line.startswith("run="), f"non key=value line: {line!r}"


# --------------------------------------------------------------------------- #
# The workflow wiring itself                                                  #
# --------------------------------------------------------------------------- #
def test_both_dst_crons_are_registered():
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    on = wf[True] if True in wf else wf["on"]        # PyYAML parses `on:` as True
    hours = sorted(int(c["cron"].split()[1]) for c in on["schedule"])
    assert hours == [18, 19], f"expected the AEDT/AEST pair, got {hours}"


def test_build_is_gated_and_gate_checks_out_the_repo():
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert wf["jobs"]["build"]["if"] == "needs.gate.outputs.run == 'true'"
    assert wf["jobs"]["build"]["needs"] == "gate"
    uses = [s.get("uses", "") for s in wf["jobs"]["gate"]["steps"]]
    assert any(u.startswith("actions/checkout") for u in uses), \
        "gate must check out the repo to read data/last_email.json"


def test_render_hour_matches_the_gate_target():
    """The page promises a time; the gate enforces one. They must agree."""
    import common
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    step = next(s for s in wf["jobs"]["gate"]["steps"] if s.get("id") == "check")
    assert int(step["env"]["WANT_LOCAL_HOUR"]) == common.load_settings()["update_hour_local"]
