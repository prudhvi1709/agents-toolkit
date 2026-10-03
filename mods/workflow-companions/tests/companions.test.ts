import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

function fixture(on: On) {
  const files = new Map<string, string>()
  const store = new Map<string, unknown>()
  const world = { diff: '', head: 'abc', isFailed: false, isBackground: false, isSnapshotBroken: false, opens: 0, toasts: [] as string[] }
  const clock = mock.clock(on, { now: Date.parse('2026-10-03T00:00:00Z') })
  on('session.root', () => ({ value: '/project' }))
  on('process.run', ($, e) => ({ value: {
    exitCode: world.isSnapshotBroken && e.argv[1] === 'diff' ? 1 : 0,
    stdout: e.argv.includes('--show-toplevel') ? '/project\n' : e.argv.includes('--verify') ? world.head : e.argv[1] === 'diff' ? world.diff : '',
    stderr: '', isStdoutTruncated: false, isStderrTruncated: false,
  } }))
  on('fs.exists', ($, e) => ({ value: files.has(e.path) }))
  on('fs.stat', ($, e) => ({ value: { kind: 'file', size: files.get(e.path)?.length ?? 0, mtimeMs: 0, isLink: false, realPath: e.path } }))
  on('fs.read', ($, e) => ({ value: e.as === 'bytes' ? { base64: btoa(files.get(e.path) ?? '') } : files.get(e.path) ?? '' }))
  on('store.get', ($, e) => ({ value: store.get(e.key) }))
  on('store.set', ($, e) => { store.set(e.key, e.value); return { value: undefined } })
  on('ui.open', () => { world.opens += 1; return { value: { isPlaced: true } } })
  on('ui.close', () => ({ value: undefined }))
  on('ui.toast', ($, e) => { world.toasts.push(e.text); return { value: undefined } })
  on('command.register', ($, e) => ({ value: { command: e.name } }))
  on('session.start', () => ({ cwd: '/project' }))
  on('session.end', () => ({ sessionId: 'test-session' }))
  on('classic.SessionStart', () => ({}))
  on('tool.call', () => world.isFailed ? { isError: true, result: 'failed', text: 'failed' }
    : { result: { stdout: 'ok', stderr: '', interrupted: false, ...(world.isBackground ? { backgroundTaskId: 'background' } : {}) } })
  on('ui.render', () => ({ type: 'Text', props: {}, children: ['Existing mod'] }))
  return { files, store, world, clock }
}

function band(columns = 100, hasSurvey = false) {
  return {
    plugin: 'workflow-companions', component: 'AbovePrompt', requestId: 'band',
    viewport: { columns, rows: 30 },
    props: { hasSurvey, isWorking: false, maxRows: 12, bodyColumns: columns, scroll: { offset: 0, bodyRows: 12 }, view: {} },
  } as const
}

function pane(columns = 60) {
  return {
    plugin: 'workflow-companions', component: 'Pane', requestId: 'companions',
    viewport: { columns: 100, rows: 40 },
    props: { title: 'Work companions', isFocused: true, bodyColumns: columns, placement: 'inline', scroll: { offset: 0, bodyRows: 30 }, view: {} },
  } as const
}

function feed(completed = 4): string {
  return JSON.stringify({ name: 'Overnight evaluation', status: 'running', completed, total: 10, heartbeat_at: '2026-10-03T00:00:00Z', stale_after_seconds: 30 })
}

function hero(title = 'Homepage'): string {
  return JSON.stringify({ enabled: true, title, variants: [
    { id: 'centered', label: 'Centered', description: 'A clear, uninterrupted headline.' },
    { id: 'split', label: 'Split', description: 'Show the product beside the headline.' },
  ] })
}

test('idle companions preserve an existing mod and draw no rows', async ($, on) => {
  fixture(on)
  await $.command.run({ command: 'companions', args: '' })
  const ui = await $.ui.mount({ ...band(), surface: 'terminal' })
  expect((await ui.drawn()).type).toBe('Text')
  expect(await ui.find({ text: 'Existing mod' })).toBeDefined()
  expect(await ui.find({ text: 'Hero club' })).toBeUndefined()
  await ui.unmount()
})

test('a passing check becomes haunted after an edit and fresh after a rerun', async ($, on) => {
  fixture(on)
  await $.tool.call({ tool: 'Bash', command: 'uv run pytest -q', args: '' })
  const ui = await $.ui.mount({ ...band(), surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: /^Fresh$/ })).toBeDefined()
  await $.tool.call({ tool: 'Edit', file_path: '/project/app.py', old_string: 'old', new_string: 'new' })
  expect(await ui.find({ text: 'Haunted' })).toBeDefined()
  await $.tool.call({ tool: 'Bash', command: 'uv run pytest -q', args: '' })
  expect(await ui.find({ type: 'Text', text: /^Fresh$/ })).toBeDefined()
  expect(await ui.find({ text: 'Existing mod' })).toBeDefined()
  await ui.unmount()
})

test('external changes and clean commits retire earlier evidence', async ($, on) => {
  const { world } = fixture(on)
  await $.tool.call({ tool: 'Bash', command: 'pytest', args: '' })
  world.diff = 'external edit'
  await $.command.run({ command: 'ghost', args: '' })
  const ui = await $.ui.mount({ ...band(), surface: 'terminal' })
  expect(await ui.find({ text: 'Haunted' })).toBeDefined()
  await $.tool.call({ tool: 'Bash', command: 'pytest', args: '' })
  world.head = 'new-commit'
  await $.command.run({ command: 'ghost', args: '' })
  expect(await ui.find({ text: 'Haunted' })).toBeDefined()
  await ui.unmount()
})

test('failed, background, and uninspectable checks never look fresh', async ($, on) => {
  const { world } = fixture(on)
  world.isBackground = true
  await $.tool.call({ tool: 'Bash', command: 'pytest', args: '' })
  const ui = await $.ui.mount({ ...band(), surface: 'terminal' })
  expect(await ui.find({ text: 'Evidence' })).toBeUndefined()
  world.isBackground = false
  world.isFailed = true
  await $.tool.call({ tool: 'Bash', command: 'pytest', args: '' })
  expect(await ui.find({ text: 'Failed' })).toBeDefined()
  world.isFailed = false
  world.isSnapshotBroken = true
  await $.tool.call({ tool: 'Bash', command: 'pytest', args: '' })
  expect(await ui.find({ text: 'Unknown' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /^Fresh$/ })).toBeUndefined()
  await ui.unmount()
})

test('surveys retain the band even when companions have evidence', async ($, on) => {
  fixture(on)
  await $.tool.call({ tool: 'Bash', command: 'pytest', args: '' })
  const ui = await $.ui.mount({ ...band(100, true), surface: 'terminal' })
  expect((await ui.drawn()).type).toBe('Text')
  await ui.unmount()
})

test('chai updates, detects silence, and hides without changing the runner', async ($, on) => {
  const { files, clock } = fixture(on)
  files.set('/project/.claude/companions/chai.progress.json', feed())
  await $.command.run({ command: 'chai', args: '' })
  const ui = await $.ui.mount({ ...band(), surface: 'terminal' })
  expect(await ui.find({ text: '4/10 served' })).toBeDefined()
  files.set('/project/.claude/companions/chai.progress.json', feed(6))
  await clock.advance(31000)
  await $.command.run({ command: 'chai', args: '' })
  expect(await ui.find({ text: '6/10 served' })).toBeDefined()
  expect(await ui.find({ text: 'Silent' })).toBeDefined()
  await $.command.run({ command: 'chai', args: 'hide' })
  expect(await ui.find({ text: 'Chai stall' })).toBeUndefined()
  await ui.unmount()
})

test('malformed feeds replace old counts instead of retaining reassuring stale data', async ($, on) => {
  const { files } = fixture(on)
  files.set('/project/output/progress.json', feed())
  await $.command.run({ command: 'chai', args: 'watch output/progress.json' })
  const ui = await $.ui.mount({ ...band(), surface: 'terminal' })
  files.set('/project/output/progress.json', '{broken')
  await $.command.run({ command: 'chai', args: '' })
  expect(await ui.find({ text: 'Feed?' })).toBeDefined()
  expect(await ui.find({ text: '4/10 served' })).toBeUndefined()
  await ui.unmount()
})

test('hero is off by default and saving a direction needs a reason', async ($, on) => {
  const { files, store, world } = fixture(on)
  expect((await $.command.run({ command: 'hero', args: '' })).text).toContain('off here')
  files.set('/project/.claude/companions/hero.json', hero())
  await $.command.run({ command: 'hero', args: '' })
  const ui = await $.ui.mount({ ...pane(), surface: 'terminal' })
  await ui.press({ key: 'choose-centered' })
  expect(world.toasts).toHaveLength(1)
  expect(store.size).toBe(0)
  await ui.input({ key: 'hero-reason', text: 'Headline reads better on mobile.' })
  await ui.press({ key: 'choose-centered' })
  expect(await ui.find({ text: 'Chosen: Centered' })).toBeDefined()
  expect(store.size).toBe(1)
  files.set('/project/.claude/companions/hero.json', hero('New homepage brief'))
  await ui.press({ key: 'refresh' })
  expect(await ui.find({ text: 'Chosen: Centered' })).toBeUndefined()
  await ui.unmount()
})

test('compact and wide layouts remain valid in terminal and desktop, with hero opt-in', async ($, on) => {
  const { files } = fixture(on)
  files.set('/project/.claude/companions/chai.progress.json', feed())
  files.set('/project/.claude/companions/hero.json', hero())
  await $.tool.call({ tool: 'Bash', command: 'pytest', args: '' })
  await $.command.run({ command: 'companions', args: '' })
  for (const surface of ['terminal', 'desktop'] as const) {
    for (const columns of [36, 80, 120]) {
      const ui = await $.ui.mount({ ...band(columns), surface })
      expect(await ui.find({ text: 'Evidence' })).toBeDefined()
      expect(await ui.find({ text: 'Chai stall' })).toBeDefined()
      expect(await ui.find({ text: 'Hero club' })).toBeDefined()
      expect(await ui.find({ text: 'Existing mod' })).toBeDefined()
      await ui.unmount()
    }
    const ui = await $.ui.mount({ ...pane(), surface })
    await ui.press({ key: 'tab-hero' })
    expect(await ui.find({ text: 'Hero Fight Club' })).toBeDefined()
    await ui.unmount()
  }
})

test('timer polls a live feed and resumes after clearing the conversation', async ($, on) => {
  const { files, clock } = fixture(on)
  files.set('/project/.claude/companions/chai.progress.json', feed())
  await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/project' })
  const ui = await $.ui.mount({ ...band(), surface: 'terminal' })
  files.set('/project/.claude/companions/chai.progress.json', feed(6))
  await clock.advance(15000)
  expect(await ui.find({ text: '6/10 served' })).toBeDefined()
  await $.session.end({ reason: 'clear' })
  await $.classic.SessionStart({ source: 'clear' })
  files.set('/project/.claude/companions/chai.progress.json', feed(7))
  await clock.advance(15000)
  expect(await ui.find({ text: '7/10 served' })).toBeDefined()
  await ui.unmount()
  await $.session.end({ reason: 'prompt_input_exit' })
})

test('replacing a screenshot retires its decision and desktop preserves screenshot paths', async ($, on) => {
  const { files } = fixture(on)
  const design = JSON.parse(hero())
  design.variants[0].desktop = 'output/centered.png'
  files.set('/project/.claude/companions/hero.json', JSON.stringify(design))
  files.set('/project/output/centered.png', 'first-image')
  await $.command.run({ command: 'hero', args: '' })
  const ui = await $.ui.mount({ ...pane(), surface: 'terminal' })
  expect(await ui.find({ type: 'Image' })).toBeDefined()
  await ui.input({ key: 'hero-reason', text: 'The headline has room.' })
  await ui.press({ key: 'choose-centered' })
  expect(await ui.find({ text: 'Chosen: Centered' })).toBeDefined()
  files.set('/project/output/centered.png', 'second-image')
  await ui.press({ key: 'refresh' })
  expect(await ui.find({ text: 'Chosen: Centered' })).toBeUndefined()
  await ui.unmount()
  const desktop = await $.ui.mount({ ...pane(), surface: 'desktop' })
  expect(await desktop.find({ text: 'output/centered.png' })).toBeDefined()
  expect(await desktop.find({ type: 'Image' })).toBeUndefined()
  await desktop.unmount()
})
