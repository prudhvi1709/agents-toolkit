export type CacheTimerState = number | null

declare module 'claude-code' {
  interface PluginState {
    'cache-timer': { expiresAt: CacheTimerState }
  }
}
