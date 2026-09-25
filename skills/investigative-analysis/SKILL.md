---
name: investigative-analysis
description: A process for turning data into a defensible decision, profiling grain and missingness first, establishing a baseline before advanced analysis, stress-testing findings against base rates and confounds, and ranking by impact and defensibility. Use when investigating structured or unstructured data for actionable patterns, business insights, anomalies, segmentation, trends, or evidence-backed recommendations.
---

# Investigative Analysis

Analyze data to answer a decision, not merely to produce numbers.

## Process

1. Define the audience, decision, unit of analysis, time window, and action the
   result could support.
2. Profile the data: schema, grain, duplicates, missingness, ranges, outliers,
   date coverage, joins, and provenance.
3. Establish a simple baseline before advanced analysis.
4. Investigate pattern breaks, extremes, segments, cohort behavior, changes over
   time, and relationships that could overturn an assumption.
5. Explain plausible mechanisms, not just correlations. Check denominators,
   base rates, selection bias, survivorship bias, confounding, and Simpson's
   paradox.
6. Stress-test important findings with alternative definitions, time windows,
   samples, thresholds, or a placebo/random baseline where appropriate.
7. Rank findings by impact, actionability, surprise, and defensibility.

## Rules

- Never claim causality from observational correlation without a credible design.
- Do not display precise metrics when the sample or method cannot support them.
- State what the data cannot establish.
- Prefer median, rates, percentiles, and distributions when averages hide shape.
- Keep raw data and private identifiers out of reports and public repositories.
- Use reproducible scripts and record inputs, transformations, and assumptions.

## Deliverable

Lead with the most useful finding, then provide:

- evidence and comparison baseline;
- caveats and robustness checks;
- recommended action and owner;
- method notes and unanswered questions.

Use clear language for non-technical readers. Put code and detailed methods after
the decision-relevant result.

