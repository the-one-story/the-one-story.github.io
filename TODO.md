# One Story - TODO

Deferred / optional work. Nothing here is blocking; the site is live and the
daily job runs on its own.

## HIGH - deliverability still unresolved for BULK sends

- [ ] **NO NEWSLETTER HAS GONE OUT SINCE 10/08/2026 - the Brevo account is under validation.**
      Every send returns `HTTP 402 {"code":"account_under_validation","message":"Your account
      is under validation. You can not create another campaign."}`. Diagnosed 12/08/2026 from
      the logs of run 31530845789, which otherwise reported success. **This is a shared
      account, so The Aftertimes went dark at the same time** - see that repo's TODO for the
      full diagnosis. The account is `charlie.rochfordgroup@gmail.com` (company name "One
      Story"), recovered without a login via the API. Charlie is resolving it from the machine
      already signed in to Brevo. **Nothing here is misconfigured** - the domain is
      authenticated and verified and the API key still authenticates. **No backfill:** the
      campaign is never created, so the missed editions will not send once the hold lifts.
      Most likely trigger is the single opt-in signup form; switching to double opt-in is the
      strongest remediation to offer them.
- [x] **DONE 13/08/2026 - a failed send now fails the run.** The send step keeps
      `continue-on-error` so publishing is never blocked, but it carries `id: send` and a
      final "Surface a failed send" step re-raises `steps.send.outcome == 'failure'`
      AFTER the commit step - so the page still publishes and the run goes red. Pinned by
      `tests/test_send_email.py`, which also asserts the surfacer sits after the commit
      (put it before and a bad send would block publishing - the original instinct that
      led to the bug).
- [x] **DONE 13/08/2026 - stopped retrying into the review queue.** `send_email.py`
      recognises `402 account_under_validation`, records a hold in `data/last_email.json`
      (`{code, since, last_attempt}`) and skips further creates, re-probing every 3 days so
      sending resumes on its own when the hold lifts; a successful send clears it. Other
      HTTP errors deliberately do NOT record a hold, so a one-off 500 cannot silence the
      newsletter for days. Skips still exit non-zero, so a held day is never green.
- [x] **Superseded by the two entries above.** *(original wording kept for the reasoning)*
      **A failed send reports the job as green, which is why three dead days went unnoticed.**
      `daily.yml:120` carries `continue-on-error: true` on the send step, commented "an email
      hiccup must never block publishing". That is the right instinct and the wrong
      implementation: `send_email.py` exits 1, the step swallows it, and `gh run list` shows
      `success`, so the only trace is a job annotation nobody reads. Publishing should indeed
      not be blocked, but the failure has to surface - open an issue, or fail the job after
      the commit step has run. The Aftertimes has the identical bug in the identical place.
- [ ] **Stop retrying the send while the account is under review.** Since 10/08 the daily job
      has called campaign creation every day against an account already on a manual review
      queue. Those rejected attempts do not help the case being assessed. Short-circuit on a
      `402 account_under_validation` rather than hammering, and let the gate skip the step
      until Charlie clears the hold.

- [ ] **A real campaign from the authenticated domain still went to JUNK (07/08/2026).**
      The single-recipient `sendTest` (campaign 37) landed in the INBOX, but the first
      real `sendNow` to the list (campaign 39, "Trump signs new orders restricting
      birthright citizenship") went to junk. From-address was correct
      (`One Story <onestory@mail.charlietrenorden.com>`), so authentication is NOT the
      problem - DKIM/DMARC are ours and passing.
      **Two candidate causes, NOT yet separated:**
        1. **Shared click-tracking domain.** A real campaign rewrites every link
           through Brevo's tracking host; a `sendTest` may not. Because the branded
           subdomain was dropped to unblock authentication, that host is Brevo's
           SHARED one - the same class of problem as the old shared `brevosend.com`
           From. **Verified against the API spec: `POST /v3/emailCampaigns` has NO
           parameter to disable link tracking** (the body accepts `mirrorActive`,
           `utmCampaign`, `header`/`footer`, etc. - nothing for link rewriting), so a
           branded subdomain is the ONLY lever. This makes the earlier "branding is
           marginal, drop it" call look wrong.
        2. **No sending history.** This was the first BULK campaign from a
           days-old domain; filters are most cautious exactly there, and one send
           each way is not a pattern.
      **Cheapest discriminator:** on the junked email, read the "Why is this message
      in spam?" banner, and hover the story link - if it points at a brevo/sendibt
      tracking host rather than the publisher, cause 1 is live; if not, tracking is
      irrelevant and it is cause 2 (wait it out + mark not-spam, which now accrues to
      OUR domain).
      **To fix cause 1:** Domains -> "Set up branded subdomain" -> copy the three
      record Values -> add as CNAMEs in Cloudflare, **DNS only**. Their values still
      cannot be read programmatically (truncated in the UI, absent from the
      accessibility tree, page JS blocked) so a human must copy them. Note the Brevo
      UI would not open this flow at all on 07/08 - repeated dead clicks.

## HIGH - test coverage

- [ ] **Test the scoring pipeline. `tests/` currently holds one smoke script.**
      *(added 07/08/2026, estate-wide test audit.)*
      `tests/smoke_site.py` checks the rendered site, not the decisions that
      produced it. Eleven modules run **unattended every day** and pick the single
      story that goes on the site and into the newsletter. If `rank.py` or
      `cluster.py` silently drifts, nothing catches it - the site still renders,
      it just picks the wrong story, and it does that every day until someone
      notices by eye.

      These are deterministic pure functions (no LLM), which makes them unusually
      cheap to test:
      - `rank.py` - score a fixture set of articles and assert the ordering.
        **Pin the diversity term explicitly** - it is the anti-volume-bias
        mechanism and the thing most likely to regress into "whatever 20 outlets
        covered most".
      - `cluster.py` - a fixture where the same event is worded three ways must
        collapse to one cluster; two genuinely different events must not.
      - `ledger.py` - the same story must not be publishable twice; assert the
        dedupe survives a restart.
      - `fetch.py` - parse checked-in RSS fixtures including a malformed feed and
        an empty one. No network in tests.
      - `email_render.py` - assert the newsletter HTML against the gotchas already
        learned (table + inline + bgcolor, no SVG logo, `{{unsubscribe}}` present).

- [ ] **`trafilatura` (Apache-2.0) - full article text instead of RSS summaries.**
  *(added 31/07/2026, library-review sweep across all projects.)* `fetch.py` only
  ever sees `entry.summary` from feedparser - a truncated, publisher-controlled
  blurb. Clustering and scoring therefore run on a thin, uneven signal (some feeds
  give two sentences, some give a full lede, some give marketing copy). trafilatura
  would fetch and extract the real article body, which should sharpen both the
  clustering and the diversity term that anti-volume-bias depends on.
  **This is a design change, not a drop-in.** It adds one HTTP fetch per candidate
  article to every run (CI time, politeness, failure modes to handle) and it will
  shift scores, so the current story selection WILL change. Before adopting: run it
  side-by-side on a few days of real feeds and compare the chosen story against what
  the summary-only path picked - if the picks are the same, the added fetch cost buys
  nothing and this should be rejected outright. Sibling trafilatura item in Board
  Mover Scanner (there it fixes a live bug, so it ranks higher).

- [x] **Custom sending domain LIVE - `mail.charlietrenorden.com` authenticated
  (06/08/2026).** Brevo shows "All domains are authenticated". Sending now happens
  from `One Story <onestory@mail.charlietrenorden.com>`, a sender Brevo lists as
  **Verified** with DKIM signature `mail.charlietrenorden.com` and "DMARC is
  configured" - reputation is ours alone instead of the shared `brevosend.com`.
  Records in Cloudflare, all **DNS only**: `mail` TXT brevo-code,
  `brevo1/brevo2._domainkey.mail` CNAME -> b1/b2.mail-charlietrenorden-com.dkim.brevo.com,
  `_dmarc.mail` TXT `v=DMARC1; p=none; rua=...`. Test send verified (campaign 37).
  **Two gotchas worth remembering:** (1) Brevo will NOT authenticate a domain while
  its BRANDING records mismatch, so the optional branded subdomain becomes a hard
  prerequisite - we cleared it (wizard step 2) to unblock, and its record values are
  unreadable programmatically anyway (truncated in the UI, absent from the a11y tree,
  page JS blocked). Re-add any time via "Set up branded subdomain". (2) An
  authenticated domain is NOT sufficient to send - the address must ALSO exist as a
  Sender, else the API returns `400 invalid_parameter "Sender is invalid / inactive"`.
  Adding it on an authenticated domain auto-verifies with no confirmation email.
  **VERIFIED 06/08/2026: the test landed in the INBOX** - first send from a
  brand-new domain, no warm-up needed. The months-long first-email-to-spam problem
  is closed. (I had expected a cautious warm-up period; Gmail accepted it straight
  away, so an authenticated domain you own beats a shared ESP domain immediately, not
  just eventually.) Optional later: tighten DMARC `p=none` -> `p=quarantine` once
  there is real send history.
- [x] **DONE - verified 12/08/2026. Finish the custom sending domain cutover.**
  `brevo_sender.py list` (run in The Aftertimes' repo, same Brevo account) returns
  `mail.charlietrenorden.com authenticated=True verified=True` and
  `onestory@mail.charlietrenorden.com active=True`. The cutover is complete; only the
  JUNK-placement question above is still live, and that is reputation, not auth.
  <details><summary>Original note</summary>
  **[SUPERSEDED - see above] Finish the custom sending domain cutover.**
  Domain bought (`charlietrenorden.com`, DNS on Cloudflare) and the sending domain
  `mail.charlietrenorden.com` is set up in Brevo with branded subdomain `send`,
  method = individual DNS records / manual. **Done:** all four AUTHENTICATION
  records added in Cloudflare, every one `DNS only` (not proxied - a proxied DKIM
  CNAME breaks authentication), independently confirmed live by DNS-over-HTTPS, and
  Brevo's own "Verify records" reports all four as MATCH. "Authenticate domain"
  submitted; Brevo returned *"Authentication is pending"* (propagation, up to 48h).
  Records as entered:
    - `mail`                   TXT   `brevo-code:a70e1487e9f3991c7316df42bfcc2b80`
    - `brevo1._domainkey.mail` CNAME `b1.mail-charlietrenorden-com.dkim.brevo.com`
    - `brevo2._domainkey.mail` CNAME `b2.mail-charlietrenorden-com.dkim.brevo.com`
    - `_dmarc.mail`            TXT   `v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com`
  **Still to do, in order:**
    1. Confirm Brevo shows the domain **Authenticated** (Senders, Domains & IPs ->
       Domains). Usually minutes on Cloudflare.
    2. Switch `newsletter.sender_email` in `config/settings.yaml` from
       `charlie.rochfordgroup@gmail.com` to `onestory@mail.charlietrenorden.com`.
       **Deliberately NOT changed yet** - Brevo rejects an unverified sender, so
       flipping it before authentication completes would silently kill the daily
       send (the step is `continue-on-error`, so the site would still publish).
    3. Test-send to a FRESH Gmail address (workflow_dispatch, `test_send=true` +
       `test_email=<addr>`) and confirm it lands in the inbox, not spam - that is
       the whole point of the exercise. Check the from-address is now
       `@mail.charlietrenorden.com`, not `<id>.brevosend.com`.
    4. **BLOCKER (corrected 04/08/2026):** the three BRANDING records (`send.mail`,
       `r.send.mail`, `img.send.mail`, all CNAME) are NOT added, and Brevo **will not
       mark the domain authenticated until they match** - the domain still reads "Not
       authenticated" even though all four authentication records verify green. Its
       error text is literal: "Add this Branded record value ... *to authenticate this
       domain*." (An earlier note here saying branding "does not block
       authentication" was WRONG.) Opting into the branded subdomain `send` therefore
       made link-branding a prerequisite.
       **RECOMMENDED (04/08/2026): drop the branding.** It is the only thing blocking
       authentication, the gain is marginal (click-tracking links stay on Brevo's
       shared domain rather than ours), it is addable any time later, and dropping it
       removes all dependence on the INFERRED target values below - the fix should not
       rest on a guess. Charlie also disliked the record length. Note the length is
       cosmetically irrelevant: the long string is the TARGET, a hostname on Brevo's
       infrastructure that no reader ever sees; only the Name side
       (`send.mail.charlietrenorden.com`) is ever visible. Two ways out:
         - **Keep branding (better):** in Brevo's records step click "Copy" beside each
           of the three Branding *Value* fields and paste them, then add the three
           CNAMEs in Cloudflare as **DNS only** and re-run Verify + Authenticate. The
           values cannot be read programmatically - Brevo truncates them in the input
           AND omits them from the accessibility tree, and blocks page JS - and they
           must NOT be guessed (the obvious `.brevosend.com` pattern was tried and
           disproved by DNS).
         - **INFERRED values to try first (04/08/2026)** - pattern-derived from the
           confirmed DKIM targets plus the visible truncations (`...brand.brevose`,
           `...r.brand.brevos`, `...img.brand.brev`). NOT verified; Brevo's "Verify
           records" is the arbiter, and it compares the published string, so one click
           settles it. A wrong CNAME here is inert (nothing uses `send.mail`). All
           three **DNS only**:
             - `send.mail`     CNAME `send-mail-charlietrenorden-com.brand.brevosend.com`
             - `r.send.mail`   CNAME `send-mail-charlietrenorden-com.r.brand.brevosend.com`
             - `img.send.mail` CNAME `send-mail-charlietrenorden-com.img.brand.brevosend.com`
           (Note: an earlier claim that DNS "disproved" this pattern was too strong -
           these targets are likely only provisioned once the domain authenticates, so
           a non-resolving lookup was inconclusive, not a refutation.)
         - **Drop branding (fastest):** clear the branded subdomain so only the four
           authentication records are required - re-open "Authenticate domain", click
           "Previous" back to step 2 "Branded subdomain", empty the `send` field, then
           Continue -> Continue -> Verify records -> Authenticate domain.
- [x] **[SUPERSEDED] Custom sending domain - the real fix for first-email-to-spam.**
  Reported 30/07/2026 that new subscribers' first edition lands in spam. Root cause
  is reputation, not auth (see the deliverability item below for the full diagnosis).
  The real fix: buy a domain (e.g. `onestory.news`), authenticate it in Brevo (add
  the DKIM/SPF/DMARC DNS records Brevo generates), and send from `hello@<domain>`
  instead of the shared `<id>.brevosend.com`. That gives One Story its own sender
  reputation (instead of borrowing the cold shared one) and DMARC alignment on a
  brand domain - which is what stops the first email being filtered. Bonus: the same
  domain gets `github.io` out of the site URL, so it does double duty. Needs Charlie
  to buy the domain (his call); then Claude does the Brevo verification + DNS records
  + re-test. Interim free mitigation already shipped: the signup success note now
  tells new subscribers to mark the first edition "not spam".
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
  </details>
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
    2. Proper fix: a custom sending domain - see the **[PRIORITY]** item at the top
       of this list for the full plan.
- [ ] **"Sent with Brevo" badge in the email footer** - free-tier branding, NOT
  removable by code/settings. Only goes away on a paid plan (Starter + the
  $9/mo "Remove Brevo logo" add-on, or Standard/higher). The unsubscribe line
  next to it is legally required and stays regardless. Living with it on free
  for now; revisit if ever on a paid plan (would pair with the domain decision).
- [ ] **"Why this story?" explainer fidelity (panel audit, 28/07/2026).** Engine
  maths is sound; the explainer copy misdescribes it. (a) [MED] "they multiply
  together to rank" is wrong - the four shown bars are RAW components but the score
  is `cov^1.0 * div^1.6 * rec^0.8 * nov^1.0`, so multiplying the bars won't
  reproduce the runner-up scores shown beneath. Reword to "combine" + name the
  weights. (b) [MED] the diversity bar is almost always the SHORTEST (normalised
  against all ~25 feed countries + 5 leans -> ~0.2-0.4) yet is labelled "weighted
  heaviest"; the x1.6 exponent is invisible. Annotate the row with its weight or show
  weighted contribution. (c) [LOW] "recency favours coverage still building now"
  overstates it - it's exp-decay on the cluster's MEAN publish time (avg age), not
  momentum; soften to "fresh over fading". Both (a)/(b) are copy+annotation in
  `render.py` `_why_section` / `_COMPONENT_DESC`, not a maths change.
- [ ] **Novelty floor never reached (internal nit, 28/07/2026).**
  `novelty_penalty_floor` (0.35) is unreachable: `age_days >= 1` is required, so the
  strongest achievable penalty is `0.35 + 0.65*(1/4) = 0.51` (a yesterday-lead). The
  `settings.yaml` comment calls 0.35 "the strongest penalty" - relabel it, or base
  `frac` on `(age_days-1)/(decay_days-1)` in `rank.py:_novelty_penalties` if a
  yesterday-lead should actually hit the floor. Public copy ("~4 days") is fine;
  doesn't change current rankings materially.
- [ ] **Google-News redirect URLs quietly cancel the tier-1 hero preference.**
  *(found 31/07/2026 while fixing the off-topic hero.)* Several tier-1 wires -
  Reuters, AP, AFP, CBC - arrive via Google News, so their `url` is a
  `news.google.com/rss/articles/...` redirect. `choose_hero` demotes those
  (`_is_gnews`, to avoid featuring a redirect link), which means the wires are
  systematically ruled out of the hero slot even though `_HERO_TIER1` is supposed
  to prefer them - the two rules work against each other. Net effect: the hero is
  usually the earliest tier-1 *direct* link, which is often an explainer rather
  than the fullest straight-news account. Live example (31/07): the on-topic FIFA
  hero became ABC's "FIFA wants to sell the World Cup to a Trump associate. Here's
  what..." while Reuters' "UEFA votes to boycott World Cup over FIFA investor plan"
  was demoted purely for being a gnews URL. Two possible fixes: (a) resolve
  Google-News redirects to the publisher URL at fetch time (one extra request per
  gnews item, so weigh against the CI-time concern in the trafilatura item above -
  they share the same tradeoff and should probably be decided together), or
  (b) rank straight news above explainers/analysis (a title-pattern test like
  `_NOISE_TITLE`: "here's what", "how will", "why ...", "explained", "what to
  know"). (b) is cheap and needs no network; (a) is the more complete fix.
  Verify either on `data/history/` the same way the off-topic threshold was tuned -
  count how many heroes change and confirm each change is an improvement.
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
  ever hard-fails. Still warning as of the 12/08/2026 run - confirmed, not fixed.

## Optional design ideas raised, not taken
- **A generic "two sentence-clauses in one title" roundup guard - REJECTED on data
  (04/08/2026).** Tempting after two roundup formats slipped through (NBC, then NPR
  Up First), since the pattern list is reactive by nature. Measured before deciding:
  `[a-z'")]\.\s+[A-Z]` (period preceded by a lowercase char so `U.S.`/`No. 1` don't
  fire) hits **213 of 12,666 clean archived articles (1.68%)**, and they are
  overwhelmingly LEGITIMATE single-story headlines using a two-sentence rhetorical
  shape - "OpenAI blamed a hacking event on its AI models gone rogue. Here is
  what...", "Famine has ended in Gaza. But the gains are fragile" - plus
  abbreviation misfires ("Rep. Jim Jordan...", "Sen. Paul..."). ~200 good articles
  lost per roundup caught. Keep the precise per-format patterns instead: each new
  format is a two-line `_NOISE_URL`/`_NOISE_TITLE` addition with zero collateral,
  verified against `data/history/` the same way. Don't re-open without a materially
  better discriminator than title shape.
- **Note for whoever hits the next roundup:** the off-topic hero guard
  (`rank._offtopic_flags`) structurally CANNOT catch this class. A roundup leading
  with the cluster's dominant story is highly representative of it - the 04/08 NPR
  item scored 1.25x the cluster median, the 2nd most representative of 9 members.
  That guard detects "wrong story"; a roundup is "right story PLUS another story".
  Fix roundups at fetch (drop), not at hero selection.
- Lock the hero article for the whole local day (not just the story cluster), so
  the featured headline/link doesn't re-pick between runs. Offered 27/07, not
  taken - only matters under repeated same-day runs; production runs once/day, so
  the fresh re-pick (latest best article in the locked story) is fine.
- Highlighted-countries map (kept dots - fills over-weight large countries).
- Demote hard-paywalled sources (AFR) to non-clickable (kept: counted +
  lock-marked, never the hero link).
