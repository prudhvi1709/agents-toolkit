---
name: architecture-diagrams
description: Create source-backed architecture, workflow, sequence, data-flow, or lifecycle diagrams. Use when the user asks for a system map, service diagram, request trace, pipeline, state diagram, or an explorable standalone diagram.
---

# Architecture diagrams

Turn the requested system into a diagram that can be checked against its source. This adapts Archify's typed-diagram, evidence, and visual-review ideas without requiring its renderer. Source: https://github.com/tt-a1i/archify at `0e4949f` (MIT).

## Choose the form

- Use Mermaid for a small static diagram that fits clearly in chat or Markdown.
- Use a standalone HTML file with inline SVG when the user needs an explorable artifact, many relationships, presentation, or sharing. Keep it self-contained; add interaction only when it helps answer a question. Use a keyboard-accessible focus path and visible labels. Add motion only when requested.
- For UI design implementation, follow `DESIGN.md` and the `design-handoff` skill; this skill maps behavior and relationships, not visual design tokens.

## Build from evidence

1. Choose the smallest view that answers the request: components and boundaries, a workflow, a call sequence, a data pipeline, or states and transitions.
2. For a real repository, inspect entry points, callers, configuration, deployment files, and data contracts. Record the path or document behind each important node and edge. Use `codegraphcontext` for cross-file relationships when available; use ordinary file search for simple lookups.
3. Distinguish observed connections from inferred ones. Label unknown services, ownership, data stores, and security boundaries as unknown rather than filling them in.
4. Draw the main path and behavior-changing branches. Keep the direction and meaning of arrows explicit, including response, retry, failure, and asynchronous paths where they matter.
5. For HTML, define nodes by role and edges by meaning before positioning them. Keep a source reference or explicit assumption with each significant edge. Provide a small source list or click/focus details, readable text, contrast, and a useful static view when scripting is unavailable.

## Review and handoff

- Recheck that every important edge has a source or is labeled as an assumption. Compare the diagram with the actual requested behavior and remove decorative elements that obscure it.
- If an artifact is generated, inspect its rendered result and check labels, crossings, clipping, and keyboard use before claiming visual quality. A source check alone does not establish visual quality.
- Return the artifact path or inline Mermaid, the view type, the source revision if repository-backed, and a short list of unresolved facts. Do not claim Archify's validation or export features unless its actual renderer was used and those gates passed.
