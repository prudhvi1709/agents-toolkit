import { expect, test } from 'claude-code/testing'
import { checkLabel, parseEvidenceScopes } from './model'

test('compound commands and non-running test modes are not check evidence', () => {
  for (const command of ['echo pytest', 'pytest || true', 'pytest; echo ok', 'pytest --collect-only', 'npm test -- --watch', 'pytest --help']) {
    expect(checkLabel(command)).toBe(null)
  }
  expect(checkLabel('uv run pytest -q tests')).toBe('Tests')
  expect(checkLabel('git diff --check')).toBe('Whitespace')
})

test('evidence scopes require exact check commands and safe literal input paths', () => {
  for (const inputs of [[], ['../secret'], ['/private'], ['src/**/*.py']]) {
    expect(() => parseEvidenceScopes(JSON.stringify({ checks: [{ command: 'pytest', inputs }] }))).toThrow()
  }
  expect(() => parseEvidenceScopes(JSON.stringify({ checks: [{ command: 'echo pytest', inputs: ['src'] }] }))).toThrow()
  const scope = { command: 'pytest', inputs: ['src', 'tests'] }
  expect(() => parseEvidenceScopes(JSON.stringify({ checks: [scope, scope] }))).toThrow()
  expect(parseEvidenceScopes(JSON.stringify({ checks: [scope] }))[0]?.inputs).toEqual(['src', 'tests'])
})
