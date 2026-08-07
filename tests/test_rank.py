"""The scoring maths and hero choice - the decisions that ARE the product.

These are pure deterministic functions, so they can be pinned exactly. The
diversity term gets the most attention on purpose: it is the anti-volume-bias
mechanism, and the most likely thing to quietly regress into "whatever the most
outlets covered".
"""
from __future__ import annotations

import math

import pytest

import rank
from conftest import article


# --------------------------------------------------------------------------- #
# Component terms                                                             #
# --------------------------------------------------------------------------- #
def test_coverage_is_log_scaled_not_linear():
    """20 outlets must not be worth twice 10 - the claim the site makes."""
    ten = rank._coverage(10, 20)
    twenty = rank._coverage(20, 20)
    assert twenty == pytest.approx(1.0)
    # log1p(10)/log1p(20) ~ 0.787, i.e. 10 outlets already buys ~79% of the term.
    assert ten == pytest.approx(math.log1p(10) / math.log1p(20))
    assert 1.2 < twenty / ten < 1.35, "log scaling collapsed toward linear"


def test_coverage_handles_degenerate_maximum():
    assert rank._coverage(1, 1) == pytest.approx(1.0)
    assert rank._coverage(0, 0) == pytest.approx(0.0)


def test_diversity_is_a_weighted_geometric_mean():
    """Spread across BOTH axes must beat being maximal on one and minimal on
    the other - that is the whole point of a geometric mean."""
    both = rank._diversity(["A", "B"], ["l", "r"], 4, 4, 0.5, 0.5)
    one_axis = rank._diversity(["A", "B", "C", "D"], ["l"], 4, 4, 0.5, 0.5)
    assert both > one_axis
    assert both == pytest.approx(math.sqrt(0.5) * math.sqrt(0.5))


def test_diversity_stays_in_unit_interval():
    assert rank._diversity([], [], 5, 5, 0.5, 0.5) > 0.0     # never zero -> never kills the product
    assert rank._diversity(["a"] * 9, ["l"] * 9, 5, 5, 0.5, 0.5) <= 1.0


def test_diversity_rewards_breadth_monotonically():
    prev = 0.0
    for n in range(1, 6):
        cur = rank._diversity([str(i) for i in range(n)], ["centre"], 5, 5, 0.5, 0.5)
        assert cur > prev
        prev = cur


def test_recency_halves_at_the_half_life():
    from datetime import datetime, timedelta, timezone
    now = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
    at_half_life = (now - timedelta(hours=10)).isoformat()
    assert rank._recency(at_half_life, now, 10) == pytest.approx(0.5)
    assert rank._recency(now.isoformat(), now, 10) == pytest.approx(1.0)
    # future timestamps must not score above 1
    future = (now + timedelta(hours=5)).isoformat()
    assert rank._recency(future, now, 10) == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# Novelty                                                                     #
# --------------------------------------------------------------------------- #
def _cluster(titles):
    return {"members": [article(t) for t in titles]}


def test_novelty_is_neutral_with_an_empty_ledger(settings):
    out = rank._novelty_penalties([_cluster(["Flood hits city"])], [], 739_000, settings)
    assert out[0]["penalty"] == 1.0
    assert out[0]["matched_date"] is None


def test_novelty_penalises_a_story_that_led_yesterday(settings):
    from datetime import datetime
    run_ord = datetime.fromisoformat("2026-08-02T00:00:00").toordinal()
    ledger = [{"date": "2026-08-01", "text": "Cyclone Mara batters the Queensland coast"}]
    out = rank._novelty_penalties(
        [_cluster(["Cyclone Mara batters the Queensland coast overnight"])],
        ledger, run_ord, settings)
    assert out[0]["matched_date"] == "2026-08-01"
    assert out[0]["penalty"] < 1.0


def test_novelty_ignores_todays_own_entry(settings):
    """A same-day re-run must never self-penalise (age 0 is skipped)."""
    from datetime import datetime
    run_ord = datetime.fromisoformat("2026-08-01T00:00:00").toordinal()
    ledger = [{"date": "2026-08-01", "text": "Cyclone Mara batters the Queensland coast"}]
    out = rank._novelty_penalties(
        [_cluster(["Cyclone Mara batters the Queensland coast overnight"])],
        ledger, run_ord, settings)
    assert out[0]["penalty"] == 1.0


def test_novelty_lapses_past_the_decay_window(settings):
    from datetime import datetime
    decay = settings["scoring"]["novelty_decay_days"]
    run_ord = datetime.fromisoformat("2026-08-20T00:00:00").toordinal()
    ledger = [{"date": "2026-08-01", "text": "Cyclone Mara batters the Queensland coast"}]
    out = rank._novelty_penalties(
        [_cluster(["Cyclone Mara batters the Queensland coast overnight"])],
        ledger, run_ord, settings)
    assert out[0]["penalty"] == 1.0, f"penalty outlived novelty_decay_days={decay}"


def test_strongest_realised_novelty_penalty_is_not_the_floor(settings):
    """Documents a real quirk: `novelty_penalty_floor` is unreachable, because
    only PRIOR days penalise (age >= 1). The strongest penalty actually
    achievable is a yesterday-lead. Pinned so the constant is not "fixed" to
    mean something else without the behaviour being reconsidered."""
    sc = settings["scoring"]
    floor, decay = sc["novelty_penalty_floor"], sc["novelty_decay_days"]
    strongest = floor + (1.0 - floor) * (1 / decay)
    assert strongest > floor
    from datetime import datetime
    run_ord = datetime.fromisoformat("2026-08-02T00:00:00").toordinal()
    ledger = [{"date": "2026-08-01", "text": "Cyclone Mara batters the Queensland coast"}]
    out = rank._novelty_penalties(
        [_cluster(["Cyclone Mara batters the Queensland coast overnight"])],
        ledger, run_ord, settings)
    assert out[0]["penalty"] == pytest.approx(strongest, abs=1e-9)


# --------------------------------------------------------------------------- #
# End-to-end scoring                                                          #
# --------------------------------------------------------------------------- #
def _scored(settings, feeds, clusters, run_time="2026-08-01T12:00:00+00:00"):
    return rank.score_clusters(clusters, settings, feeds, run_time, [])


def _raw_cluster(cid, titles, countries, leans, outlets, when):
    members = [article(t, country=countries[i % len(countries)],
                       lean=leans[i % len(leans)],
                       source=f"Outlet {i}", published_at=when)
               for i, t in enumerate(titles)]
    return {"id": cid, "size": len(members), "outlets": outlets,
            "outlet_count": len(outlets), "countries": countries,
            "leans": leans, "centroid_time": when, "members": members}


def test_diversity_beats_raw_volume(settings, feeds):
    """THE anti-volume-bias guarantee: a story running loud in one country and
    one lean must lose to a smaller but globally spread story."""
    when = "2026-08-01T12:00:00+00:00"
    loud = _raw_cluster(1, [f"Domestic row rumbles on {i}" for i in range(14)],
                        ["US"], ["right"], [f"US Outlet {i}" for i in range(14)], when)
    broad = _raw_cluster(2, [f"Treaty signed in Geneva {i}" for i in range(8)],
                         ["US", "GB", "FR", "DE", "IN", "JP", "BR", "ZA"],
                         ["left", "centre-left", "centre", "centre-right", "right"],
                         [f"World Outlet {i}" for i in range(8)], when)
    ranked = _scored(settings, feeds, [loud, broad])
    assert ranked[0]["id"] == 2, (
        "a single-country single-lean story outscored a globally spread one - "
        "the diversity term has regressed")
    assert ranked[0]["components"]["diversity"] > ranked[1]["components"]["diversity"]


def test_a_winner_is_always_forced(settings, feeds):
    """Even one lonely article must yield a page - never an empty state."""
    when = "2026-08-01T12:00:00+00:00"
    ranked = _scored(settings, feeds,
                     [_raw_cluster(1, ["Only story today"], ["AU"], ["centre"], ["ABC"], when)])
    assert len(ranked) == 1 and ranked[0]["rank"] == 0
    assert ranked[0]["score"] > 0


def test_scoring_is_deterministic(settings, feeds):
    when = "2026-08-01T12:00:00+00:00"
    build = lambda: [
        _raw_cluster(1, ["Alpha event unfolds"], ["US"], ["centre"], ["A"], when),
        _raw_cluster(2, ["Beta event unfolds"], ["GB", "FR"], ["left", "right"], ["B", "C"], when),
    ]
    first = [(c["id"], round(c["score"], 12)) for c in _scored(settings, feeds, build())]
    second = [(c["id"], round(c["score"], 12)) for c in _scored(settings, feeds, build())]
    assert first == second


def test_ties_break_deterministically_not_by_dict_order(settings, feeds):
    when = "2026-08-01T12:00:00+00:00"
    a = _raw_cluster(1, ["Zebra story"], ["US"], ["centre"], ["A"], when)
    b = _raw_cluster(2, ["Antelope story"], ["US"], ["centre"], ["B"], when)
    assert [c["id"] for c in _scored(settings, feeds, [a, b])] == \
           [c["id"] for c in _scored(settings, feeds, [b, a])]


# --------------------------------------------------------------------------- #
# Hero selection                                                              #
# --------------------------------------------------------------------------- #
def test_hero_skips_noise_formats():
    members = [
        article("Live updates: the summit as it happened", source="Reuters"),
        article("Leaders sign the summit accord", source="Reuters"),
    ]
    assert rank.choose_hero(members)["title"] == "Leaders sign the summit accord"


def test_hero_prefers_free_over_paywalled():
    members = [
        article("Summit accord signed", source="Reuters", paywall="hard"),
        article("Summit accord signed in Geneva", source="Reuters", paywall="none"),
    ]
    assert rank.choose_hero(members)["paywall"] == "none"


def test_hero_prefers_a_tier1_desk():
    members = [
        article("Summit accord signed", source="Some Regional Paper"),
        article("Summit accord signed today", source="BBC News - World"),
    ]
    assert rank.choose_hero(members)["source"] == "BBC News - World"


def test_hero_must_be_on_topic_for_its_cluster():
    """Regression: on 31/07 a 27-member FIFA-stake-sale cluster heroed a
    tangential 'FIFA charges Argentina' piece purely because it was an early
    tier-1 direct link, so the featured headline misdescribed the story."""
    members = [article(f"UEFA to boycott World Cup over FIFA stake sale plan {i}",
                       source="Reuters", url=f"https://r.com/{i}") for i in range(8)]
    # tier-1, direct link, earliest - wins on every OLD criterion, but off-topic
    members.append(article("FIFA charges Argentina over scuffle at the final",
                           source="BBC News - World", url="https://bbc.co.uk/x",
                           published_at="2020-01-01T00:00:00+00:00"))
    hero = rank.choose_hero(members)
    assert "boycott" in hero["title"].lower(), \
        "an off-topic member became the hero again"


def test_offtopic_guard_is_inert_on_small_clusters():
    """Below the member threshold the median is too noisy to trust, so the
    guard must not fire at all."""
    members = [article("A"), article("B"), article("C")]
    assert rank._offtopic_flags(members) == [False, False, False]


def test_offtopic_guard_survives_degenerate_vocabulary():
    members = [article("the and of") for _ in range(6)]
    assert rank._offtopic_flags(members) == [False] * 6
