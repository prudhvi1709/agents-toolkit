---
name: decision-visualization
description: Rules for making one comparison clear and hard to misread, covering which form fits which comparison, honest scales and denominators, direct labeling, and reviewing the rendered output rather than the code. Use when selecting, designing, annotating, reviewing, or verifying a chart, table, map, dashboard, or other visual explanation of data.
---

# Decision Visualization

Make one important comparison easy to see and hard to misread.

## Before building

- State the claim, audience, decision, comparison, unit, denominator, and one
  caveat.
- Decide whether the artifact is for making one point or looking up many values.
- Select the simplest form that supports the comparison: table, line, bar,
  dot plot, scatter, map, or small multiples.

## Trustworthy defaults

- Use rates when counts have unequal denominators.
- Treat dates as dates and show missing periods rather than inventing continuity.
- Start bars at zero. Label intentional axis cropping and transformations.
- Label important series directly where practical.
- Do not use color as the only carrier of meaning. Keep color limited and
  meaningful.
- Avoid pie charts for close comparisons and avoid dual axes unless the two
  scales are explicitly necessary and clearly explained.
- Show uncertainty, sample size, and data freshness when they affect the claim.

## Review the rendered result

Check the source and the output:

- Is the takeaway visible in about five seconds?
- Are labels, legends, annotations, and tooltips readable without overlap?
- Does it work at mobile width and in grayscale?
- Are units, denominators, date ranges, and missing data clear?
- Does the visual still support the claim without the surrounding narration?

For dashboards, optimize scanning, comparison, filtering, and repeat use. For
stories, give the visual one focal point and a headline that states the finding,
not merely the topic.

