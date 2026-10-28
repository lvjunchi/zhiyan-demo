import { WorkflowOverview } from '../components/WorkflowOverview'
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api'
import { ConsistencyStats } from '../components/ConsistencyStats'
import { EvidenceDetails } from '../components/BusinessEvidence'
import { DetailOverlay } from '../components/DetailOverlay'
import { SavedRefreshNotice } from '../components/SavedRefresh'
import { useSavedRefresh } from '../useSavedRefresh'
import { objectTypeLabels, resolutionLabels, versionLabel } from '../businessPresentation'
import { conflictTypeLabels, displayCount } from '../consistencyPresentation'
import type {
  Conflict,
  ConsistencyCheckPayload,
} from '../types'
import { Empty, Notice } from '../ui'
import { DEMO_ACTOR, DEMO_ROLE, formatTime, isNotFound, reviewStatusLabels, severityLabels, toErrorMessage, validityLabels } from '../uiSupport'

const conflictEventLabels: Record<string, string> = {
  'conflict.detected': '首次检出', 'conflict.rechecked': '重新检查',
  'conflict.updated': '更新检查依据', 'conflict.reopened': '重新打开',
  'conflict.not_detected': '复检未检出', 'conflict.recheck_cleared': '复检保持关闭', 'conflict.recheck_accepted_risk': '复检保留已接受风险',
  'conflict.closed': '人工关闭',
}

export function ConsistencyPanel(props: Parameters<typeof ConsistencyWorkspace>[0]) {
  return <ConsistencyWorkspace key={props.projectId} {...props} />
}

function ConsistencyWorkspace({ projectId }: { projectId: string }) {
  const [payload, setPayload] = useState<ConsistencyCheckPayload | null>(null)
  const [conflicts, setConflicts] = useState<Conflict[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const savedRefresh = useSavedRefresh()
  const [selectedId, setSelectedId] = useState('')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerTrigger, setDrawerTrigger] = useState<HTMLElement | null>(null)
  const [drawerRow, setDrawerRow] = useState<HTMLElement | null>(null)
  const [resolutionType, setResolutionType] = useState('fixed')
  const [note, setNote] = useState('')
  const [evidence, setEvidence] = useState('')

  const loadConflicts = useCallback(async () => {
    const data = await api.listConflicts(projectId)
    setConflicts(data)
    return data
  }, [projectId])

  useEffect(() => {
    let cancelled = false
    Promise.allSettled([
      api.getLatestConsistencyCheck(projectId),
      api.listConflicts(projectId),
    ])
      .then(([checkResult, conflictResult]) => {
        if (cancelled) return
        if (checkResult.status === 'fulfilled') {
          setPayload(checkResult.value)
        } else if (!isNotFound(checkResult.reason)) {
          setError(toErrorMessage(checkResult.reason))
        }
        if (conflictResult.status === 'fulfilled') {
          setConflicts(conflictResult.value)
        } else {
          setError(toErrorMessage(conflictResult.reason))
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [projectId])

  const selected = useMemo(
    () => conflicts.find((item) => item.id === selectedId) ?? null,
    [conflicts, selectedId],
  )

  function inspectConflict(conflict: Conflict, trigger: HTMLElement) {
    setDrawerTrigger(trigger)
    setDrawerRow(trigger.closest('tr'))
    setDrawerOpen(true); setError(''); setMessage('')
    if (selectedId !== conflict.id) { setNote(''); setEvidence(''); setResolutionType('fixed') }
    setSelectedId(conflict.id)
  }

  async function handleRunCheck() {
    if (savedRefresh.blocked) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const data = await api.runConsistencyCheck(projectId)
      setPayload(data)
      await savedRefresh.afterSave('一致性检查运行', loadConflicts)
      setMessage(
        `一致性检查 ${data.check.display_code} 完成：` +
          `开放 ${displayCount(data.check.summary.open)} 条，` +
          `未关闭阻断 ${displayCount(data.check.summary.blocking_open)} 条`,
      )
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleConfirmCheck() {
    if (savedRefresh.blocked) return
    if (!payload) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await api.confirmConsistencyCheck(payload.check.id, {
        expected_revision: payload.check.revision,
        actor: DEMO_ACTOR,
        role: DEMO_ROLE,
        decision: 'confirmed',
        comment: '一致性检查人工确认',
      })
      await savedRefresh.afterSave('一致性检查审核', async () => setPayload(await api.getLatestConsistencyCheck(projectId)))
      setMessage('一致性检查已确认')
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleCloseConflict(event: FormEvent) {
    event.preventDefault()
    if (savedRefresh.blocked) return
    if (!selected || selected.status !== 'open') return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await api.closeConflict(selected.id, {
        expected_revision: selected.revision,
        actor: DEMO_ACTOR,
        role: DEMO_ROLE,
        resolution_type: resolutionType,
        note: note.trim(),
        evidence: evidence.trim(),
      })
      await savedRefresh.afterSave(`冲突 ${selected.display_code} 处置`, async () => {
        setPayload(await api.getLatestConsistencyCheck(projectId))
        await loadConflicts()
      })
      setSelectedId('')
      setDrawerOpen(false)
      setNote('')
      setEvidence('')
      setMessage(`冲突 ${selected.display_code} 已关闭并留痕`)
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      {error && !(selected && drawerOpen) && <Notice kind="error">{error}</Notice>}
      {message && !(selected && drawerOpen) && <Notice kind="success">{message}</Notice>}
      {!(selected && drawerOpen) && <SavedRefreshNotice state={savedRefresh} busy={busy} />}

      <WorkflowOverview projectId={projectId} section="consistency" refreshKey={JSON.stringify([payload,conflicts])}/>

      <section className="panel" data-object-id={payload?.check.id}>
        <div className="panel-heading">
          <h2>一致性检查</h2>
          <span className="mode-badge">规则计算 · 可复现检查</span>
        </div>
        <p className="hint">
          同时检查参数、版本、引用、工况与适用规则；审核未完成不会遮蔽冲突，
          高严重度与待审核同时显示。复检未再检出不等于自动关闭，须人工留痕关闭。
        </p>
        <div className="inline-controls">
          <button type="button" disabled={busy || savedRefresh.blocked} onClick={() => void handleRunCheck()}>
            运行一致性检查
          </button>
          {payload && payload.check.status !== 'confirmed' && (
            <button type="button" disabled={busy || savedRefresh.blocked} onClick={() => void handleConfirmCheck()}>
              确认检查报告
            </button>
          )}
          {payload && (
            <span className="muted">
              {payload.check.display_code} · V{payload.check.revision} ·{' '}
              {reviewStatusLabels[payload.check.status as keyof typeof reviewStatusLabels] ?? '状态未记录'} ·{' '}
              {validityLabels[payload.check.validity]}
            </span>
          )}
        </div>

        {loading ? (
          <Empty>正在加载一致性检查…</Empty>
        ) : !payload ? (
          <Empty>项目尚无一致性检查报告。</Empty>
        ) : (
          <>
            <ConsistencyStats summary={payload.check.summary} />
            {payload.check.validity==='current'&&payload.check.summary.total===0&&<Notice kind="success">本次检查未检出一致性冲突；此结论仅对应本次输入快照，不代表全部试验已完成。</Notice>}
            <p className="hint">
              报告更新时间：{formatTime(payload.check.updated_at)} · 输入快照包含生成时需求、
              用例、执行与规则版本。
            </p>
          </>
        )}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <h2>冲突清单</h2>
          <span className="count">{conflicts.length} 条</span>
        </div>
        {conflicts.length === 0 ? (
          <Empty>暂无冲突记录。</Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>编号</th>
                  <th>类型</th>
                  <th>严重度</th>
                  <th>状态</th>
                  <th>复检 / 审核</th>
                  <th>冲突摘要</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {conflicts.map((conflict) => (
                  <tr key={conflict.id} data-object-id={conflict.id} tabIndex={-1}>
                    <td className="mono">{conflict.display_code}</td>
                    <td>{conflictTypeLabels[conflict.conflict_type] ?? '其他类型'}</td>
                    <td>
                      <span
                        className={`status ${
                          conflict.severity === 'blocking'
                            ? 'rejected'
                            : conflict.severity === 'high'
                              ? 'draft'
                              : 'pending_review'
                        }`}
                      >
                        {severityLabels[conflict.severity] ??
                          conflict.severity}
                      </span>
                    </td>
                    <td>{conflict.status === 'open' ? '开放' : '已关闭'}</td>
                    <td className="source">
                      <span>
                        复检：{conflict.detected ? '仍检出' : '未检出'} ·
                        审核：
                        {conflict.review_pending ? '待审核' : '已完成'}
                      </span>
                      <small>
                        {objectTypeLabels[conflict.object_type] ?? '工程记录'} · {versionLabel(conflict.object_revision)} · 审核状态{' '}
                        {reviewStatusLabels[conflict.object_review_status as keyof typeof reviewStatusLabels] ?? '未记录'}
                      </small>
                    </td>
                    <td className="source">
                      <span>{conflict.title}</span>
                    </td>
                    <td className="actions">
                      <button key={conflict.status} type="button" disabled={busy || savedRefresh.blocked} onClick={event => inspectConflict(conflict, event.currentTarget)}>{conflict.status === 'open' ? '查看 / 处置' : '查看详情'}</button>
                      {conflict.status === 'closed' && <small className="muted">{resolutionLabels[conflict.resolution_type ?? ''] ?? '处置方式未记录'}</small>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {selected && drawerOpen && <DetailOverlay variant="drawer" title={`${selected.status === 'open' ? '冲突处置' : '冲突详情'} · ${selected.display_code}`} subtitle={selected.title} eyebrow="一致性检测 · 证据与处置" locked={busy} returnFocus={drawerTrigger} fallbackFocus={drawerRow} closeLabel="关闭处置详情" onClose={() => { if (!busy) { setDrawerOpen(false); setError('') } }} footer={selected.status === 'open' ? '关闭面板不会关闭冲突 · 提交处置后保留审计记录' : '只读处置档案 · 关闭冲突不等于产品验证通过'}>
          <SavedRefreshNotice state={savedRefresh} busy={busy} />
          {error && <Notice kind="error">{error}</Notice>}
          <section className="conflict-evidence"><h3>冲突证据</h3><p>{selected.detail}</p><p className="muted">{severityLabels[selected.severity]} · {objectTypeLabels[selected.object_type] ?? '工程记录'} · {versionLabel(selected.object_revision)}<br />复检：{selected.detected ? '仍检出' : '未检出'} · 审核：{selected.review_pending ? '待审核' : '已完成'}</p><EvidenceDetails data={selected.evidence} /></section>
          {selected.status === 'closed' && <section className="conflict-evidence" aria-label="已保存的处置记录"><h3>处置记录</h3><dl className="conflict-resolution-record">
            <div><dt>处置方式</dt><dd>{resolutionLabels[selected.resolution_type ?? ''] ?? '未记录'}</dd></div>
            <div><dt>处置意见</dt><dd>{selected.resolution_note || '未记录'}</dd></div>
            <div><dt>处置证据</dt><dd>{selected.evidence_text || '未记录'}</dd></div>
            <div><dt>处理人</dt><dd>{selected.closed_by || '未记录'}</dd></div>
            <div><dt>关闭时间</dt><dd>{selected.closed_at ? formatTime(selected.closed_at) : '未记录'}</dd></div>
          </dl></section>}
          <details className="business-evidence" aria-label="冲突流转记录"><summary>查看流转记录 · {selected.events.length} 条</summary><div className="business-evidence-body">{selected.events.length ? <ul className="decision-audit">{selected.events.map(event => <li key={event.id}><strong title={event.action}>{conflictEventLabels[event.action] ?? '其他状态记录'}</strong><p>{event.note || '未填写说明'}</p>{event.evidence && <p>证据：{event.evidence}</p>}<small>{event.actor || '未记录处理人'} · {formatTime(event.created_at)}</small></li>)}</ul> : <p className="muted">未保存流转记录。</p>}</div></details>
          {selected.status === 'open' && <form
            className="inline-action"
            onSubmit={(event) => void handleCloseConflict(event)}
          >
            <h3>填写处置结论</h3>
            <div className="form-grid">
              <label>
                处置类型
                <select
                  aria-label="冲突处置类型"
                  value={resolutionType}
                  disabled={busy || savedRefresh.blocked}
                  onChange={(event) => setResolutionType(event.target.value)}
                >
                  <option value="fixed">已修复</option>
                  <option value="evidence_added">补充证据</option>
                  <option value="accepted_risk">接受风险</option>
                </select>
              </label>
              <label className="wide">
                处置说明
                <input
                  aria-label="冲突处置说明"
                  value={note}
                  disabled={busy || savedRefresh.blocked}
                  onChange={(event) => setNote(event.target.value)}
                  required
                />
              </label>
              <label className="wide">
                证据
                <input
                  aria-label="冲突处置证据"
                  value={evidence}
                  disabled={busy || savedRefresh.blocked}
                  onChange={(event) => setEvidence(event.target.value)}
                  required
                />
              </label>
            </div>
            <div className="form-actions">
              <button type="submit" disabled={busy || savedRefresh.blocked}>
                确认关闭（留痕）
              </button>
            </div>
          </form>}
        </DetailOverlay>}
      </section>
    </>
  )
}
