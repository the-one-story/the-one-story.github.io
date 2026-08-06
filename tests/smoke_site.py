"""Smoke-test the rendered site in a real browser.

The unit-level pipeline (fetch -> cluster -> rank -> render) can be entirely
green while the page a reader actually gets is broken: a details panel that
never opens, a signup form pointing nowhere, an icon 404, a mobile layout that
scrolls sideways. Those only show up once something renders the HTML. This does
that - headless Chromium over a local static server, against the committed
index.html.

Usage:
    python tests/smoke_site.py            # serve repo root, test index.html
    python tests/smoke_site.py --port 8765
    python tests/smoke_site.py --shots out/dir

Exit code 0 = all checks passed, 1 = at least one failed, 2 = could not run.

Requires: pip install playwright && playwright install chromium
"""
from __future__ import annotations

import argparse
import pathlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_server(base: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(base, timeout=1).read(1)
            return
        except (urllib.error.URLError, OSError):
            time.sleep(0.2)
    raise RuntimeError(f"server at {base} did not come up within {timeout}s")


class Checks:
    """Collects pass/fail lines so one run reports every problem, not just the first."""

    def __init__(self) -> None:
        self.failures: list[str] = []

    def __call__(self, label: str, ok: bool, detail: str = "") -> bool:
        print(("  PASS  " if ok else "  FAIL  ") + label + (f" - {detail}" if detail else ""))
        if not ok:
            self.failures.append(label)
        return ok


def run(base: str, shots: pathlib.Path) -> list[str]:
    from playwright.sync_api import sync_playwright

    check = Checks()
    console_errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("console",
                lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(f"pageerror: {e}"))

        resp = page.goto(base, wait_until="networkidle")
        check("HTTP 200 on /", resp.status == 200, f"status={resp.status}")

        # --- the single story ---
        headline = page.locator("h1").first
        text = headline.inner_text().strip() if headline.count() else ""
        check("headline present", len(text) > 10, repr(text[:70]))
        for cls in ("kicker", "lede", "byline"):
            check(f".{cls} present", page.locator(f".{cls}").count() > 0)

        # --- methodology must be visible to the reader, not just in the repo ---
        for sel, body_sel, label in (("details.why", ".why-body", "methodology"),
                                     ("details.sources", ".sources-body", "sources")):
            panel = page.locator(sel)
            if not check(f"{label} panel present", panel.count() > 0):
                continue
            check(f"{label} collapsed by default",
                  panel.first.get_attribute("open") is None)
            panel.first.locator("summary").click()
            page.wait_for_timeout(300)
            body = page.locator(body_sel).first
            check(f"{label} expands on click", body.is_visible())
            check(f"{label} body has content", len(body.inner_text().strip()) > 40)

        check("coverage map present", page.locator(".covmap, .coverage").count() > 0)
        check("runners-up present", page.locator(".runners").count() > 0)

        # --- newsletter signup ---
        form = page.locator("form.signup-form")
        if check("signup form present", form.count() > 0):
            action = form.first.get_attribute("action") or ""
            check("signup posts to a remote endpoint", action.startswith("http"), action[:60])
            check("signup has an email input",
                  form.first.locator("input[type=email]").count() > 0)

        # --- outbound links ---
        ext = page.locator("a[target=_blank]")
        missing = sum(1 for i in range(ext.count())
                      if "noopener" not in (ext.nth(i).get_attribute("rel") or ""))
        check("target=_blank links carry rel=noopener", missing == 0,
              f"{missing} of {ext.count()} missing")

        # --- every declared icon must actually resolve ---
        icons = page.locator("link[rel~=icon], link[rel=apple-touch-icon]")
        n_icons = icons.count()
        check("icon links declared", n_icons > 0, f"{n_icons} found")
        broken = []
        for i in range(n_icons):
            href = icons.nth(i).get_attribute("href") or ""
            r = page.request.get(f"{base.rstrip('/')}/{href.lstrip('/')}")
            if r.status != 200:
                broken.append(f"{href}={r.status}")
        check("all icon hrefs resolve", not broken, "; ".join(broken))
        # Safari and older Chrome ignore an SVG-only icon: require a raster fallback.
        raster = [icons.nth(i).get_attribute("href") for i in range(n_icons)]
        check("raster favicon fallback declared",
              any(h and h.endswith((".png", ".ico")) for h in raster))
        check("apple-touch-icon declared",
              page.locator("link[rel=apple-touch-icon]").count() > 0)

        # --- OG image resolves (how the link unfurls) ---
        og = page.locator("meta[property='og:image']").first
        if check("og:image declared", og.count() > 0):
            content = og.get_attribute("content") or ""
            local = content.rsplit("/", 2)[-2:] if "/assets/" in content else None
            if local:
                r = page.request.get(f"{base.rstrip('/')}/{'/'.join(local)}")
                check("og:image resolves locally", r.status == 200,
                      f"status={r.status}")

        # --- mobile layout ---
        page.set_viewport_size({"width": 375, "height": 812})
        page.wait_for_timeout(300)
        scroll_w, view_w = page.evaluate(
            "() => [document.documentElement.scrollWidth, window.innerWidth]")
        check("no horizontal scroll at 375px", scroll_w <= view_w + 1,
              f"scrollW={scroll_w} vw={view_w}")

        if shots:
            shots.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(shots / "mobile.png"))
            page.set_viewport_size({"width": 1280, "height": 900})
            page.wait_for_timeout(300)
            page.screenshot(path=str(shots / "desktop.png"), full_page=True)
            print(f"\nscreenshots -> {shots}")

        check("no console errors", not console_errors, "; ".join(console_errors[:3]))
        browser.close()

    return check.failures


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=0, help="port to serve on (default: free port)")
    ap.add_argument("--shots", default=str(REPO / "data" / "smoke-shots"),
                    help="directory for screenshots")
    ap.add_argument("--no-shots", action="store_true",
                    help="skip screenshots (shells make an empty --shots awkward to pass)")
    args = ap.parse_args()
    if args.no_shots:
        args.shots = ""

    if not (REPO / "index.html").exists():
        print(f"no index.html in {REPO} - run the pipeline first", file=sys.stderr)
        return 2
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("playwright not installed: pip install playwright && playwright install chromium",
              file=sys.stderr)
        return 2

    port = args.port or free_port()
    base = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=str(REPO), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_for_server(base)
        failures = run(base, pathlib.Path(args.shots) if args.shots else None)
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()

    print(f"\n{len(failures)} check(s) failed" if failures else "\nall checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
