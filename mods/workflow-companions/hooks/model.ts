import type { Chai, Choice, Companions, Hero, Receipt } from '../types'

export function initialState(root = ''): Companions {
  return {
    root, receipts: [], evidenceError: null, editVersion: 0,
    chaiPath: null, isChaiHidden: false, chai: null, chaiError: null,
    hero: null, heroRevision: '', choice: null, reason: '', heroError: null,
    tab: 'ghost',
  }
}

export function localPath(value: string): string {
  if (!value || value.length > 1024 || /[\x00-\x1f\x7f\\:]/.test(value) || value.startsWith('/')) {
    throw new TypeError('Use a relative path inside this project.')
  }
  const parts = value.split('/').filter(part => part !== '.' && part !== '')
  if (parts.length === 0 || parts.some(part => part === '..')) {
    throw new TypeError('Use a relative path inside this project.')
  }
  return parts.join('/')
}

function record(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError('Expected a JSON object.')
  }
  return value as Record<string, unknown>
}

function text(value: unknown, name: string, limit = 160): string {
  if (typeof value !== 'string' || !value.trim() || value.length > limit || /[\x00-\x1f\x7f]/.test(value)) {
    throw new TypeError(`${name} must be a short, non-empty string without control characters.`)
  }
  return value.trim()
}

function integer(value: unknown, name: string): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) {
    throw new TypeError(`${name} must be a non-negative integer.`)
  }
  return value
}

export function parseChai(source: string): Chai {
  const value = record(JSON.parse(source))
  const completed = integer(value.completed, 'completed')
  const total = integer(value.total, 'total')
  const retrying = integer(value.retrying ?? 0, 'retrying')
  if (completed > total || retrying > total - completed) throw new TypeError('Progress counts exceed total.')
  const status = value.status
  if (status !== 'running' && status !== 'paused' && status !== 'done' && status !== 'failed') {
    throw new TypeError('status must be running, paused, done, or failed.')
  }
  if (status === 'done' && completed !== total) throw new TypeError('A done job must have completed its total.')
  const heartbeat = text(value.heartbeat_at, 'heartbeat_at')
  if (!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(heartbeat)) {
    throw new TypeError('heartbeat_at must be an ISO 8601 UTC timestamp ending in Z.')
  }
  const heartbeatAt = Date.parse(heartbeat)
  if (!Number.isFinite(heartbeatAt)) throw new TypeError('heartbeat_at is invalid.')
  const normalized = heartbeat.includes('.')
    ? heartbeat.replace(/\.(\d{1,3})Z$/, (_, digits: string) => `.${digits.padEnd(3, '0')}Z`)
    : heartbeat.replace('Z', '.000Z')
  if (new Date(heartbeatAt).toISOString() !== normalized) throw new TypeError('heartbeat_at is not a valid calendar date.')
  const staleAfterSeconds = integer(value.stale_after_seconds ?? 300, 'stale_after_seconds')
  if (staleAfterSeconds < 10 || staleAfterSeconds > 86400) throw new TypeError('stale_after_seconds must be 10 to 86400.')
  return { name: text(value.name, 'name'), status, completed, total, retrying, heartbeatAt, staleAfterMs: staleAfterSeconds * 1000 }
}

export function chaiState(chai: Chai, now: number): 'running' | 'paused' | 'done' | 'failed' | 'stalled' | 'clock' {
  if (chai.status !== 'running') return chai.status
  if (chai.heartbeatAt > now + 60000) return 'clock'
  return now - chai.heartbeatAt > chai.staleAfterMs ? 'stalled' : 'running'
}

export function parseHero(source: string): Hero | null {
  const value = record(JSON.parse(source))
  if (value.enabled === false) return null
  if (value.enabled !== true) throw new TypeError('Set enabled to true or false explicitly.')
  if (!Array.isArray(value.variants) || value.variants.length < 2 || value.variants.length > 4) {
    throw new TypeError('Provide two to four design variants.')
  }
  const variants = value.variants.map(item => {
    const variant = record(item)
    const id = text(variant.id, 'variant id', 32)
    if (!/^[a-z0-9-]+$/.test(id)) throw new TypeError('Variant ids use lowercase letters, digits, and hyphens.')
    const screenshot = (name: 'desktop' | 'mobile'): string | undefined => {
      if (variant[name] === undefined) return undefined
      const path = localPath(text(variant[name], name, 1024))
      if (!path.endsWith('.png')) throw new TypeError('Screenshots must be PNG files.')
      return path
    }
    return { id, label: text(variant.label, 'variant label', 48), description: text(variant.description, 'description', 400), desktop: screenshot('desktop'), mobile: screenshot('mobile') }
  })
  if (new Set(variants.map(variant => variant.id)).size !== variants.length) throw new TypeError('Variant ids must be unique.')
  return { enabled: true, title: text(value.title, 'title'), variants }
}

export function parseChoice(value: unknown, revision: string, hero: Hero): Choice | null {
  if (value === null || typeof value !== 'object') return null
  const choice = value as Record<string, unknown>
  if (choice.revision !== revision || typeof choice.variantId !== 'string' || !hero.variants.some(v => v.id === choice.variantId)) return null
  if (typeof choice.reason !== 'string' || !choice.reason.trim() || choice.reason.length > 400 || /[\x00-\x1f\x7f]/.test(choice.reason)) return null
  return { revision, variantId: choice.variantId, reason: choice.reason }
}

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

export function putReceipt(receipts: Receipt[], receipt: Receipt): Receipt[] {
  return [...receipts.filter(item => item.id !== receipt.id), receipt].slice(-6)
}

export function age(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000))
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  return `${Math.floor(seconds / 3600)}h`
}

export function progressBar(completed: number, total: number, width = 12): string {
  const filled = total === 0 ? 0 : Math.min(width, Math.floor(completed / total * width))
  return `[${'='.repeat(filled)}${'.'.repeat(width - filled)}]`
}
