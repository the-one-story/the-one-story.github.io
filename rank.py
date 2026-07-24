"""Stage 3 - SCORE (fully deterministic, no LLM).

    score = coverage^wc * diversity^wd * recency^wr * novelty^wn

Each component is normalised to (0, 1] so the weights (exponents in settings)
are directly comparable and the product behaves like a soft AND:

  coverage  = log-scaled distinct-outlet count, normalised by the day's max.
              Log dampens runaway raw volume.
  diversity = weighted geometric mean of (distinct countries / all countries)
              and (distinct leans / all leans). THE key term: a story spread
              across many countries AND both political leans beats one running
              loud in a single national press. Weight configurable.
  recency   = exponential decay on the cluster's centroid publish time
              (half-life in settings). Favours coverage still building now.
  novelty   = penalty in [floor, 1] if the cluster matches a story that led on
              a recent prior day (cosine vs the decay ledger). Decays back to
              1.0 over novelty_decay_days, so a day-two story needs genuinely
              new coverage to hold the top slot.

A single winner is ALWAYS forced (highest score) - never a quiet-day empty
state. The full ranked table (winner + runners-up + component scores) is
emitted to data/ranked.json for the render step.
"""
from __future__ import annotations

import math
import sys
from datetime import datetime, timezone

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from cluster import build_clusters
from common import load_feeds, load_settings, read_json, write_json
from fetch import is_noise_format
from ledger import load_ledger


# --------------------------------------------------------------------------- #
# Component terms                                                             #
# --------------------------------------------------------------------------- #
def _coverage(outlet_count: int, max_outlet_count: int) -> float:
    denom = math.log1p(max(max_outlet_count, 1))
    return math.log1p(outlet_count) / denom if denom else 1.0


def _diversity(countries: list, leans: list, n_countries: int, n_leans: int,
               country_share: float, lean_share: float) -> float:
    c = len(countries) / n_countries if n_countries else 0.0
    l = len(leans) / n_leans if n_leans else 0.0
    c = min(max(c, 1e-9), 1.0)
    l = min(max(l, 1e-9), 1.0)
    return (c ** country_share) * (l ** lean_share)


def _recency(centroid_iso: str, now_utc: datetime, half_life_hours: float) -> float:
    age_h = (now_utc - datetime.fromisoformat(centroid_iso)).total_seconds() / 3600.0
    age_h = max(age_h, 0.0)
    return 0.5 ** (age_h / half_life_hours)


def _novelty_penalties(clusters: list[dict], ledger: list[dict],
                       run_date_ord: int, settings: dict) -> list[dict]:
    """Return per-cluster novelty {penalty, matched_date, cosine}.

    Cosine is computed in a single shared TF-IDF space over today's cluster
    texts plus each prior lead's stored text, so it is reproducible.
    """
    sc = settings["scoring"]
    floor = sc["novelty_penalty_floor"]
    decay_days = sc["novelty_decay_days"]
    match_thr = sc["novelty_match_threshold"]

    n = len(clusters)
    out = [{"penalty": 1.0, "matched_date": None, "cosine": 0.0} for _ in range(n)]
    if not ledger:
        return out

    cluster_texts = [
        " ".join(dict.fromkeys(m["title"] for m in c["members"])) for c in clusters
    ]
    prior_texts = [e["text"] for e in ledger]
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    tfidf = vec.fit_transform(cluster_texts + prior_texts)
    today_m = tfidf[:n]
    prior_m = tfidf[n:]
    sims = linear_kernel(today_m, prior_m)  # n x len(ledger)

    for i in range(n):
        best_pen, best_date, best_cos = 1.0, None, 0.0
        for j, entry in enumerate(ledger):
            cos = float(sims[i, j])
            if cos < match_thr:
                continue
            age_days = run_date_ord - datetime.fromisoformat(
                entry["date"] + "T00:00:00").toordinal()
            # Only PRIOR days penalise. Skip today's own entry (age 0) so a
            # same-day re-run never self-penalises, and skip leads older than
            # the decay window (penalty has fully lapsed).
            if age_days < 1 or age_days >= decay_days:
                continue
            # Strongest (lowest) penalty for the most recent prior lead,
            # decaying linearly back to 1.0 over decay_days.
            frac = max(age_days, 0) / decay_days
            pen = floor + (1.0 - floor) * frac
            if pen < best_pen:
                best_pen, best_date, best_cos = pen, entry["date"], cos
        out[i] = {"penalty": best_pen, "matched_date": best_date, "cosine": best_cos}
    return out


# --------------------------------------------------------------------------- #
# Hero selection                                                              #
# --------------------------------------------------------------------------- #
_LEAN_RANK = {"centre": 0, "centre-left": 1, "centre-right": 1, "left": 2, "right": 2}
_PAYWALL_RANK = {"none": 0, "soft": 1, "hard": 2}

# Established general-audience international desks - preferred for the hero link
# (the featured "fullest account"). Not used for scoring/coverage, only to pick
# which single article to feature, so it isn't a regional/state-owned outlet.
_HERO_TIER1 = {
    "Reuters", "Associated Press", "Agence France-Presse", "BBC News - World",
    "The Guardian - World", "Al Jazeera English", "NPR News (US)",
    "Deutsche Welle", "France 24", "Channel News Asia (Singapore)",
    "NBC News (US)", "ABC News (AU) - Top Stories",
}


def _is_gnews(url: str) -> bool:
    return "news.google.com" in url


def choose_hero(members: list[dict]) -> dict:
    """Best single write-up. Preference order: a straight article (never a
    podcast/liveblog/roundup), freely readable, from an established
    international desk, with a clean link, neutral lean, earliest to cover."""
    return sorted(
        members,
        key=lambda m: (is_noise_format(m["url"], m["title"]),
                       _PAYWALL_RANK.get(m.get("paywall", "none"), 0),
                       m["source"] not in _HERO_TIER1,
                       _is_gnews(m["url"]),
                       _LEAN_RANK.get(m["lean"], 2),
                       m["published_at"]),
    )[0]


# --------------------------------------------------------------------------- #
# Scoring                                                                     #
# --------------------------------------------------------------------------- #
def score_clusters(clusters: list[dict], settings: dict, feeds: list[dict],
                   run_time_iso: str, ledger: list[dict]) -> list[dict]:
    w = settings["weights"]
    sc = settings["scoring"]
    n_countries = len({f["country"] for f in feeds})
    n_leans = len({f["lean"] for f in feeds})
    max_outlets = max((c["outlet_count"] for c in clusters), default=1)
    now_utc = datetime.fromisoformat(run_time_iso).astimezone(timezone.utc)
    run_date_ord = datetime.fromisoformat(run_time_iso).toordinal()

    novelty = _novelty_penalties(clusters, ledger, run_date_ord, settings)

    scored = []
    for c, nov in zip(clusters, novelty):
        cov = _coverage(c["outlet_count"], max_outlets)
        div = _diversity(c["countries"], c["leans"], n_countries, n_leans,
                         sc["country_share"], sc["lean_share"])
        rec = _recency(c["centroid_time"], now_utc, sc["recency_half_life_hours"])
        nov_pen = nov["penalty"]
        total = (cov ** w["coverage"]) * (div ** w["diversity"]) \
            * (rec ** w["recency"]) * (nov_pen ** w["novelty"])
        hero = choose_hero(c["members"])
        scored.append({
            **c,
            "hero": hero,
            "components": {
                "coverage": round(cov, 4),
                "diversity": round(div, 4),
                "recency": round(rec, 4),
                "novelty": round(nov_pen, 4),
            },
            "novelty_match": {"date": nov["matched_date"],
                              "cosine": round(nov["cosine"], 3)},
            "score": total,
        })

    # Deterministic tie-break: score, then outlet count, then earliest headline.
    scored.sort(key=lambda c: (-c["score"], -c["outlet_count"],
                               c["members"][0]["title"]))
    for rank, c in enumerate(scored):
        c["rank"] = rank
    return scored


def _print_report(scored: list[dict]) -> None:
    print("=" * 74)
    print("STAGE 3 - SCORE")
    print("=" * 74)
    print(f"{'#':>2} {'score':>7} {'cov':>5} {'div':>5} {'rec':>5} {'nov':>5} "
          f"{'out':>3} {'cty':>3} {'ln':>3}  headline")
    for c in scored[:12]:
        k = c["components"]
        print(f"{c['rank']:>2} {c['score']:>7.4f} {k['coverage']:>5.2f} "
              f"{k['diversity']:>5.2f} {k['recency']:>5.2f} {k['novelty']:>5.2f} "
              f"{c['outlet_count']:>3} {len(c['countries']):>3} {len(c['leans']):>3}  "
              f"{c['members'][0]['title'][:44]}")
    print("-" * 74)
    win = scored[0]
    print("WINNER:")
    print(f"  {win['members'][0]['title']}")
    print(f"  score={win['score']:.4f}  outlets={win['outlet_count']}  "
          f"countries={','.join(win['countries'])}  leans={','.join(win['leans'])}")
    print(f"  components={win['components']}")
    print(f"  hero -> [{win['hero']['source']}] {win['hero']['url'][:70]}")
    if win["novelty_match"]["date"]:
        print(f"  novelty: matched prior lead {win['novelty_match']['date']} "
              f"(cosine {win['novelty_match']['cosine']})")


def main() -> int:
    settings = load_settings()
    feeds = load_feeds()
    data = read_json("data/articles.json")
    if not data or not data["articles"]:
        print("No articles - run fetch.py first.")
        return 1
    clusters = build_clusters(data["articles"], settings)
    ledger = load_ledger(settings)
    scored = score_clusters(clusters, settings, feeds,
                            data["report"]["run_time"], ledger)
    _print_report(scored)
    ranked = build_ranked_table(scored, settings, data["report"])
    path = write_json(settings["ranked_json_path"], ranked)
    print(f"\nWrote ranked table -> {path}")
    return 0


def build_ranked_table(scored: list[dict], settings: dict,
                       feeds_report: dict, keep_runners: int = 5) -> dict:
    """Assemble the lean ranked blob the render step consumes.

    Full member lists are dropped on losers to keep the blob small; the winner
    keeps its members (render shows the headline from them).
    """
    return {
        "run_time": feeds_report["run_time"],
        "window_hours": settings["window_hours"],
        "timezone": settings["timezone"],
        "update_hour_utc": settings["update_hour_utc"],
        "buttondown_username": (settings.get("newsletter") or {}).get(
            "buttondown_username", ""),
        "winner": scored[0],
        "runners_up": [
            {k: v for k, v in c.items() if k != "members"}
            for c in scored[1:1 + keep_runners]
        ],
        "feeds_report": feeds_report,
    }


if __name__ == "__main__":
    sys.exit(main())
