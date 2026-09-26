---
name: deployment-preflight
description: Verify a project is ready to deploy, publish, or hand off for release. Use when preparing deployment, production-like testing, release packaging, or deciding whether a change is ready to ship. Do not deploy automatically.
---

# Deployment preflight

Perform a read-only release check first. Inspect the repository's existing
deployment convention and verify:

- working tree and intended diff;
- required build, lint, type-check, and test commands;
- runtime entry point and health check;
- environment variable names without printing values;
- dependency lockfile and generated artifacts;
- port collisions and stale local processes when running locally;
- `.gitignore`/`.deployignore` coverage without excluding runtime assets;
- migration, data, authentication, and rollback risks;
- browser console, network, accessibility, and responsive checks for UI work.

Return `ready`, `ready with warnings`, or `not ready`, with evidence and the
smallest blocking actions. A missing check is unknown, not passing. Never
claim deployment succeeded unless the user authorized the deployment and the
actual result was observed. Never expose secrets or put them in deployment
files.
