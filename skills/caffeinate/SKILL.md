---
name: caffeinate
description: Design and launch unattended long-running jobs on macOS using scripts/caffeinate.py, which holds a caffeinate sleep assertion, refuses to start on battery or a full disk, enforces a wall-clock deadline, and kills the whole process tree on exit. Use when a pipeline, crawl, batch, or agent loop must run overnight or for hours with nobody watching, or on seeing caffeinate, nohup, or a job that outlives the session.
---

# caffeinate

Nobody is awake to answer a prompt, approve a step, or restart a stage that died.
That one fact drives every rule here.

## Launch

```bash
uv run scripts/caffeinate.py --until 07:00 -- python3 pipeline/overnight.py --run
uv run scripts/caffeinate.py --max-hours 6 --dry-run -- ./crawl.sh
```

Always `--dry-run` first: it runs the preflight and prints the plan without
starting anything. The wrapper refuses to start on battery (macOS sleeps after
1 minute idle on battery, so the run would die), on low disk, when another run
holds `.caffeinate.lock`, or with a nonsensical deadline. Waive a check only
deliberately, with `--allow-battery` or `--min-free-gb`.

The sleep assertion is bound to the runner's pid, so it cannot outlive the job
even if the runner is killed. The job gets its own process group, so the deadline
terminates everything it spawned, not just the direct child. Exit codes: 0 ok,
1 command failed, 2 usage, 3 preflight refused, 4 deadline reached, 130
interrupted.

Keep the lid open. `caffeinate` does not prevent sleep on lid close unless the
Mac is on AC with an external display attached.

## Designing the job it runs

These are properties of the job itself; the wrapper cannot supply them.

- **Best-effort stages.** A failing stage is logged and skipped, never fatal. A
  partial night is worth far more in the morning than a clean stack trace at 2 AM.
- **Append-only.** Nothing deletes, truncates, or overwrites a source file.
  Re-running must be safe, so writes go to new records or a merge step.
- **Order for truncation, not for tidiness.** Any pass long enough to need a
  timeout will be cut short by it. Process the highest-value inputs first so a
  truncated run still produces a usable result.
- **Overlap independent stages.** Stages that share no inputs should run
  concurrently. Running them in series wastes most of the night.
- **Resumable.** Persist the frontier or cursor to disk so a terminated stage
  resumes instead of restarting.
- **Never spend money unattended.** Build the harness, leave the paid run for a
  human in the morning, and say so in the report.
- **Bound every stage.** Give each stage its own timeout, and escalate
  terminate to kill so a wedged stage cannot eat the night.

## Leaving a trail

Write two artifacts as the run proceeds, not at the end, because the run may not
reach the end:

1. An append-only decision log, one entry per decision, each with a timestamp and
   a `Why:`. Never rewrite earlier entries. The morning review should be a
   document to read, not an interrogation.
2. A morning report naming what changed (before and after counts), which stages
   passed, what to look at first, and an explicit "needs a human" list.

## Gotcha that costs a night

Editing the orchestrator while it runs does nothing: Python already holds the
module in memory. Put a mid-run fix in a script the orchestrator launches as a
fresh subprocess, or accept that it applies to the next run.

## Verify

```bash
uv run scripts/caffeinate.py --max-hours 0.001 --grace 2 -- sh -c 'sleep 600 & wait'
echo "exit=$?"; pgrep -fl 'caffeinate -i -m -w'; pgrep -fl 'sleep 600'; ls -a | grep lock
# expect: "deadline reached", exit 4, and all three checks empty
```

Match the assertion by its `-w` pattern, not the bare name: editors and other
tools hold their own `caffeinate` processes, and a bare name check reports those
as a leak.
