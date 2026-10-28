import { api } from '../api'
import { emptyWorkflow,emptyProgress } from '../test/workflowFixture'
import { fireEvent, render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import type {
  CoordinationOverview,
  RiskAcceptance,
} from '../types'
import { CoordinationPanel } from './CoordinationPanel'

function makeOverview(acceptances: RiskAcceptance[] = []): CoordinationOverview {
  return {
    project_id: 'p1',
    rule_label: '协同响应规则',
    source_label: '协同记录',
    topic_count: 1,
    record_count: 1,
    metrics_available: 1,
    highest_risk: 'high',
    topics: [
      {
        id: 't1',
        project_id: 'p1',
        display_code: 'CT-P01-001',
        name: '接口扭矩复核',
        expected_participants: ['设计', '试验'],
        window_start: '2026-10-18T00:00:00+00:00',
        window_end: '2026-10-19T00:00:00+00:00',
        mode: 'rule',
        created_at: '2026-10-18T00:00:00+00:00',
        records: [],
        record_count: 1,
        latest_metrics: {
          validity: 'current',
          inputs_sha256: 'a'.repeat(64),
          id: 'mr1',
          topic_id: 't1',
          run_no: 1,
          rule_label: '协同响应规则',
          mode: 'rule',
          source_label: '协同记录',
          inputs: { window_hours: 24 },
          metrics: {
            average_response_hours: 12,
            response_sample_size: 2,
            pending_count: 1,
            iteration_count: 1,
            absence_rate: 0.5,
            orphan_response_count: 0,
          },
          risk: {
            risk_level: 'high',
            score: 82,
            reasons: ['缺席率偏高'],
          },
          cost: {
            amount: 360,
            currency: 'CNY',
            basis: '3 小时 × 120 元',
          },
          created_at: '2026-10-19T00:00:00+00:00',
        },
        risk_acceptances: acceptances,
      },
    ],
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

describe('CoordinationPanel', () => {
  it('keeps communication actions ahead of the progress table and long alert list',async()=>{
    vi.spyOn(api,'getCoordinationOverview').mockResolvedValue(makeOverview())
    render(<CoordinationPanel projectId="p1"/>);
    const topic=await screen.findByRole('article',{name:'协同议题 CT-P01-001'})
    const group=within(topic).getByRole('group',{name:'议题沟通操作'})
    const progress=within(topic).getByRole('region',{name:'参与方计划与实际进度'})
    expect(within(group).getByRole('button',{name:'导入沟通记录'})).toBeVisible()
    expect(group.compareDocumentPosition(progress)&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
  it('prefills a synthetic initial message then a reply referencing the saved external id, preserving an edited draft on reopen',async()=>{
    const overview=makeOverview();const topic=overview.topics[0]
    Object.assign(topic,{name:'合成设计冻结交付协同',expected_participants:['A 主机方','B 研发方'],window_start:'2026-10-19T16:00:00Z',window_end:'2026-10-23T16:00:00Z',record_count:0})
    vi.spyOn(api,'getCoordinationOverview').mockImplementation(async()=>structuredClone(overview))
    const save=vi.spyOn(api,'createCoordinationRecord').mockImplementation(async(_id,body)=>{
      const saved={id:'root',topic_id:topic.id,external_id:String(body.external_id),record_type:'message' as const,sender:String(body.sender),sent_at:String(body.sent_at),content_summary:String(body.content_summary),reply_to_external_id:null,created_at:String(body.sent_at)}
      topic.records.push(saved)
      topic.record_count=1;return saved
    })
    const user=userEvent.setup();render(<CoordinationPanel projectId="p1"/>);
    await user.click(await screen.findByRole('button',{name:'导入沟通记录'}))
    expect(screen.getByLabelText('协同记录外部编号')).toHaveValue('DEMO-MSG-01')
    expect(screen.getByLabelText('协同记录响应对象')).toHaveValue('')
    expect(screen.getByText('发起消息无需填写响应编号；回复时关联已保存的原消息。')).toBeVisible()
    await user.clear(screen.getByLabelText('协同记录外部编号'));await user.type(screen.getByLabelText('协同记录外部编号'),'CUSTOM-ROOT')
    await user.click(screen.getByRole('button',{name:'关闭沟通详情'}));await user.click(screen.getByRole('button',{name:'导入沟通记录'}))
    expect(screen.getByLabelText('协同记录外部编号')).toHaveValue('CUSTOM-ROOT')
    expect(save).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button',{name:'导入记录'}))
    await waitFor(()=>expect(screen.getByLabelText('协同记录响应对象')).toHaveValue('CUSTOM-ROOT'))
    expect(screen.getByLabelText('协同记录外部编号')).toHaveValue('DEMO-MSG-02')
  })
  it('does not recalculate metrics when only the saved result needs to be read again', async () => {
    let reads = 0, writes = 0
    vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') { writes++; return jsonResponse({ id: 'new-metrics' }) }
      if (++reads === 2) throw new Error('看板暂不可读')
      return jsonResponse(makeOverview())
    }))
    const user = userEvent.setup()
    render(<CoordinationPanel projectId="p1" />)
    await user.click(await screen.findByRole('button', { name: '重算指标' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('协同指标计算已保存，但页面刷新失败')
    expect(screen.getByRole('button', { name: '重算指标' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: '重新读取已保存结果' }))
    expect(await screen.findByRole('button', { name: '重算指标' })).toBeEnabled()
    expect(writes).toBe(1)
  })
  it('labels an old metric as pending recalculation and blocks acceptance', async () => {
    const overview = makeOverview()
    Object.assign(overview.topics[0].latest_metrics!, { validity: 'stale', inputs_sha256: 'a'.repeat(64) })
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(overview)))
    render(<CoordinationPanel projectId="p1" />)
    expect(await screen.findByText(/沟通记录已变化，指标待重算/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '接受风险' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重算指标' })).toBeEnabled()
  })
  it('opens records and import in a drawer, preserves the same draft and isolates another topic and project', async () => {
    const overview = makeOverview()
    overview.topics.push({ ...overview.topics[0], id: 't2', display_code: 'CT-P01-002', name: '样件交付复核' })
    const fetcher = vi.fn(async (_url: RequestInfo | URL, _init?: RequestInit) => jsonResponse(overview))
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()
    const { rerender } = render(<CoordinationPanel projectId="p1" />)
    expect(screen.queryByLabelText('协同记录外部编号')).not.toBeInTheDocument()
    const topic = await screen.findByRole('article', { name: '协同议题 CT-P01-001' })
    const trigger = within(topic).getByRole('button', { name: '查看沟通记录' })
    await user.click(trigger)
    const drawer = screen.getByRole('dialog', { name: '议题沟通记录 · CT-P01-001' })
    expect(within(drawer).getByText(/设计、试验/)).toBeInTheDocument()
    await user.type(within(drawer).getByLabelText('协同记录外部编号'), 'MSG-DRAFT')
    await user.type(within(drawer).getByLabelText('协同记录发送方'), '设计部')
    await user.click(within(drawer).getByRole('button', { name: '关闭沟通详情' }))
    expect(trigger).toHaveFocus()
    await user.click(trigger)
    expect(screen.getByLabelText('协同记录外部编号')).toHaveValue('MSG-DRAFT')
    await user.click(screen.getByRole('button', { name: '关闭沟通详情' }))
    await user.click(within(screen.getByRole('article', { name: '协同议题 CT-P01-002' })).getByRole('button', { name: '导入沟通记录' }))
    expect(screen.getByLabelText('协同记录外部编号')).toHaveValue('')
    expect(screen.getByLabelText('协同记录发送方')).toHaveValue('')
    expect(fetcher.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
    rerender(<CoordinationPanel projectId="p2" />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
  it('keeps failed record imports in the drawer and refreshes the saved record on retry', async () => {
    let attempts = 0
    const overview = makeOverview()
    vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).endsWith('/records') && init?.method === 'POST') {
        if (++attempts === 1) return jsonResponse({ error: { message: '记录未保存，请重试' } }, 503)
        const record = { id: 'new1', topic_id: 't1', ...JSON.parse(String(init.body)), created_at: '2026-10-19T02:00:00Z' }
        overview.topics[0].records.push(record)
        overview.topics[0].record_count++
        return jsonResponse(record, 201)
      }
      return jsonResponse(overview)
    }))
    const user = userEvent.setup()
    render(<CoordinationPanel projectId="p1" />)
    await user.click(await screen.findByRole('button', { name: '导入沟通记录' }))
    const drawer = screen.getByRole('dialog', { name: '议题沟通记录 · CT-P01-001' })
    await user.type(within(drawer).getByLabelText('协同记录外部编号'), 'MSG-RETRY')
    await user.type(within(drawer).getByLabelText('协同记录发送方'), '试验部')
    fireEvent.change(within(drawer).getByLabelText('协同记录发送时间'), { target: { value: '2026-10-18T09:00' } })
    await user.click(within(drawer).getByRole('button', { name: '导入记录' }))
    expect(await within(drawer).findByRole('alert')).toHaveTextContent('记录未保存，请重试')
    expect(within(drawer).getByLabelText('协同记录外部编号')).toHaveValue('MSG-RETRY')
    await user.click(within(drawer).getByRole('button', { name: '导入记录' }))
    expect(await within(drawer).findByText('协同记录已导入')).toBeInTheDocument()
    expect(within(drawer).getByText('MSG-RETRY')).toBeInTheDocument()
    expect(within(drawer).getByLabelText('协同记录外部编号')).toHaveValue('')
    expect(attempts).toBe(2)
  })
  it('formats a recorded ratio as a percentage and identifies the calculation mode in Chinese', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(makeOverview())))
    render(<CoordinationPanel projectId="p1" />)
    expect(await screen.findByText('缺席率：50%')).toBeVisible()
    expect(screen.getByText(/来源 规则计算/)).toBeVisible()
    expect(screen.getByText(/2026-10-18 00:00 UTC/)).toBeVisible()
  })
  it('distinguishes saved records from a failed refresh and retries only reading the overview', async () => {
    let reads = 0, writes = 0
    vi.stubGlobal('fetch', vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') { writes++; return jsonResponse({ id: 'saved-record' }, 201) }
      return ++reads === 2 ? jsonResponse({ error: { message: '读取超时' } }, 503) : jsonResponse(makeOverview())
    }))
    const user = userEvent.setup()
    render(<CoordinationPanel projectId="p1" />)
    await user.click(await screen.findByRole('button', { name: '导入沟通记录' }))
    const drawer = screen.getByRole('dialog')
    await user.type(within(drawer).getByLabelText('协同记录外部编号'), 'MSG-SAVED')
    await user.type(within(drawer).getByLabelText('协同记录发送方'), '设计部')
    fireEvent.change(within(drawer).getByLabelText('协同记录发送时间'), { target: { value: '2026-10-18T09:00' } })
    await user.click(within(drawer).getByRole('button', { name: '导入记录' }))
    expect(await within(drawer).findByRole('alert')).toHaveTextContent('记录已保存，但列表刷新失败')
    expect(within(drawer).getByLabelText('协同记录外部编号')).toHaveValue('')
    await user.click(within(drawer).getByRole('button', { name: '重新读取记录' }))
    expect(within(drawer).queryByRole('alert')).not.toBeInTheDocument()
    expect(reads).toBe(3)
    expect(writes).toBe(1)
  })
  it('creates a topic and recalculates metrics with cost inputs', async () => {
    let overview: CoordinationOverview = {
      ...makeOverview(),
      topic_count: 0,
      record_count: 0,
      metrics_available: 0,
      highest_risk: 'insufficient',
      topics: [],
    }
    let topicBody: unknown
    let metricBody: unknown

    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (
          url === '/api/projects/p1/coordination-overview' &&
          !init?.method
        ) {
          return jsonResponse(overview)
        }
        if (
          url === '/api/projects/p1/coordination-topics' &&
          init?.method === 'POST'
        ) {
          topicBody = JSON.parse(String(init.body))
          overview = makeOverview()
          return jsonResponse(overview.topics[0], 201)
        }
        if (
          url === '/api/coordination-topics/t1/metrics' &&
          init?.method === 'POST'
        ) {
          metricBody = JSON.parse(String(init.body))
          return jsonResponse({ id: 'mr1' }, 201)
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<CoordinationPanel projectId="p1" />)

    await screen.findByText('最高风险')
    await user.clear(screen.getByLabelText('协同议题名称'))
    await user.clear(screen.getByLabelText('协同应参与方'))
    await user.type(
      screen.getByRole('textbox', { name: '协同议题名称' }),
      '接口扭矩复核',
    )
    await user.type(
      screen.getByRole('textbox', { name: '协同应参与方' }),
      '设计, 试验',
    )
    fireEvent.change(screen.getByLabelText('协同窗口开始'), {
      target: { value: '2026-10-18T08:00' },
    })
    fireEvent.change(screen.getByLabelText('协同窗口结束'), {
      target: { value: '2026-10-19T08:00' },
    })
    await user.click(screen.getByRole('button', { name: '创建议题' }))

    expect(
      await screen.findByText('协同议题 CT-P01-001 已创建'),
    ).toBeInTheDocument()
    expect(topicBody).toMatchObject({
      name: '接口扭矩复核',
      expected_participants: ['设计', '试验'],
    })
    expect(String((topicBody as { window_start: string }).window_start)).toMatch(
      /^2026-10-18T\d{2}:00:00\.000Z$/,
    )

    await user.clear(screen.getByRole('spinbutton', { name: '工时 CT-P01-001' }))
    await user.type(
      screen.getByRole('spinbutton', { name: '工时 CT-P01-001' }),
      '3',
    )
    await user.clear(screen.getByRole('spinbutton', { name: '费率 CT-P01-001' }))
    await user.type(
      screen.getByRole('spinbutton', { name: '费率 CT-P01-001' }),
      '120',
    )
    await user.click(screen.getByRole('button', { name: '重算指标' }))

    expect(
      await screen.findByText('CT-P01-001 指标已重算并记录输入快照'),
    ).toBeInTheDocument()
    expect(metricBody).toEqual({
      labor_hours: 3,
      hourly_rate: 120,
    })
  })

  it('shows computed metrics and records risk acceptance and imported records', async () => {
    let acceptances: RiskAcceptance[] = []
    let acceptanceBody: unknown
    let recordBody: unknown

    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (
          url === '/api/projects/p1/coordination-overview' &&
          !init?.method
        ) {
          return jsonResponse(makeOverview(acceptances))
        }
        if (
          url === '/api/coordination-topics/t1/risk-acceptances' &&
          init?.method === 'POST'
        ) {
          acceptanceBody = JSON.parse(String(init.body))
          acceptances = [
            {
              id: 'ra1',
              topic_id: 't1',
              metric_run_id: 'mr1',
              risk_level: 'high',
              actor: '演示工程师',
              role: 'design_engineer',
              note: '已评审，接受该风险并持续跟踪',
              created_at: '2026-10-19T02:00:00+00:00',
            },
          ]
          return jsonResponse(acceptances[0], 201)
        }
        if (
          url === '/api/coordination-topics/t1/records' &&
          init?.method === 'POST'
        ) {
          recordBody = JSON.parse(String(init.body))
          return jsonResponse({ id: 'rec2' }, 201)
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<CoordinationPanel projectId="p1" />)

    expect(await screen.findByText(/平均响应时延：12/)).toBeInTheDocument()
    expect(screen.getByText(/评分 82/)).toBeInTheDocument()
    expect(screen.getByText(/依据：缺席率偏高/)).toBeInTheDocument()
    expect(screen.getByText(/成本：360 元/)).toBeInTheDocument()
    expect(screen.getByText(/3 小时 × 120 元/)).toBeInTheDocument()

    await user.clear(screen.getByLabelText('风险接受理由 CT-P01-001'))
    await user.type(
      screen.getByRole('textbox', { name: '风险接受理由 CT-P01-001' }),
      '已评审，接受该风险并持续跟踪',
    )
    await user.click(screen.getByRole('button', { name: '接受风险' }))

    expect(
      await screen.findByText('CT-P01-001 风险接受已留痕'),
    ).toBeInTheDocument()
    expect(acceptanceBody).toEqual({
      metric_run_id: 'mr1',
      actor: '演示工程师',
      role: 'design_engineer',
      note: '已评审，接受该风险并持续跟踪',
    })
    expect(
      screen.getByRole('button', { name: '已接受风险' }),
    ).toBeDisabled()

    await user.click(screen.getByRole('button', { name: '导入沟通记录' }))

    await user.type(
      screen.getByRole('textbox', { name: '协同记录外部编号' }),
      'MSG-002',
    )
    await user.type(
      screen.getByRole('textbox', { name: '协同记录发送方' }),
      '试验部',
    )
    fireEvent.change(
      screen.getByLabelText('协同记录发送时间'),
      { target: { value: '2026-10-18T09:00' } },
    )
    await user.type(
      screen.getByRole('textbox', { name: '协同记录摘要' }),
      '补充接口扭矩试验记录',
    )
    await user.type(
      screen.getByRole('textbox', { name: '协同记录响应对象' }),
      'MSG-001',
    )
    await user.click(screen.getByRole('button', { name: '导入记录' }))

    expect(await screen.findByText('协同记录已导入')).toBeInTheDocument()
    expect(recordBody).toMatchObject({
      external_id: 'MSG-002',
      record_type: 'message',
      sender: '试验部',
      content_summary: '补充接口扭矩试验记录',
      reply_to_external_id: 'MSG-001',
    })
    expect(String((recordBody as { sent_at: string }).sent_at)).toMatch(
      /^2026-10-18T\d{2}:00:00\.000Z$/,
    )
  })
})

it('prefills a labelled synthetic topic and message without automatically saving',async()=>{
 const data=makeOverview();data.topics[0].expected_participants=['A 主机方','B 研发方']
 vi.spyOn(api,'getCoordinationOverview').mockResolvedValue(data)
 const create=vi.spyOn(api,'createCoordinationTopic'),save=vi.spyOn(api,'createCoordinationRecord')
 const user=userEvent.setup();render(<CoordinationPanel projectId="p1"/>)
 expect(screen.getByLabelText('协同议题名称')).toHaveValue('合成设计冻结交付协同')
 expect(screen.getByLabelText('协同窗口开始')).toHaveValue('2026-10-20T00:00')
 await user.click(await screen.findByRole('button',{name:'导入沟通记录'}))
 await user.click(screen.getByRole('button',{name:'填入发起消息样例'}))
 expect(screen.getByLabelText('协同记录发送方')).toHaveValue('A 主机方')
 await user.click(screen.getByRole('button',{name:'填入回复消息样例'}))
 expect(screen.getByLabelText('协同记录响应对象')).toHaveValue('')
 expect(screen.getByRole('alert')).toHaveTextContent('请先保存窗口内的发起消息')
 expect(create).not.toHaveBeenCalled();expect(save).not.toHaveBeenCalled()
})

it('prefills editable synthetic effort and rate without calculating until requested',async()=>{
 vi.spyOn(api,'getCoordinationOverview').mockResolvedValue(makeOverview())
 const calculate=vi.spyOn(api,'calculateCoordinationMetrics').mockResolvedValue({id:'metric-synthetic'})
 const user=userEvent.setup();render(<CoordinationPanel projectId="p1"/>)
 const hours=await screen.findByLabelText('工时 CT-P01-001')
 const rate=screen.getByLabelText('费率 CT-P01-001')
 expect(hours).toHaveValue(3);expect(rate).toHaveValue(120)
 expect(calculate).not.toHaveBeenCalled()
 await user.clear(hours);await user.type(hours,'5')
 await user.clear(rate)
 await user.click(screen.getByRole('button',{name:'重算指标'}))
 expect(calculate).toHaveBeenCalledWith('t1',{labor_hours:5,hourly_rate:null})
})
