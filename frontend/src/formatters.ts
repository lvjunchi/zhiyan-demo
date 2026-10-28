export function formatRequirementTarget(value: { data_type: string; operator: string; value_text: string; unit: string }): string {
  const labels: Record<string, string> = { required: '需要', not_required: '不需要', true: '是', false: '否' }
  const operators: Record<string, string> = { '>=': '≥', '<=': '≤', text: '', range: '' }
  if (value.data_type === 'boolean') return labels[value.value_text] ?? value.value_text
  const text = value.data_type === 'range' ? value.value_text.replace('~', '～') : value.value_text
  return [operators[value.operator] ?? value.operator, text, value.unit].filter(Boolean).join(' ')
}
