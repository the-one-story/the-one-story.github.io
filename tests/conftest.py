"""Shared fixtures for the pipeline tests.

Everything here is offline and deterministic - no feeds are fetched, no clock is
read, no file in the repo is written. `isolated_root` redirects common.ROOT at a
tmp dir so anything that writes state (the ledger) cannot touch real data/.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import common  # noqa: E402


@pytest.fixture
def settings():
    """The REAL settings, so a config change that breaks scoring shows up here."""
    return common.load_settings()


@pytest.fixture
def feeds():
    return common.load_feeds()


@pytest.fixture
def isolated_root(tmp_path, monkeypatch):
    """Point common's path helpers at a tmp dir (keeps tests off real data/)."""
    monkeypatch.setattr(common, "ROOT", str(tmp_path))
    return tmp_path


def article(title, *, source="Reuters", country="INT", lean="centre",
            paywall="none", url=None, published_at="2026-08-01T00:00:00+00:00",
            snippet=""):
    """One normalised article, matching what fetch.py emits."""
    return {
        "title": title,
        "source": source,
        "country": country,
        "lean": lean,
        "paywall": paywall,
        "url": url if url is not None else f"https://example.com/{abs(hash(title))}",
        "published_at": published_at,
        "snippet": snippet,
    }


@pytest.fixture
def make_article():
    return article
