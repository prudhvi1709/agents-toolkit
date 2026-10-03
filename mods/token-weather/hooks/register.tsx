import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { TokenWeatherTurn } from '../types'

const history = atom(
  { plugin: 'token-weather', key: 'history' } as const,
  [] as TokenWeatherTurn[],
)

const BARS = '\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588'
const HISTORY_LIMIT = 12

function sparkline(values: number[]): string {
  if (values.length === 0) return ''
  const max = Math.max(...values, 1)
  return values
    .map(v => BARS[Math.min(BARS.length - 1, Math.floor((v / max) * (BARS.length - 1)))])
    .join('')
}

function weather(percent: number): { icon: string; word: string; color: string } {
  if (percent < 25) return { icon: '\u2600', word: 'Clear', color: 'yellow' }
  if (percent < 50) return { icon: '\u2601', word: 'Cloudy', color: 'cyan' }
  if (percent < 75) return { icon: '\u2602', word: 'Showers', color: 'blue' }
  if (percent < 90) return { icon: '\u2607', word: 'Storm', color: 'magenta' }
  return { icon: '\u21af', word: 'Compact soon', color: 'red' }
}

function formatUsed(tokens: number): string {
  return `${(tokens / 1000).toFixed(1)}k`
}

function formatWindow(tokens: number): string {
  return `${Math.round(tokens / 1000)}k`
}

export const register: Register = on => {
  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    const usage = await $.session.usage()
    const turn: TokenWeatherTurn = {
      tokens: usage.context.tokens ?? 0,
      window: usage.context.window,
      percent: usage.context.percent ?? 0,
    }

    await update($, history, prev => [...prev, turn].slice(-HISTORY_LIMIT))

    return result
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    const turns = await read($, history)

    if (turns.length === 0) {
      return next(e)
    }

    const { Box, Text } = $.ui.resolve(e)
    const last = turns[turns.length - 1]
    const prior = turns.length > 1 ? turns[turns.length - 2] : null
    const delta = prior ? last.tokens - prior.tokens : last.tokens
    const forecast = weather(last.percent)
    const chart = sparkline(turns.map(t => t.tokens))
    const existing = await next(e)

    return (
      <Box flexDirection="column">
        <Box flexDirection="row">
          <Text color={forecast.color}>
            {forecast.icon} {forecast.word}
          </Text>
          <Text dimColor>
            {'  '}
            {Math.round(last.percent)}% ({formatUsed(last.tokens)} / {formatWindow(last.window)}){'  '}
          </Text>
          <Text dimColor>{chart}</Text>
          <Text dimColor>
            {'  '}
            {delta >= 0 ? '\u25b2' : '\u25bc'} {delta >= 0 ? '+' : '-'}
            {formatUsed(Math.abs(delta))} last turn
          </Text>
        </Box>
        {existing}
      </Box>
    )
  })
}
