# One Story - project context for Claude

Daily single-story news site. Deterministic scoring, **no LLM anywhere in the
pipeline**: `fetch.py` -> `cluster.py` -> `rank.py` -> `render.py`, plus
`email_render.py` / `send_email.py` for the Brevo newsletter. Runs unattended on
a GitHub Actions cron and publishes to GitHub Pages.

## Test coverage - KNOWN GAP (flagged 07/08/2026, estate-wide test audit)

**`tests/` holds one smoke script (`smoke_site.py`) and nothing else.** It checks
that the rendered site looks sane. It does not check any of the decisions that
produced it.

Why that matters here more than in a typical repo: this thing runs **every day
with nobody watching**, and its whole job is a judgement call - which single
story leads. A regression in `rank.py` or `cluster.py` does not crash and does not
show up as a broken page. The site renders perfectly and picks the wrong story,
silently, every day, until someone notices by eye.

The scoring is deterministic and pure, so the tests are cheap. There is no reason
for them not to exist.

**If you are changing `rank.py`, `cluster.py`, `ledger.py` or `fetch.py`, add
tests for what you touch before you finish.** In particular:

- **Pin the diversity term with an explicit test.** It is the anti-volume-bias
  mechanism. Without a guard, the natural failure mode is quiet collapse into
  "whatever the most outlets covered", which is exactly what this site exists
  not to do.
- Cluster fixtures must cover both directions: same event worded three ways
  collapses to one; two different events stay separate.
- No network in tests - checked-in RSS fixtures, including a malformed feed and
  an empty one.

See `TODO.md` for the tracked item and the suggested first pass.

## Conventions and gotchas

- Australian English, hyphens only (no en or em dashes) in anything rendered.
- Newsletter is Brevo, single opt-in. Editions have landed in junk on the shared
  sending domain - see the global `html-email-gotchas` memory before touching
  `email_render.py`.
- GitHub cron is unreliable (runs late, occasionally dropped entirely). Any
  scheduling change needs an idempotence guard on the **publish** step, not just
  on the send.
