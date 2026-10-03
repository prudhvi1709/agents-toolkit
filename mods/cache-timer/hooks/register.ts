import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

const expiresAt = atom(
  { plugin: 'cache-timer', key: 'expiresAt' } as const,
  null as number | null,
)

const CACHE_TTL_MS = 60 * 60 * 1000

function format(msLeft: number): string {
  const totalSeconds = Math.max(0, Math.round(msLeft / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    $.clock.every(1000, async () => {
      const at = await read($, expiresAt)

      if (at === null) {
        $.ui.status(undefined)
        return
      }

      const now = await $.clock.now()
      const msLeft = at - now

      if (msLeft <= 0) {
        await update($, expiresAt, () => null)
        $.ui.status(undefined)
        return
      }

      $.ui.status(`cache ${format(msLeft)}`)
    })

    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const usage = e.usage
    const touchedCache =
      usage !== undefined &&
      ((usage.cache_creation_input_tokens ?? 0) > 0 ||
        (usage.cache_read_input_tokens ?? 0) > 0)

    if (touchedCache) {
      const now = await $.clock.now()
      await update($, expiresAt, () => now + CACHE_TTL_MS)
    }

    return next(e)
  })
}
