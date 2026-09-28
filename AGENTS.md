# Agent Working Agreement

This file contains portable guidance for coding and non-coding agents. Keep
machine-specific paths, credentials, client data, and runtime state outside
version control.

## General

- Inspect the existing project and its conventions before making changes.
- State assumptions when they affect behavior, security, or deployment.
- Prefer the standard library and existing dependencies before adding new ones.
- Keep changes focused and review the final diff before handing work over.
- Treat AI-generated drafts as starting points. Verify claims and reasoning.

## Security and privacy

- Read secrets from environment variables or a secret manager.
- Never log credentials, tokens, personal data, or private transcripts.
- Validate input at trust boundaries and use timeouts for network calls.
- Keep session histories, caches, logs, local settings, and generated state out
  of public repositories.

## Code quality

- Use clear names, typed public interfaces, specific errors, and predictable
  cleanup behavior.
- Prefer small functions and simple control flow over speculative abstractions.
- Add tests for shared behavior and boundary conditions.
- Use the repository's existing formatter, linter, type checker, and test tools.

## Agent workflows

- Read the relevant skill instructions completely before applying a skill.
- Separate analysis, generated drafts, and confirmed user decisions.
- For meeting or transcript workflows, preserve uncertainty and ask for
  confirmation before turning suggestions into commitments.
- Keep provider-specific integrations configurable through environment variables.

## Version control

- Never commit secrets, runtime data, generated caches, or private transcripts.
- Review `git diff` and `git status` before proposing a commit.
- Leave commits and pushes to the repository owner unless explicitly delegated.

