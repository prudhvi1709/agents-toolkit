# Upstream and local changes

Source: https://github.com/wheresryan22/anatomy
Revision: `689dcf966e63d92be10a5d593c6e19e10acd4422`
Reviewed: 2026-10-12
License: MIT, Copyright (c) 2026 Ryan. The original LICENSE is retained.

The SVG core, lathe, tubes, geometry audit, React components and optional WebGL
layer are adapted copies. ASCII equivalents replace typography in source,
messages and guides. The guides retain API and craft detail; the entrypoint
defines the narrower local workflow. Upstream-only examples remain documented
as references, not as bundled files. The 3D runtime and browser drivers are
excluded. The inline helper exposes only the two bundled runtimes.

Local additions are the scoped SKILL.md, standalone CSP wrapper and verification
guide. The dial example uses the wrapper and cleans up its browser resources.
Mandatory part counts, fixed duration estimates, universal idle animation,
forced themes and upstream's no-comments rule do not apply here. Approved brand
tokens and project security policy take priority.

When updating, compare the pinned revision with upstream changes, preserve the
license, review imports and API guide changes, and rerun the example and relevant
checks in a temporary copy. Do not merge upstream policy back into local routing.
