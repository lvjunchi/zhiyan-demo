import type { ReactNode } from 'react'
import { ProductImage } from '../components/ProductImage'
import { Icon } from '../components/Icon'
import type { IconName, TabKey } from '../navigation'
import { locateOverview } from './overviewProgress'
import { nextOverviewAction } from './overviewActions'
import { OverviewIntroduction } from './OverviewIntroduction'
import { OverviewTrace } from './OverviewTrace'
import { OverviewPackage } from './OverviewPackage'
import { OverviewRisk } from './OverviewRisk'
import type { OverviewArtifact, ProjectOverview } from '../types'
import { executionLabels, formatTime, packageStatusLabels, reviewStatusLabels } from '../uiSupport'
import './showcase.css'

type Navigate = (tab: TabKey) => void
const ACTIONS: Record<string, string> = {
  'requirement.updated': '修订需求版本', 'requirement.confirmed': '确认工程需求',
  'source_document.created': '登记来源文档', 'source_document.parsed': '完成协议解析',
  'design_review.generated': '生成设计评审', 'design_review.confirmed': '确认设计评审',
  'dfmea.generated': '生成 DFMEA 草案', 'fmea.generated': '生成 DFMEA 草案',
  'fmea.confirmed': '确认 DFMEA', 'test_plan.generated': '生成试验方案',
  'test_run.created': '记录试验执行', 'material_package.generated': '生成评审材料包',
  'material_package.created': '生成评审材料包', 'material_package.approved': '批准并冻结材料包',
  'similarity.generated': '检索相似历史项目', 'consistency_check.created': '生成一致性报告',
  'consistency.checked': '执行一致性检测', 'issue.closed': '关闭澄清问题',
}
function Header({ title, caption, action, onClick }: { title: string; caption?: string; action?: string; onClick?: () => void }) {
  return <header className="dash-card-head"><div><h3>{title}</h3>{caption && <small>{caption}</small>}</div>{action && <button type="button" className="dash-link" onClick={onClick}>{action}<Icon name="arrow" size={13} /></button>}</header>
}
function Fact({ label, value, tone }: { label: string; value: ReactNode; tone?: string }) {
  return <div className="dash-fact" data-tone={tone}><span>{label}</span><strong>{value}</strong></div>
}
function Artifact({ label, value }: { label: string; value: OverviewArtifact | null }) {
  return <div className="dash-artifact"><span>{label}</span><small>{value ? `V${value.revision} · ${reviewStatusLabels[value.status as keyof typeof reviewStatusLabels] ?? value.status}` : '尚未生成'}</small>{value?.needs_reconfirmation && <em>待复核</em>}</div>
}
export function ProjectShowcase({ data, onNavigate, onReload }: { data: ProjectOverview; onNavigate: Navigate; onReload: () => void }) {
  const coverage = data.traceability
  const location = locateOverview(data)
  const nextAction = nextOverviewAction(data)
  const unimported = !data.requirements.total && !(data.cockpit?.resources.source_documents)
  const pack = data.package
  const resources = data.cockpit?.resources
  const parameters = data.cockpit?.parameters ?? []
  const activity = data.cockpit?.recent_activity ?? []
  const productParameters = [{ key: 'engineMaxTorque', label: '发动机最大扭矩' }, { key: 'gearboxRatedInputTorque', label: '最低额定输入扭矩' }, { key: 'gearCount', label: '挡位要求' }]
  const flow: { title: string; detail: string; icon: IconName; tab: TabKey }[] = [
    { title: '协议导入', detail: resources ? `${resources.source_documents} 份已导入` : '来源待登记', icon: 'parsing', tab: 'parsing' },
    { title: '需求结构化', detail: `${data.requirements.confirmed}/${data.requirements.total} 项已确认`, icon: 'requirements', tab: 'requirements' },
    { title: '变型设计', detail: `变型 ${data.spectrum.variant_points} · 零件 ${data.spectrum.reusable_parts}`, icon: 'bases', tab: 'bases' },
    { title: '试验验证', detail: coverage ? `${coverage.covered_count}/${coverage.denominator} 条有效覆盖` : '尚未生成方案', icon: 'testing', tab: 'testing' },
    { title: '评审交付', detail: pack ? (pack.requires_regeneration ? '旧版材料待更新' : packageStatusLabels[pack.status]) : '尚未生成材料包', icon: 'packages', tab: 'packages' },
  ]
  type MetricTone = 'blue' | 'teal' | 'green' | 'amber' | 'red' | 'muted'
  let executionTone: MetricTone = 'muted'
  if (coverage) {
    executionTone = 'amber'
    if (coverage.execution_summary.fail || coverage.execution_summary.invalid) executionTone = 'red'
    else if ((coverage.execution_summary.pass ?? 0) === coverage.denominator) executionTone = 'green'
  }
  const metrics: { label: string; value: string; detail: string; icon: IconName; tab: TabKey; tone: MetricTone }[] = [
    { label: '需求总量', value: String(data.requirements.total), detail: `${data.issues.open} 项待澄清`, icon: 'requirements', tab: 'requirements', tone: 'blue' },
    { label: '有效用例覆盖率', value: coverage ? `${coverage.coverage_percentage}%` : '—', detail: '当前版本定义', icon: 'testing', tab: 'testing', tone: coverage ? 'teal' : 'muted' },
    { label: '当前执行通过', value: coverage ? `${coverage.execution_summary.pass ?? 0}/${coverage.denominator}` : '—', detail: '按验证要求去重', icon: 'check', tab: 'testing', tone: executionTone },
    { label: '阻断冲突', value: data.consistency ? String(data.consistency.blocking_open) : '—', detail: !data.consistency ? '尚未检查' : data.consistency.check.validity === 'stale' ? '上次报告 · 待重检' : '最近检测报告', icon: 'consistency', tab: 'consistency', tone: data.consistency ? data.consistency.blocking_open ? 'red' : 'green' : 'muted' },
  ]
  return <div className={`project-dashboard${unimported ? ' is-unimported' : ''}`}>
    <div className="dash-workflow">

      <nav className="dash-flow" aria-label="研发流程">{flow.map((item, index) => { const detail = unimported ? ['等待导入技术协议', '解析条款并审核', '选型与变型分析', '方案、用例与证据', '汇编当前版本材料'][index] : item.detail; return <button type="button" key={item.tab} aria-current={location.phase === index ? 'step' : undefined} onClick={() => onNavigate(item.tab)}><span className="dash-flow-icon"><Icon name={item.icon} size={19} /></span><div><strong>{item.title}</strong><small title={detail}>{detail}</small></div>{index < flow.length - 1 && <Icon name="arrow" size={16} className="dash-flow-arrow" />}</button> })}</nav>
    </div>
    {unimported ? <OverviewIntroduction data={data} onNavigate={onNavigate} /> : <>
    <div className="dash-top">
      <section className="dash-product" aria-label="项目产品总览"><header><span className="dash-eyebrow"><i />当前成果 · {location.label}<span>{location.detail}</span></span><h2>{data.project.name}</h2><p>{data.project.customer}<span> / </span>{data.project.product}</p></header><div className="dash-product-body"><dl>{productParameters.map((item) => { const parameter = parameters.find((value) => value.key === item.key); return <div key={item.key}><dt>{item.label}</dt><dd>{parameter ? `${parameter.operator === '>=' ? '≥ ' : parameter.operator === '<=' ? '≤ ' : ''}${parameter.value_text} ${parameter.unit}` : '待录入'}{parameter && <small>V{parameter.revision}</small>}</dd></div> })}</dl><div className="dash-machine"><ProductImage /><small>重型变速器 · 产品展示</small></div></div><footer><div className="dash-next-action" aria-label="下一步建议" data-tone={nextAction.tone}><div><small>下一步建议</small><strong title={nextAction.detail}>{nextAction.title}</strong></div><button type="button" onClick={() => onNavigate(nextAction.tab)}>去处理<Icon name="arrow" size={13} /></button></div><button type="button" className="dash-refresh" onClick={onReload} aria-label="刷新项目数据">刷新</button></footer></section>
      <div className="dash-verification"><section className="dash-metrics" aria-label="项目实时指标">{metrics.map((item) => <button type="button" key={item.label} data-tone={item.tone} aria-label={item.label} onClick={() => onNavigate(item.tab)}><Icon name={item.icon} size={18} /><span>{item.label}</span><strong>{item.value}</strong><small>{item.detail}</small></button>)}</section>
        <OverviewTrace data={data} onNavigate={onNavigate} />
      </div>
    </div>
    <div className="dash-middle"><section className="dash-card dash-agents" aria-label="三智能体成果展示"><Header title="三智能体协同工作" caption="工程知识辅助 · 人工确认 · 成果可追溯" /><div className="dash-agent-grid">
      <article aria-label="需求解析智能体成果"><header><span><Icon name="parsing" size={20} /></span><h3>需求解析智能体</h3></header><p>技术协议 → 结构化工程需求</p><div className="dash-agent-facts"><div className="dash-review-status" role="group" aria-label="需求审核状态"><span data-tone="green">已确认<strong>{data.requirements.confirmed}</strong></span><span data-tone="amber">待审核<strong>{data.requirements.draft + data.requirements.pending_review}</strong></span><span data-tone="red">已驳回<strong>{data.requirements.rejected}</strong></span><span data-tone="amber">待复核<strong>{data.requirements.stale}</strong></span><span data-tone={data.issues.open ? 'amber' : 'green'} title="待澄清问题"><span>待澄清</span><strong>{data.issues.open}</strong></span></div></div><div className="dash-agent-bottom"><button type="button" aria-label="查看需求清单" onClick={() => onNavigate('requirements')}>需求清单<Icon name="arrow" size={13} /></button><button type="button" className="dash-link" onClick={() => onNavigate('parsing')} aria-label="协议与澄清问题">协议澄清</button></div></article>
      <article aria-label="变型设计智能体成果"><header><span><Icon name="bases" size={20} /></span><h3>变型设计智能体</h3></header><p>型谱差异 → 变型与风险评审</p><div className="dash-agent-facts"><Fact label="变型 / 复用决策" value={`${data.spectrum.variant_points} / ${data.spectrum.reusable_parts}`} /><Artifact label="设计评审" value={data.design_review} /><Artifact label="DFMEA" value={data.dfmea} /></div><div className="dash-agent-bottom"><button type="button" aria-label="查看设计成果" onClick={() => onNavigate('design')}>设计成果<Icon name="arrow" size={13} /></button><button type="button" className="dash-link" onClick={() => onNavigate('bases')} aria-label="型谱与变型依据">型谱变型</button></div></article>
      <article aria-label="试验验证智能体成果"><header><span><Icon name="testing" size={20} /></span><h3>试验验证智能体</h3></header><p>试验用例 → 验证证据与材料</p><div className="dash-agent-facts"><Fact label="有效覆盖" value={coverage ? `${coverage.covered_count}/${coverage.denominator}` : '尚未生成'} /><Fact label="执行通过要求" value={coverage ? `${coverage.execution_summary.pass ?? 0} 条` : '—'} /><Fact label="样件比对" value={data.samples.latest_result ? executionLabels[data.samples.latest_result] : '尚未比对'} /></div><div className="dash-agent-bottom"><button type="button" aria-label="查看试验与追溯" onClick={() => onNavigate('testing')}>试验追溯<Icon name="arrow" size={13} /></button><button type="button" className="dash-link" onClick={() => onNavigate('samples')} aria-label="样件检验记录">样件检验</button></div></article>
    </div></section>
      <OverviewRisk data={data} onOpenWorkspace={() => onNavigate('coordination')} />
    </div>
    <div className="dash-bottom"><section className="dash-card dash-knowledge"><Header title="工程知识底座" caption="受控候选与可查询来源" /><div>{([
      ['产品型谱库', resources ? `${resources.product_bases}款` : '—', 'bases', 'bases'], ['历史项目库', resources ? `${resources.history_projects}个` : '—', 'design', 'overview'], ['来源证据库', resources ? `${resources.source_documents}份` : '—', 'parsing', 'requirements'], ['检测规则', '参数 / 版本 / 工况', 'consistency', 'consistency'],
    ] as const).map(([label, value, tab, icon]) => <button type="button" key={label} onClick={() => onNavigate(tab)}><span className="dash-knowledge-icon"><Icon name={icon} size={32} /></span><strong>{label}</strong><small className={tab === 'consistency' ? undefined : 'dash-knowledge-count'}>{tab === 'consistency' ? ['参数', '版本', '工况'].map(term => <span key={term}>{term}</span>) : value}</small></button>)}</div></section>
      <OverviewPackage value={pack} onOpen={() => onNavigate('packages')} />
      <section className="dash-card dash-activity"><Header title="最近任务与动态" action="指标与能力说明" onClick={() => onNavigate('settings')} /><div className="dash-activity-scroll" role="region" aria-label="项目动态记录" tabIndex={0}><ol>{activity.map((event) => <li key={event.id}><i /><span title={event.action}>{ACTIONS[event.action] ?? '业务记录已更新'}<small>{event.object_revision ? `V${event.object_revision}` : ''}</small></span><time dateTime={event.created_at}>{formatTime(event.created_at)}</time></li>)}</ol>{!activity.length && <p className="dash-empty">暂无审计记录，业务操作后显示</p>}</div><footer>最近 {activity.length} 条真实审计 · 手动滚动查看</footer></section>
    </div></>}
  </div>
}
