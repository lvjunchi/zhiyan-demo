import { useEffect, useState } from 'react'
import { api } from '../api'
import { MODULE_TABS, TAB_LABELS, nextModule, type ModuleTabKey, type NavigateTo } from '../navigation'
import type { WorkspaceData } from '../workspaceTypes'
import { reviewStatusLabels, toErrorMessage, formatTime } from '../uiSupport'
import { Icon } from './Icon'

const objectLabels: Record<string, string> = { requirement: '工程需求', variant: '变型点', part: '零件决策', design_review: '设计评审', fmea_document: 'DFMEA', test_case: '试验用例' }
const changeFields = [['parameter_name', '参数名称'], ['value_text', '目标值'], ['operator', '比较符'], ['unit', '单位'], ['source_location', '来源位置'], ['source_excerpt', '来源摘录']] as const
const stateLabels = { empty: '待生成', attention: '待处理', reviewed: '已记录' }
const target = (value: Record<string, unknown>) => `${typeof value.operator === 'string' ? value.operator + ' ' : ''}${String(value.value_text ?? '未记录')} ${String(value.unit ?? '')}`.trim()
export function WorkspaceJourney({ projectId, tab, onNavigate }: { projectId: string; tab: ModuleTabKey; onNavigate: NavigateTo }) {
  const [data, setData] = useState<WorkspaceData | null>(null)
  const [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [expanded, setExpanded] = useState(false)
  const [selectedId, setSelectedId] = useState('')
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    let active = true
    api.getWorkspace(projectId).then(value => { if (active) { setData(value); setError(''); setLoading(false) } })
      .catch((err: unknown) => { if (active) { setError(toErrorMessage(err)); setLoading(false) } })
    return () => { active = false }
  }, [projectId, tab, refresh])
  useEffect(() => {
    let timer: number | undefined
    const reload = () => { window.clearTimeout(timer); timer = window.setTimeout(() => setRefresh(n => n + 1), 200) }
    window.addEventListener('zhiyan:data-changed', reload)
    return () => { window.removeEventListener('zhiyan:data-changed', reload); window.clearTimeout(timer) }
  }, [])
  const current = data?.stages.find(s => s.key === tab)
  const next = nextModule(tab)
  const module = MODULE_TABS.find(item => item.key === tab)
  const change = data?.changes.find(c => c.requirement_id === selectedId) ?? data?.changes[0]
  return <section className="work-journey" aria-label="当前模块工作提示" aria-busy={loading}>
    <div className="work-overview">
    <div className="work-current">
    <div className="work-context-heading">
      <div className="work-context-title"><span className="work-context-icon"><Icon name={module?.icon ?? 'overview'} size={22} /></span><div><small>当前工作</small><strong>{current?.action ?? '读取工作状态与当前待办'}</strong></div></div>
      <div className="work-tools">
        {tab === 'requirements' && <button type="button" className="secondary" aria-expanded={expanded} onClick={() => setExpanded(v => !v)}>变更影响{data ? ` · ${data.changes.length}` : ''}</button>}
        <button type="button" className="context-refresh" aria-label="刷新工作状态" onClick={() => { setLoading(true); setRefresh(n => n + 1) }}><Icon name="consistency" size={16} />刷新状态</button>
      </div>
    </div>
    {error ? <div className="work-unavailable" role="status">操作进度暂不可用：{error}<button type="button" onClick={() => { setLoading(true); setRefresh(n => n + 1) }}>重试进度</button></div> : data ? current ? <div className="work-context-detail">
      <div className="work-context-metrics"><span className={`context-state ${current.state}`}>{stateLabels[current.state]}</span><span>待办检查 <strong>{current.pending_count}</strong></span><span>待复核 <strong>{current.stale_count}</strong></span><span>已登记 <strong>{current.record_count}</strong></span></div>
      {!!current.notes.length && <p>{current.notes.join(' · ')}</p>}
    </div> : <p className="state">当前模块暂没有可用状态，请刷新或核对服务。</p> : <p className="state">正在读取实际工作状态…</p>}
    </div>
    <section className="work-next-step" aria-label="下一步操作">
      <small>{next ? '下一步操作' : '返回项目工作台'}</small>
      <strong>{next ? TAB_LABELS[next] : '项目总览'}</strong>
      <p>按需继续处理，当前审核状态不会自动改变</p>
      <button type="button" className="context-next" aria-label={next ? `下一步：${TAB_LABELS[next]}` : '回到项目总览'} onClick={() => onNavigate(next ?? 'overview')}>{next ? '进入下一步' : '回到项目总览'}<Icon name="arrow" size={18} /></button>
    </section>
    </div>
    {expanded && !error && data && <div className="change-impact" aria-label="需求变更影响"><div className="change-impact-header"><div><h2>需求变更影响</h2><p>相邻需求版本对比 · 当前对象引用证据</p></div>{!!data.changes.length && <label>选择修订<select aria-label="选择变更需求" value={change?.requirement_id ?? ''} onChange={e => setSelectedId(e.target.value)}>{data.changes.map(c => <option key={c.requirement_id} value={c.requirement_id}>{c.display_code} · {c.parameter_name} · V{c.to_revision}</option>)}</select></label>}</div>
      {change ? <><div className="change-diff"><div><small>{change.display_code} · V{change.from_revision}</small><strong>{target(change.before)}</strong></div><Icon name="arrow" size={22} /><div><small>当前 V{change.to_revision} · {formatTime(change.created_at)}</small><strong>{target(change.after)}</strong></div><button type="button" className="secondary" onClick={() => onNavigate('requirements', { objectId: change.requirement_id, revision: change.to_revision, message: change.parameter_name, origin: 'change', returnTab: tab })}>查看源需求</button></div>
        <div className="table-wrap change-fields"><table><thead><tr><th>变更字段</th><th>V{change.from_revision}</th><th>V{change.to_revision}</th></tr></thead><tbody>{changeFields.filter(([key]) => change.before[key] !== change.after[key]).map(([key, label]) => <tr key={key}><th>{label}</th><td>{String(change.before[key] ?? '未记录')}</td><td>{String(change.after[key] ?? '未记录')}</td></tr>)}</tbody></table></div>
        <div className="impact-summary">已记录 {change.impacts.length} 项关联成果 · {change.impacts.filter(i => i.validity === 'stale').length} 项待复核</div>
        <div className="table-wrap"><table><thead><tr><th>关联成果</th><th>当前版本 / 审核</th><th>有效性</th><th>版本引用依据</th><th>操作</th></tr></thead><tbody>{change.impacts.map(item => <tr key={`${item.object_type}:${item.object_id}`}><td><strong>{item.display_code}</strong><small className="impact-kind">{objectLabels[item.object_type] ?? '工程记录'}</small></td><td>V{item.revision} · <span>{reviewStatusLabels[item.review_status as keyof typeof reviewStatusLabels] ?? item.review_status}</span></td><td><span className={`status ${item.validity === 'stale' ? 'rejected' : 'confirmed'}`}>{item.validity === 'stale' ? '待复核' : '当前有效'}</span>{!item.applicable && <small>已不适用</small>}</td><td>{item.references.map((r, index) => <p key={index}>{r.evidence} · 引用 V{r.referenced_revision} / 当前 V{r.current_revision}<small className="impact-kind">{r.upstream_display_code ?? r.upstream_id}</small></p>)}</td><td><button type="button" className="secondary" aria-label={`处理 ${item.display_code}`} onClick={() => onNavigate(item.tab, { objectId: item.object_id, revision: item.revision, message: `${change.display_code} → ${item.display_code}`, origin: 'change', returnTab: tab })}>查看 / 复核</button></td></tr>)}</tbody></table></div>{!change.impacts.length && <p className="state">当前没有查到已保存的下游引用；不能据此认定没有工程影响。</p>}</> : <p className="state">尚无可对比的需求修订，修改并保存需求后查看版本影响。</p>}
      <p className="hint">{data.scope_note} 待办检查可涉及同一对象的多个缺口，阶段标记不替代审核、试验结论或材料门禁。</p>
    </div>}
  </section>
}
