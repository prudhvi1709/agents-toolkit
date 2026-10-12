---
name: isometric-illustrations
description: Create detailed isometric SVG illustrations and interactive physical-mechanism explainers for technical articles, documentation, or product pages. Use when the user wants an isometric object, cutaway, exploded view, or a physical metaphor that explains a mechanism. Ordinary architecture diagrams, charts, and general page design use their own skills.
license: MIT
---

# Isometric illustrations

Adapted from [Anatomy](https://github.com/wheresryan22/anatomy) at
`689dcf966e63d92be10a5d593c6e19e10acd4422`. The bundled drawing library is
MIT licensed; preserve [LICENSE](LICENSE) when copying it into a project or
distributing generated work containing its source. See
[references/upstream.md](references/upstream.md) for the adaptation boundary.

## Choose the illustration

Use a recognizable physical object whose operation explains the idea: a lock
for matching cache keys, a carriage and gauge for displacement, or drawers for
different storage capacities. State what moves and what that movement means.
Make the metaphor's limits explicit when it could imply incorrect behavior.

Keep scope proportional to the request. A small SVG is a valid result; do not
require a minimum part count, animation, both themes, or a multi-hour workflow.
Add parts that clarify structure, support or operation, rather than filling
every empty region. Default to SVG; add interaction only when it teaches the
requested behavior. WebGL is optional for effects SVG cannot convey well.
True rotating 3D and its beta runtime are not bundled.

Use `architecture-diagrams` for actual service relationships and
`interactive-explanation` when the teaching interaction needs design. For a
branded page, `brand-ui-prototyping` owns the page and approved brand tokens;
this skill supplies the illustration. Use the installed `motion` skill and
official motion documentation when exploring website motion options.

## Build from one model

1. Establish the actual counts, sizes, units and behavior from the user's
   sources. Use a pure model to drive geometry, readouts and captions. Label
   illustrative dimensions and assumptions; a geometry audit cannot prove
   scientific or explanatory accuracy.
2. Sketch the object and its purposeful parts before drawing. Read
   [references/craft.md](references/craft.md) for solids, shading, composition,
   painter's order, mounts and pipe routing. These are craft techniques, not
   rules overriding brand choices or the requested level of detail.
3. Read [references/kit.md](references/kit.md) for exact API signatures. Build
   static geometry once, shade by facing, and paint back to front. Put supports
   under parts and terminate cables on real connections. Split a shape when
   another part needs to pass between its front and back.
4. Use [references/motion.md](references/motion.md) for eased motion, input and
   exploded views. Provide keyboard and touch controls, visible focus and
   meaningful accessible values. Stop offscreen animation. Reduced motion
   disables idle tours and uses immediate state updates without spring bounce.
   Clean up observers, event listeners, timers and animation frames on exit or
   component unmount. Keep page state inside a module or closure.
5. Verify the relevant geometry and the rendered artifact using
   [references/verify.md](references/verify.md). Inspect the result at normal
   size and close up where joints or depth order are uncertain.

## Kit and output

Node.js 20.10+ builds the SVG with built-in modules; no package installation is
needed. React output needs the target project's existing React dependency.

- `kit/iso-kit.mjs` and `kit/iso-kit.ts`: projection, solids, parts, SVG strings
  and card/page builders. `kit/iso.css` contains the same theme styles.
- `kit/lathe.mjs`: round parts on arbitrary axes and curved surfaces.
- `kit/tube.mjs`: depth-sortable pipes and cables.
- `kit/audit.mjs`: recorded-shape clearance, supports and painter's order.
  Record the shapes actually drawn and fix geometry rather than hiding failures.
- `kit/react/draw.tsx` and `kit/react/live.tsx`: server-safe drawing components
  and client motion hooks. Read [references/react.md](references/react.md)
  before using the server/client split.
- `kit/gl.mjs`: optional shader layer in the same camera. Read
  [references/webgl.md](references/webgl.md) only for shader work. Retain a
  readable SVG fallback, cap pixel ratio, stop inactive rendering, and release
  graphics resources when removing the figure.
- `scripts/inline-kit.mjs`: `kitScript()` and `glScript()` for trusted generated
  standalone output. `scripts/standalone-page.mjs` wraps `pageHtml` with an
  exact-content CSP, without `unsafe-inline` or `unsafe-eval`.
- `examples/dial-indicator/build.mjs`: the small runnable example. Build in a
  scratch copy with `node examples/dial-indicator/build.mjs`; add `--light` for
  light. Generated pages are ignored in the skill checkout. The example uses
  pixel dimensions to illustrate displacement, not calibrated measurements.

For project integration, copy the needed kit modules and LICENSE into the
project, not runtime imports pointing to a global skill folder. Use ES modules,
external styles and the project's CSP for a website. For a standalone file,
use `standalonePageHtml` from `scripts/standalone-page.mjs`; hashes must be
regenerated if script, style or style attributes change. Dynamic style values
need a project-specific CSP strategy; do not weaken the policy to bypass errors.

The string renderers take trusted build-time SVG and markup. Do not feed user
HTML, arbitrary shader source or runtime input into them. Use textContent for
live text and validate numeric inputs. Local policy permits useful code comments
and takes priority over upstream's no-comments convention.

Return the source and requested artifact, what the mechanism explains, source
facts versus assumptions, and which checks actually ran. Do not describe sampled
geometry checks as proof of every continuous state or every real-world property.
