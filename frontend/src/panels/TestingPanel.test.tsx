import { api } from '../api'
import { emptyWorkflow,emptyProgress } from '../test/workflowFixture'
import { render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import type {
  TestCase,
  TestPlanPayload,
  TestRun,
  TraceabilityMatrix,
  Requirement,
} from '../types'
import { TestingPanel } from './TestingPanel'

const baseCase: TestCase = {
  id: 'tc1',
  plan_id: 'plan1',
  display_code: 'TC-007',
  case_key: 'staticTorsion',
  case_kind: 'static_torsion',
  title: '静扭强度与后备系数',
  purpose: '验证当前加载基准',
  revision: 1,
  review_status: 'confirmed',
  validity: 'current',
  conditions_text: '合成台架工况',
  load_conditions_text: '逐级加载',
  acceptance_criteria: '后备系数≥2.5',
  load_basis_requirement_id: 'r-b003',
  minimum_coefficient: 2.5,
  requirement_refs: [],
  fmea_refs: [],
  complete: true,
  coverage_valid: true,
  runs: [],
}
const baselineRequirement:Requirement={id:'r-b003',project_id:'p1',display_code:'REQ-B003',category:'B',parameter_name:'发动机最大扭矩',data_type:'number',operator:'=',value_text:'2600',value_num:2600,value_num_high:null,unit:'N·m',raw_expression:'2600 N·m',source_document_id:null,source_location:'合成测试',source_excerpt:'合成测试',review_status:'confirmed',validity:'current',current_revision:1,created_at:'2026-10-26T00:00:00+08:00',updated_at:'2026-10-26T00:00:00+08:00'}
it('focuses the execution form and prefills the referenced baseline for each current case version without submitting',async()=>{
 const currentCase={...baseCase,requirement_refs:[{requirement_id:'r-b003',revision:1,current_revision:1}]}
 vi.spyOn(api,'getTestPlan').mockResolvedValue(planFor(currentCase))
 vi.spyOn(api,'getTraceabilityMatrix').mockResolvedValue(matrix)
 vi.spyOn(api,'listRequirements').mockResolvedValue([baselineRequirement])
 const save=vi.spyOn(api,'recordTestRun')
 Element.prototype.scrollIntoView=vi.fn()
 const user=userEvent.setup();const {rerender}=render(<TestingPanel projectId="p1"/>)
 await user.click(await screen.findByRole('button',{name:'记录执行'}))
 await waitFor(()=>expect(screen.getByLabelText('加载基准 N·m')).toHaveValue(2600))
 expect(screen.getByLabelText('后备系数')).toHaveValue(2.6)
 expect(screen.getByLabelText('执行工况')).toHaveFocus()
 expect(screen.getByRole('button',{name:'记录执行'})).toHaveAttribute('aria-expanded','true')
 expect(screen.getByRole('dialog',{name:'记录执行：TC-007'})).toBeVisible()
 await user.clear(screen.getByLabelText('后备系数'));await user.type(screen.getByLabelText('后备系数'),'2.4')
 await user.click(screen.getByRole('button',{name:'关闭执行记录'}))
 expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
 await user.click(screen.getByRole('button',{name:'记录执行'}))
 expect(screen.getByLabelText('后备系数')).toHaveValue(2.4)
 vi.mocked(api.listRequirements).mockResolvedValue([{...baselineRequirement,project_id:'p2',current_revision:2,value_num:2800,value_text:'2800'}])
 vi.mocked(api.getTestPlan).mockResolvedValue(planFor({...currentCase,revision:2,requirement_refs:[{requirement_id:'r-b003',revision:2,current_revision:2}]}))
 rerender(<TestingPanel projectId="p2"/>);
 await user.click(await screen.findByRole('button',{name:'记录执行'}))
 await waitFor(()=>expect(screen.getByLabelText('加载基准 N·m')).toHaveValue(2800))
 expect(save).not.toHaveBeenCalled()
})

it('keeps failed execution input in the modal and closes after a saved run even when readback fails',async()=>{
 const currentCase={...baseCase,requirement_refs:[{requirement_id:'r-b003',revision:1,current_revision:1}]}
 const run:TestRun={id:'run-saved',case_id:'tc1',case_revision:1,run_no:1,status:'completed',result:'pass',mode:'rule',conditions_text:'合成台架工况',evidence:'合成记录',load_basis_numeric:2600,backup_coefficient:2.6,manual_result:null,reasons:['合成通过'],reason:'合成通过',measured_values:{},actor:'演示工程师',role:'engineer',created_at:'2026-10-27T00:00:00+08:00'}
 vi.spyOn(api,'getTestPlan').mockResolvedValueOnce(planFor(currentCase)).mockRejectedValueOnce(new Error('方案重读失败')).mockResolvedValue(planFor({...currentCase,runs:[run]}))
 vi.spyOn(api,'getTraceabilityMatrix').mockResolvedValue(matrix)
 vi.spyOn(api,'listRequirements').mockResolvedValue([baselineRequirement])
 const save=vi.spyOn(api,'recordTestRun').mockRejectedValueOnce(new Error('执行未保存')).mockResolvedValue({case:currentCase,run})
 const user=userEvent.setup();render(<TestingPanel projectId="p1"/>);
 const trigger=await screen.findByRole('button',{name:'记录执行'})
 await user.click(trigger)
 await waitFor(()=>expect(screen.getByLabelText('加载基准 N·m')).toHaveValue(2600))
 await user.click(screen.getByRole('button',{name:'提交执行记录'}))
 expect(await screen.findByRole('alert')).toHaveTextContent('执行未保存')
 expect(screen.getByRole('dialog',{name:'记录执行：TC-007'})).toBeVisible()
 expect(screen.getByLabelText('后备系数')).toHaveValue(2.6)
 await user.click(screen.getByRole('button',{name:'提交执行记录'}))
 await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
 expect(await screen.findByRole('alert')).toHaveTextContent('执行记录已保存，但页面刷新失败')
 await user.click(screen.getByRole('button',{name:'重新读取已保存结果'}))
 await waitFor(()=>expect(trigger).toBeEnabled())
 expect(save).toHaveBeenCalledTimes(2)
 expect(screen.getByText('已执行 · 通过')).toBeVisible()
})

const matrix: TraceabilityMatrix = {
  mode: 'rule',
  scope_label: '固定验证范围',
  denominator: 5,
  covered_count: 5,
  coverage_percentage: 100,
  items: [
    {
      key: 'gearboxRatedInputTorque',
      label: '变速器最低额定输入扭矩',
      requirement_id: 'r-c002',
      display_code: 'REQ-P01-C-002',
      requirement_revision: 1,
      covered: true,
      coverage_valid: true,
      valid_case_ids: ['tc1'],
      pending_case_ids: [],
      execution: 'pass',
      reason: '有效用例已覆盖，最新执行通过',
      latest_runs: [],
    },
  ],
  uncovered: [],
  pending_review: [],
  execution_summary: { pass: 5, not_run: 0 },
}

function planFor(item: TestCase): TestPlanPayload {
  return {
    mode: 'rule',
    source_label: '固定验证范围',
    plan: {
      id: 'plan1',
      display_code: 'TP-P01',
      revision: 1,
      status: 'confirmed',
      purpose: 'P0 验证',
      conditions_text: '台架',
      sample_description: '样件',
      load_conditions_text: '加载',
      acceptance_criteria: '判定',
      source_label: '固定验证范围',
      created_at: '2026-10-19T00:00:00+00:00',
      updated_at: '2026-10-19T00:00:00+00:00',
    },
    cases: [item],
    confirmations: [],
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response
}

beforeEach(()=>{vi.spyOn(api,'getWorkflowSummary').mockResolvedValue(emptyWorkflow);vi.spyOn(api,'getCoordinationProgress').mockImplementation(async(topicId)=>emptyProgress(topicId))})
afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

it('prefills editable synthetic evidence for the selected case version without saving a run',async()=>{
 vi.spyOn(api,'getTestPlan').mockResolvedValue(planFor(baseCase))
 vi.spyOn(api,'getTraceabilityMatrix').mockResolvedValue(matrix)
 const save=vi.spyOn(api,'recordTestRun')
 render(<TestingPanel projectId="p1"/>)
 expect(screen.queryByLabelText('执行证据')).not.toBeInTheDocument()
 const user=userEvent.setup();await user.click(await screen.findByRole('button',{name:'记录执行'}))
 expect(await screen.findByLabelText('执行证据')).toHaveValue('合成执行记录 TC-007 · V1（演示样例，待操作者核对）')
 expect(save).not.toHaveBeenCalled()
})

describe('TestingPanel', () => {
  it('rejects an incomplete draft case with a reason and reviews the plan separately', async () => {
    let current = planFor({ ...baseCase, review_status: 'draft', complete: false, coverage_valid: false })
    current.plan.status = 'draft'
    vi.spyOn(api, 'getTestPlan').mockImplementation(async () => structuredClone(current))
    vi.spyOn(api, 'getTraceabilityMatrix').mockResolvedValue(matrix)
    const rejectCase = vi.spyOn(api, 'confirmTestCase').mockImplementation(async () => {current.cases[0].review_status='rejected';return {case:current.cases[0]}})
    const rejectPlan = vi.spyOn(api, 'confirmTestPlan').mockImplementation(async () => {current.plan.status='rejected';return {id:'plan-review',actor:'试验工程师',role:'engineer',decision:'rejected',comment:'方案需补充条件',created_at:'2026-10-25T00:00:00+00:00'}})
    const user = userEvent.setup()
    render(<TestingPanel projectId="p1" />)
    await user.click(await screen.findByRole('button', {name:'驳回用例 TC-007'}))
    expect(screen.getByRole('button', {name:'提交驳回'})).toBeEnabled()
    await user.type(screen.getByLabelText('驳回原因'), '判定标准不完整')
    await user.click(screen.getByRole('button', {name:'提交驳回'}))
    expect(rejectCase).toHaveBeenCalledWith('tc1',expect.objectContaining({decision:'rejected',expected_revision:1,comment:'判定标准不完整'}))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', {name:'确认用例'})).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', {name:'驳回试验方案'}))
    await user.type(screen.getByLabelText('驳回原因'), '方案需补充条件')
    await user.click(screen.getByRole('button', {name:'提交驳回'}))
    expect(rejectPlan).toHaveBeenCalledWith('plan1',expect.objectContaining({decision:'rejected',comment:'方案需补充条件'}))
    expect(screen.queryByRole('button', {name:'确认试验方案'})).not.toBeInTheDocument()
  })
  it('does not repeat a saved case confirmation after a read failure', async () => {
    let reads = 0, writes = 0
    const draft = { ...baseCase, review_status: 'draft' as const }
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') { writes++; return jsonResponse({ id: 'confirmed-case' }) }
      if (String(input).endsWith('/test-plan')) {
        if (++reads === 2) throw new Error('方案暂不可读')
        return jsonResponse(planFor(reads > 2 ? baseCase : draft))
      }
      return jsonResponse(matrix)
    }))
    const user = userEvent.setup()
    render(<TestingPanel projectId="p1" />)
    await user.click(await screen.findByRole('button', { name: '确认用例' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('TC-007 审核已保存，但页面刷新失败')
    expect(screen.getByRole('button', { name: '确认用例' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: '重新读取已保存结果' }))
    expect(await screen.findByRole('button', { name: '记录执行' })).toBeEnabled()
    expect(screen.queryByRole('button', { name: '确认用例' })).not.toBeInTheDocument()
    expect(writes).toBe(1)
  })
  it('shows Chinese execution counts separately from coverage without raw response keys', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => jsonResponse(url.endsWith('test-plan') ? planFor(baseCase) : matrix)))
    render(<TestingPanel projectId="p1" />)
    const summary = await screen.findByRole('region', { name: '执行结果汇总' })
    expect(within(summary).getByText('通过').parentElement).toHaveTextContent('5')
    expect(within(summary).getByText('未执行').parentElement).toHaveTextContent('0')
    expect(summary).not.toHaveTextContent('not_run')
    expect(summary).not.toHaveTextContent('pass')
    expect(screen.getByText(/覆盖率 100%/)).toBeInTheDocument()
  })
  it('records a static torsion run with load basis and coefficient', async () => {
    let current = baseCase
    let runBody: unknown
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url === '/api/projects/p1/test-plan' && !init?.method) {
          return jsonResponse(planFor(current))
        }
        if (
          url === '/api/projects/p1/traceability-matrix' &&
          !init?.method
        ) {
          return jsonResponse(matrix)
        }
        if (url === '/api/test-cases/tc1/runs' && init?.method === 'POST') {
          runBody = JSON.parse(String(init.body))
          const run: TestRun = {
            id: 'run1',
            case_id: 'tc1',
            case_revision: 1,
            run_no: 1,
            status: 'completed',
            result: 'pass',
            mode: 'rule',
            conditions_text: '合成台架工况',
            evidence: 'RUN-001',
            load_basis_numeric: 2800,
            backup_coefficient: 2.5,
            manual_result: null,
            reasons: ['加载基准与当前需求一致', '后备系数 2.5 ≥ 2.5'],
            reason: '加载基准与当前需求一致；后备系数 2.5 ≥ 2.5',
            measured_values: {},
            actor: '演示工程师',
            role: 'design_engineer',
            created_at: '2026-10-19T01:00:00+00:00',
          }
          current = { ...current, runs: [run] }
          return jsonResponse({ case: current, run })
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<TestingPanel projectId="p1" />)

    await screen.findByText('TC-007')
    await user.click(
      screen.getByRole('button', { name: '记录执行' }),
    )
    await user.clear(screen.getByRole('textbox', { name: '执行证据' }))
    await user.type(
      screen.getByRole('textbox', { name: '执行证据' }),
      'RUN-001',
    )
    await user.type(
      screen.getByRole('spinbutton', { name: '加载基准 N·m' }),
      '2800',
    )
    await user.clear(screen.getByRole('spinbutton', { name: '后备系数' }))
    await user.type(
      screen.getByRole('spinbutton', { name: '后备系数' }),
      '2.5',
    )
    await user.click(
      screen.getByRole('button', { name: '提交执行记录' }),
    )

    expect(await screen.findByText(/第 1 次执行：通过/)).toBeInTheDocument()
    expect(runBody).toMatchObject({
      expected_revision: 1,
      load_basis_numeric: 2800,
      backup_coefficient: 2.5,
      conditions: '合成台架工况',
    })
    expect(runBody).not.toHaveProperty('manual_result')
  })

  it('generates and confirms a plan, confirms a manual case, and records its conclusion', async () => {
    const manualCase: TestCase = {
      ...baseCase,
      id: 'tc-manual',
      display_code: 'TC-001',
      case_key: 'benchEndurance',
      case_kind: 'manual',
      title: '台架耐久补充验证',
      revision: 1,
      review_status: 'draft',
      load_basis_requirement_id: null,
      minimum_coefficient: null,
    }
    let plan: TestPlanPayload | null = null
    let planConfirmBody: unknown
    let caseConfirmBody: unknown
    let runBody: unknown

    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url === '/api/projects/p1/test-plan' && !init?.method) {
          return plan
            ? jsonResponse(plan)
            : jsonResponse({ error: { message: '尚未生成' } }, 404)
        }
        if (url === '/api/projects/p1/test-plan' && init?.method === 'POST') {
          plan = {
            ...planFor(manualCase),
            plan: { ...planFor(manualCase).plan, status: 'draft' },
          }
          return jsonResponse(plan)
        }
        if (
          url === '/api/projects/p1/traceability-matrix' &&
          !init?.method
        ) {
          return jsonResponse(matrix)
        }
        if (
          url === '/api/test-plans/plan1/confirmations' &&
          init?.method === 'POST'
        ) {
          planConfirmBody = JSON.parse(String(init.body))
          if (plan) {
            plan = {
              ...plan,
              plan: { ...plan.plan, status: 'confirmed' },
            }
          }
          return jsonResponse({ id: 'c-plan' }, 201)
        }
        if (
          url === '/api/test-cases/tc-manual/confirmations' &&
          init?.method === 'POST'
        ) {
          caseConfirmBody = JSON.parse(String(init.body))
          if (plan) {
            plan = {
              ...plan,
              cases: [{ ...plan.cases[0], review_status: 'confirmed' }],
            }
          }
          return jsonResponse({ case: plan?.cases[0] }, 201)
        }
        if (
          url === '/api/test-cases/tc-manual/runs' &&
          init?.method === 'POST'
        ) {
          runBody = JSON.parse(String(init.body))
          const run: TestRun = {
            id: 'run-manual',
            case_id: 'tc-manual',
            case_revision: 1,
            run_no: 1,
            status: 'completed',
            result: 'fail',
            mode: 'manual',
            conditions_text: '合成台架工况',
            evidence: 'MANUAL-RUN-01',
            load_basis_numeric: null,
            backup_coefficient: null,
            manual_result: 'fail',
            reasons: ['人工判定未通过'],
            reason: '人工判定未通过',
            measured_values: {},
            actor: '演示工程师',
            role: 'design_engineer',
            created_at: '2026-10-19T01:00:00+00:00',
          }
          if (plan) {
            plan = {
              ...plan,
              cases: [{ ...plan.cases[0], runs: [run] }],
            }
          }
          return jsonResponse({ case: plan?.cases[0], run })
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<TestingPanel projectId="p1" />)

    expect(
      await screen.findByText('尚未生成试验方案。'),
    ).toBeInTheDocument()
    await user.click(
      screen.getByRole('button', { name: '生成试验方案' }),
    )
    expect(
      await screen.findByText(/试验方案 TP-P01 已生成/),
    ).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: '确认试验方案' }),
    )
    expect(
      await screen.findByText('试验方案已确认'),
    ).toBeInTheDocument()
    expect(planConfirmBody).toMatchObject({
      expected_revision: 1,
      decision: 'confirmed',
    })

    await user.click(screen.getByRole('button', { name: '确认用例' }))
    expect(await screen.findByText('TC-001 已确认')).toBeInTheDocument()
    expect(caseConfirmBody).toMatchObject({
      expected_revision: 1,
      decision: 'confirmed',
    })
    await user.click(screen.getByRole('button',{name:'记录执行'}))
    await user.selectOptions(
      screen.getByRole('combobox', { name: '人工结论' }),
      'fail',
    )
    await user.clear(screen.getByRole('textbox', { name: '执行证据' }))
    await user.type(
      screen.getByRole('textbox', { name: '执行证据' }),
      'MANUAL-RUN-01',
    )
    await user.click(
      screen.getByRole('button', { name: '提交执行记录' }),
    )

    expect(
      await screen.findByText(/第 1 次执行：未通过（人工判定未通过）/),
    ).toBeInTheDocument()
    expect(runBody).toMatchObject({
      expected_revision: 1,
      manual_result: 'fail',
      evidence: 'MANUAL-RUN-01',
    })
    expect(runBody).not.toHaveProperty('load_basis_numeric')
  })

  it('rebases a stale case onto current requirements', async () => {
    let current: TestCase = {
      ...baseCase,
      validity: 'stale',
      review_status: 'confirmed',
    }
    let patchBody: unknown
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url === '/api/projects/p1/test-plan' && !init?.method) {
          return jsonResponse(planFor(current))
        }
        if (
          url === '/api/projects/p1/traceability-matrix' &&
          !init?.method
        ) {
          return jsonResponse(matrix)
        }
        if (url === '/api/test-cases/tc1' && init?.method === 'PATCH') {
          patchBody = JSON.parse(String(init.body))
          current = {
            ...current,
            revision: 2,
            validity: 'current',
            review_status: 'draft',
          }
          return jsonResponse(current)
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<TestingPanel projectId="p1" />)

    await screen.findByText('TC-007')
    await user.click(
      screen.getByRole('button', { name: '重基需求' }),
    )

    expect(
      await screen.findByText(/已重基到 V2，需重新确认/),
    ).toBeInTheDocument()
    expect(patchBody).toMatchObject({
      expected_revision: 1,
      rebase_requirements: true,
    })
  })
})

it('rejects a draft case without requiring a reason',async()=>{
 vi.spyOn(api,'getTestPlan').mockResolvedValue(planFor({...baseCase,review_status:'draft'}))
 vi.spyOn(api,'getTraceabilityMatrix').mockResolvedValue(matrix)
 const save=vi.spyOn(api,'confirmTestCase').mockResolvedValue({case:baseCase})
 const user=userEvent.setup();render(<TestingPanel projectId="p1"/>)
 await user.click(await screen.findByRole('button',{name:`驳回用例 ${baseCase.display_code}`}))
 const submit=screen.getByRole('button',{name:'提交驳回'})
 expect(submit).toBeEnabled();await user.click(submit)
 expect(save).toHaveBeenCalledWith(baseCase.id,expect.objectContaining({decision:'rejected',comment:''}))
})
