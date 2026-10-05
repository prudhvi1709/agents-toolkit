---
name: design-handoff
description: Turn design reviews, screenshots, prototypes, and stakeholder feedback into an implementation-ready handoff. Use when moving from design to UI code, reconciling a reference artifact with an existing app, or documenting visual gaps and decisions.
---

# Design handoff

Create or update a focused handoff in the project's existing convention.
Preserve the existing design system and separate confirmed decisions from
suggestions. For initial branded website exploration, use
`brand-ui-prototyping` as the primary workflow; this skill covers the
implementation handoff.

The handoff should include:

- goal, audience, and acceptance criteria;
- selected references and screenshot paths with file/page/frame, version/date, purpose, role,
  state, review status and supporting decision; keep unknown approval explicit;
- tokens: color, type, spacing, radius, motion, and responsive behavior, with
  the governing source; distinguish corporate rules, approved application
  tokens and merely observed reference values;
- screen inventory and states, including loading, empty, error, and language
  variants when relevant;
- component behavior and interaction details;
- implementation mapping to existing files and backend data;
- known mismatches, unresolved questions, and an approval gate;
- consequential review corrections, rationale and resolution, including
  rejected patterns that should not be selected again;
- verification steps and evidence using rendered screenshots, browser checks,
  and accessibility checks, tied to artifact revision, viewport and state;
  mark evidence affected by later changes stale until rechecked.

Explain what each reference contributes and when its pattern would be unsuitable.
Do not treat version labels, sample business claims or AI-generated feedback as
approval. Keep a review-ready draft distinct from an accepted design. Use
`requirement-reconciliation` when incoming feedback changes accepted scope or
conflicts with the existing handoff; preserve the current record and authorization.

Do not invent visual requirements from a screenshot when the source is
ambiguous. Mark uncertainty and ask the smallest question that resolves it.
Do not redesign unrelated screens. Before claiming fidelity, render the live
page at the relevant viewports and compare it with the reference.
