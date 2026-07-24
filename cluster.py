"""Stage 2 - CLUSTER.

Group articles covering the same story.

v1 method ("connected_components"): TF-IDF over (title + snippet), cosine
similarity, then join any two articles whose cosine >= settings.similarity_threshold
into the same cluster (transitively, via union-find). This matches the plain-English
rule in settings.yaml and is fully deterministic given the fetched data.

The clustering function is swappable: add a new function and register it in
CLUSTER_METHODS, then set the method name where cluster_articles is called.

Per cluster we compute the facts the SCORE stage needs:
    outlets    - distinct source count
    countries  - set of distinct country codes
    leans      - set of distinct outlet leans
    centroid_time - mean member publish time (ISO-8601 UTC)
    members    - the member articles (kept whole for render)
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime, timezone

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from common import load_settings, read_json, write_json


# --------------------------------------------------------------------------- #
# Clustering methods (swappable)                                              #
# --------------------------------------------------------------------------- #
def _connected_components(sim, threshold: float) -> list[int]:
    """Union-find over the thresholded cosine-similarity matrix -> labels."""
    n = sim.shape[0]
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)  # deterministic: lower index wins

    for i in range(n):
        # sim is symmetric; only need j > i
        row = sim[i]
        for j in range(i + 1, n):
            if row[j] >= threshold:
                union(i, j)

    roots = [find(i) for i in range(n)]
    # Relabel roots to compact 0..k-1 in order of first appearance (deterministic).
    remap: dict[int, int] = {}
    labels = []
    for r in roots:
        if r not in remap:
            remap[r] = len(remap)
        labels.append(remap[r])
    return labels


def _agglomerative(sim, threshold: float) -> list[int]:
    """Average-linkage agglomerative clustering on cosine distance.

    Unlike single-linkage union-find, this only merges two groups when their
    AVERAGE similarity is high enough, so a broad article (e.g. an oil-price
    story that mentions both Iran and the stock market) can't chain two
    unrelated stories together. `threshold` is the cosine-DISTANCE cut
    (1 - similarity); larger = more permissive merging.
    """
    import numpy as np
    from sklearn.cluster import AgglomerativeClustering

    dist = np.clip(1.0 - sim, 0.0, 2.0)
    np.fill_diagonal(dist, 0.0)
    ac = AgglomerativeClustering(
        metric="precomputed", linkage="average",
        distance_threshold=threshold, n_clusters=None,
    )
    return ac.fit_predict(dist).tolist()


def cluster_labels(articles: list[dict], settings: dict,
                   method: str | None = None) -> list[int]:
    """Return a cluster label per article using the configured method."""
    method = method or settings.get("cluster_method", "agglomerative")
    texts = [f"{a['title']} {a.get('snippet', '')}".strip() for a in articles]
    vec = TfidfVectorizer(
        stop_words="english",
        min_df=settings["min_df"],
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    tfidf = vec.fit_transform(texts)
    sim = linear_kernel(tfidf)  # rows are L2-normalised -> dot == cosine

    if method == "agglomerative":
        threshold = settings.get("cluster_distance_threshold", 0.92)
    else:
        threshold = settings["similarity_threshold"]
    return CLUSTER_METHODS[method](sim, threshold)


CLUSTER_METHODS = {
    "connected_components": _connected_components,
    "agglomerative": _agglomerative,
}


# --------------------------------------------------------------------------- #
# Cluster assembly                                                            #
# --------------------------------------------------------------------------- #
def _centroid_time(members: list[dict]) -> str:
    epochs = [
        datetime.fromisoformat(m["published_at"]).timestamp() for m in members
    ]
    mean = sum(epochs) / len(epochs)
    return datetime.fromtimestamp(mean, tz=timezone.utc).isoformat()


def build_clusters(articles: list[dict], settings: dict,
                   method: str | None = None) -> list[dict]:
    labels = cluster_labels(articles, settings, method)

    groups: dict[int, list[dict]] = {}
    for label, art in zip(labels, articles):
        groups.setdefault(label, []).append(art)

    clusters = []
    for label, members in groups.items():
        outlets = sorted({m["source"] for m in members})
        countries = sorted({m["country"] for m in members})
        leans = sorted({m["lean"] for m in members})
        clusters.append({
            "id": label,
            "size": len(members),
            "outlets": outlets,
            "outlet_count": len(outlets),
            "countries": countries,
            "leans": leans,
            "centroid_time": _centroid_time(members),
            "members": members,
        })

    # Deterministic order: most outlets, then most members, then earliest title.
    clusters.sort(
        key=lambda c: (-c["outlet_count"], -c["size"], c["members"][0]["title"])
    )
    for rank, c in enumerate(clusters):
        c["rank_by_outlets"] = rank
    return clusters


def _print_report(clusters: list[dict], n_articles: int) -> None:
    print("=" * 70)
    print("STAGE 2 - CLUSTER")
    print("=" * 70)
    sizes = Counter(c["size"] for c in clusters)
    multi = [c for c in clusters if c["size"] > 1]
    print(f"Articles in         : {n_articles}")
    print(f"Clusters out        : {len(clusters)}")
    print(f"  multi-article      : {len(multi)}")
    print(f"  singletons         : {len(clusters) - len(multi)}")
    biggest = clusters[0]["size"] if clusters else 0
    print(f"Largest cluster size: {biggest}")
    print(f"Size distribution   : "
          f"{dict(sorted(sizes.items(), key=lambda kv: -kv[0]))}")
    print("-" * 70)
    print("Top 12 clusters by distinct-outlet count:")
    print(f"{'#':>2} {'outl':>4} {'size':>4}  {'countries':<20}{'leans':<28}headline")
    for c in clusters[:12]:
        countries = ",".join(c["countries"])
        leans = ",".join(c["leans"])
        head = c["members"][0]["title"][:52]
        print(f"{c['rank_by_outlets']:>2} {c['outlet_count']:>4} {c['size']:>4}  "
              f"{countries:<20}{leans:<28}{head}")
    print("-" * 70)
    print("Member outlets of the top cluster:")
    if clusters:
        for m in clusters[0]["members"][:12]:
            print(f"  [{m['country']:>3}/{m['lean']:<12}] {m['source']:<26} "
                  f"{m['title'][:44]}")


def main() -> int:
    settings = load_settings()
    data = read_json("data/articles.json")
    if not data or not data["articles"]:
        print("No articles to cluster - run fetch.py first.")
        return 1
    articles = data["articles"]
    clusters = build_clusters(articles, settings)
    _print_report(clusters, len(articles))
    path = write_json("data/clusters.json",
                      {"run_time": data["report"]["run_time"],
                       "clusters": clusters})
    print(f"\nWrote {len(clusters)} clusters -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
