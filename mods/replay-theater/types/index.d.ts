export type ReplayStep = {
  path: string
  tool: 'Edit' | 'Write'
  diff: string | null
  note: string | null
}

export type ReplayState = {
  pending: ReplayStep[]
  steps: ReplayStep[]
  index: number
  omitted: number
  pendingOmitted: number
}

declare module 'claude-code' {
  interface PluginState {
    'replay-theater': { replay: ReplayState }
  }
}
