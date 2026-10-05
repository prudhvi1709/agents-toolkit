import { expect, test } from 'claude-code/testing'
import type { On } from 'claude-code'
import { replacementDiff, safeDisplay } from '../hooks/model'

function fixture(on: On) {
  const files = new Map<string, string>([['/project/a.ts', 'const value = 1\n']])
  const world = { isFailed: false, isDenied: false, isUnreadable: false, opens: 0, closes: 0, calls: 0 }
  on('fs.exists', ($, e) => ({ value: files.has(e.path) }))
  on('fs.stat', ($, e) => ({ value: { kind: 'file', size: files.get(e.path)?.length ?? 0, mtimeMs: 0, isLink: false } }))
  on('fs.read', ($, e) => {
    if (world.isUnreadable) throw new Error('unreadable')
    return { value: files.get(e.path) ?? '' }
  })
  on('tool.call', ($, e) => {
    world.calls += 1
    if (world.isDenied) return { deny: 'not allowed' }
    if (world.isFailed) return { isError: true, result: 'failed', text: 'failed' }
    if (e.tool === 'Write') files.set(e.file_path, e.content)
    if (e.tool === 'Edit') files.set(e.file_path, (files.get(e.file_path) ?? '').replace(e.old_string, e.new_string))
    return { result: 'ok', text: 'ok' }
  })
  on('session.start', () => ({ cwd: '/project' }))
  on('turn.start', ($, e) => ({ turnId: e.turnId }))
  on('turn.complete', ($, e) => ({ text: e.answer }))
  on('command.register', ($, e) => ({ value: { command: e.name } }))
  on('ui.open', () => { world.opens += 1; return { value: { isPlaced: true } } })
  on('ui.close', () => { world.closes += 1; return { value: undefined } })
  on('ui.render', () => ({ type: 'Text', props: {}, children: ['Existing bands'] }))
  return { files, world }
}

const complete = { answer: 'done', durationMs: 100, isAborted: false, turnId: 't', reason: 'answer' } as const
const replayCommand = { command: 'replay', args: '', origin: { kind: 'composer' }, presentation: { isFullscreen: true, columns: 100 } } as const

function band(hasSurvey = false) {
  return {
    plugin: 'replay-theater', component: 'AbovePrompt', requestId: 'band',
    viewport: { columns: 100, rows: 30 },
    props: { hasSurvey, isWorking: false, maxRows: 12, bodyColumns: 100, scroll: { offset: 0, bodyRows: 12 }, view: {} },
  } as const
}

function pane(columns = 60) {
  return {
    plugin: 'replay-theater', component: 'Pane', requestId: 'replay',
    viewport: { columns: 100, rows: 40 },
    props: { title: 'Replay Theater', isFocused: true, bodyColumns: columns, placement: 'inline', scroll: { offset: 0, bodyRows: 30 }, view: {} },
  } as const
}

test('replay records actual successful edits and navigates on both surfaces', async ($, on) => {
  const { world } = fixture(on)
  await $.session.start({ cwd: '/project', surface: 'terminal', isInteractive: true })
  await $.turn.start({ turnId: 't', text: 'edit files' })
  await $.tool.call({ tool: 'Edit', file_path: '/project/a.ts', old_string: '1', new_string: '2' })
  await $.tool.call({ tool: 'Write', file_path: '/project/b.ts', content: 'new file\n' })
  const result = await $.turn.complete(complete)
  expect(result.text).toBe('done')
  expect(world.calls).toBe(2)
  await $.command.run(replayCommand)
  expect(world.opens).toBe(1)
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...pane(surface === 'terminal' ? 36 : 100), surface })
    expect(await ui.find({ text: 'Replay Theater: 1/2' })).toBeDefined()
    const code = await ui.find({ type: 'Code' })
    expect(code).toBeDefined()
    expect(code?.props.source).toContain('-const value = 1')
    expect(code?.props.source).toContain('+const value = 2')
    await ui.press({ key: 'next' })
    expect(await ui.find({ text: 'Replay Theater: 2/2' })).toBeDefined()
    expect(await ui.find({ text: 'Write: /project/b.ts' })).toBeDefined()
    await ui.press({ key: 'step-0' })
    expect(await ui.find({ text: 'Replay Theater: 1/2' })).toBeDefined()
    await ui.press({ key: 'close' })
    await ui.unmount()
  }
  expect(world.closes).toBe(2)
})

test('failed, denied, unchanged, and subagent calls do not become replay steps', async ($, on) => {
  const { world } = fixture(on)
  await $.turn.start({ turnId: 't', text: '' })
  world.isFailed = true
  await $.tool.call({ tool: 'Edit', file_path: '/project/a.ts', old_string: '1', new_string: '2' })
  world.isFailed = false
  world.isDenied = true
  await $.tool.call({ tool: 'Write', file_path: '/project/b.ts', content: 'denied' })
  world.isDenied = false
  await $.tool.call({ tool: 'Write', file_path: '/project/a.ts', content: 'const value = 1\n' })
  const childWrite = { tool: 'Write', file_path: '/project/b.ts', content: 'child', agentId: 'child' } as const
  await $.tool.call(childWrite)
  await $.turn.complete(complete)
  const result = await $.command.run(replayCommand)
  expect(result.text).toContain('No successful')
  expect(world.calls).toBe(4)
  expect(world.opens).toBe(0)
})

test('a no-edit main turn clears replay while a subagent turn leaves it intact', async ($, on) => {
  fixture(on)
  await $.turn.start({ turnId: 't', text: '' })
  await $.tool.call({ tool: 'Write', file_path: '/project/b.ts', content: 'new' })
  const childTurn = { turnId: 'child', text: '', agentId: 'child' }
  await $.turn.start(childTurn)
  await $.turn.complete({ ...complete, turnId: 'child', agentId: 'child' })
  await $.turn.complete(complete)
  const ui = await $.ui.mount({ ...band(), surface: 'terminal' })
  expect(await ui.find({ text: 'Replay: 1 edit. /replay' })).toBeDefined()
  expect(await ui.find({ text: 'Existing bands' })).toBeDefined()
  await $.turn.start({ turnId: 'empty', text: '' })
  await $.turn.complete({ ...complete, turnId: 'empty' })
  expect(await ui.find({ key: 'open-replay' })).toBeUndefined()
  expect(await ui.find({ text: 'Existing bands' })).toBeDefined()
  await ui.unmount()
})

test('replay yields to surveys instead of adding a band', async ($, on) => {
  fixture(on)
  await $.tool.call({ tool: 'Write', file_path: '/project/b.ts', content: 'new' })
  await $.turn.complete(complete)
  const ui = await $.ui.mount({ ...band(true), surface: 'terminal' })
  expect((await ui.drawn()).type).toBe('Text')
  expect(await ui.find({ text: 'Existing bands' })).toBeDefined()
  await ui.unmount()
})

test('snapshot failure reports a gap without preventing or rewriting an edit', async ($, on) => {
  const { files, world } = fixture(on)
  world.isUnreadable = true
  const result = await $.tool.call({ tool: 'Write', file_path: '/project/a.ts', content: 'changed' })
  expect(result.text).toBe('ok')
  expect(files.get('/project/a.ts')).toBe('changed')
  await $.turn.complete(complete)
  const ui = await $.ui.mount({ ...pane(), surface: 'terminal' })
  expect(await ui.find({ text: /^Snapshot unavailable/ })).toBeDefined()
  expect(await ui.find({ type: 'Code' })).toBeUndefined()
  await ui.unmount()
})

test('step and diff limits are explicit and do not affect file writes', async ($, on) => {
  const { files } = fixture(on)
  for (let index = 0; index < 25; index += 1) {
    await $.tool.call({ tool: 'Write', file_path: `/project/${index}.txt`, content: index === 0 ? 'x'.repeat(10000) : 'new' })
  }
  await $.turn.complete(complete)
  const ui = await $.ui.mount({ ...pane(), surface: 'terminal' })
  expect(await ui.find({ text: 'Replay Theater: 1/24' })).toBeDefined()
  expect(await ui.find({ text: '1 additional edits omitted (24-step limit).' })).toBeDefined()
  expect(await ui.find({ text: 'Diff exceeds the replay display limit. Review this file with /diff.' })).toBeDefined()
  expect(files.get('/project/24.txt')).toBe('new')
  await ui.unmount()
})

test('oversized files retain a step with an explicit inspection limit', async ($, on) => {
  const { files } = fixture(on)
  files.set('/project/large.txt', 'a'.repeat(65537))
  await $.tool.call({ tool: 'Write', file_path: '/project/large.txt', content: 'smaller' })
  await $.turn.complete(complete)
  const ui = await $.ui.mount({ ...pane(), surface: 'terminal' })
  expect(await ui.find({ text: 'File exceeds the 64 KiB replay limit or is not a regular file.' })).toBeDefined()
  expect(files.get('/project/large.txt')).toBe('smaller')
  await ui.unmount()
})

test('replacement hunks preserve shared prefixes and suffixes and sanitize controls', () => {
  expect(replacementDiff('a\nb\nc', 'a\nB\nc')).toBe('@@ -2,1 +2,1 @@\n-b\n+B')
  expect(replacementDiff('same', 'same')).toBeNull()
  expect(replacementDiff('', 'new')).toBe('@@ -0,0 +1,1 @@\n+new\n\\ No newline at end of file')
  expect(replacementDiff('old\n', '')).toBe('@@ -1,1 +0,0 @@\n-old')
  expect(replacementDiff('same', 'same\n')).toBe('@@ -1,1 +1,1 @@\n-same\n\\ No newline at end of file\n+same')
  expect(safeDisplay('hello\u001b[31m\nnext\tline')).toBe('hello?[31m\nnext\tline')
})

test('creation of an empty file is captured rather than treated as a no-op', async ($, on) => {
  const { files } = fixture(on)
  await $.tool.call({ tool: 'Write', file_path: '/project/empty.ts', content: '' })
  await $.turn.complete(complete)
  const ui = await $.ui.mount({ ...pane(), surface: 'terminal' })
  expect(await ui.find({ text: 'Created an empty file.' })).toBeDefined()
  expect(files.has('/project/empty.ts')).toBe(true)
  await ui.unmount()
})
