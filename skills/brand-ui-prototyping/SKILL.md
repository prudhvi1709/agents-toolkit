---
name: brand-ui-prototyping
description: Iteratively explore and prototype branded website pages using approved assets, real content, visual references, review feedback, and browser checks. Use when a homepage or multi-page UI concept needs multiple visual passes and an interactive theme comparison.
---

# Brand UI prototyping

Turn a page scope into a reviewed visual direction and working HTML prototype through repeated concept, render, feedback, and revision cycles. A concept image, Figma frame, or code prototype can be the starting point; move between them as the work reveals new issues. Keep approved brand rules fixed while proposals evolve.

## Establish the brief

- Inventory the requested pages, their purpose, audience, content, calls to action, and important states. Read the actual homepage copy before choosing a hero layout. Record what is confirmed and what is still a proposal.
- Inspect the project's existing design system and user-provided brand assets. If paths are not given, check for a user-local asset source configured for this project, then inspect its color guide and logo files; never use another project's sources as a default. Treat approved logos, color values, and theme definitions as fixed. Use the supplied files and exact values; do not redraw, recolor, approximate, or replace them with generated versions. If an asset type is unavailable, identify the missing input and keep any affected concept explicitly provisional.
- A screenshot of a brand guide is evidence for its written swatches and pairing rules, not a reusable logo or image asset. Read printed hex values rather than sampling screenshot pixels. Distinguish approved color groupings from a loose palette before offering themes.
- Keep a project-local working record of approved assets and pairings, real copy, page scope, current concept and prototype paths, decisions, feedback, and open questions. Record each iteration's specific change and reason so later passes preserve accepted decisions. Keep private client assets and machine-specific paths outside this shared skill and public repositories.

## Find a visual direction

- For a familiar product category, study comparable live products for relevant patterns. For a novel product, break the page into jobs such as orientation, explanation, proof, and action; find a reference for each job, then compose a coherent flow. Record source links and the specific pattern borrowed. Do not copy a full page or mistake a reference's branding for the project's branding.
- When exploring frontend components or visual directions, use https://designeer.xyz/llms-full.txt to find candidates, then check each candidate's official documentation and fit with the existing design system.
- Generate or edit images to explore layout, atmosphere, and illustration ideas when a static visual will clarify the choice. Use an approved logo file in the composition rather than asking an image model to recreate it. Carry approved colors through the exploration, and label generated images as concepts rather than brand source files. Compare viable directions against content length, clarity, and brand fit before selecting one.
- Choose the hero composition from the content, not a fixed template. For dense copy, favor a stable, readable background. A centered, concise hero may use restrained background motion. A split hero may use a representative illustration on the open side. Illustration can be 2D or 3D, but it should communicate the product or use case rather than serve as unrelated abstract decoration. Animation is optional; preserve readability and support reduced motion.

## Iterate with evidence

1. Name the question for the next pass, such as hero composition, content hierarchy, illustration relevance, or a theme pairing. Keep a usable baseline and preserve promising alternatives.
2. Make the smallest useful change in the image, design, or code. State what must stay fixed, especially logo, palette, copy, and accepted layout decisions. For a new direction, branch from the baseline instead of overwriting it.
3. Review the result with real content at desktop and mobile sizes. Check whether a visitor can understand the offer and act, whether the illustration explains anything, and whether the design respects brand and accessibility constraints. Use task-based feedback from representative users when available; designer preference alone does not establish usability.
4. Turn feedback into a concrete next change or a recorded decision. Distinguish observed problems, stakeholder preferences, and untested assumptions. Continue the cycle; a code render may send the work back to image exploration or layout design. Show a reviewable version when subjective direction needs the user's or design owner's input, and never infer approval from silence.

## Make the concept reviewable

- Translate the selected direction into semantic, responsive HTML and CSS with real text and working interactions. Recreate the layout with elements and reusable tokens; do not use a full-page generated image as the interface. Preserve approved logo files and palette values.
- When multiple approved themes exist, add a usable theme switcher at the lower right of the review prototype. Switching must visibly update the page through shared theme tokens, preserve contrast, work by keyboard, and remain usable on small screens. Do not invent unapproved brand colors to fill missing theme values.
- Check each theme's actual pairings against [WCAG 2.2 text contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) and [non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html): 4.5:1 for normal text, 3:1 for large text, and 3:1 for meaningful control indicators. If an approved swatch pairing fails, choose another approved pairing or permitted support color; do not alter the swatch value.
- Show the concept image beside or linked from the prototype when useful, and explain intentional differences between the image and implementation. Render and inspect every approved theme at relevant desktop and mobile sizes, including content legibility, logo fidelity, keyboard theme switching, and reduced-motion behavior. Compare new renders with the accepted baseline in a consistent browser environment; inspect meaningful differences rather than accepting a screenshot diff alone. For a live page, use `playwright-verification`; for an implementation handoff, use `design-handoff`.

## Hand off

When the direction satisfies the brief and the user or design owner accepts it, provide the page map, approved asset and token sources, reference links with what each contributed, chosen visual direction, prototype location, accepted decisions, and remaining implementation questions. If feedback is still pending, preserve the current baseline and next question so the following session resumes the loop. Keep client-specific decisions in the project handoff, not in this reusable skill.
