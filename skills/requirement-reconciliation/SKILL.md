---
name: requirement-reconciliation
description: Reconcile new or conflicting scope documents, decks, reference designs, spreadsheets, and stakeholder feedback against accepted requirements and the current implementation. Use when references change mid-project, requested features need a coverage check, or it is unclear whether new material replaces existing scope.
---

# Requirement reconciliation

Produce a source-backed account of what the project now requires, what changed,
and what the current build actually satisfies. Follow the project's existing
documentation convention and update its requirement record rather than creating
a competing source of truth.

## Establish the baseline

- Identify the accepted scope, confirmed user decisions, current implementation,
  and incoming references. Record each source's version/date and useful locators:
  document section, deck page, spreadsheet sheet/cell, design node, or feedback item.
- Compare incoming material with the accepted scope end to end before continuing
  incremental edits. A newer file is not automatically authoritative. Apply explicit
  replacement instructions; flag conflicting sources when precedence is unresolved.
- Separate confirmed requirements, proposals, illustrative examples, and open
  questions. Do not promote a stakeholder suggestion or AI-generated draft to a
  commitment. Preserve the reason for an accepted or rejected decision when known.

## Reconcile with the build

Extract individually checkable requirements. Preserve qualifiers, exclusions,
data mappings, roles, and acceptance conditions; split compound requests where
the implementation could satisfy only part of them. Deduplicate repeated wording
without losing source references. Label inferred requirements as inferred.

Trace each requirement to the relevant implementation and, when available,
observable verification. For a screen, check its place in the user journey,
navigation, state changes, and data behavior as well as visual appearance. A file
or screenshot alone does not demonstrate a working feature.

Use these statuses consistently:

- `verified`: implementation and relevant behavior were checked against the requirement.
- `implemented-unverified`: relevant implementation exists, but the required behavior
  has not been checked or the previous evidence is stale.
- `missing`: a targeted implementation search found no coverage; state the search scope.
- `conflict`: sources or implementation contradict one another; identify both sides.
- `decision-needed`: intent, precedence, or acceptance criteria remain unresolved.
- `deferred`: a confirmed decision explicitly postponed the requirement; cite it.

Treat partial coverage as `implemented-unverified` with the missing part stated,
or split it into separate rows. Do not count a deferred feature as delivered.

## Deliver the reconciliation

Lead with the material scope changes and decisions that affect the next action.
Use a compact matrix, adapting columns to the project's established record:

| ID | Requirement | Source / locator | Change / supersedes | Implementation | Status / evidence | Next action |
| --- | --- | --- | --- | --- | --- | --- |

Keep source statements separate from implementation evidence. Cite concrete paths,
sections, or verification artifacts. State what was not inspected and whether
checks apply to the current source/configuration. Avoid an aggregate completion
percentage when row granularity or coverage would make it misleading.

Ask only about unresolved choices that materially affect the work. Continue
independent reconciliation while answers are pending. Existing authorization to
implement still applies; a request to reconcile alone does not authorize unrelated
implementation, publishing, deployment, or external messages.

For document extraction, use `document-pipeline` when available. Use
`design-handoff` for reviewed design implementation requirements and
`playwright-verification` for relevant live user journeys. These tools support the
matrix; they do not replace the source comparison or decide scope precedence.

Before handing over, check every explicit incoming request has a row or a clear
reason for exclusion, recheck any claim of absence, and preserve unresolved
conflicts instead of silently choosing a convenient interpretation.
