# One Story - TODO

Deferred / optional work. Nothing here is blocking; the site is live and the
daily job runs on its own.

- [x] **Brevo cutover - DONE + verified end-to-end 27/07/2026.** Switched
  Buttondown -> Brevo because Buttondown forces double opt-in on form signups
  (no toggle) and Brevo allows SINGLE opt-in (instant, no confirmation email) AND
  supports campaign send via API. Live config: sender_email
  charlie.rochfordgroup@gmail.com (verified), list_id 2, signup form = Brevo
  sibforms serve URL set to "No confirmation email". Verified: (a) real signup on
  the live site -> SUBSCRIBED contact, zero confirmation email; (b) CI test-send
  created Brevo campaign 5 + sendTest to inbox, no error. Both Buttondown subs
  ported to Brevo list 2. Secrets BREVO_API_KEY + BREVO_TEST_EMAIL set.
- [x] **Daily email subscription - LIVE (Brevo, single opt-in).** Signup form +
  automated daily send in CI. `send_email.py` creates a campaign then `sendNow`;
  `--test` uses `sendTest` (never touches the live list). Send step is
  `continue-on-error`; per-day guard prevents double-sends. Signup form carries a
  Brevo honeypot for bot hygiene.
- [x] **Cleanup done (27/07/2026).** Old `BUTTONDOWN_API_KEY` GitHub secret and
  the `+ostest` test contact in Brevo both deleted.
- [ ] **Email deliverability - custom sending domain (editions currently land in
  JUNK).** Confirmed 27/07/2026: the test edition delivered but Gmail filed it to
  Junk because the Brevo sender is a **`@gmail.com` freemail address**. Mail that
  claims to be "from @gmail.com" but is sent via a third party (Brevo) fails
  DMARC alignment, so Gmail/Yahoo/Outlook spam-filter it for ALL subscribers
  (Brevo itself flags the sender: "Freemail domain is not recommended"). The
  plumbing is fine - it's purely the from-address. Fix:
    1. Register a domain for One Story (~A$15-40/yr; e.g. onestory.news /
       theonestory.com / onestory.email) - also gets `github.io` out of the site
       URL (one job, two wins).
    2. Authenticate it in Brevo -> it generates DKIM + a Brevo SPF record + a
       DMARC record to add at the registrar's DNS.
    3. Change `sender_email` (settings + Brevo verified sender) to e.g.
       `hello@<domain>`.
  Charlie registers the domain (his call, a purchase); then I handle the Brevo
  authentication + DNS records + re-test until it inboxes cleanly. Interim:
  marking "not junk" fixes it only for that one recipient, not subscribers.
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
