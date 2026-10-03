import { expect, test } from 'claude-code/testing'
import { localPath } from '../hooks/model'

test('feed and screenshot paths stay within the project', () => {
  for (const path of ['../private.json', '/tmp/feed.json', 'C:\\feed.json', 'a/../../feed.json', 'a\nfeed.json']) {
    expect(() => localPath(path)).toThrow()
  }
  expect(localPath('./output/feed.json')).toBe('output/feed.json')
})
