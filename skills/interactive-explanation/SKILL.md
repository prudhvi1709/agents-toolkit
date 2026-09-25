---
name: interactive-explanation
description: Guidance for choosing and building an interaction that teaches, matching the form to the learning moment, showing the conclusion without requiring interaction, and keeping the piece usable by keyboard, touch, and reduced motion. Use when building a scrollytelling piece, explorable explanation, simulation, guess-then-reveal interaction, or data story where user action improves understanding.
---

# Interactive Explanation

Use interaction to make a concept easier to understand, not to decorate a page.

## Choose the interaction

- Use scrollytelling for a complex sequence with controlled pacing.
- Use a simulation when system behavior or second-order effects matter.
- Use guess-then-reveal when prediction creates the learning moment.
- Use sliders or scenarios when changing an input should make a relationship
  visible.
- Use progressive disclosure when details would otherwise overload the reader.
- Skip interaction when the message is simple or the interaction hides essential
  information.

## Design contract

- State the reader's question and the insight the interaction should reveal.
- Show the important conclusion without requiring interaction.
- Make state bookmarkable where practical.
- Support keyboard navigation, visible focus, touch, and reduced motion.
- Provide a static or text alternative for important findings.
- Keep input and resulting output close together so users do not lose context.
- Use clear labels, units, defaults, reset behavior, and loading/error states.

## Verification

Test the first-load experience, every meaningful state, mobile layout, keyboard
flow, reduced-motion mode, and the no-JavaScript or static fallback where one is
promised. Check that animations do not hide, overlap, or delay the core message.

