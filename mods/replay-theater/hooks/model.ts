// A single replacement hunk avoids quadratic line matching. Distant changes
// include their intervening lines; use a bounded multi-hunk diff if needed later.
export function replacementDiff(before: string, after: string): string | null {
  if (before === after) return null
  const oldLines = before.match(/[^\n]*\n|[^\n]+$/g) ?? []
  const newLines = after.match(/[^\n]*\n|[^\n]+$/g) ?? []
  let start = 0
  while (start < oldLines.length && start < newLines.length && oldLines[start] === newLines[start]) start += 1
  let oldEnd = oldLines.length
  let newEnd = newLines.length
  while (oldEnd > start && newEnd > start && oldLines[oldEnd - 1] === newLines[newEnd - 1]) {
    oldEnd -= 1
    newEnd -= 1
  }
  const removed = oldLines.slice(start, oldEnd)
  const added = newLines.slice(start, newEnd)
  const oldStart = removed.length === 0 ? start : start + 1
  const newStart = added.length === 0 ? start : start + 1
  return [
    `@@ -${oldStart},${removed.length} +${newStart},${added.length} @@`,
    ...removed.flatMap(line => line.endsWith('\n') ? [`-${line.slice(0, -1)}`] : [`-${line}`, '\\ No newline at end of file']),
    ...added.flatMap(line => line.endsWith('\n') ? [`+${line.slice(0, -1)}`] : [`+${line}`, '\\ No newline at end of file']),
  ].join('\n')
}

export function safeDisplay(text: string): string {
  return text.replace(/[\u0000-\u0008\u000b-\u001f\u007f-\u009f]/g, '?')
}
