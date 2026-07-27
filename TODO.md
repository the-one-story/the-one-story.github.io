# One Story - TODO

Deferred / optional work. Nothing here is blocking; the site is live and the
daily job runs on its own.

- [ ] **Brevo cutover - Charlie's account setup (code is done, awaiting these).**
  Switched provider Buttondown -> Brevo (decided 27/07/2026) because Buttondown
  forces double opt-in on form signups (no toggle; confirmed via
  docs.buttondown.com/double-opt-in) and Brevo allows SINGLE opt-in (instant, no
  confirmation email) AND supports full campaign send via API. Code is migrated +
  dry-run-verified; it stays dormant until these are filled. Charlie's steps
  (I can't create accounts or handle the key):
    1. Create a free Brevo account.
    2. Verify a sender address (Settings -> Senders) -> that's `sender_email`.
    3. Create a contact list -> note its numeric `list_id`.
    4. Create a subscription form (single opt-in) -> copy its action URL (a
       `sibforms.com/serve/...` URL) -> that's `signup_form_url`.
    5. Add GitHub Actions secret `BREVO_API_KEY` (repo Settings -> Secrets ->
       Actions). Optional: `BREVO_TEST_EMAIL` for the manual test send.
    6. Port the list: Buttondown Subscribers -> export CSV -> Brevo -> Import,
       mark contacts subscribed (already confirmed, won't re-confirm).
  Then hand me `sender_email`, `list_id`, `signup_form_url`; I fill
  `config/settings.yaml`, regenerate index.html, and run a `--test` to verify a
  real signup + a real inbox delivery end-to-end before it goes live.
- [x] **Daily email subscription - built.** Signup form + automated daily send in
  CI. Provider is now **Brevo** (single opt-in). `send_email.py` creates a
  campaign then `sendNow`; `--test` uses `sendTest` (never touches the live
  list). Send step is `continue-on-error` so an email hiccup never blocks
  publishing; per-day guard prevents double-sends. Signup form carries a Brevo
  honeypot for bot hygiene. LIVE pending Charlie's Brevo setup above.
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
