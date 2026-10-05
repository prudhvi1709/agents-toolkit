---
name: brand-ui-prototyping
description: Iteratively explore and prototype branded websites and application screens using approved assets, purpose-matched references, review feedback, and browser checks. Use when a website concept or an application form, dashboard, queue, or document workflow needs visual iteration.
---

# Brand UI prototyping

Move between concept images, design frames, and code prototypes as needed. Keep approved brand rules fixed; revise the proposal through render, feedback, and review cycles.

## Ground the concept

- Map the pages, audience, real content, calls to action, and important states. Always include a homepage direction for a website concept. Mark confirmed facts separately from proposals.
- Before proposing a new direction, inspect any existing HTML, running product, screenshots, or current pages supplied for the project. Treat these as the baseline to understand and improve, not disposable references. Record what to preserve, what appears inconsistent with the brief, and what is unknown. Do not create a disconnected concept before checking this baseline.
- Inspect the project design system and supplied assets. If no path is given, check for a project-specific local asset source. Use approved logos, color values, and theme pairings exactly; never redraw or generate a replacement logo. Read printed color values from a guide screenshot rather than sampling pixels. Treat missing assets as an open input.
- Classify inputs as approved brand/product assets, current implementation, inspiration, or generated concept. Record the source and intended use of each important asset. Never treat an inspiration image or generated image as an approved asset, and never copy its unsupported product claims or identity.
- Select UI references by task purpose, user role, and state rather than visual similarity alone. Record the file/page/frame, version, review status, what to reuse, and when the pattern would be unsuitable. A label such as "latest", "live", or "Final" does not establish approval. Prefer reviewed examples when available; keep unreviewed candidates provisional. Read `references/purpose-patterns.md` for application screens or a mixed-purpose reference collection.
- Keep corporate brand rules, approved application tokens, and observed reference values distinct. Record which source governs each token; flag unresolved precedence instead of inventing a blend, tint, font substitution, or spacing standard.
- Keep a project-local record of sources, copy, decisions, feedback, and each iteration's change and reason; start from `references/project-record.md`. Keep private assets and machine-specific paths outside the shared skill and public repositories.
- Study comparable products when they exist. For a novel product, break the experience into needs such as orientation, explanation, proof, and action; find references for the relevant pieces, then compose a coherent flow. Record the specific contribution of each reference and why it fits. Do not copy its branding or full page. For component and visual discovery, check https://designeer.xyz/llms-full.txt and then each candidate's official documentation and design-system fit.
- Generate or edit concept images when they help compare layout or illustration ideas. Place approved logo files in the composition; never ask an image model to recreate them. Label generated images as concepts, not brand assets.

## Set up the iteration

- First extract the brief from the supplied material: audience, desired outcome, core journey, required pages, real content, interactions, constraints, and assets. Ask only for missing information that could change the page map, hero story, interaction, or delivery. Record lower-impact gaps as explicit assumptions.
- Keep a settled baseline, an assumptions list, and open questions in the project handoff. Once a direction is accepted, preserve it while exploring the next unresolved question. Do not reopen settled choices without new evidence or feedback.
- When the hero direction is genuinely unresolved, show two meaningfully different options using the same confirmed headline, supporting line, CTA paths, brand tokens, and content. Include the visual's role and intended motion or still state in each option. Ask for a focused choice, then record the choice and any adjustments before detailed implementation.

## Shape the homepage

- Write one specific headline and one short supporting line from the confirmed scope. Put detail below the hero. Use one primary CTA for the main task; add a quieter secondary CTA only for a distinct path. Record each destination.
- Choose the hero after seeing the copy, CTA paths, and assets. A centered hero can use a restrained shared background. A split hero puts copy on the left and a relevant product, workflow, person, or use-case visual on the right. Align text, CTAs, and visual by reading order, content length, and visual weight; adjust spacing and alignment at each viewport instead of forcing a fixed grid. For a task-first app, keep the first action visible and reduce artwork that delays it.
- Give each visual a job: show something about the product or clarify a relationship. A workflow illustration should have a few traceable stages, readable labels, and a clear outcome. Use confirmed data or label sample values. Avoid invented metrics, tiny illegible UI, and unrelated abstraction. Background shapes, light, and texture may support hierarchy but should not pose as the product explanation.
- Choose visual treatment from the content and layout: a centered hero may use a restrained background illustration or animation when it leaves the copy clear; a split hero should use a relevant, representative visual in the open column. Use an illustration when it helps explain the product, workflow, or audience; use background motion for atmosphere or a simple concept, not as a substitute for explanation. Keep illustrative detail subordinate to the headline and CTA.
- For a centered hero, decide whether a background illustration or animation helps only after the final copy is in place. For a split hero, animate the right visual when motion explains a process or state change. Plan a readable sequence such as input, transformation, and outcome. The still frame and paused state must also explain the idea. If the layout choice is uncertain, prototype both with the same copy, CTAs, tokens, and viewports, including purposeful motion and reduced-motion states in each.
- Keep the headline and CTAs legible in every frame. Provide a stable reduced-motion state; provide pause, stop, or hide for qualifying autoplay motion lasting over five seconds alongside content. Use [WCAG Pause, Stop, Hide](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html) for the rule.
- Keep the homepage's first impression focused. Move detailed workflow cards and comparison controls below the hero. Use supplied screenshots to judge hierarchy, density, and polish without copying unsupported claims or another project's visual language.

## Extend to inner pages

- Carry the hero's accepted tokens, typography, spacing scale, and logo usage into every other page in the page map. An inner page drifting from the homepage's visual decisions is a regression, not a fresh design opportunity.
- Reuse one shared navigation and footer across pages unless the brief calls for a distinct one, such as a focused signup flow. Record any intentional per-page departure and why in the decision log.
- Give each inner page a primary CTA suited to its own job (a pricing page's CTA differs from the homepage's), but keep its visual treatment, hierarchy, and placement consistent with the homepage's CTA pattern.
- Hold inner pages to the same `references/review-checklist.md` and viewports as the homepage. A direction is not accepted until its inner pages hold up too, not just the hero.

## Shape application screens

- For an application task, start from the working area and its primary action; a homepage hero or shared website footer is not a prerequisite. Preserve the accepted application shell and component system.
- Choose the appropriate form, dashboard, queue, administration, or document-workflow pattern from `references/purpose-patterns.md`. Match information density and context panes to the task, role, and states; do not combine unrelated patterns merely to show more features.
- Check alignment, grouping, repeated-control consistency, task hierarchy, and relevant permission/loading/empty/error states. Verify data definitions and agreement between totals, labels, denominators, and narrative claims. Keep sample content labeled and separate from business facts.

## Iterate and review

1. Name one question for the next pass, such as layout, illustration relevance, or theme pairing. Preserve an accepted baseline and promising alternatives.
2. Make the smallest useful change in image, design, or code. Keep approved logos, palette, copy, and accepted decisions fixed.
3. Run the applicable checks in `references/review-checklist.md` against the render at 375/768/1440px (or the project's own supported viewports). Can a first-time user understand the offer or complete the screen's primary task? Does the visual add understanding? Compare first, later, paused, and reduced-motion frames when motion exists. If a homepage screenshot was supplied, compare composition and whitespace with the render. Seek task-based feedback when possible.
4. Check the render against the supplied current HTML or product baseline as well as the brief. Review what was preserved, changed, or still needs a decision. Log feedback, decision, and the next question in `references/project-record.md`; distinguish observed issues from preferences and assumptions.
5. Use the agreed iteration budget; if none was given, state a small corrective-pass budget before starting. Continue only while a named defect or unresolved design question justifies the next pass. Stop when the applicable checks are satisfied, the budget is reached, or another pass needs a material decision. Hand over the best current draft with remaining defects and questions; agent judgment establishes review readiness, not reviewer acceptance. Show subjective choices for review; never infer full approval of every open item from a general reply like "looks fine".
6. Tie screenshots and interaction checks to the artifact revision, viewport, and state. After relevant code, token, copy, or configuration changes, mark affected evidence stale and rerun those checks before relying on it. Preserve unaffected evidence with its scope rather than restarting every check.

## Prototype and hand off

- Build the selected direction with semantic, responsive HTML and CSS, real text, and working CTA destinations. Do not use a full-page generated image as the interface. If two directions remain under review, keep both accessible as separate variants.
- For multiple approved themes, place a keyboard-usable switcher at the lower right of the review prototype. Switch shared tokens, check small screens, and use only approved pairings.
- Run `scripts/contrast_check.py` against every pairing actually used on the page rather than judging by eye; see [text contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) and [non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html): 4.5:1 for normal text, 3:1 for large text and meaningful controls. If an approved pairing fails, switch to another approved pairing or permitted support color; never alter the swatch value to force a pass.
- Render each theme at desktop and mobile sizes. Check logo fidelity, legibility, interactions, and reduced-motion behavior against the accepted baseline. Use playwright-verification for a live page and design-handoff for an implementation handoff.
- After acceptance, hand over the page map, approved sources, references and their contribution, chosen direction, prototype, decisions, and open questions. If review is pending, preserve the baseline and next question. Keep client-specific decisions in the project handoff, not this skill.
