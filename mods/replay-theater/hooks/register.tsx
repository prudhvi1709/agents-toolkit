import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'
import type { ReplayState, ReplayStep } from '../types'
import { replacementDiff, safeDisplay } from './model'

const state = atom({ plugin: 'replay-theater', key: 'replay' } as const, {
  pending: [], steps: [], index: 0, omitted: 0, pendingOmitted: 0,
} as ReplayState)
const MAX_STEPS = 24
const MAX_FILE_BYTES = 65536
const MAX_DIFF_CHARS = 9000

async function snapshot($: EngineInterface, path: string): Promise<{ text: string | null; note: string | null; isPresent: boolean }> {
  try {
    if (!(await $.fs.exists(path))) return { text: '', note: null, isPresent: false }
    const info = await $.fs.stat(path)
    if (info.kind !== 'file' || info.size > MAX_FILE_BYTES) {
      return { text: null, note: 'File exceeds the 64 KiB replay limit or is not a regular file.', isPresent: true }
    }
    return { text: await $.fs.read(path), note: null, isPresent: true }
  } catch (error) {
    // Inspection failure must not prevent the user's edit. Report the gap in
    // the replay rather than treating an unreadable file as an empty file.
    return { text: null, note: `Snapshot unavailable (${error instanceof Error ? error.name : 'unknown error'}).`, isPresent: true }
  }
}

async function openReplay($: EngineInterface): Promise<void> {
  await $.ui.open({ id: 'replay', title: 'Replay Theater', focus: true, closeOnEscape: true })
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const result = await next(e)
    await $.command.register({ name: 'replay', description: "Review the last turn's successful file edits" })
    return result
  })

  on('turn.start', async ($, e, next) => {
    if (!('agentId' in e && e.agentId)) await update($, state, current => ({ ...current, pending: [], pendingOmitted: 0 }))
    return next(e)
  })

  on('tool.call', async ($, e, next) => {
    if (e.agentId || (e.tool !== 'Edit' && e.tool !== 'Write') || typeof e.file_path !== 'string') return next(e)
    const current = await read($, state)
    if (current.pending.length >= MAX_STEPS) {
      const result = await next(e)
      if (!result.isError && !result.deny) await update($, state, value => ({ ...value, pendingOmitted: value.pendingOmitted + 1 }))
      return result
    }
    const before = await snapshot($, e.file_path)
    const result = await next(e)
    if (result.isError || result.deny) return result
    const after = await snapshot($, e.file_path)
    if (before.text !== null && after.text !== null && before.text === after.text && before.isPresent === after.isPresent) return result
    let diff = before.text === null || after.text === null ? null : replacementDiff(before.text, after.text)
    let note = before.note ?? after.note
    if (!before.isPresent && after.text === '') note = 'Created an empty file.'
    if (diff !== null && diff.length > MAX_DIFF_CHARS) {
      diff = null
      note = 'Diff exceeds the replay display limit. Review this file with /diff.'
    }
    const step: ReplayStep = { path: safeDisplay(e.file_path).slice(0, 1000), tool: e.tool, diff: diff === null ? null : safeDisplay(diff), note }
    await update($, state, value => value.pending.length < MAX_STEPS
      ? { ...value, pending: [...value.pending, step] }
      : { ...value, pendingOmitted: value.pendingOmitted + 1 })
    return result
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    if (!e.agentId) await update($, state, value => ({
      ...value, steps: value.pending, omitted: value.pendingOmitted, index: 0,
    }))
    return result
  })

  on('command.run', { command: 'replay' }, async $ => {
    if ((await read($, state)).steps.length === 0) return { text: 'No successful Edit/Write changes in the last turn.' }
    await openReplay($)
    return { text: '' }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const existing = await next(e)
    if (e.props.hasSurvey) return existing
    const current = await read($, state)
    if (current.steps.length === 0) return existing
    const { Box, Text, Button } = $.ui.resolve(e)
    return <Box flexDirection="column">
      {existing}
      <Box flexDirection="row" flexWrap="wrap" gap={1}>
        <Text dimColor>{`Replay: ${current.steps.length} edit${current.steps.length === 1 ? '' : 's'}${current.omitted ? ` (+${current.omitted} omitted)` : ''}. /replay`}</Text>
        <Button key="open-replay" label="Review" plain onPress={async () => { await openReplay($) }} />
      </Box>
    </Box>
  })

  on('ui.render', { component: 'Pane', requestId: 'replay' }, async ($, e, next) => {
    if (e.surface !== 'terminal' && e.surface !== 'desktop') return next(e)
    const current = await read($, state)
    const { Box, Text, Button, Code } = $.ui.resolve(e)
    const step = current.steps[current.index]
    if (!step) return <Text>No edits in the last turn.</Text>
    const select = async (index: number): Promise<void> => {
      await update($, state, value => ({ ...value, index: Math.max(0, Math.min(index, value.steps.length - 1)) }))
    }
    return <Box flexDirection="column" paddingX={1} gap={1}>
      <Text bold>{`Replay Theater: ${current.index + 1}/${current.steps.length}`}</Text>
      <Box flexDirection="row" flexWrap="wrap" gap={1}>
        {current.steps.map((item, index) => <Button key={`step-${index}`} label={`${index + 1}`} variant={index === current.index ? 'primary' : 'secondary'} onPress={async () => { await select(index) }} />)}
      </Box>
      <Text wrap="truncate-end">{`${step.tool}: ${step.path}`}</Text>
      {step.diff !== null ? <Code source={step.diff} path={step.path} format="diff" /> : <Text color="yellow">{step.note ?? 'Diff unavailable.'}</Text>}
      {current.omitted > 0 && <Text color="yellow">{`${current.omitted} additional edits omitted (24-step limit).`}</Text>}
      <Box flexDirection="row" flexWrap="wrap" gap={1}>
        {current.index > 0 ? <Button key="previous" label="Prev" hotkey={e.props.isFocused ? 'p' : undefined} onPress={async () => { await select(current.index - 1) }} /> : <Text dimColor>Prev</Text>}
        {current.index < current.steps.length - 1 ? <Button key="next" label="Next" hotkey={e.props.isFocused ? 'n' : undefined} onPress={async () => { await select(current.index + 1) }} /> : <Text dimColor>Next</Text>}
        <Button key="close" label="Close" role="dismiss" hotkey={e.props.isFocused ? 'x' : undefined} onPress={async () => { await $.ui.close({ id: 'replay' }) }} />
      </Box>
      <Text dimColor>Observed foreground Edit/Write calls only. Shell, notebook, and subagent edits are not captured.</Text>
    </Box>
  })
}
