import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { EngineeringDetail, EngineeringRecord } from '../types'
import { Badge, Empty, Notice } from '../ui'
import { DEMO_ACTOR, DEMO_ROLE, classificationLabels, formatTime, reviewStatusLabels, toErrorMessage } from '../uiSupport'
import { DecisionDialog } from './DecisionDialog'
import { DetailOverlay } from './DetailOverlay'
import { SavedRefreshNotice } from './SavedRefresh'
import { useSavedRefresh } from '../useSavedRefresh'

function title(item: EngineeringRecord): string {
  return item.display_code ?? item.part_display_code ?? item.id
}
function batchAction(item: EngineeringRecord): string {
  if (!item.is_applicable) return '历史记录，不参与确认'
  if (item.status !== 'current') return '待复核，请更新依据'
  if (item.review_status === 'confirmed') return '已确认，无需重复'
  if (item.review_status === 'rejected') return '已驳回，请先修订'
  if (!['draft','pending_review'].includes(item.review_status)) return '当前状态不参与确认'
  return '本次确认'
}
type EngineeringProps = { projectId: string; refreshKey?: number; onChanged?: () => void }
function summary(snapshot: Record<string, unknown>): string {
  return ['parameter_name', 'requirement_value', 'part_name', 'part_number', 'classification', 'reason'].map(key => key === 'classification' && typeof snapshot[key] === 'string' ? classificationLabels[snapshot[key]] ?? snapshot[key] : snapshot[key]).filter((value): value is string => typeof value === 'string').join(' · ')
}

export function EngineeringRecords({ projectId, refreshKey = 0, onChanged }: EngineeringProps) {
  return <EngineeringWorkspace key={projectId} projectId={projectId} refreshKey={refreshKey} onChanged={onChanged} />
}

function EngineeringWorkspace({ projectId, refreshKey, onChanged }: EngineeringProps & { refreshKey: number }) {
  const [records, setRecords] = useState<EngineeringRecord[]>([])
  const [selected, setSelected] = useState<EngineeringRecord | null>(null)
  const [opener, setOpener] = useState<HTMLElement | null>(null)
  const [detail, setDetail] = useState<EngineeringDetail | null>(null)
  const [comment, setComment] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const savedRefresh = useSavedRefresh()
  const [showHistory, setShowHistory] = useState(false)
  const [baseFilter, setBaseFilter] = useState('all')
  const [batch,setBatch]=useState<{records:EngineeringRecord[];items:EngineeringRecord[]}|null>(null)
  const [batchChecked,setBatchChecked]=useState(false)
  const [batchOpener,setBatchOpener]=useState<HTMLElement|null>(null)
  const baseOptions = [...new Set(records.flatMap(item => item.base_display_code ? [item.base_display_code] : []))].sort()
  const filteredRecords = records.filter(item => baseFilter === 'all' || item.base_display_code === baseFilter)
  const currentRecords = filteredRecords.filter(item => item.is_applicable === 1)
  const historicalCount = filteredRecords.length - currentRecords.length
  const pendingScope=currentRecords.filter(item=>batchAction(item)==='本次确认')
  const requestEpoch = useRef(0)
  const load = useCallback(async () => {
    const items = await api.listEngineeringRecords(projectId)
    if (!Array.isArray(items)) throw new Error('工程决策列表响应无效')
    setRecords(items)
  }, [projectId])
  useEffect(() => {
    let active = true
    api.listEngineeringRecords(projectId).then(items => {
      if (!Array.isArray(items)) throw new Error('工程决策列表响应无效')
      if (active) {
        requestEpoch.current += 1
        setRecords(items); setSelected(null); setDetail(null); setLoading(false)
      }
    }).catch((err: unknown) => { if (active) setError(toErrorMessage(err)) })
    return () => { active = false; requestEpoch.current += 1 }
  }, [projectId, refreshKey])
  async function inspect(item: EngineeringRecord, trigger?: HTMLElement) {
    const epoch = ++requestEpoch.current
    if (trigger) setOpener(trigger)
    setSelected(item); setDetail(null); setComment('')
    setError(''); setMessage(''); setLoading(true)
    try {
      const result = await api.engineeringDetail(item.kind, item.id)
      if (epoch === requestEpoch.current) setDetail(result)
    } catch (err) {
      if (epoch === requestEpoch.current) setError(toErrorMessage(err))
    } finally {
      if (epoch === requestEpoch.current) setLoading(false)
    }
  }
  function close() {
    if (saving) return
    requestEpoch.current += 1
    setSelected(null); setDetail(null); setLoading(false); setError(''); setMessage('')
  }
  async function review(decision: 'confirmed' | 'rejected') {
    if (!detail || (decision==='rejected'&&!comment.trim()) || savedRefresh.blocked || !detail.current.is_applicable || !['draft', 'pending_review'].includes(detail.current.review_status)) return
    setError(''); setMessage(''); setSaving(true)
    try {
      await api.confirmEngineering(detail.kind, detail.current.id, { expected_revision: detail.current.revision, actor: DEMO_ACTOR, role: DEMO_ROLE, decision, comment: comment.trim() })
      onChanged?.()
      requestEpoch.current += 1
      setSelected(null); setDetail(null); setLoading(false)
      setMessage('当前版本审核已保存；历史审核保留。')
      await savedRefresh.afterSave('工程决策审核', load)
    } catch (err) { setError(toErrorMessage(err)) }
    finally { setSaving(false) }
  }
  async function confirmBatch(){
    if(!batch?.items.length||!batchChecked||saving||savedRefresh.blocked)return
    setSaving(true);setError('');setMessage('')
    try{
      const result=await api.confirmEngineeringBatch(projectId,{actor:DEMO_ACTOR,role:DEMO_ROLE,items:batch.items.map(item=>({kind:item.kind,object_id:item.id,expected_revision:item.revision}))})
      setBatch(null);onChanged?.();setMessage(`已批量确认 ${result.confirmed_count} 项工程版本；逐项审核留痕已保存。`)
      await savedRefresh.afterSave('工程批量审核',load)
    }catch(err){setError(toErrorMessage(err))}finally{setSaving(false)}
  }
  return <section className="panel engineering-records" aria-label="工程决策版本与审核">
    <div className="panel-heading"><h2>工程决策版本与审核</h2><span className="count">当前 {currentRecords.length} 项{historicalCount ? ` · 历史 ${historicalCount} 项` : ''}</span></div>
    <p className="hint">这里与变型分析及下方零件选型使用同一批工程记录：V 编号审核变型点，P 编号查看零件选型及历史。先确认相关变型点，再确认依赖它的零件；重新生成不会继承旧版审核。</p>
    {!!records.length&&<div className="inline-controls"><button type="button" disabled={!filteredRecords.length||loading||saving||savedRefresh.blocked} onClick={event=>{setBatchOpener(event.currentTarget);setBatch({records:[...(showHistory?filteredRecords:currentRecords)],items:[...pendingScope]});setBatchChecked(false);setError('')}}>一键确认 · 先预览</button><span className="hint">确认当前待审核的变型点与零件决策；已审核、待复核和历史项保留当前状态。</span></div>}
    {!selected&&message&&<Notice kind="success">{message}</Notice>}
    {batch&&<DetailOverlay variant="wide" title="批量确认工程决策" subtitle={`共 ${batch.records.length} 项，本次确认 ${batch.items.length} 项，其余 ${batch.records.length-batch.items.length} 项保留当前状态。`} locked={saving} returnFocus={batchOpener} onClose={()=>{setBatch(null);setError('')}}>
      {error&&<Notice kind="error">{error}</Notice>}
      <p className="hint">先确认本范围内变型点，再确认零件；任一版本或依据不满足，整批不提交。</p>
      <p className="hint">本次审核复用／变型决策，不会自动选择候选型号。若已选候选，仍按当前约束校验。</p>
      <div className="table-wrap"><table aria-label="工程批量确认预览"><thead><tr><th>对象</th><th>基型</th><th>名称 / 型号</th><th>版本</th><th>审核</th><th>本次处理</th></tr></thead><tbody>{batch.records.map(item=><tr key={`${item.kind}-${item.id}`}><td className="mono">{title(item)}</td><td>{item.base_display_code||'未记录基型'}</td><td>{item.parameter_name??item.part_name}{item.part_number&&<small className="muted"> · {item.part_number}</small>}</td><td>V{item.revision}</td><td><Badge className={item.review_status}>{reviewStatusLabels[item.review_status as keyof typeof reviewStatusLabels]??item.review_status}</Badge></td><td>{batchAction(item)}</td></tr>)}</tbody></table></div>
      <label className="batch-acknowledgement"><input type="checkbox" aria-label="已核对本次工程确认范围" checked={batchChecked} onChange={event=>setBatchChecked(event.target.checked)} disabled={saving}/>已核对本次工程确认范围</label>
      <button type="button" className="primary-action" disabled={!batch.items.length||!batchChecked||saving||savedRefresh.blocked} onClick={()=>void confirmBatch()}>确认以上版本</button>
    </DetailOverlay>}
    {!selected && !batch && error && <Notice kind="error">{error}</Notice>}
    {!selected && <SavedRefreshNotice state={savedRefresh} busy={saving} />}
    {!records.length && <Empty>运行变型分析后，可核对各项版本、依据与审核记录。</Empty>}
    {baseOptions.length > 1 && <div className="inline-controls"><label>按基型查看<select aria-label="工程决策基型筛选" value={baseFilter} onChange={event => { setBaseFilter(event.target.value); setShowHistory(false) }}><option value="all">全部基型</option>{baseOptions.map(code => <option key={code} value={code}>{code}</option>)}</select></label><span className="muted">同一编号在不同基型下分别保留审核；请核对基型后操作。</span></div>}
    {historicalCount > 0 && <div className="inline-controls"><span className="muted">默认显示当前适用记录，历史仅供查阅。</span><button type="button" className="secondary" aria-expanded={showHistory} onClick={() => setShowHistory(value => !value)}>{showHistory ? '收起历史工程记录' : `展开历史工程记录（${historicalCount} 项）`}</button></div>}
    {!!records.length && <div className="table-wrap"><table><thead><tr><th>对象</th><th>基型</th><th>名称</th><th>版本</th><th>审核</th><th>有效性</th><th>操作</th></tr></thead><tbody>{(showHistory ? filteredRecords : currentRecords).map(item => <tr key={`${item.kind}-${item.id}`} data-object-id={item.id}><td className="mono">{title(item)}</td><td>{item.base_display_code || '未记录基型'}</td><td>{item.parameter_name ?? item.part_name}</td><td>V{item.revision}</td><td><Badge className={item.review_status}>{reviewStatusLabels[item.review_status as keyof typeof reviewStatusLabels] ?? item.review_status}</Badge></td><td>{!item.is_applicable ? '已不适用 · 历史保留' : item.status === 'stale' ? '待复核' : '当前'}</td><td><button type="button" disabled={loading || saving || savedRefresh.blocked} onClick={event => void inspect(item, event.currentTarget)}>{item.is_applicable ? `查看 ${title(item)} 版本` : `查看 ${title(item)} 历史记录`}</button></td></tr>)}</tbody></table></div>}
    {selected && <DecisionDialog title={`${title(selected)} 版本与审核`} subtitle={`${selected.base_display_code || '未记录基型'} · ${selected.parameter_name ?? selected.part_name ?? '工程决策'} · 版本对比 / 引用依据 / 人工审核`} locked={saving} returnFocus={opener} onClose={close}>
      {error && <Notice kind="error">{error}</Notice>}{message && <Notice kind="success">{message}</Notice>}
      <SavedRefreshNotice state={savedRefresh} busy={saving} />
      {loading && <p role="status">正在读取版本档案…</p>}
      {!loading && !detail && <button type="button" onClick={() => void inspect(selected)}>重试加载版本</button>}
      {detail && <>
        <section><h3>版本对比</h3><div className="engineering-versions">{detail.versions.map(version => <article key={version.revision} data-current={version.revision === detail.current.revision}><strong>V{version.revision} · {version.revision === detail.current.revision ? '当前版本' : '历史版本'}</strong><p>{summary(version.snapshot) || '此版本未保存摘要字段'}</p></article>)}</div></section>
        <section><h3>当前版本引用依据</h3>{detail.current.dependency_versions.length ? <ul>{detail.current.dependency_versions.map(dep => <li key={`${dep.object_type}-${dep.object_id}`}>{dep.object_id} · V{dep.revision}</li>)}</ul> : <p className="hint">此记录未保存引用依据，请先重新运行分析。</p>}</section>
        <section className="decision-review"><h3>当前版本审核 · V{detail.current.revision}</h3><p className="hint">{reviewStatusLabels[detail.current.review_status as keyof typeof reviewStatusLabels] ?? detail.current.review_status} · {detail.current.status === 'current' ? '当前有效' : '待复核'}。</p>
          {!detail.current.is_applicable ? <p>该记录已不适用，仅供历史查阅。</p> : ['draft', 'pending_review'].includes(detail.current.review_status) ? <>
            <label>审核意见（确认可留空，驳回必填）<textarea aria-label="工程决策审核意见" value={comment} onChange={event => setComment(event.target.value)} disabled={saving || savedRefresh.blocked} placeholder="填写核对依据或驳回原因" /></label>
            <div className="form-actions"><button type="button" disabled={saving || savedRefresh.blocked || detail.current.status !== 'current'} onClick={() => void review('confirmed')}>确认当前版本</button><button type="button" className="secondary" disabled={saving || savedRefresh.blocked || !comment.trim() || detail.current.status !== 'current'} onClick={() => void review('rejected')}>驳回当前版本</button></div>
          </> : <p>该版本已完成审核，调整内容后请重新生成并审核新版本。</p>}
        </section>
        <section><h3>审核留痕</h3>{detail.confirmations.length ? <ul className="decision-audit">{detail.confirmations.map(item => <li key={item.id}><strong>V{item.object_revision} · {reviewStatusLabels[item.decision as keyof typeof reviewStatusLabels] ?? item.decision}</strong> · {item.comment}<small>{item.actor} · {formatTime(item.created_at)}</small></li>)}</ul> : <p className="hint">暂无审核记录。</p>}</section>
      </>}
    </DecisionDialog>}
  </section>
}
