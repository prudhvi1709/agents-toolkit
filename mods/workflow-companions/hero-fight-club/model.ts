import type { Choice, Hero } from '../types'
import { localPath, record, text } from '../hooks/model'

export function parseHero(source: string): Hero | null {
  const value = record(JSON.parse(source))
  if (value.enabled === false) return null
  if (value.enabled !== true) throw new TypeError('Set enabled to true or false explicitly.')
  if (!Array.isArray(value.variants) || value.variants.length < 2 || value.variants.length > 4) {
    throw new TypeError('Provide two to four design variants.')
  }
  const variants = value.variants.map(item => {
    const variant = record(item)
    const id = text(variant.id, 'variant id', 32)
    if (!/^[a-z0-9-]+$/.test(id)) throw new TypeError('Variant ids use lowercase letters, digits, and hyphens.')
    const screenshot = (name: 'desktop' | 'mobile'): string | undefined => {
      if (variant[name] === undefined) return undefined
      const path = localPath(text(variant[name], name, 1024))
      if (!path.endsWith('.png')) throw new TypeError('Screenshots must be PNG files.')
      return path
    }
    return { id, label: text(variant.label, 'variant label', 48), description: text(variant.description, 'description', 400), desktop: screenshot('desktop'), mobile: screenshot('mobile') }
  })
  if (new Set(variants.map(variant => variant.id)).size !== variants.length) throw new TypeError('Variant ids must be unique.')
  return { enabled: true, title: text(value.title, 'title'), variants }
}

export function parseChoice(value: unknown, revision: string, hero: Hero): Choice | null {
  if (value === null || typeof value !== 'object') return null
  const choice = value as Record<string, unknown>
  if (choice.revision !== revision || typeof choice.variantId !== 'string' || !hero.variants.some(v => v.id === choice.variantId)) return null
  if (typeof choice.reason !== 'string' || !choice.reason.trim() || choice.reason.length > 400 || /[\x00-\x1f\x7f]/.test(choice.reason)) return null
  return { revision, variantId: choice.variantId, reason: choice.reason }
}
