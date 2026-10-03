export type TokenWeatherTurn = {
  tokens: number
  window: number
  percent: number
}

declare module 'claude-code' {
  interface PluginState {
    'token-weather': { history: TokenWeatherTurn[] }
  }
}
