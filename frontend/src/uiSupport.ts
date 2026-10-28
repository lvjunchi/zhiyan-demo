import { ApiError } from './api'
import type {
  ExecutionResult,
  ReviewStatus,
  RiskLevel,
  Severity,
  Validity,
} from './types'

export const DEMO_ACTOR = '演示工程师'
export const DEMO_ROLE = 'design_engineer'
export const DEMO_ROLE_LABEL = '设计工程师（演示角色，非认证）'

export const reviewStatusLabels: Record<ReviewStatus, string> = {
  draft: '草案',
  pending_review: '待审核',
  confirmed: '已确认',
  rejected: '已驳回',
}

export const validityLabels: Record<Validity, string> = {
  current: '当前',
  stale: '待复核',
}

export const executionLabels: Record<ExecutionResult, string> = {
  pass: '通过',
  fail: '未通过',
  incomplete: '证据不足',
  invalid: '无效',
  not_run: '未执行',
}

export const severityLabels: Record<Severity, string> = {
  blocking: '阻断',
  high: '高',
  medium: '中',
  low: '低',
}

export const riskLabels: Record<RiskLevel, string> = {
  high: '高风险',
  medium: '中风险',
  low: '低风险',
  insufficient: '数据不足',
}

export const classificationLabels: Record<string, string> = {
  carryover: '沿用',
  modify: '修改',
  new_design: '新设计',
}

export const variantTypeLabels: Record<string, string> = {
  parameter_adjustment: '参数调整',
  structural_change: '结构变更',
  new_function: '新增功能',
}

export const packageStatusLabels: Record<string, string> = {
  draft: '草稿',
  ready_to_submit: '可提交',
  human_approved: '人工已批准',
}

export const docTypeLabels: Record<string, string> = {
  protocol: '技术协议',
  change_notice: '变更通知',
  drawing: '图纸',
  test_report: '试验报告',
  communication: '沟通记录',
  other: '其他',
}

export function toErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return '请求失败'
}

export function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404
}

export function toConflictMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 409) {
    return `版本冲突：${error.message}`
  }
  return toErrorMessage(error)
}

export function formatTime(value: string | null | undefined): string {
  if (!value) return '—'
  const match = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})(?::\d{2})?/.exec(value)
  if (!match) return value
  const zone = value.endsWith('Z') || value.includes('+00:00') ? ' UTC' : ''
  return `${match[1]} ${match[2]}${zone}`
}

