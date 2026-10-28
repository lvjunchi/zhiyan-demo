import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { OverviewPanel } from './OverviewPanel'
import { nextOverviewAction } from './overviewActions'
import type { Project, ProjectOverview } from '../types'

const project: Project = {
  id: 'p1',
  display_code: 'P01',
  name: '法士特—陕汽定制项目试点',
  customer: '陕汽集团',
  product: '重型商用车变速器',
  stage: 'requirement_parsing',
  created_at: '2026-10-19T00:00:00+00:00',
  updated_at: '2026-10-19T00:00:00+00:00',
}

it('summarizes live project figures without confusing coverage with execution', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(makeOverview({ traceability: { mode: 'rule', scope_label: '5 条', denominator: 5, covered_count: 4, coverage_percentage: 80, execution_summary: { pass: 2, fail: 1, not_run: 2 } } }))))
  render(<OverviewPanel project={project} onNavigate={() => undefined} />)
  const metrics = await screen.findByRole('region', { name: '项目实时指标' })
  expect(within(metrics).getByLabelText('需求总量')).toHaveTextContent('13')
  expect(within(metrics).getByLabelText('有效用例覆盖率')).toHaveTextContent('80%')
  expect(within(metrics).getByLabelText('当前执行通过')).toHaveTextContent('2/5')
})

it('explains why a protocol alone has no response chart and opens coordination entry', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(makeOverview({coordination:{topic_count:0,record_count:0,metrics_available:0,highest_risk:'insufficient',high_risk_topics:0,rule_label:'COORD-DEMO-V1',source_label:'合成记录 / 规则计算'}}))))
  const navigate = vi.fn()
  render(<OverviewPanel project={project} onNavigate={navigate} />)
  expect(await screen.findByText('响应图需要配对沟通记录，协议导入不包含这些记录。')).toBeVisible()
  await userEvent.click(screen.getByRole('button',{name:'查看风险'}))
  expect(navigate).toHaveBeenCalledWith('coordination')
})

function makeOverview(
  overrides: Partial<ProjectOverview> = {},
): ProjectOverview {
  return {
    project: {
      id: 'p1',
      display_code: 'P01',
      name: project.name,
      customer: project.customer,
      product: project.product,
      stage: project.stage,
      updated_at: project.updated_at,
    },
    requirements: {
      total: 13,
      confirmed: 13,
      draft: 0,
      pending_review: 0,
      rejected: 0,
      stale: 0,
    },
    issues: {
      open: 1,
      closed: 1,
      open_by_severity: { blocking: 0, high: 0, medium: 1, low: 0 },
    },
    spectrum: {
      variant_points: 1,
      stale_variant_points: 0,
      reusable_parts: 8,
    },
    design_review: {
      display_code: 'DR-P01',
      status: 'confirmed',
      revision: 1,
      item_count: 6,
      missing_inputs: [],
      needs_reconfirmation: false,
      mode: 'rule',
    },
    dfmea: {
      display_code: 'DFMEA-P01',
      status: 'confirmed',
      revision: 1,
      item_count: 4,
      missing_inputs: [],
      needs_reconfirmation: false,
      mode: 'rule',
      pending_score_count: 0,
    },
    traceability: {
      mode: 'rule',
      scope_label: '验证集 5 条',
      denominator: 5,
      covered_count: 5,
      coverage_percentage: 100,
      execution_summary: { pass: 5, fail: 0, incomplete: 0, invalid: 0 },
    },
    samples: {
      delivery_count: 1,
      comparison_count: 1,
      latest_status: 'confirmed',
      latest_result: 'pass',
    },
    consistency: {
      check: {
        display_code: 'CR-P01-001',
        status: 'confirmed',
        validity: 'current',
        revision: 1,
        summary: {},
      },
      open_conflicts: 0,
      blocking_open: 0,
      review_pending: 0,
    },
    coordination: {
      topic_count: 1,
      record_count: 4,
      metrics_available: 1,
      highest_risk: 'high',
      high_risk_topics: 1,
      rule_label: '协同响应规则 V1',
      source_label: '演示记录',
    },
    package: {
      id: 'pkg1',
      display_code: 'MP-P01-001',
      status: 'ready_to_submit',
      blocker_count: 0,
      warning_count: 1,
      snapshot_hash:
        'abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789',
      created_at: '2026-10-19T01:00:00+00:00',
      frozen_at: null,
    },
    ...overrides,
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response
}

afterEach(() => {
  vi.unstubAllGlobals()
})

it.each([false,true])('shows a useful package snapshot summary (outdated=%s) without approving it', async (outdated) => {
  const baseline = makeOverview()
  const fetchMock = vi.fn().mockResolvedValue(jsonResponse(makeOverview({package:{...baseline.package!,status:'draft',blocker_count:1,warning_count:2,requires_regeneration:outdated}})))
  vi.stubGlobal('fetch',fetchMock)
  const navigate = vi.fn()
  render(<OverviewPanel project={project} onNavigate={navigate}/>)
  const card = await screen.findByRole('region',{name:'评审材料摘要'})
  const checks = within(card).getByRole('group',{name:'材料包快照检查摘要'})
  expect(checks).toHaveTextContent('1 项阻断')
  expect(checks).toHaveTextContent('2 项提示')
  expect(card).toHaveTextContent('MP-P01-001')
  expect(card).toHaveTextContent('尚未冻结')
  expect(card).toHaveTextContent(outdated ? '上次快照 · 待更新' : '生成时快照')
  expect(card).not.toHaveTextContent('可提交')
  await userEvent.click(within(card).getByRole('button',{name:'查看评审材料'}))
  expect(navigate).toHaveBeenCalledWith('packages')
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('keeps clarification counts beside review counts and its action reachable', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(makeOverview({
    issues: {open:2,closed:1,open_by_severity:{blocking:0,high:1,medium:1,low:0}},
  }))))
  const navigate = vi.fn()
  render(<OverviewPanel project={project} onNavigate={navigate} />)
  const card = await screen.findByRole('article',{name:'需求解析智能体成果'})
  const statuses = within(card).getByRole('group',{name:'需求审核状态'})
  expect(statuses).toHaveTextContent('待澄清2')
  expect(within(card).queryByText('待澄清问题',{exact:true})).not.toBeInTheDocument()
  await userEvent.click(within(card).getByRole('button',{name:'协议与澄清问题'}))
  expect(navigate).toHaveBeenCalledWith('parsing')
})

function cockpit(overrides: Partial<NonNullable<ProjectOverview['cockpit']>> = {}): NonNullable<ProjectOverview['cockpit']> {
  return { parameters: [], traceability_items: [], resources: { source_documents: 1, product_bases: 4, history_projects: 5 }, risk_topics: [], recent_activity: [], ...overrides }
}

it('keeps the risk overview compact and opens full causes, progress and records in a read-only dialog', async () => {
  const topic: NonNullable<ProjectOverview['cockpit']>['risk_topics'][number] = {
    id:'topic-r',name:'初始展示 · 接口交付协同（合成）',mode:'rule',created_at:project.created_at,risk_level:'high',
    reasons:['平均响应时延 > 48 小时','反复次数 ≥ 3 次','应参与方缺席率 ≥ 1/3','B计划80%，实际30%，落后50个百分点'],
    average_response_hours:52,iteration_count:4,absence_rate:1/3,response_latencies_hours:[48,52,56],window_start:project.created_at,window_end:project.updated_at,
    headline:'最大进度落后 50 个百分点',source_label:'合成沟通样例',rule_label:'COORD-DEMO-V1',expected_participants:['A','B'],
    progress:{topic_id:'topic-r',rows:[{id:'pg1',revision:1,participant:'B',milestone:'接口交付',planned_percent:80,actual_percent:30,artifact_version:'V1',reported_at:project.created_at,evidence:'合成计划表'}],assessment:{rule_label:'PROGRESS-DEMO-V1',risk_level:'high',alerts:[],data_gaps:[],thresholds:'计划落后≥40个百分点为高风险'}},
    records:[{id:'msg1',topic_id:'topic-r',external_id:'M1',record_type:'message',sender:'A',content_summary:'请核对接口图纸',sent_at:project.created_at,created_at:project.created_at,reply_to_external_id:null}],
    rule_conditions:[{key:'average_response',label:'平均响应时延 > 48 小时',actual:52,threshold:48,hit:true,available:true}],
    metric_details:{response_sample_size:3,expected_participants:['A','B'],actual_participants:['A'],absent_participants:['B'],data_gaps:[]},
  }
  const fetchMock = vi.fn().mockResolvedValue(jsonResponse(makeOverview({cockpit:cockpit({risk_topics:[topic]})})))
  vi.stubGlobal('fetch',fetchMock)
  render(<OverviewPanel project={project} onNavigate={vi.fn()}/>)
  const card = await screen.findByRole('region',{name:'协同风险依据'})
  expect(card).toHaveTextContent('接口交付协同')
  expect(card).toHaveTextContent('最大进度落后 50 个百分点')
  expect(card).toHaveTextContent('合成样例')
  expect(within(card).queryByText('B计划80%，实际30%，落后50个百分点')).not.toBeInTheDocument()
  await userEvent.click(within(card).getByRole('button',{name:'预警详情'}))
  const dialog = screen.getByRole('dialog',{name:'协同预警详情'})
  expect(dialog).toHaveTextContent('B计划80%，实际30%，落后50个百分点')
  expect(dialog).toHaveTextContent('请核对接口图纸')
  expect(dialog).toHaveTextContent('合成计划表')
  expect(within(dialog).getByRole('table',{name:/参与方进度/})).toHaveTextContent('80%')
  expect(within(dialog).getByRole('table',{name:/参与方进度/})).toHaveTextContent('30%')
  await userEvent.click(within(dialog).getByRole('button',{name:'关闭预警详情'}))
  await userEvent.click(within(card).getByRole('button',{name:'指标说明'}))
  expect(screen.getByRole('dialog',{name:'协同指标说明'})).toHaveTextContent('3 个配对样本')
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('shows requirement-design-test links and opens read-only evidence without leaving the overview', async () => {
  const fetchMock = vi.fn().mockResolvedValue(jsonResponse(makeOverview({cockpit: cockpit({
    parameters: [{requirement_id:'r1',key:'gearCount',display_code:'REQ-C-001',label:'挡位数',operator:'=',value_text:'12',unit:'挡',revision:2,review_status:'confirmed',validity:'current'}],
    traceability_items: [{key:'gearCount',label:'挡位数',requirement_id:'r1',display_code:'REQ-C-001',requirement_revision:2,covered:false,coverage_valid:false,valid_case_ids:[],pending_case_ids:['tc1'],execution:'fail',reason:'实测 10 挡，不满足 12 挡',latest_runs:[],
      design_items:[{id:'d1',display_code:'DR-02',check_point:'档位配置核对',standard_basis:'按需求核对档位数',revision:1,requirement_revision:1,status:'confirmed',validity:'stale'}],
      test_cases:[{id:'tc1',display_code:'TC-001',title:'挡位验证',revision:2,review_status:'draft',validity:'current',conditions_text:'静态台架',load_conditions_text:'空载换挡',acceptance_criteria:'应有 12 挡',requirement_refs:[{requirement_id:'r1',revision:2,current_revision:2}],coverage_valid:false,runs:[]}],
    }],
  })})))
  vi.stubGlobal('fetch',fetchMock)
  render(<OverviewPanel project={project} onNavigate={vi.fn()} />)
  const trace = await screen.findByRole('region',{name:'当前验证追溯'})
  for (const name of ['需求项','设计评审项','试验项','执行结果','操作']) expect(within(trace).getByRole('columnheader',{name})).toBeVisible()
  expect(trace).toHaveTextContent('DR-02')
  expect(trace).toHaveTextContent('TC-001')
  expect(trace).toHaveTextContent('未通过')
  expect(trace).toHaveTextContent('待审核')
  expect(trace).toHaveTextContent('V2')
  expect(trace).not.toHaveTextContent('检出率')
  await userEvent.click(within(trace).getByRole('button',{name:'查看挡位数追溯详情'}))
  const dialog = screen.getByRole('dialog',{name:'挡位数 · 追溯详情'})
  expect(dialog).toHaveTextContent('实测 10 挡，不满足 12 挡')
  expect(dialog).toHaveTextContent('应有 12 挡')
  expect(dialog).toHaveTextContent('待复核')
  expect(dialog).toHaveTextContent('引用需求 V1')
  await userEvent.click(within(dialog).getByRole('button',{name:'关闭追溯详情'}))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

describe('overview before and after import', () => {
  it('introduces an unimported project without invented business progress', async () => {
    const navigate = vi.fn()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(makeOverview({
      requirements: { total: 0, confirmed: 0, draft: 0, pending_review: 0, rejected: 0, stale: 0 },
      cockpit: cockpit({ resources: { source_documents: 0, product_bases: 4, history_projects: 5 } }),
      package: null, design_review: null, dfmea: null, traceability: null,
      spectrum: { variant_points: 0, stale_variant_points: 0, reusable_parts: 0 },
    }))))
    render(<OverviewPanel project={project} onNavigate={navigate} />)
    const introduction = await screen.findByRole('region', { name: '项目启动介绍' })
    expect(introduction).toHaveTextContent('尚未导入技术协议')
    expect(screen.queryByRole('region', { name: '项目实时指标' })).not.toBeInTheDocument()
    for (const label of ['需求解析智能体', '变型设计智能体', '试验验证智能体', '一致性检测', '协同风险预警']) expect(screen.getByRole('heading', { name: label })).toBeVisible()
    expect(screen.getByRole('region', { name: '产品与零件展示' })).toHaveTextContent('结构示意')
    expect(screen.getByRole('heading', { name: '工程知识底座' }).closest('section')).toHaveTextContent('4 款')
    await userEvent.click(screen.getByRole('button', { name: '开始导入技术协议' }))
    expect(navigate).toHaveBeenCalledWith('parsing')
  })

  it('keeps an imported document with zero parsed requirements in the working dashboard', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(makeOverview({
      requirements: { total: 0, confirmed: 0, draft: 0, pending_review: 0, rejected: 0, stale: 0 },
      cockpit: cockpit(), package: null, design_review: null, dfmea: null, traceability: null,
      spectrum: { variant_points: 0, stale_variant_points: 0, reusable_parts: 0 },
      samples: { delivery_count: 0, comparison_count: 0, latest_status: null, latest_result: null },
    }))))
    render(<OverviewPanel project={project} onNavigate={vi.fn()} />)
    expect(await screen.findByRole('region', { name: '项目实时指标' })).toBeVisible()
    expect(screen.queryByRole('region', { name: '项目启动介绍' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('下一步建议')).toHaveTextContent('解析已导入文档')
  })

  it('keeps review counts and a real unresolved action visible even when downstream outputs exist', async () => {
    const navigate = vi.fn()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(makeOverview({
      requirements: { total: 13, confirmed: 6, draft: 3, pending_review: 2, rejected: 2, stale: 1 }, cockpit: cockpit(),
    }))))
    render(<OverviewPanel project={project} onNavigate={navigate} />)
    const review = await screen.findByRole('group', { name: '需求审核状态' })
    expect(review).toHaveTextContent('已确认6')
    expect(review).toHaveTextContent('待审核5')
    expect(review).toHaveTextContent('已驳回2')
    expect(review).toHaveTextContent('待复核1')
    const next = screen.getByLabelText('下一步建议')
    expect(next).toHaveTextContent('需求待复核')
    await userEvent.click(within(next).getByRole('button'))
    expect(navigate).toHaveBeenLastCalledWith('requirements')
  })

  it('shows every returned activity in a focusable manual scroll region', async () => {
    const recent_activity = Array.from({ length: 12 }, (_, i) => ({ id: `audit-${i}`, project_id: 'p1', object_type: 'requirement', object_id: `r-${i}`, object_revision: i + 1, action: 'requirement.updated', actor: '工程师', created_at: project.updated_at }))
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(makeOverview({ cockpit: cockpit({ recent_activity }) })) ))
    render(<OverviewPanel project={project} onNavigate={vi.fn()} />)
    const list = await screen.findByRole('region', { name: '项目动态记录' })
    expect(list).toHaveAttribute('tabindex', '0')
    expect(within(list).getAllByRole('listitem')).toHaveLength(12)
    expect(within(list).getByText('V12')).toBeVisible()
  })

  it('shows separate risk levels and backend reasons for multiple topics without inventing an alarm for missing data', async () => {
    const common = { mode: 'rule' as const, created_at: project.created_at, average_response_hours: null, iteration_count: null, absence_rate: null, response_latencies_hours: [], window_start: project.created_at, window_end: project.updated_at }
    const risk_topics = [
      { ...common, id: 'a', name: '样件交接', risk_level: 'high' as const, reasons: ['平均响应时延 > 48 小时'] },
      { ...common, id: 'b', name: '图纸评审', risk_level: 'medium' as const, reasons: ['议题反复次数 > 3 次'] },
      { ...common, id: 'c', name: '新议题', risk_level: 'insufficient' as const, reasons: [] },
    ]
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(makeOverview({ cockpit: cockpit({ risk_topics }) }))))
    render(<OverviewPanel project={project} onNavigate={vi.fn()} />)
    const alerts = await screen.findByRole('list', { name: '协同预警列表' })
    expect(within(alerts).getAllByRole('listitem')).toHaveLength(1)
    expect(within(alerts).getByText('高风险')).toBeVisible()
    expect(alerts).toHaveTextContent('平均响应时延 > 48 小时')
    await userEvent.click(screen.getByRole('button',{name:'预警详情'}))
    const dialog = screen.getByRole('dialog',{name:'协同预警详情'})
    expect(within(dialog).getAllByRole('article')).toHaveLength(3)
    expect(within(dialog).getByText('中风险')).toBeVisible()
    expect(within(dialog).getByText('数据不足')).toBeVisible()
    expect(dialog).toHaveTextContent('暂无当前可用的计算依据')
  })
})

describe('next action is guidance rather than gate approval', () => {
  const clean = () => makeOverview({ issues: { open: 0, closed: 2, open_by_severity: { blocking: 0, high: 0, medium: 0, low: 0 } }, coordination: { topic_count: 0, record_count: 0, metrics_available: 0, highest_risk: 'insufficient', high_risk_topics: 0, rule_label: 'rule', source_label: 'records' } })
  it.each([
    ['rejected requirements', { requirements: { total: 1, confirmed: 0, draft: 0, pending_review: 0, rejected: 1, stale: 0 } }, 'requirements'],
    ['stale variant', { spectrum: { variant_points: 1, stale_variant_points: 1, reusable_parts: 8 } }, 'bases'],
    ['no variant analysis', { spectrum: { variant_points: 0, stale_variant_points: 0, reusable_parts: 0 } }, 'bases'],
    ['missing design review', { design_review: null }, 'design'],
    ['missing fmea', { dfmea: null }, 'design'],
    ['no plan', { traceability: null }, 'testing'],
    ['coverage gap', { traceability: { mode: 'rule', scope_label: '5', denominator: 5, covered_count: 4, coverage_percentage: 80, execution_summary: { pass: 4 } } }, 'testing'],
    ['failed current execution', { traceability: { mode: 'rule', scope_label: '5', denominator: 5, covered_count: 5, coverage_percentage: 100, execution_summary: { pass: 4, fail: 1 } } }, 'testing'],
    ['unrun current execution', { traceability: { mode: 'rule', scope_label: '5', denominator: 5, covered_count: 5, coverage_percentage: 100, execution_summary: { not_run: 5 } } }, 'testing'],
    ['unchecked consistency', { consistency: null }, 'consistency'],
    ['missing material', { package: null }, 'packages'],
  ] as [string, Partial<ProjectOverview>, string][])('routes %s to its actual workspace', (_, overrides, tab) => {
    expect(nextOverviewAction({ ...clean(), ...overrides }).tab).toBe(tab)
  })
  it('does not call a draft material package approved when blockers are zero', () => {
    const data = clean()
    data.package = { ...data.package!, status: 'draft', blocker_count: 0 }
    expect(nextOverviewAction(data).title).toBe('查看材料审核与提交状态')
    expect(data.package.status).toBe('draft')
    data.package = { ...data.package, blocker_count: 3 }
    expect(nextOverviewAction(data).title).toContain('3 项材料阻断')
    data.package = { ...data.package, blocker_count: 0, status: 'human_approved' }
    expect(nextOverviewAction(data).title).toBe('查看已冻结评审材料')
  })
  it('keeps invalid reports and historical confirmations actionable', () => {
    const data = clean()
    data.design_review = { ...data.design_review!, needs_reconfirmation: true }
    expect(nextOverviewAction(data).tab).toBe('design')
    data.design_review.needs_reconfirmation = false
    data.consistency = { ...data.consistency!, open_conflicts: 1, blocking_open: 1 }
    expect(nextOverviewAction(data).tone).toBe('red')
    data.consistency.check.validity = 'stale'
    expect(nextOverviewAction(data).title).toContain('运行当前版本')
  })
})

describe('single-screen project dashboard', () => {
  it('locates an empty project at protocol import with a real entry action', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(makeOverview({
      requirements: { total: 0, confirmed: 0, draft: 0, pending_review: 0, rejected: 0, stale: 0 },
      spectrum: { variant_points: 0, stale_variant_points: 0, reusable_parts: 0 },
      design_review: null, dfmea: null, traceability: null, package: null,
      samples: { delivery_count: 0, comparison_count: 0, latest_status: null, latest_result: null },
      issues: { open: 0, closed: 0, open_by_severity: { blocking: 0, high: 0, medium: 0, low: 0 } },
    }))))
    const navigate = vi.fn(), user = userEvent.setup()
    render(<OverviewPanel project={project} onNavigate={navigate} />)
    await screen.findByRole('navigation', { name: '研发流程' })
    expect(screen.queryByRole('region', { name: '当前项目进度' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /协议导入/ })).toHaveAttribute('aria-current', 'step')
    await user.click(screen.getByRole('button', { name: /协议导入/ }))
    expect(navigate).toHaveBeenCalledWith('parsing')
  })
  it('highlights recorded variant work and leaves unresolved source issues visible', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(makeOverview({
      design_review: null, dfmea: null, traceability: null, package: null,
      samples: { delivery_count: 0, comparison_count: 0, latest_status: null, latest_result: null },
    }))))
    const navigate = vi.fn(), user = userEvent.setup()
    render(<OverviewPanel project={project} onNavigate={navigate} />)
    await screen.findByRole('navigation', { name: '研发流程' })
    expect(screen.queryByRole('region', { name: '当前项目进度' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('需求总量')).toHaveTextContent('1 项待澄清')
    expect(screen.getByRole('button', { name: /变型设计/ })).toHaveAttribute('aria-current', 'step')
    await user.click(screen.getByRole('button', { name: /变型设计/ }))
    expect(navigate).toHaveBeenCalledWith('bases')
  })
  it('shows draft delivery and blockers without presenting recorded milestones as approved completion', async () => {
    const baseline = makeOverview()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(makeOverview({
      package: { ...baseline.package!, status: 'draft', blocker_count: 26, requires_regeneration: true },
    }))))
    render(<OverviewPanel project={project} onNavigate={vi.fn()} />)
    const flow = await screen.findByRole('navigation', { name: '研发流程' })
    const delivery = within(flow).getByRole('button', { name: /评审交付/ })
    expect(delivery).toHaveAttribute('aria-current', 'step')
    expect(delivery).toHaveTextContent('待更新')
    expect(screen.getByRole('group',{name:'材料包快照检查摘要'})).toHaveTextContent('26 项阻断')
    expect(within(flow).queryByText(/已完成|已通过/)).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '当前项目进度' })).not.toBeInTheDocument()
  })
  it('shows all three agents, both engines, resources and activity immediately', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(makeOverview())))
    render(<OverviewPanel project={project} onNavigate={() => undefined} />)
    await screen.findByRole('heading', { name: project.name })
    for (const name of ['需求解析智能体', '变型设计智能体', '试验验证智能体', '一致性检测', '协同风险预警', '工程知识底座', '最近任务与动态', '评审材料']) {
      expect(screen.getByRole('heading', { name })).toBeVisible()
    }
    expect(screen.queryByRole('tablist', { name: '项目成果讲解' })).not.toBeInTheDocument()
    expect(screen.getByRole('region', { name: '当前验证追溯' })).toBeVisible()
    expect(screen.getByRole('img', { name: '法士特 12JS 系列变速器产品参考图' })).toBeVisible()
  })
  it('opens actual modules without generating or confirming business artifacts', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse(makeOverview()))
    vi.stubGlobal('fetch', fetchMock)
    const onNavigate = vi.fn()
    render(<OverviewPanel project={project} onNavigate={onNavigate} />)
    await screen.findByRole('heading', { name: project.name })
    const user = userEvent.setup()
    for (const [name, target] of [['查看需求清单', 'requirements'], ['协议与澄清问题', 'parsing'], ['查看检测', 'consistency'], ['查看风险', 'coordination'], ['查看设计成果', 'design'], ['型谱与变型依据', 'bases'], ['查看试验与追溯', 'testing'], ['样件检验记录', 'samples'], ['查看评审材料', 'packages']] as const) {
      await user.click(screen.getByRole('button', { name }))
      expect(onNavigate).toHaveBeenLastCalledWith(target)
    }
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
  it('keeps unknown checks and unrun evidence distinct from passing and coverage', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(makeOverview({
      consistency: null, package: null, design_review: null, dfmea: null,
      traceability: { mode: 'rule', scope_label: '固定 5 条', denominator: 5, covered_count: 5, coverage_percentage: 100, execution_summary: { not_run: 5, pass: 0 } },
    }))))
    render(<OverviewPanel project={project} onNavigate={() => undefined} />)
    await screen.findByRole('heading', { name: project.name })
    expect(screen.getByLabelText('一致性检查摘要')).toHaveTextContent('尚未检查')
    expect(screen.getByLabelText('一致性检查摘要')).not.toHaveTextContent('0 项阻断冲突')
    expect(screen.getByRole('heading', { name: '评审材料' }).closest('section')).toHaveTextContent('尚未生成材料包')
    const packageChecks = screen.getByRole('group',{name:'材料包快照检查摘要'})
    expect(within(packageChecks).getAllByText('—')).toHaveLength(2)
    expect(packageChecks).not.toHaveTextContent('0 项阻断')
    expect(screen.getByLabelText('当前执行通过')).toHaveTextContent('0/5')
    expect(screen.getByLabelText('有效用例覆盖率')).toHaveTextContent('100%')
  })
  it('reports stale design independently from its historical confirmation', async () => {
    const original = makeOverview()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(makeOverview({ design_review: { ...original.design_review!, needs_reconfirmation: true } }))))
    render(<OverviewPanel project={project} onNavigate={() => undefined} />)
    const design = await screen.findByRole('article', { name: '变型设计智能体成果' })
    expect(design).toHaveTextContent('待复核')
    expect(design).toHaveTextContent('已确认')
  })
  it('shows request errors and retries the overview', async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError('Failed to fetch')).mockResolvedValueOnce(jsonResponse(makeOverview()))
    vi.stubGlobal('fetch', fetchMock)
    render(<OverviewPanel project={project} onNavigate={() => undefined} />)
    expect(await screen.findByText('Failed to fetch')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '重新加载' }))
    expect(await screen.findByRole('heading', { name: project.name })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
  it('keeps real failure, version and risk evidence visible together', async () => {
    const cockpit: NonNullable<ProjectOverview['cockpit']> = {
      parameters: [{ requirement_id: 'engine-id', key: 'engineMaxTorque', display_code: 'REQ-P01-B-003', label: '发动机最大扭矩', operator: '=', value_text: '2800', unit: 'N·m', revision: 2, review_status: 'confirmed', validity: 'current' }],
      traceability_items: [{ key: 'gearboxRatedInputTorque', label: '变速器最低额定输入扭矩', requirement_id: 'torque-id', display_code: 'REQ-P01-C-002', requirement_revision: 2, covered: false, coverage_valid: false, valid_case_ids: [], pending_case_ids: ['case-007'], execution: 'fail', reason: '后备系数不足', latest_runs: [] }],
      resources: { source_documents: 2, product_bases: 4, history_projects: 3 },
      risk_topics: [{ id: 'topic-1', name: '样件协同', mode: 'rule', created_at: project.created_at, risk_level: 'high', reasons: ['平均响应时延 > 48 小时'], average_response_hours: 52, iteration_count: 4, absence_rate: 1 / 3, response_latencies_hours: [48, 52, 56], window_start: project.created_at, window_end: project.updated_at }],
      recent_activity: [{ id: 'audit-1', project_id: project.id, object_type: 'requirement', object_id: 'engine-id', object_revision: 2, action: 'requirement.updated', actor: '演示工程师', created_at: project.updated_at }],
    }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(makeOverview({ cockpit })))
    vi.stubGlobal('fetch', fetchMock)
    render(<OverviewPanel project={project} onNavigate={() => undefined} />)
    const trace = await screen.findByRole('region', { name: '当前验证追溯' })
    expect(trace).toHaveTextContent('未通过')
    expect(trace).toHaveTextContent('未覆盖')
    expect(trace).toHaveTextContent('V2')
    expect(screen.getByRole('img', { name: '响应耗时：48、52、56 小时' })).toBeVisible()
    expect(screen.getByText('修订需求版本')).toBeVisible()
    expect(within(screen.getByRole('group',{name:'协同指标摘要'})).getByText('33.3%')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: '刷新项目数据' }))
    expect(await screen.findByRole('heading', { name: project.name })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
