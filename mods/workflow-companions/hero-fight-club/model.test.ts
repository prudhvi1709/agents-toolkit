import { expect, test } from 'claude-code/testing'
import { parseHero } from './model'

test('hero requires explicit opt-in and unique design identities', () => {
  expect(parseHero('{"enabled":false}')).toBe(null)
  expect(() => parseHero('{}')).toThrow()
  const variant = { id: 'centered', label: 'Centered', description: 'Lead with the headline.' }
  expect(() => parseHero(JSON.stringify({ enabled: true, title: 'Homepage', variants: [variant, variant] }))).toThrow()
})
