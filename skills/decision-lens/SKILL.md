---
name: decision-lens
description: Applies a structured decision procedure that separates facts from assumptions, names the governing trade-offs, picks the few lenses that could change the answer, and verifies with the strongest available check. Use when the task is non-trivial analysis, diagnosis, design, review, strategy, planning, or judgment where assumptions and trade-offs can change the answer. Skip simple lookups, mechanical rewrites, and pure tone edits.
---

# Decision Lens

Use this skill to make difficult work clearer before acting. It applies to
technical decisions, business analysis, product choices, research, design
reviews, debugging, and recommendations.

## Workflow

1. Reframe the request in one sentence: intended outcome, audience, decision,
   constraints, and what would count as success.
2. Separate facts, assumptions, preferences, and unknowns.
3. Identify the one to three principles or trade-offs that govern the decision.
4. Choose the smallest useful set of lenses. Examples: user impact, security,
   operational cost, reversibility, evidence quality, maintainability, and risk.
5. Compare options against the stated success metric. Include the failure mode
   each option is most likely to create.
6. Prefer the strongest verification available: deterministic test, source
   lookup, repository evidence, adversarial example, then uncertainty note.
7. Give a recommendation, the reasoning that changes the decision, and the next
   concrete action. Do not expose private chain-of-thought.

## Defaults

- Prefer a simple reversible option when the evidence is weak.
- Push back on scope that does not improve the outcome.
- Do not manufacture precision, confidence, or metrics unsupported by data.
- Surface privacy, security, licensing, and maintenance risks early.
- Preserve the user's constraints unless explicitly explaining why one is unsafe
  or inconsistent with the goal.

## Output

For meaningful decisions, structure the answer as:

1. Recommendation
2. Decisive reasons
3. Risks and assumptions
4. Next action

