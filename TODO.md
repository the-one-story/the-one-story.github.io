# One Story - TODO

Deferred / optional work. Nothing here is blocking; the site is live and the
daily job runs on its own.

- [ ] **Finish newsletter setup (Buttondown dashboard - Charlie's clicks).**
  Turn off double opt-in (Settings -> Subscribing); rename the newsletter
  "Charlie" -> "One Story" (Settings -> Basics) so emails are branded; make own
  address active in Subscribers so the daily send arrives.
- [x] **Daily email subscription.** LIVE (Buttondown, username "onestory").
  Signup form on the site + automated daily send in CI (verified 24/07: HTTP 201
  real send). Needed the `X-Buttondown-Live-Dangerously: true` header for
  API sends. Send step is `continue-on-error` so an email hiccup never blocks
  publishing; per-day guard prevents double-sends.
- [ ] **Tune scoring weights on real data.** Once `data/history/` has ~1-2
  weeks of daily snapshots, use `replay.py` to test alternative weights
  (esp. bumping `recency` from 0.8). Don't tune on a single day.
- [ ] **Light-mode variant.** Site is committed to the dark "Ink" theme; add a
  matching light palette (burnt-orange accent) for light-mode browsers if
  wanted. Would restore the `prefers-color-scheme` / `data-theme` token split.
- [ ] **History archive size.** Each `data/history/YYYY-MM-DD.json` is ~400KB
  (full article pool). Fine for months; if the repo gets heavy, gzip the files
  or drop the raw `articles` array after N days (keep the winner + config).
- [ ] **GDELT breadth source.** Deferred from v1 (RSS-only). Add as a swappable
  fetch source alongside RSS if more coverage volume is wanted - will need
  diversity-term retuning to avoid volume skew.
- [ ] **CI action versions.** `actions/checkout@v4` + `setup-python@v5` log a
  Node 20 deprecation warning (auto-run on Node 24). Cosmetic; bump only if it
  ever hard-fails.

## Optional design ideas raised, not taken
- Highlighted-countries map (kept dots - fills over-weight large countries).
- Demote hard-paywalled sources (AFR) to non-clickable (kept: counted +
  lock-marked, never the hero link).
