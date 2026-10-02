# Per-iteration review checklist

Run this against the rendered prototype, not the code, before calling a
pass done. Every item is pass/fail - record a fail and its fix, not a
vague "looks okay."

## Viewports

Check every item below at each of these widths unless the project brief
specifies different breakpoints:

- [ ] 375px (mobile)
- [ ] 768px (tablet)
- [ ] 1440px (desktop)

## Motion frames

For any hero or section with animation, capture and check all four states
at every viewport above:

- [ ] first frame
- [ ] a later frame (mid-sequence, not the loop point)
- [ ] paused state (reads correctly with no motion)
- [ ] reduced-motion state (`prefers-reduced-motion: reduce`)

An autoplaying motion that runs more than five seconds alongside content
needs a visible pause/stop/hide control - check it is present and reachable
by keyboard.

## Content and hierarchy

- [ ] Headline and supporting line are the confirmed copy, not placeholder
- [ ] Primary CTA is visually dominant; any secondary CTA is visually quieter
- [ ] Every CTA's destination resolves (no dead `href="#"`, no 404)
- [ ] A first-time visitor can state the offer and find the main CTA from
      the hero alone
- [ ] Detailed workflow cards / comparison controls are below the hero, not
      competing with it

## Brand fidelity

- [ ] Logo file is the approved asset, unmodified (not redrawn, recolored,
      or regenerated)
- [ ] Color values match the approved tokens exactly (compare hex, not by
      eye)
- [ ] No inspiration-image branding or claim leaked into the copy or visuals

## Accessibility

- [ ] Run `scripts/contrast_check.py` against every text and non-text
      pairing actually used on the page; see
      [WCAG text contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
      (4.5:1 normal text, 3:1 large text) and
      [non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)
      (3:1 meaningful controls)
- [ ] Theme switcher (if present) is keyboard-operable and visibly focused
- [ ] Page remains usable with the hero visual removed (visual is additive,
      not load-bearing for comprehension)

## Baseline comparison

- [ ] Compared against the existing HTML/product baseline (if one exists):
      what was preserved, what changed, what's still open
- [ ] Compared against a supplied homepage screenshot (if one exists):
      composition and whitespace, not just content
- [ ] Feedback and the next open question are logged in the project record,
      distinguishing observed issues from preferences and untested
      assumptions
