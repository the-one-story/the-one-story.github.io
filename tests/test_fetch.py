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


# --------------------------------------------------------------------------- #
# Affiliate commerce (added 28/11/2026)                                        #
# --------------------------------------------------------------------------- #
# One Story led with "All the best Walmart Black Friday deals to shop this
# weekend": a cluster of eleven articles held together by the phrase "Black
# Friday", five of them NBC Select shopping posts. These pin the URL rule that
# drops that desk, and - just as important - the news stories ABOUT retail that
# must survive it, since a title-word rule was tried first and ate them.
@pytest.mark.parametrize("url", [
    "https://www.nbcnews.com/select/shopping/walmart-black-friday-deals-2026-rcna611473",
    "https://www.nbcnews.com/select/shopping/best-black-friday-tv-deals-2026-rcna611453",
    "https://www.foxnews.com/deals/kate-spade-outlet-handbags-73-off",
    "https://example.com/gift-guide/music-lovers",
    "https://example.com/reviews/best-mattresses-2026",
])
def test_affiliate_commerce_is_dropped(url):
    assert is_noise_format(url, "Some product is on sale") is True


@pytest.mark.parametrize("url,title", [
    # Real reporting about the retail event. These share the commerce
    # vocabulary and must stay in the pool.
    ("https://www.nbcnews.com/news/us-news/black-friday-shoppers-head-brick-mortar-stores-us-rcna611564",
     "Black Friday shoppers head to brick-and-mortar stores across the U.S."),
    ("https://www.theguardian.com/world/2026/nov/27/bbl-adverts",
     "Black Friday deals for liquid Brazilian butt lifts criticised over safety"),
    ("https://www.afr.com/companies/retail/black-friday-fizzles",
     "Australia's $450b retail sector's reckoning as Black Friday fizzles"),
    ("https://www.commondreams.org/news/first-amazon-collective-bargaining-agreement",
     "'Historic Breakthrough' for Amazon Warehouse Workers Celebrated on Black Friday"),
    # "deal" is diplomatic far more often than commercial.
    ("https://example.com/world/iran", "US signs landmark nuclear deal with Saudi Arabia"),
    ("https://example.com/world/venezuela", "US, Venezuela announce 'historic' oil deal"),
])
def test_news_about_commerce_survives(url, title):
    assert is_noise_format(url, title) is False


def test_photo_galleries_are_dropped_by_title():
    # AP's gallery arrived through the Google News proxy, where the real path is
    # unreachable, so only the title could catch it - and "in pictures" was
    # listed while "in photos" was not.
    assert is_noise_format(
        "https://news.google.com/rss/articles/CBMiswFBVV95cUxOcHYtYzBER0Fu",
        "Black Friday's annual hunt for holiday deals, in photos") is True


# --------------------------------------------------------------------------- #
# Pool de-duplication (added 28/11/2026)                                       #
# --------------------------------------------------------------------------- #
def test_the_same_url_is_fetched_once(monkeypatch):
    """500 duplicated entries sat in the archive across 128 of 129 days.

    They never reached the outlet count, which is distinct SOURCES, so nothing
    on the page revealed them - but inside a cluster the article was counted
    twice, pulling the centroid time and the TF-IDF weights with it.
    """
    import time
    import fetch as fetch_mod

    now = time.gmtime()
    entry = {"title": "One story, carried twice",
             "link": "https://example.com/news/the-one-story",
             "summary": "Body text.", "published_parsed": now}
    other = {"title": "A different story",
             "link": "https://example.com/news/another",
             "summary": "Body text.", "published_parsed": now}
    # Same URL arriving from two feeds, plus a repeat inside one feed.
    monkeypatch.setattr(fetch_mod, "_fetch_one", lambda cfg: [entry, entry, other])

    feeds = [{"name": "Feed A", "country": "US", "lean": "centre", "url": "a"},
             {"name": "Feed B", "country": "GB", "lean": "centre", "url": "b"}]
    settings = {"window_hours": 24, "snippet_cap_words": 25,
                "fetch_timeout_secs": 5, "timezone": "Australia/Sydney"}

    articles, report = fetch_mod.fetch_all(settings, feeds)
    urls = [a["url"] for a in articles]
    assert len(urls) == len(set(urls)), "a URL reached the pool twice"
    assert len(articles) == 2
    assert report["dropped_duplicate"] == 4
