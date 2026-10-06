# Automatic knowledge from Claude and Codex history

No separate notes folder or repeated skill mention is required. At session start
or resume, coding agents check index coverage, request a bounded project brief
when prior context matters, and read focused evidence. Hourly refresh keeps the
persisted scope current. This workflow retrieves historical knowledge; it does
not automatically extract facts or treat every conversation as a decision.

 The backend indexes conversation text
from known Claude Code and Codex JSONL locations, restricted to explicitly
selected project paths. It stores normalized text, record hashes, session and
project relationships, and reviewed memory records in a private local SQLite
database. It does not invoke a model, make embeddings, change retention settings,
or read desktop chat stores. Tool arguments, tool results, reasoning and common
injected context blocks are excluded. Common credential patterns are redacted;
this is not comprehensive secret or client-data detection.

## CLI for coding agents

Resolve the installed skill symlink to the canonical checkout. Use the pinned
runtime at `<toolkit>/mcps/local-context` and the script at
`<toolkit>/skills/local-context-search/scripts/history_search.py`:

```bash
uv run --frozen --offline --project <toolkit>/mcps/local-context python <script> status
uv run --frozen --offline --project <toolkit>/mcps/local-context python <script> brief --project /path/to/project
uv run --frozen --offline --project <toolkit>/mcps/local-context python <script> search 'brand fonts' --project /path/to/project
uv run --frozen --offline --project <toolkit>/mcps/local-context python <script> read <turn-id> --part 0
```

Search returns locators by default. Use `--excerpts` only when needed; the
default selected-record budget is 6000 serialized ASCII characters, not an
exact model token count. Each read returns at most 3000 characters of source
text. Search is stemmed and uses literal AND-matched words, with `--match any`
as an explicit broader fallback. Duplicate passages are suppressed from results.
Use `--role user` to locate user requirements and corrections without ranking
assistant prose above them. Keyword search can miss synonyms; do not infer
absence from one failed query. Working subdirectories resolve to their approved
project root; queries outside registered scope fail explicitly.

## Indexing and resume

This is a local write operation. Use it only for approved history/project scope:

```bash
uv run --frozen --offline --project <toolkit>/mcps/local-context python <script> index --project /path/to/project
```

The private database defaults to `~/.local/share/agents-toolkit/history.sqlite`.
Use `--db` before the command for an isolated trial. Scope cannot silently
expand: changed projects require a separate database. Historical project paths
may be moved or deleted; registered paths select log metadata and do not
authorize reading project files. Home-directory sessions match only that exact
working directory, so they do not silently cover unregistered projects. Build a replacement index privately, verify
coverage and preserve reviewed memories before switching the active database. Indexing resumes at
complete JSONL records, commits each file and cursor atomically, detects prefix
rewrites/truncation, and skips duplicate record identities. `--max-files` bounds
a trial run. Original logs are not modified. Cached indexed text remains when
logs disappear, but is labeled `cached_only` and cannot establish new confirmed
memory without a current original. Coverage reports unsupported, malformed,
oversized and out-of-scope records. Unsupported is often expected noise, not
necessarily missing conversational evidence; unknown formats still need review.

## Reviewed memories and relationships

The local-only `remember` command records a short requirement, decision,
correction, question or finding with a supporting turn ID. It defaults to
`candidate`. Use `--confirmed` only after reviewing clear user approval that
supports the exact claim. It rejects assistant-only and stale sources, but
cannot itself judge whether a user's wording expresses approval. Do not infer
approval from "maybe", an unrelated "yes", or an assistant completion claim.

Use `--supersedes <memory-id>` only when the source explicitly replaces the old
decision. Both records remain; a confirmed replacement hides the earlier record
from the default briefing. Project -> session -> turn -> source and memory ->
evidence / superseded-memory relationships are stored in ordinary tables.
No graph database or automated relationship extraction is required.

## Desktop and optional Obsidian

The same backend is exposed through the existing read-only desktop MCP as
`history_status`, `search_history`, `read_history`, and `project_brief`. Desktop
tools cannot index logs or create confirmed memory. Retrieved content enters
the receiving app's conversation. Desktop application connection status must
be checked independently; a working stdio test is not proof of app access.

## Generated Obsidian review vault

Obsidian is an optional local review interface. The SQLite database remains the
retrieval source; agents do not need the app, CLI registration or community
plugins. The exporter creates project, memory and bounded evidence notes with
links for Graph view, plus a Reviews folder for personal annotations. Original
log paths and historical excerpts are private. Keep the vault outside Git and
leave cloud sync disabled unless separately authorized.

From the toolkit root:

```bash
uv run --frozen --offline --project mcps/local-context python scripts/obsidian_memory.py export
uv run --frozen --offline --project mcps/local-context python scripts/obsidian_memory.py export --apply
uv run --frozen --offline --project mcps/local-context python scripts/obsidian_memory.py refresh --apply
uv run --frozen --offline --project mcps/local-context python scripts/obsidian_memory.py schedule --apply
```

Commands audit by default. The vault defaults to
`~/.local/share/agents-toolkit/Agent Memory`; use `--db` and `--vault` before the
subcommand for a separate trial. Open that folder as a vault in Obsidian, then
open Home or Graph view. App installation and opening are separate from export.

`refresh` incrementally indexes only the database's persisted project scope,
then exports its view. `schedule --apply` registers the user LaunchAgent
`local.agents-toolkit.obsidian-memory` to run once on load and hourly thereafter.
It uses the pinned offline runtime, takes an overlap lock and writes only
aggregate status or sanitized errors under the private `obsidian-state` folder.
The job depends on this checkout remaining at its configured path. Inspect it
with `launchctl print gui/$(id -u)/local.agents-toolkit.obsidian-memory`; to stop
it, run `launchctl bootout gui/$(id -u)/local.agents-toolkit.obsidian-memory` and
remove its matching plist from `~/Library/LaunchAgents`.

Refresh preserves user-created notes and never deletes old generated notes.
Ownership hashes prevent overwriting edited or conflicting notes; a recovery
journal allows interrupted writes to resume. Create annotations in Reviews.
If you edit a generated note, move the edit to Reviews and restore the generated
version before refreshing. Candidate memories, cached evidence and superseded
records remain labeled. Reviews are not automatically imported, approved or
used to rewrite the index. Ask an agent to reconcile a review with the original
source and current build before recording a new memory.
