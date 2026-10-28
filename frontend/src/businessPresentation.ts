export const modeLabels: Record<string, string> = { rule: '规则计算', mock: '模拟生成', manual: '人工判定' }
export const objectTypeLabels: Record<string, string> = {
  requirement: '工程需求', variant: '变型点', part: '零件决策', design_review: '设计评审',
  fmea_document: 'DFMEA', test_plan: '试验方案', test_case: '试验用例', test_run: '试验执行',
  source_document: '来源文档', sample_comparison: '样件比对', material_package: '评审材料',
}
export const resolutionLabels: Record<string, string> = { fixed: '已修正', accepted_risk: '接受风险', not_applicable: '不适用' }
export const criterionLabels: Record<string, string> = {
  transmissionType: '变速器类型', gearCount: '档位数', gearboxRatedInputTorque: '最低额定输入扭矩',
  firstGearRatio: '一档速比', assemblyWeight: '总成重量', torqueMargin: '扭矩匹配余量',
  pto: '取力器功能', weightMargin: '重量余量', topGearType: '最高档类型',
}
const engineeringEnums: Record<string, string> = { required: '需要', not_required: '不需要', direct: '直接档', overdrive: '超速档' }
export function engineeringValue(value: unknown): string {
  const text = businessText(value)
  const normalized = text.replace(/^(?:text|boolean)\s+/, '')
  return engineeringEnums[normalized] ?? normalized
}
export function modeLabel(value: unknown): string {
  return typeof value === 'string' ? modeLabels[value] ?? '模式未识别' : '模式未记录'
}
export function businessText(value: unknown): string {
  if (typeof value === 'string') return value.trim() || '未记录'
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : '无效数值'
  if (typeof value === 'boolean') return value ? '是' : '否'
  return value === null || value === undefined ? '未记录' : '结构化记录'
}
export function versionLabel(value: unknown): string {
  return typeof value === 'number' && Number.isSafeInteger(value) && value > 0 ? `V${value}` : '版本未记录'
}
export function referenceLabel(value: Record<string, unknown>): string {
  return [businessText(value.display_code ?? value.requirement_id ?? value.object_id),
    typeof (value.parameter_name ?? value.check_point) === 'string' ? String(value.parameter_name ?? value.check_point) : '', versionLabel(value.revision ?? value.requirement_revision)].filter(Boolean).join(' · ')
}
export function ratioLabel(value: unknown): string {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1
    ? `${Number((value * 100).toFixed(1))}%` : '数据不足'
}
export function parseStatusLabel(value: unknown): string {
  return value === 'parsed' ? '已完成解析' : value === 'needs_manual_review' ? '需人工核对' : '解析状态未记录'
}
