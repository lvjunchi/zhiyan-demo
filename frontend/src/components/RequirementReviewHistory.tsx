import { useEffect, useState } from 'react'
import { api } from '../api'
import type { AuditEvent, Requirement } from '../types'
import { Notice } from '../ui'
import { formatTime, toErrorMessage } from '../uiSupport'
import { DetailOverlay } from './DetailOverlay'

export function RequirementReviewHistory({ requirement, returnFocus, onClose }: {
  requirement: Requirement; returnFocus: HTMLElement | null; onClose: () => void
}) {
  const [records, setRecords] = useState<AuditEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    api.requirementConfirmations(requirement.id).then(items => {
      if (active) setRecords(items)
    }).catch((err: unknown) => {
      if (active) setError(toErrorMessage(err))
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [requirement.id, attempt])
  return <DetailOverlay variant="drawer" title="需求审核记录" subtitle={`${requirement.display_code} · ${requirement.parameter_name}`} eyebrow="需求档案 · 审核留痕" returnFocus={returnFocus} onClose={onClose} footer="按需求版本保留历史审核 · 只读查看">
    {error && <Notice kind="error">{error}</Notice>}
    {loading ? <p role="status">正在读取审核记录…</p> : error ? <button type="button" onClick={() => { setError(''); setLoading(true); setAttempt(value => value + 1) }}>重试读取审核记录</button> : records.length ? <ol className="communication-timeline">{[...records].reverse().map(record => <li key={record.id}>
      <div><strong>{record.decision === 'confirmed' ? '已确认' : '已驳回'}</strong><span>V{record.object_revision} · {record.object_revision === requirement.current_revision ? '当前版本' : '历史版本'}</span></div>
      <p>{record.comment || '未填写审核意见'}</p>
      <small>{record.actor} · {record.role === 'design_engineer' ? '设计工程师' : record.role} · {formatTime(record.created_at)}</small>
    </li>)}</ol> : <p>暂无已保存的审核记录。</p>}
  </DetailOverlay>
}
