# Evaluate a skill against task outcomes

Use this when deciding whether a substantive instruction change improves a
recurring task. Syntax validation establishes packaging, not task quality.
This is an original workflow inspired by the example-driven comparison in
https://github.com/sanand0/promptevals; it does not copy that implementation.

## Fix the comparison before generating outputs

1. Name the observed failure and the expected behavior change. Choose a few
   sanitized tasks representative of real work, including an awkward boundary
   case. Reserve at least one task that is not used to revise the instructions.
   Do not put private logs, transcripts, client assets, or credentials in fixtures.
2. Snapshot the baseline and candidate skill plus relevant references; record
   their hashes. Keep task inputs, assets, agent/model settings, available tools,
   and generation budget equivalent. Record unavoidable differences. Do not
   import a newer candidate reference into the baseline condition.
3. Define observable acceptance checks before seeing outputs. For UI, use task
   completion, approved brand tokens, readable layouts, and required states.
   For videos, use readable captures, accurate claims, caption/audio timing,
   and a coherent ending. For handoffs, check preserved decisions and source
   locators. Separate factual defects from reviewer preferences.
4. Set a time/cost limit and the allowed side effects. Use temporary workspaces
   and permitted providers. Do not upload private material or install a judge
   merely because the comparison would be easier.

## Run and inspect

- Produce the baseline and candidate outputs independently, so one output does
  not become the other's example. Use the project's established run commands.
  For long or paid batches, use the resumable-benchmark manifest and recovery
  workflow when available; preserve completed work and count paid retries.
- Inspect artifacts with the checks appropriate to the task: execute code,
  exercise a browser journey, or watch/listen to the rendered video. Missing
  tools or unperformed checks remain `unverified`, not `pass`.
- Compare outputs in varied order and hide their condition labels from a
  reviewer when practical. A second model's opinion can suggest defects, but
  it cannot replace executable checks or establish brand approval.
- Keep a small local record per task/condition: input identity, skill/reference
  hashes, runtime settings, artifact locators, checks with `pass`/`fail`/
  `unverified` and evidence, reviewer corrections, elapsed time, and cost or
  `unknown`. Keep private evaluation state outside version control.
- If a task or artifact changes, invalidate the affected result. If the skill
  changes after reviewing a failure, treat it as a new candidate snapshot and
  evaluate the held-out task without tuning on its outcome.

## Decide what to retain

Report the concrete differences and unresolved gaps. A handful of tasks supports
a narrow decision, not a percentage accuracy claim or proof of general quality.
Do not use embedding similarity as a substitute for correctness, visual quality,
or factual fidelity. Prefer the smaller rule when outcomes are equivalent; keep
an improvement provisional until later real work corroborates it.

For a first pilot, use three sanitized tasks: a routine case, a known failure,
and a held-out boundary case. If generation cannot run within the authorized
budget, deliver the cases and acceptance checks and mark execution pending.
