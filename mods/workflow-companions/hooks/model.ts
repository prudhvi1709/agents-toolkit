import type { Companions } from '../types'

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

export function record(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError('Expected a JSON object.')
  }
  return value as Record<string, unknown>
}

export function text(value: unknown, name: string, limit = 160): string {
  if (typeof value !== 'string' || !value.trim() || value.length > limit || /[\x00-\x1f\x7f]/.test(value)) {
    throw new TypeError(`${name} must be a short, non-empty string without control characters.`)
  }
  return value.trim()
}

export function integer(value: unknown, name: string): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) {
    throw new TypeError(`${name} must be a non-negative integer.`)
  }
  return value
}

export function age(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000))
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  return `${Math.floor(seconds / 3600)}h`
}
