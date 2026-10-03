export type Receipt = {
  id: string
  label: string
  status: 'passed' | 'failed' | 'stale' | 'unknown'
  snapshot: string | null
  at: number
}

export type Chai = {
  name: string
  status: 'running' | 'paused' | 'done' | 'failed'
  completed: number
  total: number
  retrying: number
  heartbeatAt: number
  staleAfterMs: number
}

export type Variant = {
  id: string
  label: string
  description: string
  desktop?: string
  mobile?: string
}

export type Hero = { enabled: true; title: string; variants: Variant[] }
export type Choice = { revision: string; variantId: string; reason: string }

export type Companions = {
  root: string
  receipts: Receipt[]
  evidenceError: string | null
  editVersion: number
  chaiPath: string | null
  isChaiHidden: boolean
  chai: Chai | null
  chaiError: string | null
  hero: Hero | null
  heroRevision: string
  choice: Choice | null
  reason: string
  heroError: string | null
  tab: 'ghost' | 'chai' | 'hero'
}


declare module 'claude-code' {
  interface PluginState {
    'workflow-companions': { companions: Companions }
  }
}
