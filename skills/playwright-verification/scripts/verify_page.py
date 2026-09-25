#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright>=1.49"]
# ///
"""Load a page in Chromium and report what a reviewer would otherwise miss.

Collects console errors, failed requests, accessible-name gaps, and horizontal
overflow at each viewport width, then exits non-zero if anything at or above
the chosen severity was found, so an agent or CI job can gate on it.

Deliberate ceiling: the accessibility checks here are a handful of high-yield
DOM rules, not a WCAG audit. For a real audit inject axe-core and run that.

Exit codes:
  0   nothing at or above --fail-on
  1   findings at or above --fail-on
  2   usage error
  3   the page or the browser could not be loaded
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

DEFAULT_WIDTHS = "1280,375"
DEFAULT_HEIGHT = 900
DEFAULT_TIMEOUT_MS = 30_000

# One pass over the DOM for the rules that catch the most real defects. Returns
# plain data so nothing but strings crosses back from the page context.
AUDIT_JS = """
() => {
  const text = (el) => (el.textContent || '').trim();
  const named = (el) =>
    text(el) ||
    el.getAttribute('aria-label') ||
    el.getAttribute('aria-labelledby') ||
    el.getAttribute('title') ||
    Array.from(el.querySelectorAll('img[alt]')).some((i) => i.getAttribute('alt').trim());
  const where = (el) => {
    const id = el.id ? `#${el.id}` : '';
    const cls = (el.className && typeof el.className === 'string')
      ? '.' + el.className.trim().split(/\\s+/).slice(0, 2).join('.')
      : '';
    return `${el.tagName.toLowerCase()}${id}${cls}`;
  };

  const out = { title: document.title || '', lang: document.documentElement.lang || '', issues: [] };
  const add = (rule, detail) => out.issues.push({ rule, detail });

  if (!out.title) add('title', 'page has no title element');
  if (!out.lang) add('lang', 'html element has no lang attribute');

  for (const img of document.querySelectorAll('img:not([alt])')) {
    add('img-alt', `${where(img)} src=${(img.getAttribute('src') || '').slice(0, 60)}`);
  }
  for (const el of document.querySelectorAll('button, a[href], [role=button]')) {
    if (!named(el)) add('accessible-name', where(el));
  }
  for (const el of document.querySelectorAll('input:not([type=hidden]), select, textarea')) {
    const id = el.getAttribute('id');
    const labelled =
      (id && document.querySelector(`label[for="${CSS.escape(id)}"]`)) ||
      el.closest('label') ||
      el.getAttribute('aria-label') ||
      el.getAttribute('aria-labelledby') ||
      el.getAttribute('title');
    if (!labelled) {
      const only = el.getAttribute('placeholder') ? ' (placeholder is not a label)' : '';
      add('form-label', where(el) + only);
    }
  }

  const levels = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6'))
    .map((h) => Number(h.tagName[1]));
  for (let i = 1; i < levels.length; i += 1) {
    if (levels[i] - levels[i - 1] > 1) {
      add('heading-order', `h${levels[i - 1]} is followed by h${levels[i]}`);
      break;
    }
  }
  if (levels.length && levels[0] !== 1) add('heading-order', `first heading is h${levels[0]}, not h1`);

  return out;
}
"""


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class Finding:
    severity: Severity
    source: str
    detail: str
    viewport: str = ""


class PageError(RuntimeError):
    """The page or the browser could not be loaded."""


def parse_widths(raw: str) -> list[int]:
    try:
        widths = [int(part) for part in raw.split(",") if part.strip()]
    except ValueError as err:
        raise ValueError(f"--widths must be comma-separated integers, got {raw!r}") from err
    if not widths:
        raise ValueError("--widths needs at least one width")
    return widths


def audit_viewport(page, width: int, *, screenshots: Path | None) -> list[Finding]:
    """Re-check layout-dependent rules at one viewport width."""
    label = f"{width}px"
    page.set_viewport_size({"width": width, "height": DEFAULT_HEIGHT})
    page.wait_for_timeout(250)  # let responsive layout settle before measuring

    findings: list[Finding] = []
    overflow = page.evaluate(
        "() => ({ scroll: document.documentElement.scrollWidth, inner: window.innerWidth })"
    )
    if overflow["scroll"] > overflow["inner"] + 1:
        findings.append(
            Finding(
                Severity.WARNING,
                "layout",
                f"content is {overflow['scroll']}px wide in a {overflow['inner']}px viewport, "
                "so the page scrolls sideways",
                label,
            )
        )
    if screenshots is not None:
        screenshots.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=screenshots / f"{width}.png", full_page=True)
    return findings


def verify(
    url: str, *, widths: list[int], timeout_ms: int, wait_for: str | None, screenshots: Path | None
) -> tuple[list[Finding], dict[str, str]]:
    findings: list[Finding] = []
    console: list[Finding] = []
    network: list[Finding] = []

    with sync_playwright() as driver:
        try:
            browser = driver.chromium.launch()
        except PlaywrightError as err:
            raise PageError(
                f"could not launch Chromium: {err}\nInstall it with: uv run playwright install chromium"
            ) from err

        page = browser.new_page(viewport={"width": widths[0], "height": DEFAULT_HEIGHT})
        page.on(
            "console",
            lambda msg: console.append(Finding(Severity.ERROR, "console", msg.text[:300]))
            if msg.type == "error"
            else console.append(Finding(Severity.WARNING, "console", msg.text[:300]))
            if msg.type == "warning"
            else None,
        )
        page.on(
            "pageerror",
            lambda exc: console.append(Finding(Severity.ERROR, "pageerror", str(exc)[:300])),
        )
        page.on(
            "requestfailed",
            lambda req: network.append(
                Finding(Severity.ERROR, "network", f"{req.method} {req.url[:120]} failed")
            ),
        )
        page.on(
            "response",
            lambda res: network.append(
                Finding(Severity.ERROR, "network", f"{res.status} {res.url[:120]}")
            )
            if res.status >= 400
            else None,
        )

        try:
            response = page.goto(url, timeout=timeout_ms, wait_until="load")
        except PlaywrightError as err:
            browser.close()
            raise PageError(f"could not load {url}: {err}") from err

        if response is None:
            findings.append(Finding(Severity.WARNING, "navigation", "no response object returned"))
        elif response.status >= 400:
            findings.append(
                Finding(Severity.ERROR, "navigation", f"{url} returned HTTP {response.status}")
            )

        if wait_for:
            try:
                page.wait_for_selector(wait_for, timeout=timeout_ms)
            except PlaywrightError as err:
                browser.close()
                raise PageError(f"--wait-for selector {wait_for!r} never appeared: {err}") from err

        audit = page.evaluate(AUDIT_JS)
        for issue in audit["issues"]:
            severity = Severity.ERROR if issue["rule"] in {"accessible-name", "form-label"} else Severity.WARNING
            findings.append(Finding(severity, issue["rule"], issue["detail"]))

        for width in widths:
            findings.extend(audit_viewport(page, width, screenshots=screenshots))

        browser.close()

    findings = console + network + findings
    return findings, {"title": audit["title"], "lang": audit["lang"] or "(none)"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verify_page.py",
        description="Load a page in Chromium and report console, network, accessibility, and layout defects.",
        epilog=(
            "examples:\n"
            "  verify_page.py http://localhost:8000\n"
            "  verify_page.py http://localhost:8000 --widths 1440,768,375 --screenshots shots/\n"
            "  verify_page.py https://example.com --output json --fail-on warning\n\n"
            "exit codes: 0 clean, 1 findings at or above --fail-on, 2 usage, 3 page/browser failure"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("url", help="page to verify")
    parser.add_argument("--widths", default=DEFAULT_WIDTHS, help=f"viewport widths (default {DEFAULT_WIDTHS})")
    parser.add_argument("--wait-for", metavar="SELECTOR", help="wait for this selector before auditing")
    parser.add_argument("--screenshots", type=Path, metavar="DIR", help="write a full-page shot per width")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_MS, help="navigation timeout in ms")
    parser.add_argument("--fail-on", choices=("error", "warning"), default="error", help="lowest failing severity")
    parser.add_argument("--output", choices=("text", "json"), default="text", help="report format")
    return parser


def render_text(url: str, findings: list[Finding], info: dict[str, str]) -> str:
    out = [f"{url}", f"  title: {info['title'] or '(none)'}   lang: {info['lang']}"]
    if not findings:
        out.append("  no findings")
        return "\n".join(out)
    for severity in (Severity.ERROR, Severity.WARNING):
        group = [f for f in findings if f.severity is severity]
        if not group:
            continue
        out.append(f"\n  {severity.value} ({len(group)})")
        for f in group:
            where = f" [{f.viewport}]" if f.viewport else ""
            out.append(f"    {f.source}{where}: {f.detail}")
    return "\n".join(out)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.url.startswith(("http://", "https://", "file://")):
        parser.error(f"url must start with http://, https:// or file://, got {args.url!r}")
    try:
        widths = parse_widths(args.widths)
    except ValueError as err:
        parser.error(str(err))

    try:
        findings, info = verify(
            args.url,
            widths=widths,
            timeout_ms=args.timeout,
            wait_for=args.wait_for,
            screenshots=args.screenshots,
        )
    except PageError as err:
        print(f"error: {err}", file=sys.stderr)
        return 3

    if args.output == "json":
        print(
            json.dumps(
                {"url": args.url, **info, "findings": [asdict(f) for f in findings]},
                indent=2,
            )
        )
    else:
        print(render_text(args.url, findings, info))

    failing = (
        {Severity.ERROR} if args.fail_on == "error" else {Severity.ERROR, Severity.WARNING}
    )
    return 1 if any(f.severity in failing for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
