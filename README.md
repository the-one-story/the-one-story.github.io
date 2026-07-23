# One Story

**Live: https://the-one-story.github.io/**

A website that shows exactly **one** thing: the single most important news
story of the last 24 hours, refreshed once a day. No feed, no scroll, no second
story. The discipline of showing one thing is the point.

The winner is chosen by a fully deterministic score - no external LLM, no paid
API, no editorial hand. Everything is reproducible from the fetched feed data.

## How it works

A Python pipeline runs once daily (GitHub Actions cron), regenerates a static
`index.html`, and commits it for GitHub Pages. Zero infrastructure cost.

```
fetch.py  ->  cluster.py  ->  rank.py  ->  render.py        (run.py orchestrates)
 RSS in       group same     deterministic  spartan
 24h window   story           score         index.html
                                  ^
                            ledger.py (novelty state)
```

| Stage | File | What it does |
|-------|------|--------------|
| 1 Fetch | `fetch.py` | Pull RSS entries, filter to a rolling 24h window, normalise to `{title, source, country, lean, url, published_at, snippet}`. One dead feed never kills the run. |
| 2 Cluster | `cluster.py` | Group articles about the same story: TF-IDF + cosine similarity, joined by union-find. Swappable via `CLUSTER_METHODS`. |
| 3 Score | `rank.py` | `coverage × diversity × recency × novelty`, fully deterministic. Always forces a single winner. |
| 4 Ledger | `ledger.py` | The only persistent state: fingerprints of the last ~7 days' winners, to power the novelty term. Not a public archive. |
| 5 Render | `render.py` | One static, spartan `index.html`. |
| 6 Fallback | `run.py` | Never serves a broken page (see below). |

## Run it locally

```bash
pip install -r requirements.txt
python run.py           # full pipeline -> index.html
```

Each stage is also runnable on its own and prints its output for inspection:

```bash
python fetch.py         # writes data/articles.json
python cluster.py       # writes data/clusters.json
python rank.py          # writes data/ranked.json
python render.py        # writes index.html
python render.py --stale   # render with the "showing yesterday's story" flag
python ledger.py        # print the current decay ledger
```

Preview the page: `python -m http.server 8000` then open
`http://127.0.0.1:8000/index.html` (a browser won't open `file://` reliably).

## Adding or tagging feeds

Feeds live in `config/feeds.yaml`. Add a list item - that's it:

```yaml
  - name: Some Outlet
    url: https://example.com/rss.xml
    country: US            # ISO-ish code, or INT for a transnational wire
    lean: centre-left       # left | centre-left | centre | centre-right | right
    via: gnews              # OPTIONAL - only for Google News site-scoped feeds
```

- `country` and `lean` are the **outlet's** tags, used only by the diversity
  term. `lean` is the editorial lean of the outlet, never a claim about any
  individual article.
- `via: gnews` marks a Google News site-scoped search feed (used for outlets
  that have retired their own RSS, e.g. Reuters, AP, AFR). For these the
  `" - Source"` title suffix is stripped and the junk description is dropped.
- The seed list is deliberately balanced across geography and lean so the
  diversity term has something to measure - keep it that way when editing.

## How the deterministic scoring works

```
score = coverage^wc  ×  diversity^wd  ×  recency^wr  ×  novelty^wn
```

Each component is normalised to `(0, 1]`, so the weights (exponents in
`config/settings.yaml`) are directly comparable and the product behaves like a
soft AND.

- **coverage** - log-scaled distinct-outlet count, normalised by the day's
  busiest cluster. The log dampens runaway raw volume.
- **diversity** - *the key term.* A weighted geometric mean of
  `(distinct countries / all countries)` and `(distinct leans / all leans)`.
  A story spread across many countries **and** both political leans beats one
  running loud in a single national press. This is how volume bias is fought.
- **recency** - exponential decay on the cluster's centroid publish time
  (half-life in settings). Favours coverage still building now.
- **novelty** - a penalty in `[floor, 1]` if the cluster matches a story that
  led on a recent prior day (cosine vs the decay ledger). Strongest for
  yesterday's lead, decaying back to 1.0 over `novelty_decay_days`. A day-two
  story must rebuild genuinely new coverage to hold the top slot.

A single winner is always forced - there is no "quiet day" empty state.

## Tuning the weights

All in `config/settings.yaml` under `weights:` and `scoring:`.

| Want to... | Change |
|------------|--------|
| Reward broad, cross-spectrum stories harder | raise `weights.diversity` |
| Stop high-volume stories dominating | lower `weights.coverage` |
| Favour breaking news | raise `weights.recency` / lower `recency_half_life_hours` |
| Let a big story hold the top slot for days | lower `weights.novelty` / raise `novelty_penalty_floor` |
| Weight geography over politics (or vice versa) | shift `country_share` vs `lean_share` (they sum to 1.0) |
| Merge stories more/less aggressively | raise/lower `similarity_threshold` |

The scoring is a pure function of the fetched data plus the ledger, so any run
is reproducible: re-run `rank.py` on the same `data/articles.json` and you get
the same ranking.

## Fallback behaviour

`run.py` never publishes a broken page:

- **Too little data** - the scorer always forces the best available pick, so
  even a single article yields a page. Only *zero* articles counts as failure.
- **Whole run fails** - the previous `index.html` (committed in the repo) is
  left intact and a subtle "showing yesterday's story" banner is injected. The
  injection is idempotent, so repeated failures don't stack banners.

## Deploy

The workflow is `.github/workflows/daily.yml`:

1. Runs daily at **20:00 UTC** (≈06:00 AEST / 07:00 AEDT - fixed UTC, so it
   drifts ~1h with Sydney daylight saving), plus manual `workflow_dispatch`.
2. Installs deps, runs `python run.py`.
3. Commits `index.html` and `data/recent_leads.json` (the ledger - the only
   state that must persist between runs) back to the repo.

To publish via **GitHub Pages**: repo *Settings → Pages → Build and deployment
→ Deploy from a branch*, set branch to `main`, folder `/ (root)`. The daily
commit then updates the live page.

## Copyright

The site only ever displays: the **headline**, the **feed-supplied
description** (hard-capped to `snippet_cap_words`), a **link** to the source,
and **coverage stats we compute ourselves**. No article body is ever fetched or
stored, and no "analysis" or "why it matters" prose is generated - only
computed facts. All fetched content is assumed copyrighted.
