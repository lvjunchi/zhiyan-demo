export interface DisplayPreferences { density: 'comfortable' | 'compact'; reduceMotion: boolean }
const KEY = 'zhiyan.display.v2'
export const DEFAULT_PREFERENCES: DisplayPreferences = { density: 'compact', reduceMotion: false }
export function loadPreferences(): DisplayPreferences {
  try {
    const saved = localStorage.getItem(KEY)
    const value: unknown = JSON.parse(saved ?? localStorage.getItem('zhiyan.display.v1') ?? 'null')
    if (typeof value !== 'object' || value === null) return DEFAULT_PREFERENCES
    const item = value as Record<string, unknown>
    if (!['comfortable', 'compact'].includes(String(item.density)) || typeof item.reduceMotion !== 'boolean') return DEFAULT_PREFERENCES
    return { density: saved === null ? 'compact' : item.density as DisplayPreferences['density'], reduceMotion: item.reduceMotion }
  } catch { return DEFAULT_PREFERENCES }
}
export function applyPreferences(value: DisplayPreferences) {
  document.documentElement.dataset.density = value.density
  document.documentElement.dataset.reduceMotion = String(value.reduceMotion)
}
export function savePreferences(value: DisplayPreferences) {
  localStorage.setItem(KEY, JSON.stringify(value))
  applyPreferences(value)
}
