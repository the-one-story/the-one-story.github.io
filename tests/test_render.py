"""Rendering rules that are easy to regress and invisible until a reader sees
them: the no-dash house style, source-name cleaning, and the "next update" line
(which must stay truthful across a daylight-saving switch).
"""
from __future__ import annotations

import pytest

import email_render
from render import _clean_source, _hyphenate, _next_update
from conftest import article

SYD = "Australia/Sydney"


# --------------------------------------------------------------------------- #
# House style                                                                 #
# --------------------------------------------------------------------------- #
def test_em_and_en_dashes_are_collapsed_to_hyphens():
    assert _hyphenate("a — b") == "a - b"
    assert _hyphenate("a – b") == "a - b"
    assert _hyphenate("already - fine") == "already - fine"
    assert _hyphenate("") == ""
    assert _hyphenate(None) == ""


def test_no_stray_dashes_survive_into_the_page_or_email():
    """Feed text arrives with real em/en dashes; none may reach the reader."""
    for raw in ("Talks collapse — again", "Rates rise – sharply"):
        assert "—" not in _hyphenate(raw)
        assert "–" not in _hyphenate(raw)


# --------------------------------------------------------------------------- #
# Source names                                                                #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("raw,clean", [
    ("The Guardian - World", "The Guardian"),
    ("The Nation (US, left)", "The Nation"),
    ("BBC News - World", "BBC News"),
    ("Reuters", "Reuters"),
])
def test_section_and_tag_suffixes_are_stripped(raw, clean):
    assert _clean_source(raw) == clean


def test_internal_hyphen_in_a_name_survives():
    """Regression: a greedy rule turned 'Agence France-Presse' into
    'Agence France'."""
    assert _clean_source("Agence France-Presse") == "Agence France-Presse"


# --------------------------------------------------------------------------- #
# Next-update line                                                            #
# --------------------------------------------------------------------------- #
def test_next_update_is_the_next_local_occurrence():
    out = _next_update("2026-08-05T06:00:00+10:00", SYD, 5)
    assert out.startswith("Thu 06 Aug, 05:00")


def test_next_update_same_day_when_still_ahead():
    out = _next_update("2026-08-05T01:00:00+10:00", SYD, 5)
    assert out.startswith("Wed 05 Aug, 05:00")


def test_next_update_holds_the_wall_clock_across_a_dst_switch():
    """Built from the calendar date, not by adding 24h - otherwise the hour
    slides to 04:00 or 06:00 on the changeover day."""
    out = _next_update("2026-10-03T06:00:00+10:00", SYD, 5)
    assert "05:00" in out and "AEDT" in out, out


def test_next_update_reports_the_local_zone_abbreviation():
    assert "AEST" in _next_update("2026-08-05T06:00:00+10:00", SYD, 5)


# --------------------------------------------------------------------------- #
# Email body                                                                  #
# --------------------------------------------------------------------------- #
@pytest.fixture
def ranked():
    hero = article("Leaders sign the Geneva accord", source="Reuters",
                   url="https://example.com/accord", snippet="A deal was struck.")
    return {
        "run_time": "2026-08-05T06:00:00+10:00",
        "timezone": SYD,
        "window_hours": 24,
        "update_hour_local": 5,
        "signup_form_url": "",
        "winner": {"hero": hero, "members": [hero], "outlet_count": 9,
                   "countries": ["US", "GB", "FR"], "leans": ["left", "centre"],
                   "components": {"coverage": 1.0, "diversity": 0.5,
                                  "recency": 0.9, "novelty": 1.0},
                   "novelty_match": {"date": None, "cosine": 0.0}, "score": 0.4},
        "runners_up": [],
        "feeds_report": {"run_time": "2026-08-05T06:00:00+10:00"},
    }


def test_email_uses_table_layout_with_bgcolor(ranked):
    """Outlook needs the bgcolor ATTRIBUTE, not just CSS background."""
    _, html = email_render.build_email(ranked)
    assert "<table" in html and 'bgcolor="' in html
    assert "display:flex" not in html and "display:grid" not in html


def test_email_declares_a_dark_colour_scheme(ranked):
    _, html = email_render.build_email(ranked)
    assert 'name="color-scheme"' in html and "dark" in html


def test_email_has_no_svg_logo(ranked):
    """SVG does not render in Gmail or Outlook."""
    _, html = email_render.build_email(ranked)
    assert "<svg" not in html.lower()


def test_email_adds_no_unsubscribe_footer_by_default(ranked):
    """Brevo appended its own; duplicating it stranded a line above the badge.
    So the footer is opt-in, and the default stays bare."""
    _, html = email_render.build_email(ranked)
    assert "unsubscribe" not in html.lower()


def test_email_renders_an_unsubscribe_footer_when_given_one(ranked):
    """Resend appends nothing - without this the edition would go out with no
    unsubscribe link at all."""
    _, html = email_render.build_email(
        ranked, unsubscribe_url="{{{RESEND_UNSUBSCRIBE_URL}}}")
    assert "Unsubscribe" in html


def test_unsubscribe_placeholder_is_not_html_escaped(ranked):
    """It has to reach the provider verbatim to be substituted; escaping the
    braces would mail a literal, broken link."""
    _, html = email_render.build_email(
        ranked, unsubscribe_url="{{{RESEND_UNSUBSCRIBE_URL}}}")
    assert "{{{RESEND_UNSUBSCRIBE_URL}}}" in html
    assert "&#123;" not in html and "&lbrace;" not in html


def test_email_subject_carries_the_headline_and_no_dashes(ranked):
    ranked["winner"]["hero"]["title"] = "Talks collapse — again"
    subject, _ = email_render.build_email(ranked)
    assert "Talks collapse - again" in subject
    assert "—" not in subject


def test_email_escapes_feed_text(ranked):
    ranked["winner"]["hero"]["title"] = 'A <script>alert("x")</script> headline'
    _, html = email_render.build_email(ranked)
    assert "<script>" not in html
