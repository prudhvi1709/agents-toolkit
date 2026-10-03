import type { Receipt } from '../types'
import { localPath, record, text } from '../hooks/model'

export function checkLabel(command: string): string | null {
  // Deliberately recognize simple foreground checks only. Compound shells need
  // a real shell parser before they can provide reliable check attribution.
  const clean = command.trim()
  if (/[;&|<>`\n\r]/.test(clean) || /\$\(|(?:^|\s)(?:--help|--version|--collect-only|--listTests|--list-tests|--watch|-h)(?:\s|$|=)/.test(clean)) return null
  const patterns: [RegExp, string][] = [
    [/^(?:uv run )?(?:python3? -m )?pytest(?:\s|$)/, 'Tests'],
    [/^(?:npm|pnpm|yarn|bun) (?:run )?test(?:\s|$)/, 'Tests'],
    [/^(?:uv run )?ruff check(?:\s|$)/, 'Lint'],
    [/^(?:npm|pnpm|yarn|bun) run lint(?:\s|$)/, 'Lint'],
    [/^(?:uv run )?(?:mypy|ty check)(?:\s|$)/, 'Types'],
    [/^(?:npx )?tsc(?:\s|$)/, 'Types'],
    [/^git diff --check$/, 'Whitespace'],
    [/^claude plugin (?:test|validate)(?:\s|$)/, 'Mod checks'],
    [/^cargo (?:test|check)(?:\s|$)/, 'Rust checks'],
    [/^go test(?:\s|$)/, 'Go tests'],
  ]
  return patterns.find(([pattern]) => pattern.test(clean))?.[1] ?? null
}

export function parseEvidenceScopes(source: string): { command: string; inputs: string[] }[] {
  const value = record(JSON.parse(source))
  if (!Array.isArray(value.checks) || value.checks.length > 32) {
    throw new TypeError('Provide at most 32 check scopes.')
  }
  const commands = new Set<string>()
  return value.checks.map(item => {
    const check = record(item)
    const command = text(check.command, 'command', 1024)
    if (checkLabel(command) === null || commands.has(command)) {
      throw new TypeError('Scopes require distinct, recognized check commands.')
    }
    commands.add(command)
    if (!Array.isArray(check.inputs) || check.inputs.length === 0 || check.inputs.length > 32) {
      throw new TypeError('Provide one to 32 input files or directories per check.')
    }
    const inputs = [...new Set(check.inputs.map(path => localPath(text(path, 'input', 1024))))].sort()
    if (inputs.some(path => /[*?\[\]]/.test(path))) {
      throw new TypeError('Inputs are literal paths, not glob patterns.')
    }
    return { command, inputs }
  })
}

export function putReceipt(receipts: Receipt[], receipt: Receipt): Receipt[] {
  return [...receipts.filter(item => item.id !== receipt.id), receipt].slice(-6)
}
