import { expect, it } from 'vitest'
import { formatRequirementTarget } from './formatters'

it('shows engineering operators and feature requirements in readable Chinese', () => {
  expect(formatRequirementTarget({ data_type: 'numeric', operator: '>=', value_text: '2800', unit: 'N·m' })).toBe('≥ 2800 N·m')
  expect(formatRequirementTarget({ data_type: 'boolean', operator: '=', value_text: 'required', unit: '' })).toBe('需要')
  expect(formatRequirementTarget({ data_type: 'text', operator: 'text', value_text: 'AMT', unit: '' })).toBe('AMT')
  expect(formatRequirementTarget({ data_type: 'range', operator: 'range', value_text: '-40~50', unit: '℃' })).toBe('-40～50 ℃')
})
