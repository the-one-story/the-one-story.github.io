"""run.py's FALLBACK path - the one that only executes on a day already gone wrong.

Flagged untested on 28/11/2026 while closing the test-coverage item. It keeps
yesterday's page up when a run dies, and the marker guard stops the banner being
injected twice across repeated failures. The marker is deliberately quote-agnostic
text that must appear in BOTH the injected banner here and the rendered one in
render.py; if that copy is ever edited, these tests are what catch the drift.
"""
from __future__ import annotations

import os

import pytest

import run as run_mod


PRIOR_PAGE = ('<!doctype html><html><body><div class="wrap">'
              "<h1>Yesterday's story</h1></div></body></html>")


@pytest.fixture
def page(tmp_path, monkeypatch):
    """Point run.py's output path at a temp file."""
    p = tmp_path / "index.html"
    monkeypatch.setattr(run_mod, "load_settings",
                        lambda: {"output_html": "index.html"})
    monkeypatch.setattr(run_mod, "rel", lambda _rel: str(p))
    return p


def test_a_failed_run_keeps_the_prior_page_and_flags_it(page):
    page.write_text(PRIOR_PAGE, encoding="utf-8")
    assert run_mod._inject_stale_banner() is True
    out = page.read_text(encoding="utf-8")
    assert "Yesterday's story" in out, "the prior page's content was lost"
    assert run_mod._STALE_MARKER in out


def test_the_banner_is_not_injected_twice(page):
    page.write_text(PRIOR_PAGE, encoding="utf-8")
    run_mod._inject_stale_banner()
    once = page.read_text(encoding="utf-8")
    assert run_mod._inject_stale_banner() is True
    twice = page.read_text(encoding="utf-8")
    assert once == twice
    assert twice.count(run_mod._STALE_MARKER) == 1


def test_no_prior_page_means_there_is_nothing_to_fall_back_to(page):
    assert not os.path.exists(page)
    assert run_mod._inject_stale_banner() is False


def test_the_marker_matches_the_copy_render_actually_emits():
    """The guard is text matching, so the two copies must agree."""
    import render
    src = open(render.__file__, encoding="utf-8").read()
    assert run_mod._STALE_MARKER in src, (
        "render.py's stale banner no longer contains the marker run.py greps for, "
        "so a repeated failure would stack banners")


def test_the_wrapper_anchor_still_exists_in_what_render_emits():
    """The banner is injected by string match against render.py's wrapper.

    Renaming or re-quoting that div used to make the injection find nothing,
    write nothing, and still report success - so the page served yesterday's
    story with no banner. Pin the coupling here.
    """
    import render
    src = open(render.__file__, encoding="utf-8").read()
    assert '<div class="wrap">' in src


def test_a_page_without_the_anchor_is_still_flagged(page, capsys):
    """Fallback anchor: better a banner after <body> than no banner at all."""
    page.write_text("<!doctype html><html><body><h1>Yesterday</h1></body></html>",
                    encoding="utf-8")
    assert run_mod._inject_stale_banner() is True
    assert run_mod._STALE_MARKER in page.read_text(encoding="utf-8")


def test_no_anchor_at_all_warns_loudly(page, capsys):
    page.write_text("<h1>Yesterday</h1>", encoding="utf-8")
    assert run_mod._inject_stale_banner() is True
    assert "WARNING" in capsys.readouterr().err
