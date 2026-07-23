"""Weight-tuning replay tool.

Once data/history/ has accumulated a few days (run.py logs one snapshot per
day), use this to see how a different set of scoring weights WOULD have chosen,
without waiting for live days:

    python replay.py                         # replay under current settings
    python replay.py --diversity 1.2         # override one weight
    python replay.py --recency 1.2 --coverage 0.8

For each archived day it rebuilds the clusters from the logged articles and
re-scores them under the chosen weights, then prints the recorded winner next
to the replayed winner and flags where they differ.

Note: the novelty term is date/ledger-dependent and is NOT reconstructed here
(replay uses an empty ledger), so this is for tuning coverage/diversity/recency.
"""
from __future__ import annotations

import argparse
import glob
import os

from cluster import build_clusters
from common import load_feeds, load_settings, rel
from rank import score_clusters

import json


def _load_history() -> list[dict]:
    days = []
    for path in sorted(glob.glob(rel("data/history/*.json"))):
        with open(path, "r", encoding="utf-8") as fh:
            days.append(json.load(fh))
    return days


def main() -> int:
    settings = load_settings()
    feeds = load_feeds()

    ap = argparse.ArgumentParser()
    for w in ("coverage", "diversity", "recency", "novelty"):
        ap.add_argument(f"--{w}", type=float, default=settings["weights"][w])
    args = ap.parse_args()
    new_weights = {w: getattr(args, w) for w in
                   ("coverage", "diversity", "recency", "novelty")}
    settings = {**settings, "weights": new_weights}

    days = _load_history()
    if not days:
        print("No history yet - run.py logs a snapshot per day into "
              "data/history/. Come back after a few days.")
        return 1

    print(f"Replaying {len(days)} day(s) under weights: {new_weights}\n")
    print(f"{'date':<12}{'chg':<5}{'recorded winner':<42}replayed winner")
    print("-" * 100)
    changed = 0
    for day in days:
        clusters = build_clusters(day["articles"], settings)
        # Empty ledger -> novelty neutral; we are tuning the other three terms.
        scored = score_clusters(clusters, settings, feeds, day["run_time"], [])
        replayed = scored[0]["hero"]["title"] if scored else "-"
        recorded = day["winner"]["title"]
        diff = replayed.strip()[:40] != recorded.strip()[:40]
        changed += diff
        print(f"{day['run_date']:<12}{'*' if diff else '':<5}"
              f"{recorded[:40]:<42}{replayed[:44]}")
    print("-" * 100)
    print(f"{changed}/{len(days)} winners would change under these weights.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
