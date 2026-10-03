import type { Chai } from '../types'
import { integer, record, text } from '../hooks/model'

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

export function progressBar(completed: number, total: number, width = 12): string {
  const filled = total === 0 ? 0 : Math.min(width, Math.floor(completed / total * width))
  return `[${'='.repeat(filled)}${'.'.repeat(width - filled)}]`
}
