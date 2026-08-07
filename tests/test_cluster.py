"""Clustering: the same event told three ways is ONE story; different events
are not. Get this wrong and the coverage/diversity counts - and therefore the
whole ranking - are measuring the wrong thing.
"""
from __future__ import annotations

from cluster import build_clusters
from conftest import article


def _labels_of(clusters, needle):
    """Which cluster id holds the article whose title contains `needle`?"""
    for c in clusters:
        for m in c["members"]:
            if needle.lower() in m["title"].lower():
                return c["id"]
    raise AssertionError(f"no cluster contains {needle!r}")


def test_same_event_worded_differently_collapses_to_one_cluster(settings):
    articles = [
        article("Cyclone Mara batters the Queensland coast",
                source="ABC", country="AU", snippet="Thousands evacuated as Cyclone Mara made landfall in Queensland."),
        article("Queensland coast hit as Cyclone Mara makes landfall",
                source="Reuters", country="INT", snippet="Cyclone Mara struck the Queensland coast, forcing evacuations."),
        article("Thousands flee Cyclone Mara in Queensland",
                source="BBC News - World", country="GB", snippet="Cyclone Mara forced thousands to evacuate the Queensland coast."),
    ]
    clusters = build_clusters(articles, settings)
    assert len(clusters) == 1, [c["outlet_count"] for c in clusters]
    assert clusters[0]["outlet_count"] == 3
    assert set(clusters[0]["countries"]) == {"AU", "INT", "GB"}


def test_unrelated_events_do_not_merge(settings):
    articles = [
        article("Cyclone Mara batters the Queensland coast", source="ABC", country="AU",
                snippet="Thousands evacuated as Cyclone Mara made landfall in Queensland."),
        article("Central bank raises interest rates by 25 basis points",
                source="Reuters", country="INT",
                snippet="The central bank lifted its benchmark rate to curb inflation."),
    ]
    clusters = build_clusters(articles, settings)
    assert len(clusters) == 2
    assert _labels_of(clusters, "Cyclone") != _labels_of(clusters, "interest rates")


def test_cluster_facts_are_deduped_sets(settings):
    """outlet_count counts DISTINCT outlets - two pieces from one paper is one
    outlet, otherwise a prolific publisher inflates coverage."""
    articles = [
        article("Cyclone Mara batters the Queensland coast", source="ABC", country="AU",
                lean="centre", snippet="Cyclone Mara made landfall in Queensland."),
        article("Cyclone Mara: Queensland coast battered overnight", source="ABC",
                country="AU", lean="centre", snippet="Cyclone Mara hit the Queensland coast overnight."),
    ]
    clusters = build_clusters(articles, settings)
    assert len(clusters) == 1
    assert clusters[0]["size"] == 2
    assert clusters[0]["outlet_count"] == 1
    assert clusters[0]["countries"] == ["AU"]


def test_clustering_is_deterministic(settings):
    articles = [
        article("Cyclone Mara batters the Queensland coast", source="ABC", country="AU",
                snippet="Cyclone Mara made landfall in Queensland."),
        article("Queensland hit as Cyclone Mara makes landfall", source="Reuters",
                country="INT", snippet="Cyclone Mara struck Queensland."),
        article("Central bank raises rates", source="AFP", country="INT",
                snippet="The central bank lifted its benchmark rate."),
    ]
    shape = lambda cs: sorted(sorted(m["title"] for m in c["members"]) for c in cs)
    assert shape(build_clusters(articles, settings)) == \
           shape(build_clusters(list(reversed(articles)), settings))


def test_single_article_still_forms_a_cluster(settings):
    clusters = build_clusters([article("Only story today", snippet="A thing happened.")], settings)
    assert len(clusters) == 1 and clusters[0]["size"] == 1
