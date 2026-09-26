---
name: resumable-benchmark
description: Design or run long benchmark, evaluation, crawl, or batch workflows that can resume safely after interruption. Use when work spans many items, launches judges or model calls, requires polling, or risks losing progress between sessions.
---

# Resumable benchmark

Before running, write a small manifest that defines the input snapshot, item
IDs, configuration, model/provider, output directory, retry policy, stopping
condition, and acceptance criteria. Never mix results from incompatible
configurations without labeling them.

For each item, persist an atomic result and an explicit state such as
`pending`, `running`, `succeeded`, `failed`, or `skipped`. On restart, validate
the manifest and resume only pending or retryable items. Do not rerun
successful items unless the user requests a fresh run or the configuration
hash changed.

Record counts for completed, failed, skipped, retried, and remaining items;
timestamps; error classes; and the exact command or configuration needed to
reproduce the run. Keep intermediate output separate from the final report.

Bound retries, concurrency, wall time, and cost. Use a dry run when the
workflow changes data or starts services. Prefer structured JSON/CSV results
and a concise human summary. Report partial completion honestly and make the
next resume command obvious.
