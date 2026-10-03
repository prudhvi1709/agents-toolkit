import { expect, test } from 'claude-code/testing'

function band(hasSurvey = false) {
  return {
    plugin: 'token-weather', component: 'AbovePrompt', requestId: 'band',
    viewport: { columns: 100, rows: 30 },
    props: { hasSurvey, isWorking: false, maxRows: 12, bodyColumns: 100, scroll: { offset: 0, bodyRows: 12 }, view: {} },
  } as const
}

test('weather preserves a downstream companion band and yields to surveys', async ($, on) => {
  on('session.usage', () => ({ value: { context: { tokens: 25000, window: 200000, percent: 12.5 } } }))
  on('turn.complete', ($, e) => ({ text: e.answer }))
  on('ui.render', () => ({ type: 'Text', props: {}, children: ['Companion strip'] }))
  await $.turn.complete({ answer: 'done', durationMs: 100, isAborted: false, turnId: 't', reason: 'answer' })
  const ui = await $.ui.mount({ ...band(), surface: 'terminal' })
  expect(await ui.find({ type: 'Text', text: 'Clear' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: 'Companion strip' })).toBeDefined()
  await ui.unmount()
  const survey = await $.ui.mount({ ...band(true), surface: 'terminal' })
  expect((await survey.drawn()).type).toBe('Text')
  await survey.unmount()
})
