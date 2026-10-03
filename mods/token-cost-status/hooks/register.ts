import type { Register } from 'claude-code'

export const register: Register = on => {
  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    const usage = await $.session.usage()
    const cost = usage.cost?.usd
    const tokens = usage.context.tokens

    const parts: string[] = []
    if (cost !== undefined) parts.push(`$${cost.toFixed(2)}`)
    if (tokens !== undefined) parts.push(`${(tokens / 1000).toFixed(1)}k tok`)

    $.ui.status(parts.length > 0 ? parts.join(' | ') : undefined)

    return result
  })
}
