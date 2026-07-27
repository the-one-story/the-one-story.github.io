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
- [ ] **Email deliverability - editions land in JUNK (reputation, not auth).**
  Confirmed 27/07/2026 by the actual from-address: `One Story
  <charlie.rochfordgroup@11756300.brevosend.com>`. Brevo auto-rewrites the from
  to its OWN authenticated domain (brevosend.com) because it can't authenticate a
  gmail address - so SPF/DKIM/DMARC all PASS. (My earlier note here blaming a
  "gmail DMARC failure" was WRONG - corrected.) The real cause is **shared-domain
  reputation + brand-new sender**: `11756300.brevosend.com` is a shared Brevo
  sending domain and there's zero send history/engagement, so Gmail defaults it
  to Junk until trust builds. Not broken, not a dead end. Options, cheapest first:
    1. Interim/free: mark "not junk" + add sender to contacts + a Gmail filter
       "never send to spam". Works because the list is currently all Charlie's
       own addresses. Reputation also improves with engagement over time.
    2. Proper fix: a custom domain (dedicated reputation Charlie owns) authenticated
       in Brevo (DKIM/SPF/DMARC DNS records), sending from hello@<domain> - also
       gets github.io out of the site URL. Charlie buys the domain (his call, not
       yet); then Claude does the Brevo/DNS auth + re-test. Only needed once there
       are external subscribers.
- [ ] **"Sent with Brevo" badge in the email footer** - free-tier branding, NOT
  removable by code/settings. Only goes away on a paid plan (Starter + the
  $9/mo "Remove Brevo logo" add-on, or Standard/higher). The unsubscribe line
  next to it is legally required and stays regardless. Living with it on free
  for now; revisit if ever on a paid plan (would pair with the domain decision).
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
