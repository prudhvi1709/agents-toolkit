---
name: design-handoff
description: Turn design reviews, screenshots, prototypes, and stakeholder feedback into an implementation-ready handoff. Use when moving from design to UI code, reconciling a reference artifact with an existing app, or documenting visual gaps and decisions.
---

# Design handoff

Create or update a focused handoff document, preferably `DESIGN.md` when the
repository uses that convention. Preserve the existing design system and
separate confirmed decisions from suggestions.

The handoff should include:

- goal, audience, and acceptance criteria;
- authoritative references and screenshot paths;
- tokens: color, type, spacing, radius, motion, and responsive behavior;
- screen inventory and states, including loading, empty, error, and language
  variants when relevant;
- component behavior and interaction details;
- implementation mapping to existing files and backend data;
- known mismatches, unresolved questions, and an approval gate;
- verification steps using rendered screenshots, browser checks, and
  accessibility checks.

Do not invent visual requirements from a screenshot when the source is
ambiguous. Mark uncertainty and ask the smallest question that resolves it.
Do not redesign unrelated screens. Before claiming fidelity, render the live
page at the relevant viewports and compare it with the reference.
