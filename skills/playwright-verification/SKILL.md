---
name: playwright-verification
description: Verifies a live page with Playwright using scripts/verify_page.py, which reports console errors, failed requests, missing accessible names and form labels, heading-order breaks, and horizontal overflow at each viewport width, and exits non-zero so a run can be gated. Use when testing, debugging, or reviewing a web page, dashboard, demo, or browser workflow, or on seeing a claim that a visual or responsive fix works without a rendered page behind it.
---

# playwright-verification

Reading the source tells you what the page should do. Only loading it tells you
what it does. Run the script before claiming a page works.

## Run it

```bash
uv run scripts/verify_page.py http://localhost:8000
uv run scripts/verify_page.py http://localhost:8000 --widths 1440,768,375 --screenshots shots/
uv run scripts/verify_page.py https://example.com --output json --fail-on warning
```

It needs no project install: the dependency is declared inline and `uv` fetches
it. The browser binary is separate, and a missing one exits 3 with the fix
(`uv run playwright install chromium`) rather than a stack trace.

Findings are errors or warnings. Console errors, page exceptions, failed
requests, HTTP 4xx and 5xx, unnamed buttons and links, and unlabelled inputs are
errors. Missing title or `lang`, missing `alt`, heading-order breaks, and
sideways scrolling are warnings. Exit codes: 0 clean, 1 findings at or above
`--fail-on`, 2 usage, 3 the page or browser would not load.

## What it does not cover

The accessibility rules are a handful of high-yield DOM checks, not a WCAG
audit. For a real audit, inject axe-core and run that instead. The script also
loads one URL and does not log in, so put an authenticated page behind
`--wait-for` on a post-login selector, or drive the flow interactively.

## Driving the browser by hand

Use the script for anything repeatable or gated. Use interactive Playwright or
the Playwright MCP server for exploration, multi-step flows, and login.

- Inspect the accessibility tree before choosing selectors, and prefer role and
  accessible name over CSS paths that break on the next restyle.
- Exercise loading, empty, error, and success states, not just the happy path.
- Never mask a flake with a fixed sleep. Wait for a selector, a response, or a
  load state, which is what the timeout in the script waits on.

## When something fails

Capture the screenshot, console error, failing request, and current URL before
changing any code, then reduce it to the smallest page that still reproduces.
Report the viewport and workflow tested, what passed, what still fails, and
where the artifacts are. Do not call a visual fix done without looking at the
rendered result.

## Verify

```bash
uv run scripts/verify_page.py "file://$PWD/scripts/fixture_broken.html" --fail-on warning
# the fixture is deliberately broken: expect 9 errors, 7 warnings, exit 1
```
