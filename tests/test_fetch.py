"""Noise-format filtering and snippet handling.

`is_noise_format` runs at FETCH time and drops the item entirely, so a miss does
not just spoil the hero - it lets a roundup count as an outlet covering the
story and bridge unrelated clusters. Both live regressions are pinned below.
"""
from __future__ import annotations

import pytest

from fetch import _clean_snippet, is_noise_format


@pytest.mark.parametrize("url,title", [
    ("https://x.com/podcasts/ep-1", "The week in review"),
    ("https://x.com/video/clip", "Watch: the moment it happened"),
    ("https://x.com/live/blog", "Summit live updates"),
    ("https://x.com/news/a", "Live: the summit as it happens"),
    ("https://x.com/news/a", "ICYMI: the biggest news you missed this weekend"),
    ("https://x.com/in-pictures/a", "The year in pictures"),
    ("https://x.com/news/a", "Your morning briefing"),
])
def test_known_noise_formats_are_dropped(url, title):
    assert is_noise_format(url, title) is True


def test_npr_up_first_roundup_is_dropped():
    """Regression (04/08/2026): NPR's daily Up First newsletter heroed as
    'Todd Blanche rescinds anti-weaponization fund. And, Trump calls off
    striking Iran' - two unrelated stories in one item. It beat BOTH checks:
    the URL has no /newsletter/ path segment, and the feed title contains
    neither 'newsletter' nor 'Up First' - only the ". And, " shape gives it
    away."""
    url = ("https://www.npr.org/2026/08/03/g-s1-136892/"
           "up-first-newsletter-iran-war-todd-blanche-capital-one")
    title = ("Todd Blanche rescinds 'anti-weaponization fund'. "
             "And, Trump calls off striking Iran")
    assert is_noise_format(url, title) is True
    # each half must independently catch it
    assert is_noise_format(url, "Some ordinary headline") is True, "URL check regressed"
    assert is_noise_format("https://example.com/a", title) is True, "title shape check regressed"


def test_newsletter_in_a_slug_is_caught_not_just_a_path_segment():
    assert is_noise_format("https://x.com/2026/an-expanding-war-newsletter", "A war") is True


@pytest.mark.parametrize("title", [
    # Legitimate single-story headlines that use a two-sentence rhetorical
    # shape. A broad "two clauses" rule would drop ~1.7% of the real corpus;
    # these pin that we did NOT adopt one.
    "OpenAI blamed a hacking event on its AI models gone rogue. Here is what we know",
    "Famine has ended in Gaza. But the gains are fragile",
    "Rep. Jim Jordan formally asks DOJ to prosecute Jack Smith",
    "Sen. Paul threatens to hold Fauci in contempt",
    "A protest movement is challenging India's establishment. What to know",
])
def test_ordinary_headlines_are_not_treated_as_roundups(title):
    assert is_noise_format("https://example.com/story", title) is False


def test_plain_article_passes():
    assert is_noise_format("https://www.bbc.co.uk/news/articles/abc", "Leaders sign accord") is False


def test_snippet_is_word_capped_for_copyright():
    long = " ".join(f"word{i}" for i in range(200))
    out = _clean_snippet(long, 25)
    assert len([w for w in out.replace("...", " ").split() if w.startswith("word")]) <= 25


def test_snippet_strips_html_and_collapses_whitespace():
    out = _clean_snippet("<p>Hello   <b>there</b></p>\n\n  world", 25)
    assert "<" not in out and ">" not in out
    assert "  " not in out


def test_snippet_handles_empty_input():
    assert _clean_snippet("", 25) == ""
