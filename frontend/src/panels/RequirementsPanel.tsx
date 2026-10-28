import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, api } from '../api'
import { formatRequirementTarget } from '../formatters'
import { RequirementInspector } from '../components/RequirementInspector'
import { RequirementReviewHistory } from '../components/RequirementReviewHistory'
import { DetailOverlay } from '../components/DetailOverlay'
import { RequirementBatchDialog } from './RequirementBatchDialog'
import { RequirementReviewChart } from './RequirementReviewChart'
import './requirements.css'
import type { Project, Requirement } from '../types'
import { Badge, Empty, Notice } from '../ui'
import { DEMO_ACTOR, DEMO_ROLE, reviewStatusLabels, toConflictMessage, toErrorMessage, validityLabels } from '../uiSupport'

export function RequirementsPanel(props: Parameters<typeof RequirementsWorkspace>[0]) {
  return <RequirementsWorkspace key={`${props.project.id}:${props.focusRequirementId ?? ''}`} {...props} />
}

function RequirementsWorkspace({
  project,
  focusRequirementId,
}: {
  project: Project
  focusRequirementId?: string
}) {
  const [requirements, setRequirements] = useState<Requirement[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [actioningId, setActioningId] = useState<string | null>(null)
  const [editingId, setEditingId] = useState('')
  const [newValue, setNewValue] = useState<string | null>(null)
  const [sourceExcerpt, setSourceExcerpt] = useState('')
  const [updating, setUpdating] = useState(false)
  const [query, setQuery] = useState('')
  const [categoryFilter,setCategoryFilter]=useState('all')
  const [sortField,setSortField]=useState<'original'|'code'|'parameter'|'target'|'revision'>('original')
  const [descending,setDescending]=useState(false)
  const [selectedIds,setSelectedIds]=useState<Set<string>>(new Set())
  const [locateCode,setLocateCode]=useState('')
  const [locatedId,setLocatedId]=useState(focusRequirementId??'')
  const [locateRequest,setLocateRequest]=useState(0)
  const [revisionOpen,setRevisionOpen]=useState(false)
  const [revisionFallback,setRevisionFallback]=useState<HTMLElement|null>(null)
  const [revisionTrigger,setRevisionTrigger]=useState<HTMLElement|null>(null)
  const [updateError,setUpdateError]=useState('')
  const [batchRows,setBatchRows]=useState<Requirement[]|null>(null)
  const [batchTrigger,setBatchTrigger]=useState<HTMLElement|null>(null)
  const listElement=useRef<HTMLElement>(null)
  const [reviewFilter, setReviewFilter] = useState<'pending' | 'confirmed' | 'rejected' | 'all'>(focusRequirementId ? 'all' : 'pending')
  const [validityFilter, setValidityFilter] = useState('all')
  const [inspecting, setInspecting] = useState<Requirement | null>(null)
  const [inspectorTrigger, setInspectorTrigger] = useState<HTMLElement | null>(null)
  const [history, setHistory] = useState<Requirement | null>(null)
  const [historyTrigger, setHistoryTrigger] = useState<HTMLElement | null>(null)
  const [rejecting, setRejecting] = useState<Requirement | null>(null)
  const [rejectTrigger, setRejectTrigger] = useState<HTMLElement | null>(null)
  const [rejectFallback, setRejectFallback] = useState<HTMLElement | null>(null)
  const [rejectionDraft, setRejectionDraft] = useState({ id: '', reason: '' })
  const [decisionError, setDecisionError] = useState('')
  const [refreshRequired, setRefreshRequired] = useState(false)
  const operationLock = useRef(false)
  const queueHeading = useRef<HTMLHeadingElement>(null)
  const revisionInput = useRef<HTMLInputElement>(null)
  const reasonInput = useRef<HTMLTextAreaElement>(null)
  const isPending = (item: Requirement) => item.review_status === 'draft' || item.review_status === 'pending_review'
  const groups = [
    { key: 'pending', label: '待审核', count: requirements.filter(isPending).length },
    { key: 'confirmed', label: '已确认', count: requirements.filter(item => item.review_status === 'confirmed').length },
    { key: 'rejected', label: '已驳回', count: requirements.filter(item => item.review_status === 'rejected').length },
    { key: 'all', label: '全部需求', count: requirements.length },
  ] as const
  const visible = requirements.filter(item => `${item.display_code} ${item.parameter_name} ${item.value_text} ${item.source_excerpt}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()) && (reviewFilter === 'all' || (reviewFilter === 'pending' ? isPending(item) : item.review_status === reviewFilter)) && (validityFilter === 'all' || item.validity === validityFilter) && (categoryFilter==='all'||item.category===categoryFilter))
  if(sortField!=='original') visible.sort((left,right)=>{
    const order=sortField==='revision'?left.current_revision-right.current_revision:sortField==='target'&&left.value_num!==null&&right.value_num!==null?left.value_num-right.value_num:new Intl.Collator('zh-CN',{numeric:true}).compare(sortField==='code'?left.display_code:sortField==='parameter'?left.parameter_name:left.value_text,sortField==='code'?right.display_code:sortField==='parameter'?right.parameter_name:right.value_text)
    return (descending?-1:1)*order||left.id.localeCompare(right.id)
  })
  const visiblePending=visible.filter(isPending)
  const selectedVisible=visiblePending.filter(row=>selectedIds.has(row.id))

  useEffect(()=>{
    if(loading||!locatedId)return
    const row=[...(listElement.current?.querySelectorAll<HTMLTableRowElement>('tbody tr[data-object-id]')??[])].find(element=>element.dataset.objectId===locatedId)
    row?.scrollIntoView?.({block:'center'});row?.focus()
  },[locatedId,locateRequest,loading])

  function openRevision(requirement:Requirement,trigger:HTMLElement){
    setMessage('')
    if(editingId!==requirement.id){setEditingId(requirement.id);setNewValue(null);setSourceExcerpt('')}
    setUpdateError('');setRevisionFallback(queueHeading.current);setRevisionTrigger(trigger);setRevisionOpen(true)
  }
  function chartFilter(filter:typeof reviewFilter){setReviewFilter(filter);setQuery('');setCategoryFilter('all');setValidityFilter('all');queueHeading.current?.scrollIntoView?.({block:'start'});queueHeading.current?.focus()}
  function locate(){
    const row=requirements.find(item=>item.display_code.toLocaleLowerCase()===locateCode.trim().toLocaleLowerCase())
    if(!row){setError('未找到该需求编号，请核对完整编号');return}
    setError('');setReviewFilter('all');setQuery('');setCategoryFilter('all');setValidityFilter('all');setLocatedId(row.id);setLocateRequest(value=>value+1)
  }
  async function afterBatch(count:number){
    setSelectedIds(new Set())
    try{await loadRequirements();setMessage(`已批量确认 ${count} 条需求，已移至已确认列表。`)}
    catch(err){setRefreshRequired(true);setError(`批量审核已保存，但列表刷新失败：${toErrorMessage(err)}。请重新读取列表，勿重复提交。`)}
    queueHeading.current?.focus()
  }

  const projectId = project.id

  const loadRequirements = useCallback(async () => {
    const data = await api.listRequirements(projectId)
    setRequirements(data)
    return data
  }, [projectId])

  useEffect(() => {
    let cancelled = false
    api
      .listRequirements(projectId)
      .then((data) => {
        if (!cancelled) setRequirements(data)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(toErrorMessage(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [projectId])

  const selectedForEdit = useMemo(
    () =>
      requirements.find((item) => item.id === editingId) ??
      requirements[0] ??
      null,
    [requirements, editingId],
  )

  async function handleDecision(
    requirement: Requirement,
    decision: 'confirmed' | 'rejected',
    reason = '',
  ) {
    if (operationLock.current || refreshRequired || !isPending(requirement)) return
    operationLock.current = true
    setActioningId(requirement.id)
    setError('')
    setMessage('')
    setDecisionError('')
    let saved = false
    try {
      await api.confirmRequirement(requirement.id, {
        expected_revision: requirement.current_revision,
        actor: DEMO_ACTOR,
        role: DEMO_ROLE,
        decision,
        comment: decision === 'confirmed' ? '工程师确认' : reason.trim(),
      })
      saved = true
      setRejecting(null)
      setRejectionDraft({ id: '', reason: '' })
      await loadRequirements()
      setMessage(
        decision === 'confirmed' ? `已确认 ${requirement.display_code}，已移至已确认列表。` : `已驳回 ${requirement.display_code}，已移至已驳回列表，待修订。`,
      )
      queueHeading.current?.focus()
    } catch (err) {
      if (saved) {
        setRefreshRequired(true)
        setError(`审核已保存，但列表刷新失败：${toErrorMessage(err)}。请重新读取列表后继续操作。`)
      } else {
        const detail = err instanceof ApiError && err.status === 409 ? toConflictMessage(err) : toErrorMessage(err)
        if (decision === 'rejected') setDecisionError(detail)
        else setError(detail)
      }
    } finally {
      setActioningId(null)
      operationLock.current = false
    }
  }

  async function retryList() {
    if (operationLock.current) return
    operationLock.current = true
    setLoading(true)
    try {
      await loadRequirements()
      setRefreshRequired(false)
      setError('')
      setMessage('需求列表已刷新，请在对应审核视图查看已保存结果。')
    } catch (err) { setError(`列表读取失败：${toErrorMessage(err)}`) }
    finally { setLoading(false); operationLock.current = false }
  }

  async function handleUpdate(event: FormEvent) {
    event.preventDefault()
    if (!selectedForEdit || operationLock.current || refreshRequired) return
    operationLock.current = true
    setUpdating(true)
    setUpdateError('')
    setError('')
    setMessage('')
    let saved = false
    try {
      const payload: Record<string, unknown> = {
        expected_revision: selectedForEdit.current_revision,
        value_text: (newValue ?? selectedForEdit.value_text).trim(),
      }
      if (sourceExcerpt.trim()) {
        payload.source_excerpt = sourceExcerpt.trim()
      }
      const updated = await api.updateRequirement(
        selectedForEdit.id,
        payload,
      )
      saved = true
      if(updated.current_revision!==selectedForEdit.current_revision)setRevisionOpen(false)
      await loadRequirements()
      setSourceExcerpt('')
      setNewValue(null)
      if (updated.current_revision === selectedForEdit.current_revision) {
        setMessage(`${updated.display_code} 未发生实质变化，仍为${reviewStatusLabels[updated.review_status]}，未创建新版本。`)
      } else {
        if (isPending(updated)) { setReviewFilter('pending'); setQuery(''); setValidityFilter('all') }
        setMessage(`${updated.display_code} 已更新为 V${updated.current_revision}，${isPending(updated) ? '已返回待审核；' : ''}下游对象按依赖传播校验。`)
      }
    } catch (err) {
      if (saved) { setRefreshRequired(true); setError(`修订已保存，但列表刷新失败：${toErrorMessage(err)}。请重新读取列表后继续操作。`) }
      else setUpdateError(toConflictMessage(err))
    } finally {
      setUpdating(false)
      operationLock.current = false
    }
  }

  return (
    <>
      {error && <Notice kind="error">{error}</Notice>}
      {message && !revisionOpen && <Notice kind="success">{message}</Notice>}
      {refreshRequired && <button type="button" className="secondary" disabled={loading} onClick={() => void retryList()}>重新读取需求列表</button>}

      <section className="panel requirement-sheet" ref={listElement}>
        <div className="panel-heading">
          <h2 ref={queueHeading} tabIndex={-1}>结构化需求</h2>
          <span className="count">{requirements.length} 条</span>
        </div>
        <div className="requirement-review-views" role="group" aria-label="需求审核视图">{groups.map(group => <button type="button" key={group.key} aria-label={`${group.label} ${group.count} 条`} aria-pressed={reviewFilter === group.key} onClick={() => setReviewFilter(group.key)}><span>{group.label}</span><strong>{group.count}</strong></button>)}</div>
        <p className="hint requirement-review-hint">{reviewFilter === 'pending' ? '待审核包括草案与待审核需求。确认或驳回后移至对应视图，来源和历史记录保留。' : reviewFilter === 'rejected' ? '已驳回需求待修订；核对审核记录中的原因，提交实质修订后重新审核。' : reviewFilter === 'confirmed' ? '已确认需求保留为设计和验证依据。需要调整时请提交修订，生成新版本后重新审核。' : '查看全部需求及当前审核状态，审核与有效性分别展示。'}</p>
        <div className="inline-controls requirement-filters"><label>搜索需求<input aria-label="搜索需求" placeholder="编号、参数、目标或原文" value={query} onChange={event => setQuery(event.target.value)} /></label><label>类别<select aria-label="需求类别筛选" value={categoryFilter} onChange={event=>setCategoryFilter(event.target.value)}><option value="all">全部类别</option>{'ABCDEFGHI'.split('').map(category=><option key={category} value={category}>{category} 类</option>)}</select></label><label>有效性<select aria-label="有效性筛选" value={validityFilter} onChange={event => setValidityFilter(event.target.value)}><option value="all">全部有效性</option><option value="current">当前有效</option><option value="stale">待复核</option></select></label><label>排序<select aria-label="需求排序字段" value={sortField} onChange={event=>setSortField(event.target.value as typeof sortField)}><option value="original">默认顺序</option><option value="code">需求编号</option><option value="parameter">参数名称</option><option value="target">目标值</option><option value="revision">版本</option></select></label><button type="button" className="secondary" disabled={sortField==='original'} onClick={()=>setDescending(value=>!value)}>{descending?'降序 ↓':'升序 ↑'}</button><span>显示 {visible.length} / {requirements.length} 条</span></div>
        <div className="requirement-sheet-actions"><div className="requirement-locate"><input aria-label="定位需求编号" placeholder="输入完整需求编号" value={locateCode} onChange={event=>setLocateCode(event.target.value)} onKeyDown={event=>{if(event.key==='Enter')locate()}}/><button type="button" className="secondary" onClick={locate} disabled={!locateCode.trim()||loading}>定位需求</button></div><div><span className="muted">{selectedVisible.length?`已选 ${selectedVisible.length} 条`:'按当前筛选范围核对'}</span><button type="button" aria-label="预览一键确认范围" disabled={loading||updating||actioningId!==null||refreshRequired||!visiblePending.length} onClick={event=>{setBatchTrigger(event.currentTarget);setBatchRows(selectedVisible.length?selectedVisible:visiblePending)}}>一键确认 · 先预览</button></div></div>
        {!loading && requirements.length > 0 && visible.length === 0 && <Empty>{reviewFilter === 'pending' && !query.trim() && validityFilter === 'all' ? '当前没有待审核需求，可切换至已确认、已驳回或全部需求查看记录。' : '没有符合筛选条件的需求。'}</Empty>}
        {loading ? (
          <Empty>正在加载需求…</Empty>
        ) : requirements.length === 0 ? (
          <Empty>暂无需求。</Empty>
        ) : (
          <div className="table-wrap requirement-sheet-scroll">
            <table>
              <thead>
                <tr>
                  <th><input type="checkbox" aria-label="选择当前列表待审核需求" checked={!!visiblePending.length&&selectedVisible.length===visiblePending.length} onChange={event=>setSelectedIds(event.target.checked?new Set(visiblePending.map(row=>row.id)):new Set())}/></th>
                  <th>编号</th>
                  <th>参数</th>
                  <th>目标</th>
                  <th>版本</th>
                  <th>审核状态</th>
                  <th>有效性</th>
                  <th>来源</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((requirement) => (
                  <tr key={requirement.id} data-object-id={requirement.id} data-located={locatedId===requirement.id} tabIndex={-1}>
                    <td><input type="checkbox" aria-label={`选择 ${requirement.display_code}`} disabled={!isPending(requirement)||refreshRequired} checked={selectedIds.has(requirement.id)} onChange={event=>setSelectedIds(current=>{const next=new Set(current);if(event.target.checked)next.add(requirement.id);else next.delete(requirement.id);return next})}/></td>
                    <td className="mono">{requirement.display_code}</td>
                    <td>{requirement.parameter_name}</td>
                    <td>
                      {formatRequirementTarget(requirement)}
                    </td>
                    <td>V{requirement.current_revision}</td>
                    <td>
                      <Badge className={requirement.review_status}>
                        {reviewStatusLabels[requirement.review_status]}
                      </Badge>
                    </td>
                    <td>
                      <span
                        className={`validity ${requirement.validity}`}
                      >
                        {validityLabels[requirement.validity]}
                      </span>
                    </td>
                    <td className="source">
                      <span>{requirement.source_location || '未记录'}</span>
                      <small>{requirement.source_excerpt}</small>
                    </td>
                    <td className="actions"><div className="requirement-row-actions">
                      <button type="button" className="secondary" aria-label={`查看 ${requirement.display_code} 来源与版本`} onClick={event=>{setInspectorTrigger(event.currentTarget);setInspecting(requirement)}}>来源 / 版本</button>
                      {isPending(requirement)?<><button type="button" aria-label={`确认 ${requirement.display_code}`} disabled={actioningId!==null||updating||refreshRequired} onClick={()=>void handleDecision(requirement,'confirmed')}>确认</button><button type="button" className="secondary" aria-label={`驳回 ${requirement.display_code}`} disabled={actioningId!==null||updating||refreshRequired} onClick={event=>{setRejectTrigger(event.currentTarget);setRejectFallback(queueHeading.current);setRejecting(requirement);setDecisionError('');if(rejectionDraft.id!==requirement.id)setRejectionDraft({id:requirement.id,reason:''})}}>驳回</button></>:<><span aria-hidden="true"/><span aria-hidden="true"/></>}
                      <button type="button" className="secondary" aria-label={`修订 ${requirement.display_code}`} disabled={actioningId!==null||updating||refreshRequired} onClick={event=>openRevision(requirement,event.currentTarget)}>修订需求</button>
                      <button type="button" className="secondary" aria-label={`查看 ${requirement.display_code} 审核记录`} onClick={event=>{setHistoryTrigger(event.currentTarget);setHistory(requirement)}}>审核记录</button>
                    </div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <RequirementReviewChart rows={requirements} onFilter={chartFilter} activeFilter={reviewFilter} unavailable={loading||refreshRequired||(!requirements.length&&!!error)}/>
      {batchRows&&<RequirementBatchDialog projectId={projectId} requirements={batchRows} returnFocus={batchTrigger} onClose={()=>setBatchRows(null)} onSaved={afterBatch}/>}

      {inspecting && <RequirementInspector key={inspecting.id} projectId={projectId} requirement={inspecting} returnFocus={inspectorTrigger} onClose={() => setInspecting(null)} />}
      {history && <RequirementReviewHistory key={history.id} requirement={history} returnFocus={historyTrigger} onClose={() => setHistory(null)} />}
      {rejecting && <DetailOverlay title="驳回需求" variant="drawer" subtitle={`${rejecting.display_code} · ${rejecting.parameter_name} · V${rejecting.current_revision}`} eyebrow="需求审核 · 退回修订" returnFocus={rejectTrigger} fallbackFocus={rejectFallback} initialFocus={reasonInput} locked={actioningId !== null} onClose={() => setRejecting(null)} footer="驳回保留需求和来源；修订后需重新审核。关闭不提交。">
        <p>当前目标：{formatRequirementTarget(rejecting)}</p><blockquote>{rejecting.source_excerpt || '未记录来源摘录'}</blockquote>
        {decisionError && <Notice kind="error">{decisionError}</Notice>}
        <form className="form-grid" onSubmit={event => { event.preventDefault(); void handleDecision(rejecting, 'rejected', rejectionDraft.reason) }}>
          <label className="wide">驳回原因（选填）<textarea ref={reasonInput} aria-label="驳回原因" value={rejectionDraft.reason} onChange={event => setRejectionDraft({ id: rejecting.id, reason: event.target.value })} maxLength={2000} rows={5} placeholder="说明原文、数值或依据中需要修订的问题" disabled={actioningId !== null} /></label>
          <div className="form-actions"><button type="submit" disabled={actioningId !== null || refreshRequired}>{actioningId ? '正在保存…' : '提交驳回'}</button></div>
        </form>
      </DetailOverlay>}

      {revisionOpen&&selectedForEdit && (
        <DetailOverlay title="修订需求" variant="wide" eyebrow="需求审核 · 新版本修订" subtitle={`${selectedForEdit.display_code} · ${selectedForEdit.parameter_name} · V${selectedForEdit.current_revision}`} returnFocus={revisionTrigger} fallbackFocus={revisionFallback} initialFocus={revisionInput} locked={updating} onClose={()=>setRevisionOpen(false)} footer="关闭不提交；同一需求的未提交输入在本页保留。实质变化建立新版本后重新审核。">
          {message&&<Notice kind="success">{message}</Notice>}
          {updateError&&<Notice kind="error">{updateError}</Notice>}
          <p className="hint">
            修订仅改变当前版本；确认记录与旧版本保留，下游用例、追溯与一致性需复核。
          </p>
          <form className="form-grid" onSubmit={(event) => void handleUpdate(event)}>
            <label>
              要修订的需求
              <select
                aria-label="选择要修订的需求"
                value={selectedForEdit?.id ?? ''}
                onChange={(event) => { setEditingId(event.target.value); setNewValue(null); setSourceExcerpt(''); setUpdateError('') }}
              >
                {requirements.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.display_code} · {item.parameter_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              新数值
              <input
                ref={revisionInput}
                aria-label="修订后的数值"
                value={newValue ?? selectedForEdit?.value_text ?? ''}
                onChange={(event) => setNewValue(event.target.value)}
                required
              />
            </label>
            <label className="wide">
              修订来源说明
              <input
                aria-label="修订来源说明"
                value={sourceExcerpt}
                onChange={(event) => setSourceExcerpt(event.target.value)}
                placeholder="例如：发动机最大扭矩 2800 N·m（合成变更记录 CN-01）"
              />
            </label>
            <div className="form-actions">
              <button type="submit" disabled={updating || actioningId !== null || refreshRequired}>
                提交修订
              </button>
            </div>
          </form>
        </DetailOverlay>
      )}
    </>
  )
}
