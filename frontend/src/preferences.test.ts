import { afterEach, expect, it } from 'vitest'
import { loadPreferences, savePreferences } from './preferences'

afterEach(() => localStorage.clear())
it('uses compact density by default and migrates the old display preference', () => {
  expect(loadPreferences().density).toBe('compact')
  localStorage.setItem('zhiyan.display.v1', JSON.stringify({ density: 'comfortable', reduceMotion: true }))
  expect(loadPreferences()).toEqual({ density: 'compact', reduceMotion: true })
})
it('keeps a newly saved preference and safely ignores malformed stored values', () => {
  savePreferences({ density: 'comfortable', reduceMotion: true })
  expect(loadPreferences()).toEqual({ density: 'comfortable', reduceMotion: true })
  localStorage.setItem('zhiyan.display.v2', '{broken')
  expect(loadPreferences().density).toBe('compact')
})
