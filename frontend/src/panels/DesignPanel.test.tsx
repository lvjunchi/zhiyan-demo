import { fireEvent, render, screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type {
  DesignReviewPayload,
  DfmeaPayload,
  FmeaItem,
  SimilarProjectsResult,
} from '../types'
import { DesignPanel } from './DesignPanel'
import { api } from '../api'

const similar: SimilarProjectsResult = {
  project_id: 'p1',
  mode: 'rule',
  source_label: '历史项目库',
  candidate_count: 1,
  top_n: 3,
  candidate_shortage: true,
  missing_criteria: [],
  requirement_versions: [],
  matches: [
    {
      history_project_id: 'h1',
      display_code: 'HP-01',
      name: '历史 12 档项目',
      customer: '陕汽',
      score: 91,
      matched_points: ['档位数一致'],
      differences: ['扭矩更高'],
      missing_criteria: [],
      criteria: [],
      source: '历史项目库',
      notes: '',
    },
  ],
}

const reviewPayload: DesignReviewPayload = {
  review: {
    id: 'dr1',
    project_id: 'p1',
    display_code: 'DR-P01',
    base_display_code: 'JX-12A',
    revision: 1,
    status: 'draft',
    created_at: '2026-10-19T00:00:00+00:00',
    updated_at: '2026-10-19T00:00:00+00:00',
  },
  items: [
    {
      id: 'dri1',
      display_code: 'DR-01',
      revision: 1,
      status: 'current',
      check_point: '输入扭矩匹配校核',
      standard_basis: '派生要求 ≥ 发动机最大扭矩',
      responsible_role: '设计工程师',
      dependencies: [
        { display_code: 'REQ-P01-C-002', parameter_name: '最低额定输入扭矩' },
      ],
    },
  ],
  inputs_snapshot: {},
  missing_inputs: [],
  confirmations: [],
  needs_reconfirmation: false,
  mode: 'rule',
}

const fmeaItem: FmeaItem = {
  id: 'f1',
  display_code: 'FM-01',
  revision: 1,
  status: 'current',
  function_text: '传递发动机扭矩',
  failure_mode: '输入轴断裂',
  cause: '扭矩超出设计能力',
  effect: '动力中断',
  control: '材料与热处理控制',
  action_text: '按 2800 N·m 复核',
  severity: 7,
  occurrence: 5,
  detection: 3,
  scores_confirmed: false,
  rpn: null,
  rpn_status: 'pending_confirmation',
  dependencies: [],
}

function makeFmea(): DfmeaPayload {
  return {
    fmea: {
      id: 'fmea1',
      project_id: 'p1',
      display_code: 'DF-P01',
      base_display_code: 'JX-12A',
      revision: 1,
      status: 'draft',
      scale: { severity: '1–10' },
      created_at: '2026-10-19T00:00:00+00:00',
      updated_at: '2026-10-19T00:00:00+00:00',
    },
    items: [{ ...fmeaItem }],
    inputs_snapshot: {},
    missing_inputs: [],
    confirmations: [],
    needs_reconfirmation: false,
    mode: 'rule',
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

describe('DesignPanel', () => {
  it('preserves another item draft when saving one FMEA score row', async () => {
    let data = makeFmea()
    data.items.push({ ...fmeaItem, id: 'f2', display_code: 'FM-02' })
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'PATCH') {
        data = { ...data, items: data.items.map(item => item.id === 'f1' ? { ...item, severity: 8, revision: 2 } : item) }
        return jsonResponse(data.items[0])
      }
      return jsonResponse(String(input).endsWith('/dfmea') ? data : reviewPayload)
    }))
    const user = userEvent.setup()
    render(<DesignPanel projectId="p1" />)
    const first = await screen.findByLabelText('FM-01 severity')
    const second = screen.getByLabelText('FM-02 severity')
    await user.clear(first); await user.type(first, '8')
    await user.clear(second); await user.type(second, '9')
    await user.click(within(screen.getByRole('row', { name: /FM-01/ })).getByRole('button', { name: '保存评分' }))
    expect(await screen.findByText(/FM-01 评分已保存/)).toBeInTheDocument()
    expect(second).toHaveValue(9)
    expect(within(screen.getByRole('row', { name: /FM-02/ })).getByRole('button', { name: '确认评分' })).toBeDisabled()
  })
  it('requires saving edited scores before confirming scores or the document', async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => jsonResponse(String(input).endsWith('/dfmea') ? makeFmea() : reviewPayload))
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()
    render(<DesignPanel projectId="p1" />)
    const severity = await screen.findByLabelText('FM-01 severity')
    await user.clear(severity)
    await user.type(severity, '8')
    expect(screen.getByRole('button', { name: '确认评分' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '确认 DFMEA' })).toBeDisabled()
    expect(screen.getByText('评分有未保存修改，请先保存评分。')).toBeInTheDocument()
    expect(fetcher.mock.calls.every(([, init]) => !init?.method)).toBe(true)
  })
  it('keeps a successful review saved when readback fails and retries only the read', async () => {
    let reads = 0, writes = 0
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (init?.method === 'POST') { writes++; return jsonResponse({ id: 'saved-audit' }) }
      if (url.endsWith('/design-review')) {
        if (++reads === 2) throw new Error('读取暂不可用')
        return jsonResponse(reads > 2 ? { ...reviewPayload, review: { ...reviewPayload.review, status: 'confirmed' } } : reviewPayload)
      }
      return jsonResponse(makeFmea())
    }))
    const user = userEvent.setup()
    render(<DesignPanel projectId="p1" />)
    await user.click(await screen.findByRole('button', { name: '确认设计评审' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('设计评审审核已保存，但页面刷新失败')
    expect(screen.getByRole('button', { name: '确认设计评审' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: '重新读取已保存结果' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: '确认设计评审' })).not.toBeInTheDocument())
    expect(writes).toBe(1)
  })
  it('loads existing design without calculating similarity until the user requests it', async () => {
    const fetcher = vi.fn(async (url: RequestInfo | URL, _init?: RequestInit) => jsonResponse(
      String(url).includes('similar') ? similar : reviewPayload,
      String(url).endsWith('dfmea') ? 404 : 200,
    ))
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()
    render(<DesignPanel projectId="p1" />)
    await screen.findByText('1 项检查')
    expect(fetcher.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
    await user.click(screen.getByRole('button', { name: '重新计算相似项目' }))
    expect(await screen.findByText('历史 12 档项目')).toBeInTheDocument()
    expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  })
  it('keeps review work compact and moves the full checklist and dependencies into the preview', async () => {
    const fetcher = vi.fn(async (url: RequestInfo | URL, _init?: RequestInit) => jsonResponse(String(url).includes('similar') ? similar : String(url).endsWith('design-review') ? reviewPayload : {}, String(url).endsWith('dfmea') ? 404 : 200))
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()
    render(<DesignPanel projectId="p1" />)
    const workspace = await screen.findByRole('region', { name: '设计评审工作区' })
    expect(within(workspace).queryByRole('table')).not.toBeInTheDocument()
    expect(within(workspace).queryByText('输入扭矩匹配校核')).not.toBeInTheDocument()
    expect(await within(workspace).findByText('1 项检查')).toBeInTheDocument()
    expect(within(workspace).getByText('DR-01')).toHaveAttribute('data-object-id', 'dri1')
    expect(within(workspace).getByRole('button', { name: '确认设计评审' })).toBeEnabled()
    const before = fetcher.mock.calls.length
    const trigger = within(workspace).getByRole('button', { name: '预览设计评审' })
    await user.click(trigger)
    const preview = screen.getByRole('dialog', { name: '设计评审预览' })
    expect(within(preview).getByText('输入扭矩匹配校核')).toBeInTheDocument()
    expect(within(preview).getByText(/REQ-P01-C-002/)).toBeInTheDocument()
    expect(within(preview).getByText('设计工程师')).toBeInTheDocument()
    expect(fetcher).toHaveBeenCalledTimes(before)
    await user.click(within(preview).getByRole('button', { name: '关闭预览' }))
    expect(trigger).toHaveFocus()
  })
  it('opens similar projects in a dialog and reopens the saved result without recalculating', async () => {
    const fetcher = vi.fn(async (url: RequestInfo | URL, _init?: RequestInit) => jsonResponse(String(url).includes('similar') ? similar : {}, String(url).includes('similar') ? 200 : 404))
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()
    render(<DesignPanel projectId="p1" />)
    await user.click(screen.getByRole('button', { name: '重新计算相似项目' }))
    await screen.findByText('历史 12 档项目', { exact: false })
    await user.click(screen.getByRole('button', { name: '关闭相似项目' }))
    const trigger = await screen.findByRole('button', { name: '查看相似项目' })
    const count = fetcher.mock.calls.length
    await user.click(trigger)
    const dialog = await screen.findByRole('dialog', { name: '相似项目匹配结果' })
    expect(within(dialog).getByText('历史 12 档项目', { exact: false })).toBeInTheDocument()
    expect(fetcher).toHaveBeenCalledTimes(count)
    await user.click(within(dialog).getByRole('button', { name: '关闭相似项目' }))
    expect(trigger).toHaveFocus()
    await user.click(screen.getByRole('button', { name: '重新计算相似项目' }))
    expect(await screen.findByRole('dialog', { name: '相似项目匹配结果' })).toBeInTheDocument()
    expect(fetcher.mock.calls.filter(([url]) => String(url).includes('similar'))).toHaveLength(2)
  })
  it('previews a saved review with its actual check points without generating a new artifact', async () => {
    const fetcher = vi.fn(async (url: string, _init?: RequestInit) => jsonResponse(url.includes('similar') ? similar : url.endsWith('design-review') ? reviewPayload : {}, url.endsWith('dfmea') ? 404 : 200))
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()
    render(<DesignPanel projectId="p1" />)
    const previewButton = await screen.findByRole('button', { name: '预览设计评审' })
    const callsBeforePreview = fetcher.mock.calls.length
    await user.click(previewButton)
    const dialog = screen.getByRole('dialog', { name: '设计评审预览' })
    expect(dialog).toHaveTextContent('输入扭矩匹配校核')
    expect(dialog).toHaveTextContent('派生要求 ≥ 发动机最大扭矩')
    expect(fetcher).toHaveBeenCalledTimes(callsBeforePreview)
  })
  it('generates and confirms review, then confirms DFMEA scores before RPN', async () => {
    let review: DesignReviewPayload | null = null
    let fmea: DfmeaPayload | null = null
    let scoreBody: unknown
    let saveBody: unknown
    let reviewConfirmBody: unknown
    let fmeaConfirmBody: unknown

    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (
          url === '/api/projects/p1/similar-projects' &&
          init?.method === 'POST'
        ) {
          return jsonResponse(similar)
        }
        if (url === '/api/projects/p1/design-review' && !init?.method) {
          return review
            ? jsonResponse(review)
            : jsonResponse({ error: { message: '不存在' } }, 404)
        }
        if (
          url === '/api/projects/p1/design-review' &&
          init?.method === 'POST'
        ) {
          review = reviewPayload
          return jsonResponse(review)
        }
        if (
          url === '/api/design-reviews/dr1/confirmations' &&
          init?.method === 'POST'
        ) {
          reviewConfirmBody = JSON.parse(String(init.body))
          review = {
            ...reviewPayload,
            review: { ...reviewPayload.review, status: 'confirmed' },
          }
          return jsonResponse({ id: 'c1' }, 201)
        }
        if (url === '/api/projects/p1/dfmea' && !init?.method) {
          return fmea
            ? jsonResponse(fmea)
            : jsonResponse({ error: { message: '不存在' } }, 404)
        }
        if (
          url === '/api/projects/p1/dfmea' &&
          init?.method === 'POST'
        ) {
          fmea = makeFmea()
          return jsonResponse(fmea)
        }
        if (
          url === '/api/fmea-items/f1' &&
          init?.method === 'PATCH'
        ) {
          saveBody = JSON.parse(String(init.body))
          if (fmea) {
            fmea = {
              ...fmea,
              items: [{ ...fmeaItem, revision: 2, severity: 8 }],
            }
          }
          return jsonResponse({ id: 'f1' })
        }
        if (
          url === '/api/fmea-items/f1/confirm-scores' &&
          init?.method === 'POST'
        ) {
          scoreBody = JSON.parse(String(init.body))
          if (fmea) {
            fmea = {
              ...fmea,
              items: [
                {
                  ...fmeaItem,
                  revision: 3,
                  severity: 8,
                  scores_confirmed: true,
                  rpn: 120,
                  rpn_status: 'confirmed',
                },
              ],
            }
          }
          return jsonResponse({ id: 'f1' })
        }
        if (
          url === '/api/fmea-documents/fmea1/confirmations' &&
          init?.method === 'POST'
        ) {
          fmeaConfirmBody = JSON.parse(String(init.body))
          if (fmea) {
            fmea = {
              ...fmea,
              fmea: { ...fmea.fmea, status: 'confirmed' },
            }
          }
          return jsonResponse({ id: 'c-fmea' }, 201)
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<DesignPanel projectId="p1" />)

    await user.click(await screen.findByRole('button', { name: '重新计算相似项目' }))
    expect(await screen.findByText(/历史 12 档项目/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '关闭相似项目' }))
    expect(
      await screen.findByText('尚未生成设计评审清单。'),
    ).toBeInTheDocument()
    expect(await screen.findByText('尚未生成 DFMEA。')).toBeInTheDocument()

    await user.type(
      screen.getByRole('textbox', { name: '设计评审基型编号' }),
      'JX-12A',
    )
    await user.click(
      screen.getByRole('button', { name: '生成设计评审' }),
    )
    await user.click(await screen.findByRole('button', { name: '预览设计评审' }))
    expect(
      await screen.findByText('输入扭矩匹配校核'),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '关闭预览' }))
    await user.click(
      screen.getByRole('button', { name: '确认设计评审' }),
    )
    expect(
      await screen.findByText('设计评审已确认'),
    ).toBeInTheDocument()
    expect(reviewConfirmBody).toMatchObject({
      expected_revision: 1,
      decision: 'confirmed',
    })

    await user.type(
      screen.getByRole('textbox', { name: 'DFMEA 基型编号' }),
      'JX-12A',
    )
    await user.click(screen.getByRole('button', { name: '生成 DFMEA' }))
    expect(await screen.findByText('输入轴断裂')).toBeInTheDocument()
    expect(screen.getByText('待确认')).toBeInTheDocument()

    fireEvent.change(
      screen.getByRole('spinbutton', { name: 'FM-01 severity' }),
      { target: { value: '8' } },
    )
    await user.click(screen.getByRole('button', { name: '保存评分' }))
    expect(
      await screen.findByText(
        'FM-01 评分已保存，需人工确认后才计入 RPN',
      ),
    ).toBeInTheDocument()
    expect(saveBody).toMatchObject({
      expected_revision: 1,
      severity: 8,
      occurrence: 5,
      detection: 3,
    })
    expect(screen.getByText('待确认')).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: '确认评分' }),
    )
    expect(await screen.findByText('120')).toBeInTheDocument()
    expect(scoreBody).toMatchObject({
      expected_revision: 2,
      actor: '演示工程师',
    })

    await user.click(
      screen.getByRole('button', { name: '确认 DFMEA' }),
    )
    expect(await screen.findByText('DFMEA 已确认')).toBeInTheDocument()
    expect(fmeaConfirmBody).toMatchObject({
      expected_revision: 1,
      decision: 'confirmed',
    })
  })
})

it('inherits the persisted base and prefills labelled synthetic score drafts without saving',async()=>{
 vi.spyOn(api,'getDesignContext').mockResolvedValue({base_display_code:'JX-12B',source:'variant_analysis'})
 vi.spyOn(api,'getDesignReview').mockResolvedValue(reviewPayload)
 vi.spyOn(api,'getDfmea').mockResolvedValue({...makeFmea(),items:[{...fmeaItem,display_code:'FMEA-01',severity:null,occurrence:null,detection:null,rpn_status:'incomplete'}]})
 const save=vi.spyOn(api,'updateFmeaItem')
 const user=userEvent.setup();render(<DesignPanel projectId="p1"/>)
 await waitFor(()=>expect(screen.getByLabelText('设计评审基型编号')).toHaveValue('JX-12B'))
 expect(screen.getByLabelText('DFMEA 基型编号')).toHaveValue('JX-12B')
 await user.click(screen.getByRole('button',{name:'填入合成评分'}))
 const row=screen.getByRole('row',{name:/FMEA-01/})
 expect(within(row).getByLabelText('FMEA-01 severity')).toHaveValue(8)
 expect(within(row).getByText('待保存')).toBeVisible()
 expect(within(row).queryByText('评分缺失')).not.toBeInTheDocument()
 expect(save).not.toHaveBeenCalled()
 fireEvent.change(within(row).getByLabelText('FMEA-01 severity'),{target:{value:'9'}})
 await user.click(screen.getByRole('button',{name:'填入合成评分'}))
 expect(within(row).getByLabelText('FMEA-01 severity')).toHaveValue(9)
 fireEvent.change(within(row).getByLabelText('FMEA-01 severity'),{target:{value:'23'}})
 expect(within(row).getByText(/1–10 的整数/)).toBeVisible()
 expect(within(row).getByRole('button',{name:'保存评分'})).toBeDisabled()
})
