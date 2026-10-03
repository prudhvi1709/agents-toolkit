import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, Timer } from 'claude-code'
import type { Companions, Receipt } from '../types'
import { age, initialState, localPath } from './model'
import { digest } from './snapshot'
import { chaiState, parseChai, progressBar } from '../benchmark-chai-stall/model'
import { parseChoice, parseHero } from '../hero-fight-club/model'
import { checkLabel, parseEvidenceScopes, putReceipt } from '../evidence-ghost/model'

const state = atom({ plugin: 'workflow-companions', key: 'companions' } as const, initialState())

const set = async ($: EngineInterface, change: Partial<Companions>): Promise<void> => {
  await update($, state, previous => ({ ...previous, ...change }))
}

const rootFor = async ($: EngineInterface): Promise<string> => {
  const cwd = await $.session.root()
  const repo = await $.process.run(['git', 'rev-parse', '--show-toplevel'], { cwd, timeoutMs: 3000 })
  return repo.exitCode === 0 ? repo.stdout.trim() : cwd
}

const readLocal = async ($: EngineInterface, root: string, path: string): Promise<string | null> => {
  const absolute = `${root}/${localPath(path)}`
  if (!(await $.fs.exists(absolute))) return null
  const info = await $.fs.stat(absolute, { resolve: true })
  if (info.kind !== 'file' || info.size > 65536 || !info.realPath?.startsWith(`${root}/`)) {
    throw new TypeError('Use a regular JSON file under this project, at most 64 KiB.')
  }
  return $.fs.read(absolute)
}

const refresh = async ($: EngineInterface, runtime: { isRefreshing: boolean }): Promise<void> => {
  if (runtime.isRefreshing) return
  runtime.isRefreshing = true
  try {
    const root = await rootFor($)
    let current = await read($, state)
    if (root !== current.root) {
      await update($, state, () => initialState(root))
      current = await read($, state)
    }
    if (current.receipts.length > 0) {
      try {
        await refreshEvidence($, root)
      } catch {
        await update($, state, previous => ({
          ...previous, evidenceError: 'Worktree snapshot unavailable. Freshness is unknown.',
          receipts: previous.receipts.map(item => item.status === 'passed' ? { ...item, status: 'unknown' } : item),
        }))
      }
    }
    if (!current.isChaiHidden) {
      try {
        const source = await readLocal($, root, current.chaiPath ?? '.claude/companions/chai.progress.json')
        await set($, { chai: source === null ? null : parseChai(source), chaiError: source === null && current.chaiPath !== null ? 'Progress file is missing. Check the watched path.' : null })
      } catch {
        await set($, { chai: null, chaiError: 'Invalid progress feed. Check the documented JSON fields and counts.' })
      }
    }
    try {
      const source = await readLocal($, root, '.claude/companions/hero.json')
      const hero = source === null ? null : parseHero(source)
      const revision = hero === null ? '' : await digest(JSON.stringify(hero))
      // Each revision includes screenshot content, so replacing an image also
      // retires the old decision rather than carrying it into a new comparison.
      const screenshots: string[] = []
      if (hero !== null) {
        for (const variant of hero.variants) {
          for (const path of [variant.desktop, variant.mobile]) {
            if (path === undefined) continue
            const absolute = `${root}/${path}`
            if (!(await $.fs.exists(absolute))) { screenshots.push(path, 'missing'); continue }
            const info = await $.fs.stat(absolute, { resolve: true })
            if (info.kind !== 'file' || info.size > 2 * 1024 * 1024 || !info.realPath?.startsWith(`${root}/`)) {
              throw new TypeError('Screenshots must be regular PNG files inside this project, at most 2 MiB.')
            }
            screenshots.push(path, (await $.fs.read(absolute, { as: 'bytes' })).base64)
          }
        }
      }
      const heroRevision = hero === null ? '' : await digest(revision + JSON.stringify(screenshots))
      const choice = hero === null ? null : parseChoice(await $.store.get(`hero:${root}`), heroRevision, hero)
      await update($, state, previous => ({
        ...previous, hero, heroRevision, choice, heroError: null,
        reason: previous.heroRevision === heroRevision ? previous.reason : '',
      }))
    } catch {
      await set($, { hero: null, choice: null, heroError: 'Invalid hero comparison. Check its opt-in file and screenshot paths.' })
    }
    $.ui.invalidate('ui.render')
  } finally {
    runtime.isRefreshing = false
  }
}

const open = async ($: EngineInterface, tab: Companions['tab'], runtime: { isRefreshing: boolean }): Promise<void> => {
  await refresh($, runtime)
  await set($, { tab })
  await $.ui.open({ id: 'companions', title: 'Work companions', focus: true, closeOnEscape: true })
}


async function evidenceSnapshot($: EngineInterface, root: string, id: string): Promise<{ fingerprint: string; isScoped: boolean }> {
  const source = await readLocal($, root, '.claude/companions/evidence.json')
  const scopes = source === null ? [] : parseEvidenceScopes(source)
  let inputs: string[] | null = null
  for (const scope of scopes) {
    if (await digest(scope.command) === id) { inputs = scope.inputs; break }
  }
  if (inputs === null) return { fingerprint: await snapshot($, root), isScoped: false }
  const listing = await $.process.run([
    'git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z', '--',
    ...inputs.map(path => `:(literal)${path}`),
  ], { cwd: root, timeoutMs: 3000 })
  if (listing.exitCode !== 0 || listing.isStdoutTruncated) throw new Error('Cannot inspect scoped inputs.')
  const files = [...new Set(listing.stdout.split('\0').filter(Boolean))].sort()
  if (files.length === 0) throw new Error('The configured scope contains no Git-visible inputs.')
  if (files.length > 64) throw new Error('Too many scoped files for a complete snapshot.')
  const parts = [JSON.stringify(inputs)]
  let bytes = 0
  for (const file of files) {
    const path = `${root}/${localPath(file)}`
    if (!(await $.fs.exists(path))) { parts.push(file, 'missing'); continue }
    const info = await $.fs.stat(path, { resolve: true })
    bytes += info.size
    if (info.isLink || info.kind !== 'file' || !info.realPath?.startsWith(`${root}/`) || bytes > 2 * 1024 * 1024) {
      throw new Error('Scoped inputs exceed the snapshot budget or include an unsafe path.')
    }
    parts.push(file, (await $.fs.read(path, { as: 'bytes' })).base64)
  }
  return { fingerprint: await digest(JSON.stringify(parts)), isScoped: true }
}

async function snapshot($: EngineInterface, root: string): Promise<string> {
  const results = await Promise.all([
    $.process.run(['git', ...['diff', '--no-ext-diff', '--no-textconv', '--binary']], { cwd: root, timeoutMs: 3000 }),
    $.process.run(['git', ...['diff', '--cached', '--no-ext-diff', '--no-textconv', '--binary']], { cwd: root, timeoutMs: 3000 }),
    $.process.run(['git', ...['ls-files', '--others', '--exclude-standard', '-z']], { cwd: root, timeoutMs: 3000 }),
    $.process.run(['git', ...['rev-parse', '--verify', 'HEAD']], { cwd: root, timeoutMs: 3000 }),
  ])
  if (results.slice(0, 3).some(result => result.exitCode !== 0 || result.isStdoutTruncated)) {
    throw new Error('Cannot inspect this worktree.')
  }
  const files = results[2]!.stdout.split('\0').filter(Boolean).sort()
  // Bound snapshots to 64 untracked files / 2 MiB. Larger worktrees report
  // unknown rather than silently skipping files; upgrade to a watcher for scale.
  if (files.length > 64) throw new Error('Too many untracked files for a complete snapshot.')
  let bytes = 0
  const parts = [...results.slice(0, 2).map(result => result.stdout), results[3]!.exitCode === 0 ? results[3]!.stdout : 'unborn']
  for (const file of files) {
    const path = `${root}/${file}`
    const info = await $.fs.stat(path)
    bytes += info.size
    if (info.isLink || info.kind !== 'file' || bytes > 2 * 1024 * 1024) {
      throw new Error('Untracked files exceed the snapshot budget or include a link.')
    }
    const content = await $.fs.read(path, { as: 'bytes' })
    parts.push(file, content.base64)
  }
  // Contents are hashed in memory. Only the digest enters session state.
  return digest(JSON.stringify(parts))
}

async function refreshEvidence($: EngineInterface, root: string): Promise<void> {
  const current = await read($, state)
  let hasUnknown = current.receipts.some(receipt => receipt.status === 'unknown')
  for (const receipt of current.receipts) {
    if (receipt.status !== 'passed') continue
    let fingerprint: string | null = null
    try { fingerprint = (await evidenceSnapshot($, root, receipt.id)).fingerprint }
    catch { hasUnknown = true }
    await update($, state, previous => previous.root !== root ? previous : ({
      ...previous,
      receipts: previous.receipts.map(item => item.id !== receipt.id || item.status !== 'passed' ? item
        : fingerprint === null ? { ...item, status: 'unknown' }
        : item.snapshot !== fingerprint ? { ...item, status: 'stale' } : item),
    }))
  }
  await set($, { evidenceError: hasUnknown ? 'Evidence inputs unavailable. Freshness is unknown.' : null })
}

export const register: Register = on => {
  let timer: Timer | null = null
  const runtime = { isRefreshing: false }
  on('session.start', async ($, e, next) => {
    const result = await next(e)
    for (const command of [
      { name: 'companions', description: 'Open the work companions pane' },
      { name: 'ghost', description: 'Inspect check evidence and freshness' },
      { name: 'chai', description: 'Watch batch progress', argumentHint: '[watch relative/path.json | hide | show]' },
      { name: 'hero', description: 'Review this project\'s opted-in design comparison' },
    ]) await $.command.register(command)
    await refresh($, runtime)
    timer?.cancel()
    timer = $.clock.every(15000, async () => { await refresh($, runtime) })
    return result
  })

  on('session.end', async ($, e, next) => {
    timer?.cancel()
    timer = null
    return next(e)
  })

  on('classic.SessionStart', async ($, e, next) => {
    const result = await next(e)
    if (e.source === 'clear' || e.source === 'resume') {
      await update($, state, () => initialState())
      await refresh($, runtime)
      timer?.cancel()
      timer = $.clock.every(15000, async () => { await refresh($, runtime) })
    }
    return result
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    if (e.agentId === undefined) await refresh($, runtime)
    return result
  })

  on('tool.call', async ($, e, next) => {
    const label = e.tool === 'Bash' && e.run_in_background !== true ? checkLabel(e.command) : null
    const canMutate = ['Edit', 'Write', 'NotebookEdit'].includes(e.tool) || e.tool === 'Bash'
    const before = await read($, state)
    let fingerprint: string | null = null
    const root = await rootFor($)
    if (root !== before.root) await update($, state, () => initialState(root))
    const started = await read($, state)
    const id = label === null ? null : await digest(e.tool === 'Bash' ? e.command.trim() : label)
    let isScoped = false
    if (id !== null || canMutate) {
      try {
        if (id === null) fingerprint = await snapshot($, root)
        else {
          const captured = await evidenceSnapshot($, root, id)
          fingerprint = captured.fingerprint
          isScoped = captured.isScoped
        }
      }
      catch { await set($, { evidenceError: 'Worktree snapshot unavailable. Freshness is unknown.' }) }
    }
    const result = await next(e)
    if (label !== null) {
      const output = result.result
      const background = output !== null && typeof output === 'object' &&
        ['backgroundTaskId', 'backgroundedByUser', 'backgroundedByTurnAbort', 'backgroundedToDeliverMessage', 'timedOutAfterMs'].some(key => Boolean((output as Record<string, unknown>)[key]))
      if (background) return result
      const interrupted = output !== null && typeof output === 'object' && (output as Record<string, unknown>).interrupted === true
      let after: string | null = null
      try { after = (await evidenceSnapshot($, root, id!)).fingerprint }
      catch { await set($, { evidenceError: 'Worktree snapshot unavailable. Freshness is unknown.' }) }
      const now = await $.clock.now()
      await update($, state, previous => {
        if (previous.root !== root) return previous
        const status: Receipt['status'] = result.isError === true || result.deny !== undefined || interrupted ? 'failed'
          : fingerprint === null || after === null ? 'unknown'
          : fingerprint !== after || (!isScoped && previous.editVersion !== started.editVersion) ? 'stale' : 'passed'
        return { ...previous, receipts: putReceipt(previous.receipts, { id: id!, label, status, snapshot: after, at: now }) }
      })
      await refreshEvidence($, root)
    } else if (canMutate) {
      let after: string | null = null
      try { after = await snapshot($, root) }
      catch { await set($, { evidenceError: 'Worktree snapshot unavailable. Freshness is unknown.' }) }
      await update($, state, previous => {
        if (previous.root !== root) return previous
        return {
          ...previous,
          evidenceError: after === null ? 'Worktree snapshot unavailable. Freshness is unknown.' : null,
          editVersion: previous.editVersion + (fingerprint === null || after === null || fingerprint !== after ? 1 : 0),
        }
      })
      await refreshEvidence($, root)
    }
    $.ui.invalidate('ui.render')
    return result
  })

  on('command.run', { command: 'companions' }, async $ => {
    await open($, 'ghost', runtime)
    return { text: '' }
  })
  on('command.run', { command: 'ghost' }, async $ => {
    await open($, 'ghost', runtime)
    return { text: '' }
  })
  on('command.run', { command: 'hero' }, async $ => {
    await refresh($, runtime)
    const current = await read($, state)
    if (current.hero === null && current.heroError === null) return { text: 'Hero Fight Club is off here. Opt in with .claude/companions/hero.json.' }
    await open($, 'hero', runtime)
    return { text: '' }
  })
  on('command.run', { command: 'chai' }, async ($, e) => {
    await refresh($, runtime)
    const args = e.args.trim()
    if (args === 'hide') {
      await set($, { isChaiHidden: true, chai: null, chaiError: null })
      $.ui.invalidate('ui.render')
      return { text: 'Chai Stall hidden for this session.' }
    }
    if (args.startsWith('watch ')) {
      try { await set($, { chaiPath: localPath(args.slice(6).trim()), isChaiHidden: false }) }
      catch { return { text: 'Use /chai watch relative/path.json inside this project.' } }
    } else if (args === 'show') await set($, { isChaiHidden: false })
    else if (args !== '') return { text: 'Use /chai, /chai watch relative/path.json, /chai hide, or /chai show.' }
    await open($, 'chai', runtime)
    return { text: '' }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    const current = await read($, state)
    const rows: { key: string; icon: string; label: string; status: string; color: string; detail: string; tab: Companions['tab'] }[] = []
    if (current.receipts.length > 0) {
      const stale = current.receipts.filter(item => item.status === 'stale').length
      const failed = current.receipts.filter(item => item.status === 'failed').length
      const unknown = current.receipts.filter(item => item.status === 'unknown').length
      rows.push({ key: 'ghost', icon: '(o.o)', label: 'Evidence', status: failed ? 'Failed' : stale ? 'Haunted' : unknown ? 'Unknown' : 'Fresh',
        color: failed ? 'red' : stale || unknown ? 'yellow' : 'green', detail: failed ? `${failed} check failed` : stale ? `${stale} stale check${stale === 1 ? '' : 's'}. Boo.` : unknown ? 'Freshness needs a worktree snapshot.' : `${current.receipts.length} observed check${current.receipts.length === 1 ? '' : 's'}`, tab: 'ghost' })
    }
    if (current.chai !== null) {
      const chai = current.chai
      const status = chaiState(chai, await $.clock.now())
      rows.push({ key: 'chai', icon: '[~]', label: 'Chai stall', status: status === 'stalled' ? 'Silent' : status === 'clock' ? 'Clock?' : status[0]!.toUpperCase() + status.slice(1),
        color: status === 'failed' ? 'red' : status === 'done' ? 'green' : status === 'stalled' || status === 'clock' ? 'yellow' : 'cyan',
        detail: `${chai.completed}/${chai.total} served${chai.retrying ? `, ${chai.retrying} retrying` : ''}`, tab: 'chai' })
    } else if (current.chaiError !== null) rows.push({ key: 'chai', icon: '[~]', label: 'Chai stall', status: 'Feed?', color: 'yellow', detail: 'Check the progress file.', tab: 'chai' })
    if (current.hero !== null || current.heroError !== null) {
      const selected = current.hero?.variants.find(variant => variant.id === current.choice?.variantId)
      rows.push({ key: 'hero', icon: '[vs]', label: 'Hero club', status: current.heroError ? 'Setup?' : selected ? 'Chosen' : 'In ring', color: current.heroError ? 'yellow' : 'cyan', detail: selected?.label ?? current.hero?.title ?? 'Check the comparison file.', tab: 'hero' })
    }
    const existing = await next(e)
    if (rows.length === 0) return existing
    const { Box, Text, Button } = $.ui.resolve(e)
    const narrow = e.props.bodyColumns < 64
    return (
      <Box flexDirection="column">
        {existing}
        <Box flexDirection="column" borderStyle="single" borderColor="gray" paddingX={1}>
          {rows.map(row => (
            <Box key={row.key} flexDirection={narrow ? 'column' : 'row'}>
              <Box flexDirection="row" flexShrink={0}>
                <Box width={6}><Text color={row.color}>{row.icon}</Text></Box>
                <Box width={11}><Text>{row.label}</Text></Box>
                <Box width={9}><Text color={row.color} bold>{row.status}</Text></Box>
              </Box>
              <Box flexGrow={1} flexShrink={1} marginLeft={narrow ? 6 : 0}>
                <Text dimColor wrap="truncate-end">{row.detail}</Text>
              </Box>
              {!narrow && <Button key={`open-${row.key}`} label="View" plain dimColor onPress={async () => { await open($, row.tab, runtime) }} />}
            </Box>
          ))}
        </Box>
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: 'companions' }, async ($, e, next) => {
    if (e.surface !== 'terminal' && e.surface !== 'desktop') return next(e)
    const current = await read($, state)
    const now = await $.clock.now()
    const { Box, Text, Button, Input } = $.ui.resolve(e)
    const Image = e.surface === 'terminal' ? $.ui.resolve(e).Image : null
    const tabButton = (tab: Companions['tab'], label: string, hotkey: string) => (
      <Button key={`tab-${tab}`} label={label} hotkey={hotkey} variant={current.tab === tab ? 'primary' : 'secondary'}
        onPress={async () => { await set($, { tab }); $.ui.invalidate('ui.render') }} />
    )
    const selected = current.hero?.variants.find(variant => variant.id === current.choice?.variantId)
    return (
      <Box flexDirection="column" paddingX={1} gap={1}>
        <Box flexDirection="column">
          <Text bold>Work companions</Text>
          <Text dimColor>Small signals. Useful company.</Text>
        </Box>
        <Box flexDirection="row" flexWrap="wrap" gap={1}>
          {tabButton('ghost', 'Evidence', 'g')}
          {tabButton('chai', 'Chai stall', 'c')}
          {(current.hero !== null || current.heroError !== null) && tabButton('hero', 'Hero club', 'h')}
        </Box>
        {current.tab === 'ghost' && <Box flexDirection="column" gap={1}>
          <Text color="cyan" bold>(o.o) Evidence Ghost</Text>
          <Text dimColor>Passing is a check result, not a promise that everything works.</Text>
          {current.receipts.length === 0 && <Text>Run a supported test, lint, or type check in Claude's Bash tool. The ghost will remember it.</Text>}
          {current.receipts.map((receipt, index) => <Box key={receipt.id} flexDirection="column">
            <Text color={receipt.status === 'passed' ? 'green' : receipt.status === 'failed' ? 'red' : 'yellow'} bold>
              {`${index + 1}. ${receipt.label} / ${receipt.status}`}
            </Text>
            <Text dimColor>{`${age(now - receipt.at)} ago${receipt.status === 'stale' ? '. The worktree changed. Boo.' : ''}`}</Text>
          </Box>)}
          {current.evidenceError !== null && <Text color="yellow">{current.evidenceError}</Text>}
          <Text dimColor>Only observed foreground checks. The ghost never runs checks itself.</Text>
        </Box>}
        {current.tab === 'chai' && <Box flexDirection="column" gap={1}>
          <Text color="cyan" bold>[~] Benchmark Chai Stall</Text>
          {current.chai === null ? <Text>{current.chaiError ?? 'No kettle on yet. Use /chai watch relative/path.json, or provide .claude/companions/chai.progress.json.'}</Text> : <Box flexDirection="column" gap={1}>
            <Text bold>{current.chai.name}</Text>
            <Text color={chaiState(current.chai, now) === 'stalled' ? 'yellow' : 'cyan'}>{`${progressBar(current.chai.completed, current.chai.total, Math.min(20, Math.max(6, e.props.bodyColumns - 8)))} ${current.chai.completed}/${current.chai.total}`}</Text>
            <Text>{`${current.chai.total - current.chai.completed} waiting, ${current.chai.retrying} retrying`}</Text>
            <Text color={chaiState(current.chai, now) === 'stalled' ? 'yellow' : undefined}>{`State: ${chaiState(current.chai, now)}. Heartbeat ${age(now - current.chai.heartbeatAt)} ago.`}</Text>
            <Text dimColor>{chaiState(current.chai, now) === 'stalled' ? 'The kitchen went quiet. Check the runner before ordering more.' : 'The runner supplies these counts. A heartbeat is not proof of progress.'}</Text>
          </Box>}
          <Text dimColor>Updates every 15 seconds. Paused and finished jobs are never labeled stalled.</Text>
        </Box>}
        {current.tab === 'hero' && <Box flexDirection="column" gap={1}>
          <Text color="cyan" bold>[vs] Hero Fight Club</Text>
          {current.hero === null ? <Text>{current.heroError ?? 'Off in this project. Opt in with .claude/companions/hero.json.'}</Text> : <Box flexDirection="column" gap={1}>
            <Text bold>{current.hero.title}</Text>
            {selected !== undefined && <Box flexDirection="column" borderStyle="single" borderColor="green" paddingX={1}>
              <Text color="green" bold>{`Chosen: ${selected.label}`}</Text>
              <Text>{current.choice?.reason}</Text>
              <Button key="copy-decision" label="Copy decision" onPress={async press => {
                await $.ui.copy({ text: `${current.hero?.title}: ${selected.label}. ${current.choice?.reason}`, surface: press.surface })
              }} />
            </Box>}
            {current.hero.variants.map(variant => <Box key={variant.id} flexDirection="column" borderStyle="single" borderColor={selected?.id === variant.id ? 'green' : 'gray'} paddingX={1} gap={1}>
              <Text bold>{variant.label}</Text>
              <Text>{variant.description}</Text>
              {(['desktop', 'mobile'] as const).map(size => variant[size] === undefined
                ? <Text key={size} dimColor>{`${size}: no screenshot supplied`}</Text>
                : <Box key={size} flexDirection="column">
                  <Text dimColor>{`${size}: ${variant[size]}`}</Text>
                  {Image !== null && <Image key={`${variant.id}-${size}`} source={{ file: `${current.root}/${variant[size]}`, format: 'png', generation: Number.parseInt(current.heroRevision.slice(0, 8), 16) }}
                    columns={Math.min(80, Math.max(1, e.props.bodyColumns - 6))} rows={size === 'mobile' ? 12 : 8} alt={`${variant.label}, ${size} screenshot. Open the file if images are unavailable.`} />}
                </Box>)}
              <Button key={`choose-${variant.id}`} label={`Choose ${variant.label}`} onPress={async () => {
                const latest = await read($, state)
                const reason = latest.reason.trim()
                if (reason.length === 0 || reason.length > 400 || /[\x00-\x1f\x7f]/.test(reason)) {
                  await $.ui.toast('Add a short reason below before choosing a direction.')
                  return
                }
                await refresh($, runtime)
                const fresh = await read($, state)
                if (fresh.heroRevision !== current.heroRevision || !fresh.hero?.variants.some(v => v.id === variant.id)) {
                  await $.ui.toast('This comparison changed. Review it again before choosing.')
                  return
                }
                const choice = { revision: fresh.heroRevision, variantId: variant.id, reason }
                await $.store.set(`hero:${fresh.root}`, choice)
                await set($, { choice })
                $.ui.invalidate('ui.render')
              }} />
            </Box>)}
            <Input key="hero-reason" label="Why this direction?" placeholder="Headline reads better on mobile..." value={current.reason}
              onSubmit={async value => { await set($, { reason: value.slice(0, 400) }); $.ui.invalidate('ui.render') }} />
            <Text dimColor>Enter saves the reason; then choose a variant. Decisions stay local and retire when the comparison changes.</Text>
          </Box>}
        </Box>}
        <Box flexDirection="row" gap={1}>
          <Button key="refresh" label="Refresh" hotkey="r" onPress={async () => { await refresh($, runtime) }} />
          <Button key="close" label="Close" hotkey="x" role="dismiss" onPress={async () => { await $.ui.close({ id: 'companions' }) }} />
        </Box>
      </Box>
    )
  })
}
