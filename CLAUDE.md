# One Story - project context for Claude

Daily single-story news site. Deterministic scoring, **no LLM anywhere in the
pipeline**: `fetch.py` -> `cluster.py` -> `rank.py` -> `render.py`, plus
`email_render.py` / `send_email.py` for the Brevo newsletter. Runs unattended on
a GitHub Actions cron and publishes to GitHub Pages.

## Test coverage - the 07/08/2026 gap is CLOSED (verified 28/11/2026)

`tests/` holds 9 pytest modules and 141 tests, run in CI by `.github/workflows/tests.yml`
(`python -m pytest tests/ -q --ignore=tests/smoke_site.py`). The three things the old
note asked for are all there, checked rather than assumed:

- **The diversity term is pinned** - `test_rank.py` holds it to a weighted geometric
  mean and inside the unit interval. It is the anti-volume-bias mechanism, and the
  failure mode it guards is a quiet collapse into "whatever the most outlets covered".
- **Cluster fixtures run both directions** - `test_cluster.py` covers one event worded
  three ways collapsing to one, and two unrelated events staying apart, plus
  determinism.
- **No test touches the network.** `test_send_email.py` monkeypatches `urlopen`;
  nothing else reaches out. `tests/smoke_site.py` is the exception by design - it drives
  headless Chromium over the committed `index.html` and is excluded from CI.

`tests/smoke_site.py` has one standing failure, on console errors: the Cloudflare beacon
is blocked by CORS when the page is served from `127.0.0.1`. It is an artefact of local
serving, not a page fault.

**Still untested, and worth knowing before you trust a green run:** `run.py` itself. The
stale-banner fallback - the path that keeps yesterday's page up when a run dies, and the
idempotence guard that stops the banner being injected twice - has no test and is
exercised only when something has already gone wrong. That is the one place left where
the suite is green and the behaviour is unproven.

**The standing rule survives the gap being closed: if you are changing `rank.py`,
`cluster.py`, `ledger.py` or `fetch.py`, add tests for what you touch before you
finish.** This thing runs every day with nobody watching and its whole job is a
judgement call. A regression in the scorer does not crash and does not show up as a
broken page - the site renders perfectly and picks the wrong story, silently, until
someone notices by eye. On 28/11/2026 someone did, and it had led with a Black Friday
shopping listicle. See `docs/lead-audit.md` for what it has actually been leading with.

## Conventions and gotchas

- Australian English, hyphens only (no en or em dashes) in anything rendered.
- Newsletter is Brevo, single opt-in. Editions have landed in junk on the shared
  sending domain - see the global `html-email-gotchas` memory before touching
  `email_render.py`.
- GitHub cron is unreliable (runs late, occasionally dropped entirely). Any
  scheduling change needs an idempotence guard on the **publish** step, not just
  on the send.
