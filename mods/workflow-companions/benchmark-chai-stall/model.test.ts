import { expect, test } from 'claude-code/testing'
import { chaiState, parseChai, progressBar } from './model'

test('progress validation rejects impossible counts, invalid times, and incomplete completion', () => {
  const feed = { name: 'Evaluation', status: 'running', completed: 5, total: 10, heartbeat_at: '2026-10-03T00:00:00Z' }
  expect(() => parseChai(JSON.stringify({ ...feed, completed: 11 }))).toThrow()
  expect(() => parseChai(JSON.stringify({ ...feed, retrying: 6 }))).toThrow()
  expect(() => parseChai(JSON.stringify({ ...feed, status: 'done' }))).toThrow()
  expect(() => parseChai(JSON.stringify({ ...feed, heartbeat_at: 'yesterday' }))).toThrow()
  expect(() => parseChai(JSON.stringify({ ...feed, heartbeat_at: '2026-02-30T00:00:00Z' }))).toThrow()
})

test('paused and finished jobs stay distinct from stalled and clock-skewed jobs', () => {
  const job = parseChai(JSON.stringify({ name: 'Evaluation', status: 'running', completed: 5, total: 10, heartbeat_at: '2026-10-03T00:00:00Z', stale_after_seconds: 60 }))
  expect(chaiState(job, job.heartbeatAt + 61000)).toBe('stalled')
  expect(chaiState({ ...job, status: 'paused' }, job.heartbeatAt + 61000)).toBe('paused')
  expect(chaiState({ ...job, status: 'done', completed: 10 }, job.heartbeatAt + 61000)).toBe('done')
  expect(chaiState(job, job.heartbeatAt - 61000)).toBe('clock')
  expect(progressBar(5, 10, 6)).toBe('[===...]')
})
