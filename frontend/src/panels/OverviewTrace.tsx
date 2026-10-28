import { useState } from 'react'
import { DetailOverlay } from '../components/DetailOverlay'
import { Icon } from '../components/Icon'
import type { TabKey } from '../navigation'
import type { OverviewTraceItem, ProjectOverview } from '../types'
import { executionLabels, formatTime, reviewStatusLabels } from '../uiSupport'
import './overview-trace.css'

export function OverviewTrace({data, onNavigate}: {data: ProjectOverview; onNavigate: (tab: TabKey) => void}) {
  const [selection, setSelection] = useState<{item: OverviewTraceItem; trigger: HTMLElement} | null>(null)
  const rows = data.cockpit?.traceability_items ?? []
  const coverage = data.traceability
  const check = data.consistency
  const parameter = (item: OverviewTraceItem) => data.cockpit?.parameters.find(value => value.requirement_id === item.requirement_id)
  const target = (item: OverviewTraceItem) => {
    const value = parameter(item)
    if (!value) return '基准未提供'
    const operator = ({'>=':'≥','<=':'≤',text:'',range:''} as Record<string,string>)[value.operator] ?? value.operator
    return value.key === 'pto' && value.value_text === 'required' ? '需配置取力器' : `${operator} ${value.value_text} ${value.unit}`.trim()
  }
  const navigate = (tab: TabKey) => {setSelection(null); onNavigate(tab)}
  return <section className="dash-card dash-trace dash-trace-chain" aria-label="当前验证追溯">
    <header className="dash-card-head">
      <div><h3>一致性检测</h3><small>需求 → 设计评审 → 试验</small></div>
      <div className="trace-header-actions">
        <div className="trace-coverage" role="img" aria-label={coverage ? `有效用例覆盖率 ${coverage.coverage_percentage}%（${coverage.covered_count}/${coverage.denominator}）` : '有效用例覆盖率尚未计算'}>
          <svg viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="14" className="trace-ring-track"/><circle cx="18" cy="18" r="14" className="trace-ring-value" pathLength="100" strokeDasharray={`${coverage?.coverage_percentage ?? 0} 100`}/></svg>
          <span><small>有效用例覆盖</small><strong>{coverage ? `${coverage.covered_count}/${coverage.denominator}` : '—'}</strong></span>
        </div>
        <button type="button" className="dash-link" onClick={() => onNavigate('consistency')}>查看检测<Icon name="arrow" size={13}/></button>
      </div>
    </header>
    <div className="dash-check-state" aria-label="一致性检查摘要"><span>{check ? `${check.blocking_open} 项阻断冲突 · ${check.open_conflicts} 项开放冲突` : '尚未检查'}</span><small>{check ? `${check.review_pending} 项待审核${check.check.validity === 'stale' ? ' · 报告待更新' : ''}` : '执行检测后生成报告'}</small></div>
    <div className="dash-table-scroll"><table aria-label="需求设计试验追溯表"><colgroup><col style={{width:'33%'}}/><col style={{width:'23%'}}/><col style={{width:'20%'}}/><col style={{width:'15%'}}/><col style={{width:'9%'}}/></colgroup><thead><tr><th>需求项</th><th>设计评审项</th><th>试验项</th><th>执行结果</th><th>操作</th></tr></thead><tbody>{rows.map(item => {
      const designs = item.design_items ?? [], cases = item.test_cases ?? []
      const designText = designs.map(value => `${value.display_code} ${value.check_point}`).join('；')
      const caseText = cases.map(value => `${value.display_code} ${value.title}`).join('；')
      const pending = cases.some(value => value.review_status === 'draft' || value.review_status === 'pending_review') || designs.some(value => value.status === 'draft' || value.status === 'pending_review')
      const stale = cases.some(value => value.validity === 'stale') || designs.some(value => value.validity === 'stale')
      return <tr key={item.requirement_id ?? item.key}>
        <td title={`${item.display_code ?? '需求缺失'} · ${item.label} ${target(item)}`}><span className="trace-cell-text">{item.label}</span><small>V{item.requirement_revision ?? '—'}</small><span className="trace-target">{target(item)}</span></td>
        <td title={designText || '没有直接关联的设计评审项'}><span className="trace-cell-text">{designs.length ? `${designs[0].display_code} ${designs[0].check_point}` : '未关联'}{designs.length > 1 ? ` +${designs.length-1}` : ''}</span></td>
        <td title={caseText || '尚未关联试验用例'}><span className="trace-cell-text">{cases.length ? `${cases[0].display_code} ${cases[0].title}` : '未关联'}{cases.length > 1 ? ` +${cases.length-1}` : ''}</span></td>
        <td title={`${item.reason} · ${item.covered ? '已覆盖' : '未覆盖'}${pending ? ' · 待审核' : ''}${stale ? ' · 待复核' : ''}`}><span className={`trace-outcome ${item.execution}`}>{executionLabels[item.execution]}</span>{(pending || stale) && <span className="trace-review-dot" aria-label={stale ? '待复核' : '待审核'} title={stale ? '关联成果待复核' : '关联成果待审核'}><span className="trace-hidden">{pending ? '待审核' : ''}{stale ? ' · 待复核' : ''}</span></span>}<span className="trace-hidden">{item.covered ? '已覆盖' : '未覆盖'}</span></td>
        <td><button type="button" className="dash-link" aria-label={`查看${item.label}追溯详情`} onClick={event => setSelection({item,trigger:event.currentTarget})}>查看</button></td>
      </tr>
    })}</tbody></table></div>
    {!rows.length && <p className="dash-empty">尚无追溯明细，生成方案后查看</p>}
    <footer><span>覆盖、执行与审核分别记录 · 旧版结果仅作历史</span><span><i className="trace-review-dot"/> 待审核 / 复核</span></footer>
    {selection && <DetailOverlay title={`${selection.item.label} · 追溯详情`} subtitle="核对需求版本、设计依据与试验记录，可进入对应工作台继续处理。" eyebrow="需求—设计—试验" variant="wide" returnFocus={selection.trigger} closeLabel="关闭追溯详情" onClose={() => setSelection(null)}>
      <div className="trace-detail">
        <section><header><h3>需求基准</h3><button type="button" onClick={() => navigate('requirements')}>进入需求清单 →</button></header><p><strong>{selection.item.display_code ?? '需求尚未建立'}</strong> · 当前需求 V{selection.item.requirement_revision ?? '—'}</p><p>{selection.item.label}：<strong>{target(selection.item)}</strong></p><p>{parameter(selection.item) ? reviewStatusLabels[parameter(selection.item)!.review_status] : '审核状态未提供'}{parameter(selection.item)?.validity === 'stale' ? ' · 待复核' : ''}</p></section>
        <section><header><h3>设计评审依据</h3><button type="button" onClick={() => navigate('design')}>进入设计成果 →</button></header>{selection.item.design_items?.length ? selection.item.design_items.map(value => <article key={value.id}><h4>{value.display_code} · {value.check_point}</h4><p>评审 V{value.revision} · 引用需求 V{value.requirement_revision} · {reviewStatusLabels[value.status]}{value.validity === 'stale' ? ' · 待复核' : ''}</p><p>{value.standard_basis}</p></article>) : <p>尚无直接关联的设计评审项，可进入设计成果查看或补充。</p>}</section>
        <section><header><h3>试验依据与记录</h3><button type="button" onClick={() => navigate('testing')}>进入试验追溯 →</button></header>{selection.item.test_cases?.length ? selection.item.test_cases.map(value => <article key={value.id}><h4>{value.display_code} · {value.title}</h4><p>用例 V{value.revision} · {reviewStatusLabels[value.review_status]}{value.validity === 'stale' ? ' · 待复核' : ''} · {value.coverage_valid ? '当前有效覆盖' : '不计有效覆盖'}</p><p>引用需求：{value.requirement_refs.map(ref => `${ref.display_code ?? ref.requirement_id} V${ref.revision}（当前 V${ref.current_revision ?? '—'}）`).join('；')}</p><dl><dt>试验工况</dt><dd>{value.conditions_text || '未补充'}</dd><dt>加载条件</dt><dd>{value.load_conditions_text || '未补充'}</dd><dt>通过准则</dt><dd>{value.acceptance_criteria || '未补充'}</dd></dl>{value.runs.length ? value.runs.map(run => <p className="trace-run" key={run.id}>执行 #{run.run_no} · 绑定用例 V{run.case_revision} · {executionLabels[run.result]} · {run.mode} · {formatTime(run.created_at)}<br/>{run.reason}<br/>{run.evidence}</p>) : <p>尚无执行记录</p>}</article>) : <p>尚无关联试验用例。</p>}</section>
        <section><header><h3>当前执行结论</h3><button type="button" onClick={() => navigate('consistency')}>进入一致性检测 →</button></header><p><span className={`trace-outcome ${selection.item.execution}`}>{executionLabels[selection.item.execution]}</span> · {selection.item.covered ? '已覆盖' : '未覆盖'}</p><p>{selection.item.reason}</p><p>参数、版本、引用和工况冲突以一致性检测报告为准，执行通过不等于整条链路已审核通过。</p></section>
      </div>
    </DetailOverlay>}
  </section>
}
