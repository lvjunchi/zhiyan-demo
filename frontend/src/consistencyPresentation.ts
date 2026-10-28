/** Display validation only. Detection, status and gate rules remain on the backend. */
export function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}

export function displayCount(value: unknown): string {
  return isCount(value) ? String(value) : '—'
}

export const conflictTypeLabels: Record<string, string> = {
  parameter: '参数偏差', parameter_mismatch: '参数偏差',
  version: '版本问题', version_mismatch: '版本问题',
  reference: '引用问题', condition: '工况问题', rule: '规则问题',
}
