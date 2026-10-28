import { api } from '../api'
import { emptyWorkflow,emptyProgress } from '../test/workflowFixture'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import type {
  Conflict,
  ConsistencyCheckPayload,
} from '../types'
import { ConsistencyPanel } from './ConsistencyPanel'

const conflict: Conflict = {
  id: 'cf1',
  project_id: 'p1',
  display_code: 'CF-P01-001',
  revision: 1,
  conflict_type: 'parameter_mismatch',
  severity: 'blocking',
  status: 'open',
  detected: false,
  title: '派生输入扭矩低于发动机扭矩',
  detail: 'C-002 仍为 2600 N·m，B-003 已更新为 2800 N·m',
  object_type: 'requirement',
  object_id: 'r-c002',
  object_revision: 1,
  object_review_status: 'draft',
  first_seen_at: '2026-10-19T00:00:00+00:00',
  last_seen_at: '2026-10-19T01:00:00+00:00',
  recheck_status: 'not_detected',
  resolution_type: null,
  resolution_note: null,
  evidence_text: null,
  accepted_risk: false,
  closed_by: null,
  closed_at: null,
  blocking: true,
  review_pending: true,
  evidence: { comparison: '2600 < 2800' },
  events: [],
}

function payload(checkStatus: string, summaryOpen: number): ConsistencyCheckPayload {
  return {
    check: {
      id: 'check1',
      project_id: 'p1',
      display_code: 'CR-P01-001',
      check_no: 1,
      revision: 1,
      status: checkStatus,
      validity: 'current',
      mode: 'rule',
      source_label: '一致性检查',
      created_at: '2026-10-19T00:00:00+00:00',
      updated_at: '2026-10-19T01:00:00+00:00',
      summary: {
        conflict_count: 1,
        blocking_open: summaryOpen,
        open: summaryOpen,
        not_detected_open: 1,
        review_pending: 1,
      },
    },
    conflicts: [conflict],
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

describe('ConsistencyPanel', () => {
  it('locks a saved report confirmation until a failed readback is recovered', async () => {
    let reads = 0, writes = 0
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') { writes++; return jsonResponse({ id: 'saved-check-review' }) }
      if (String(input).endsWith('/conflicts')) return jsonResponse([conflict])
      if (++reads === 2) throw new Error('报告暂不可读')
      return jsonResponse(payload(reads > 2 ? 'confirmed' : 'draft', 1))
    }))
    const user = userEvent.setup()
    render(<ConsistencyPanel projectId="p1" />)
    await user.click(await screen.findByRole('button', { name: '确认检查报告' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('一致性检查审核已保存，但页面刷新失败')
    expect(screen.getByRole('button', { name: '确认检查报告' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: '重新读取已保存结果' }))
    expect(screen.queryByRole('button', { name: '确认检查报告' })).not.toBeInTheDocument()
    expect(writes).toBe(1)
  })
  it('keeps a compact conflict list and places complete evidence only in the drawer', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL) => jsonResponse(String(url).endsWith('/latest') ? payload('confirmed', 1) : [conflict])))
    const user = userEvent.setup()
    render(<ConsistencyPanel projectId="p1" />)
    const row = (await screen.findByText('CF-P01-001')).closest('tr')!
    expect(row).not.toHaveTextContent(conflict.detail)
    expect(within(row).queryByRole('group', { name: '检查依据' })).not.toBeInTheDocument()
    expect(within(row).getByText(conflict.title)).toBeInTheDocument()
    await user.click(within(row).getByRole('button', { name: '查看 / 处置' }))
    const drawer = screen.getByRole('dialog', { name: '冲突处置 · CF-P01-001' })
    expect(within(drawer).getByText(conflict.detail)).toBeInTheDocument()
    expect(within(drawer).getByRole('group', { name: '检查依据' })).toBeInTheDocument()
    expect(within(drawer).getByLabelText('冲突处置说明')).toBeInTheDocument()
  })
  it('retains closed conflict evidence and disposition history in a read-only drawer', async () => {
    const closed: Conflict = { ...conflict, status: 'closed', resolution_type: 'fixed', resolution_note: '完成独立复核', evidence_text: '复检报告-V2', closed_by: '王工', closed_at: '2026-10-22T02:00:00Z', events: [{ id: 'event1', action: 'conflict.closed', actor: '王工', role: 'design_engineer', note: '完成独立复核', evidence: '复检报告-V2', created_at: '2026-10-22T02:00:00Z' }] }
    const fetcher = vi.fn(async (url: RequestInfo | URL, _init?: RequestInit) => jsonResponse(String(url).endsWith('/latest') ? payload('confirmed', 0) : [closed]))
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()
    render(<ConsistencyPanel projectId="p1" />)
    const trigger = await screen.findByRole('button', { name: '查看详情' })
    await user.click(trigger)
    const drawer = screen.getByRole('dialog', { name: '冲突详情 · CF-P01-001' })
    const disposition = within(drawer).getByRole('region', { name: '已保存的处置记录' })
    expect(disposition).toHaveTextContent('完成独立复核')
    expect(disposition).toHaveTextContent('复检报告-V2')
    expect(disposition).toHaveTextContent('王工')
    expect(within(drawer).getByText(conflict.detail)).toBeInTheDocument()
    expect(within(drawer).queryByLabelText('冲突处置说明')).not.toBeInTheDocument()
    expect(within(drawer).queryByRole('button', { name: '确认关闭（留痕）' })).not.toBeInTheDocument()
    const history = within(drawer).getByRole('group', { name: '冲突流转记录' })
    await user.click(within(history).getByText(/查看流转记录/))
    expect(within(history).getByText(/完成独立复核/)).toBeVisible()
    await user.click(within(drawer).getByRole('button', { name: '关闭处置详情' }))
    expect(trigger).toHaveFocus()
    expect(fetcher.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true)
  })
  it('opens conflict evidence and resolution in a drawer; cancelling does not close the conflict', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => jsonResponse(String(input).endsWith('/latest') ? payload('confirmed', 1) : [conflict]))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    const { container } = render(<ConsistencyPanel projectId="p1" />)
    const trigger = await screen.findByRole('button', { name: '查看 / 处置' })
    await user.click(trigger)
    const drawer = await screen.findByRole('dialog', { name: '冲突处置 · CF-P01-001' })
    expect(drawer).toHaveClass('detail-overlay--drawer')
    expect(within(drawer).getByText(conflict.detail)).toBeInTheDocument()
    await user.click(within(drawer).getByText(/查看检查依据/))
    expect(within(drawer).getByText('2600 < 2800')).toBeVisible()
    await user.type(within(drawer).getByLabelText('冲突处置说明'), '正在核对，不提交')
    expect(container.querySelector('.inline-action')).toBeNull()
    await user.click(within(drawer).getByRole('button', { name: '关闭处置详情' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
    expect(fetchMock.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true)
    await user.click(trigger)
    expect(screen.getByLabelText('冲突处置说明')).toHaveValue('正在核对，不提交')
  })
  it('keeps failed conflict submission, evidence and comments inside the drawer', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') return jsonResponse({ error: { message: '处置版本已变化' } }, 409)
      return jsonResponse(String(input).endsWith('/latest') ? payload('confirmed', 1) : [conflict])
    }))
    const user = userEvent.setup()
    render(<ConsistencyPanel projectId="p1" />)
    await user.click(await screen.findByRole('button', { name: '查看 / 处置' }))
    const drawer = await screen.findByRole('dialog', { name: '冲突处置 · CF-P01-001' })
    await user.type(within(drawer).getByLabelText('冲突处置说明'), '保持原意见')
    await user.type(within(drawer).getByLabelText('冲突处置证据'), '报告 V2')
    await user.click(within(drawer).getByRole('button', { name: '确认关闭（留痕）' }))
    expect(await within(drawer).findByRole('alert')).toHaveTextContent('处置版本已变化')
    expect(within(drawer).getByLabelText('冲突处置说明')).toHaveValue('保持原意见')
    expect(within(drawer).getByLabelText('冲突处置证据')).toHaveValue('报告 V2')
  })
  it('expands structured Chinese evidence without hiding unknown evidence values or review state', async () => {
    const item = { ...conflict, evidence: { comparison: '2600 < 2800', case_revision: 2, extra_probe: { sample: '样件证据-X', zero: 0, missing: null } } }
    vi.stubGlobal('fetch', vi.fn(async (url: string) => jsonResponse(url.endsWith('/latest') ? payload('confirmed', 1) : [item])))
    const user = userEvent.setup()
    const { container } = render(<ConsistencyPanel projectId="p1" />)
    await user.click(await screen.findByRole('button', { name: '查看 / 处置' }))
    const evidence = await screen.findByRole('group', { name: '检查依据' })
    await user.click(within(evidence).getByText(/查看检查依据/))
    expect(within(evidence).getByText('比较关系')).toBeVisible()
    expect(within(evidence).getByText('2600 < 2800')).toBeVisible()
    expect(within(evidence).getByText('当前用例版本')).toBeVisible()
    expect(within(evidence).getByText('样件证据-X')).toBeVisible()
    expect(within(evidence).getByText('0')).toBeVisible()
    expect(within(evidence).getByText('未记录')).toBeVisible()
    const row = screen.getByText('CF-P01-001').closest('tr')!
    expect(within(row).getByText(/工程需求 · V1/)).toBeVisible()
    expect(within(row).getByText(/审核状态 草案/)).toBeVisible()
    expect(container.textContent).not.toContain('"comparison"')
    expect(container.textContent).not.toContain('[object Object]')
  })
  it('renders nested backend statistics as Chinese distributions with the original counts', async () => {
    const data = payload('confirmed', 3)
    data.check.summary = { total: 4, open: 3, closed: 1, blocking_open: 1, review_pending: 2, accepted_risk: 1, detected: 4, not_detected_open: 0, by_severity: { blocking: 1, high: 2, medium: 1, low: 0 }, by_type: { parameter: 2, version: 1, reference: 1, condition: 0, rule: 0 } }
    vi.stubGlobal('fetch', vi.fn(async (url: string) => jsonResponse(url.endsWith('/latest') ? data : [])))
    render(<ConsistencyPanel projectId="p1" />)
    const severity = await screen.findByRole('region', { name: '本次检出严重度分布' })
    expect(within(severity).getByText('高').parentElement).toHaveTextContent('2')
    expect(within(severity).getByText('阻断').parentElement).toHaveTextContent('1')
    const types = screen.getByRole('region', { name: '本次检出类型分布' })
    expect(within(types).getByText('参数偏差').parentElement).toHaveTextContent('2')
    expect(within(types).getByText('版本问题').parentElement).toHaveTextContent('1')
    expect(screen.getByText(/CR-P01-001.*已确认/)).toBeInTheDocument()
    expect(screen.queryByText('[object Object]')).not.toBeInTheDocument()
    expect(screen.queryByText('by_type')).not.toBeInTheDocument()
    expect(screen.queryByText('by_severity')).not.toBeInTheDocument()
    expect(screen.queryByText('total')).not.toBeInTheDocument()
  })

  it('preserves actual zero counts without claiming missing distributions are zero', async () => {
    const data = payload('confirmed', 0)
    data.check.summary = { total: 0, open: 0, closed: 0, blocking_open: 0, review_pending: 0, accepted_risk: 0 }
    vi.stubGlobal('fetch', vi.fn(async (url: string) => jsonResponse(url.endsWith('/latest') ? data : [])))
    render(<ConsistencyPanel projectId="p1" />)
    const summary = await screen.findByRole('region', { name: '一致性检查统计' })
    expect(within(summary).getByText('本次检出').parentElement).toHaveTextContent('0')
    expect(within(summary).getByText('开放').parentElement).toHaveTextContent('0')
    expect(screen.getByText('本次检查未检出一致性冲突；此结论仅对应本次输入快照，不代表全部试验已完成。')).toBeVisible()
    expect(screen.getByText('未记录严重度分布')).toBeInTheDocument()
    expect(screen.getByText('未记录类型分布')).toBeInTheDocument()
  })

  it('shows unavailable for invalid numeric summaries and never stringifies objects', async () => {
    const data = payload('draft', 1)
    data.check.summary = { total: {}, open: '7', closed: -1, blocking_open: Infinity, review_pending: null, accepted_risk: NaN, by_severity: { high: {} }, by_type: { parameter: [] } }
    vi.stubGlobal('fetch', vi.fn(async (url: string) => jsonResponse(url.endsWith('/latest') ? data : [])))
    render(<ConsistencyPanel projectId="p1" />)
    const summary = await screen.findByRole('region', { name: '一致性检查统计' })
    expect(within(summary).getByText('本次检出').parentElement).toHaveTextContent('—')
    expect(within(summary).getByText('开放').parentElement).toHaveTextContent('—')
    expect(within(summary).getByText('已关闭').parentElement).toHaveTextContent('—')
    expect(screen.getByText(/部分统计未记录或格式无效/)).toBeInTheDocument()
    expect(screen.queryByText('[object Object]')).not.toBeInTheDocument()
  })

  it('runs a check and confirms the report without hiding open conflicts', async () => {
    let hasRun = false
    let confirmed = false
    let confirmBody: unknown
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (
          url === '/api/projects/p1/consistency-checks/latest' &&
          !init?.method
        ) {
          return hasRun
            ? jsonResponse(payload(confirmed ? 'confirmed' : 'draft', 1))
            : jsonResponse({ error: { message: '尚无检查' } }, 404)
        }
        if (url === '/api/projects/p1/conflicts' && !init?.method) {
          return jsonResponse([conflict])
        }
        if (
          url === '/api/projects/p1/consistency-checks' &&
          init?.method === 'POST'
        ) {
          hasRun = true
          return jsonResponse(payload('draft', 1))
        }
        if (
          url === '/api/consistency-checks/check1/confirmations' &&
          init?.method === 'POST'
        ) {
          confirmBody = JSON.parse(String(init.body))
          confirmed = true
          return jsonResponse({ id: 'c-check' }, 201)
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<ConsistencyPanel projectId="p1" />)

    expect(
      await screen.findByText('项目尚无一致性检查报告。'),
    ).toBeInTheDocument()
    expect(await screen.findByText('CF-P01-001')).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: '运行一致性检查' }),
    )
    expect(
      await screen.findByText(
        '一致性检查 CR-P01-001 完成：开放 1 条，未关闭阻断 1 条',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText(/审核：待审核/)).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: '确认检查报告' }),
    )
    expect(
      await screen.findByText('一致性检查已确认'),
    ).toBeInTheDocument()
    expect(confirmBody).toMatchObject({
      expected_revision: 1,
      decision: 'confirmed',
    })
  })

  it('shows open conflict together with pending review and closes it with evidence', async () => {
    let closed = false
    let closeBody: unknown
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (
          url === '/api/projects/p1/consistency-checks/latest' &&
          !init?.method
        ) {
          return jsonResponse(payload('confirmed', closed ? 0 : 1))
        }
        if (url === '/api/projects/p1/conflicts' && !init?.method) {
          return jsonResponse([
            closed
              ? {
                  ...conflict,
                  status: 'closed',
                  resolution_type: 'fixed',
                  resolution_note: '已按 2800 更新',
                }
              : conflict,
          ])
        }
        if (url === '/api/conflicts/cf1/close' && init?.method === 'POST') {
          closeBody = JSON.parse(String(init.body))
          closed = true
          return jsonResponse({
            ...conflict,
            status: 'closed',
            resolution_type: 'fixed',
          })
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<ConsistencyPanel projectId="p1" />)

    await screen.findByText('CF-P01-001')
    expect(screen.getByText(/复检：未检出/)).toBeInTheDocument()
    expect(screen.getByText(/审核：待审核/)).toBeInTheDocument()
    expect(screen.getAllByText('阻断').length).toBeGreaterThan(0)

    await user.click(
      screen.getByRole('button', { name: '查看 / 处置' }),
    )
    await user.type(
      screen.getByRole('textbox', { name: '冲突处置说明' }),
      '已按 2800 更新派生要求并复核',
    )
    await user.type(
      screen.getByRole('textbox', { name: '冲突处置证据' }),
      'C-002 V2 确认记录；复检未再检出',
    )
    await user.click(
      screen.getByRole('button', { name: '确认关闭（留痕）' }),
    )

    expect(
      await screen.findByText('冲突 CF-P01-001 已关闭并留痕'),
    ).toBeInTheDocument()
    expect(closeBody).toMatchObject({
      expected_revision: 1,
      resolution_type: 'fixed',
      note: '已按 2800 更新派生要求并复核',
      evidence: 'C-002 V2 确认记录；复检未再检出',
    })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByText('CF-P01-001').closest('tr')).toHaveFocus()
  })
})
