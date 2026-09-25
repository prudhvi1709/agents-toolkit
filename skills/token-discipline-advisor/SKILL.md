---
name: token-discipline-advisor
description: >
  Evaluate whether a proposed token-saving rule (for CLAUDE.md, a skill, or
  an agent instruction) would actually help or would cost task quality, by
  checking it against real usage evidence in the user's agentsview database
  (~/.agentsview/sessions.db) instead of trusting the rule's stated
  rationale. Use when the user asks to add, tighten, or judge any
  instruction aimed at cutting tokens/cost (e.g. truncating tool output,
  limiting reads, capping search, capping images) — before adopting it into
  CLAUDE.md or a skill.
---

## Token-discipline advisor

Purpose: before any "cut tokens" rule goes into CLAUDE.md, a skill, or agent
instructions, check it against real evidence from this user's own sessions
instead of trusting the rule's advertised rationale. Token-saving advice is
routinely wrong for a specific workload even when it's right on average
(see: Caveman claimed -65%, independently measured -8.5%; RTK claimed
-60-90%, independently measured +7.6% cost — self-reported numbers from
these tools are not trustworthy without a local check).

### Data source

The user runs `agentsview` locally, an sqlite db at `~/.agentsview/sessions.db`
that logs every Claude Code / Cowork session: `sessions`, `messages`,
`tool_calls` (with `tool_name`, `category`, `file_path`, `result_content`,
`result_content_length`), `usage_events`. Request folder access to
`~/.agentsview` if not already connected, copy `sessions.db` somewhere
readable (it may be locked/WAL — copy it rather than querying in place), and
query with Python's `sqlite3` module (the `sqlite3` CLI binary is often not
installed in the sandbox).

Correct chronological ordering within a session is `messages.ordinal` joined
via `tool_calls.message_id = messages.id` — `tool_calls.call_index` is NOT a
global ordinal, it only orders calls within a single message and will look
like it resets to 0 repeatedly. Don't order by `call_index` across a session.

### For each proposed rule, run the matching check

**"Truncate/cap large tool output (Bash, exec_command, logs)"** — Before
approving a blind head/tail truncation, check WHERE the signal actually sits
in large outputs for this user: pull `tool_calls` rows for the relevant
tool_name(s) with `result_content_length` above the proposed cap, and find
the position of the first occurrence of error-ish markers (`error`, `failed`,
`traceback`, `exception`, `fatal`) as a fraction of content length. If most
matches cluster in the first or middle portion rather than the last portion,
a tail-only truncation (`tail -n 50`, `| head -c N` from the end) will
regularly cut the one line that mattered — reject or rewrite the rule (e.g.
grep for markers first, or keep both head and tail, rather than blind
tail-cut). If most outputs have no error marker at all, truncating the
success-path noise is safe.

**"Stop re-reading files / cap re-reads"** — Join `tool_calls` (Read) to
`messages.ordinal` per `(session_id, file_path)`, sort by ordinal, and for
each consecutive re-read pair check whether an `Edit`/`Write` on that same
file happened in between. Re-reads that follow an edit are legitimate
(verifying a change) — a blanket "don't re-read" rule would break that
workflow. Re-reads with no edit in between and a small ordinal gap (e.g.
within 1-2 messages) are the real waste — the rule should target only that
pattern, not all re-reads. A re-read separated by a large ordinal gap (tens
of messages later, e.g. after a context compaction) is often a legitimate
refresh, not waste.

**"Stop duplicate searches" (WebSearch/web_fetch)** — Group by session,
lower-case and compare queries; count exact/near-duplicates. If the
duplicate rate is already low (single-digit percent of calls), the rule is
low-risk but also low-reward — fine to add as a light guardrail, don't
oversell the expected savings.

**"Cap image/screenshot viewing"** — Check `view_image` (or equivalent)
`result_content_length` distribution; if average bytes/call is a large
outlier vs other tools, flag it as the highest per-call cost item, but only
recommend "don't re-view the same image twice in a session" — there is
usually no way to know from tool_calls alone whether a second view was
necessary, so don't claim it's provably wasteful without also checking intent
in surrounding message content.

### Output format

For each rule, give a verdict — Safe to adopt / Adopt with a specific
narrower condition / Reject as stated — backed by the actual counts (e.g.
"57% of re-reads had no edit in between, but only 36% of those were within 2
messages — narrow the rule to that subset"). Never approve or reject a rule
on first principles alone once the data is available; the point of this
skill is that intuition about which tokens are "wasted" is frequently wrong
until checked.
