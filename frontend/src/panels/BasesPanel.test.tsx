import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import type {
  CandidateBase,
  RecommendationResult,
  VariantAnalysisResult,
} from '../types'
import { api } from '../api'
import { BasesPanel } from './BasesPanel'

const base: CandidateBase = {
  id: 'b1',
  display_code: 'JX-12A',
  name: '12 档 AMT 基型',
  transmission_type: 'AMT',
  gear_count: 12,
  rated_input_torque: 2600,
  first_gear_ratio: 15.2,
  top_gear_type: 'overdrive',
  has_pto: true,
  weight_kg: 245,
  source: '型谱库',
}

const recommendation: RecommendationResult = {
  project_id: 'p1',
  top_n: 3,
  candidate_count: 2,
  candidate_shortage: true,
  missing_requirements: [],
  requirement_versions: [],
  top3: [
    {
      base,
      score: 88,
      hard_failures: [],
      satisfied_items: ['档位数'],
      unsatisfied_items: [],
      missing_items: [],
      criteria: [
        {
          criterion: '档位数',
          requirement_value: '12',
          candidate_value: '12',
          weight: 0.5,
          score: 100,
          satisfied: true,
          hard_constraint: true,
          reason: '档位数一致（12 档）',
          source: 'REQ-P01-C-001 V1',
        },
      ],
    },
  ],
}

const variant: VariantAnalysisResult = {
  project_id: 'p1',
  base,
  variants: [
    {
      id: 'v1',
      project_id: 'p1',
      base_id: 'b1',
      display_code: 'V-01',
      parameter_key: 'gearCount',
      parameter_name: '档位数',
      base_value: '12 档',
      requirement_value: '16 档',
      variant_type: 'structural_change',
      affected_parts: ['壳体'],
      upstream_requirement_ids: ['r1'],
      basis: '基型 12 档，需求 16 档',
      status: 'current',
      created_at: '2026-10-19T00:00:00+00:00',
      updated_at: '2026-10-19T00:00:00+00:00',
    },
  ],
  stale_variants: [],
  stale_reusable_parts: [],
  reusable_parts: [
    {
      id: 'part1',
      project_id: 'p1',
      base_id: 'b1',
      variant_point_id: 'v1',
      part_display_code: 'P-100',
      part_name: '输入轴',
      part_number: 'SX-100',
      classification: 'carryover',
      reason: '扭矩等级满足',
      source: '基型 BOM',
      variant_keys: ['gearCount'],
      status: 'current',
      created_at: '2026-10-19T00:00:00+00:00',
      updated_at: '2026-10-19T00:00:00+00:00',
    },
  ],
  pending_items: [],
  requirement_versions: [],
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response
}

beforeEach(()=>vi.spyOn(api,'listPartChoices').mockResolvedValue({parts:[],counts:{unselected:0,pending_review:0,confirmed:0,rejected:0,recheck:0},mode:'rule',catalog_source:'合成候选'}))
afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('BasesPanel', () => {
  it('keeps analysis results in a dialog and reopens them without creating another revision', async () => {
    const fetcher = vi.fn(async (url: RequestInfo | URL) => jsonResponse(String(url).endsWith('/variant-analysis') ? variant : []))
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()
    const { rerender } = render(<BasesPanel projectId="p1" />)
    await user.type(screen.getByLabelText('变型分析基型编号'), 'JX-12A')
    const trigger = screen.getByRole('button', { name: '运行变型分析' })
    await user.click(trigger)
    const dialog = await screen.findByRole('dialog', { name: '变型分析结果' })
    expect(await within(dialog).findByText('结构变更')).toBeInTheDocument()
    expect(within(dialog).getByText('沿用')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: '关闭变型结果' }))
    expect(trigger).toHaveFocus()
    expect(screen.queryByText('结构变更')).not.toBeInTheDocument()
    const requests = fetcher.mock.calls.length
    await user.click(screen.getByRole('button', { name: '查看变型结果' }))
    expect(fetcher).toHaveBeenCalledTimes(requests)
    expect(screen.getByRole('dialog', { name: '变型分析结果' })).toBeInTheDocument()
    rerender(<BasesPanel projectId="p2" />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '查看变型结果' })).not.toBeInTheDocument()
  })
  it('keeps failed analysis inside the dialog and retries without changing the selected base', async () => {
    let attempts = 0
    vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL) => {
      if (!String(url).endsWith('/variant-analysis')) return jsonResponse([])
      return ++attempts === 1 ? jsonResponse({ error: { message: '变型分析暂不可用' } }, 503) : jsonResponse(variant)
    }))
    const user = userEvent.setup()
    render(<BasesPanel projectId="p1" />)
    await user.type(screen.getByLabelText('变型分析基型编号'), 'JX-12A')
    await user.click(screen.getByRole('button', { name: '运行变型分析' }))
    const dialog = await screen.findByRole('dialog', { name: '变型分析结果' })
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('变型分析暂不可用')
    await user.click(within(dialog).getByRole('button', { name: '重试变型分析' }))
    expect(await within(dialog).findByText('结构变更')).toBeInTheDocument()
    expect(screen.getByLabelText('变型分析基型编号')).toHaveValue('JX-12A')
    expect(attempts).toBe(2)
  })
  it('opens Top-3 in a dialog, reopens cached evidence, and selects a base without running analysis', async () => {
    const fetcher = vi.fn(async (url: RequestInfo | URL, _init?: RequestInit) => jsonResponse(String(url).endsWith('/engineering-records') ? [] : recommendation))
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()
    render(<BasesPanel projectId="p1" />)
    const trigger = screen.getByRole('button', { name: '计算 Top-3' })
    await user.click(trigger)
    const dialog = await screen.findByRole('dialog', { name: '型谱推荐结果' })
    expect(await within(dialog).findByText('得分 88.0')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: '关闭推荐结果' }))
    expect(trigger).toHaveFocus()
    const count = fetcher.mock.calls.length
    await user.click(screen.getByRole('button', { name: '查看推荐结果' }))
    expect(fetcher).toHaveBeenCalledTimes(count)
    await user.click(screen.getByRole('button', { name: '选用 JX-12A' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByLabelText('变型分析基型编号')).toHaveValue('JX-12A')
    expect(fetcher.mock.calls.some(([url]) => String(url).includes('variant-analysis'))).toBe(false)
  })
  it('shows a failed recommendation inside the dialog and retries explicitly', async () => {
    let attempts = 0
    vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL) => {
      if (String(url).endsWith('/engineering-records')) return jsonResponse([])
      return ++attempts === 1 ? jsonResponse({ error: { message: '选型计算暂不可用' } }, 503) : jsonResponse(recommendation)
    }))
    const user = userEvent.setup()
    render(<BasesPanel projectId="p1" />)
    await user.click(screen.getByRole('button', { name: '计算 Top-3' }))
    const dialog = await screen.findByRole('dialog', { name: '型谱推荐结果' })
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('选型计算暂不可用')
    await user.click(within(dialog).getByRole('button', { name: '重试计算推荐' }))
    expect(await within(dialog).findByText('得分 88.0')).toBeInTheDocument()
  })
  it('translates controlled scoring keys and enum values while retaining expandable scoring evidence', async () => {
    const data = { ...recommendation, top3: [{ ...recommendation.top3[0], hard_failures: ['topGearType'], criteria: [{ ...recommendation.top3[0].criteria[0], criterion: 'topGearType', requirement_value: 'text overdrive', candidate_value: 'direct', weight: 0.1 }] }] }
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(data)))
    const user = userEvent.setup()
    const { container } = render(<BasesPanel projectId="p1" />)
    await user.click(screen.getByRole('button', { name: '计算 Top-3' }))
    await user.click(await screen.findByText('查看评分依据'))
    expect(screen.getByText('最高档类型')).toBeVisible()
    expect(screen.getByText('超速档')).toBeVisible()
    expect(screen.getByText('直接档')).toBeVisible()
    expect(screen.getByText('10%')).toBeVisible()
    expect(container.textContent).not.toContain('topGearType')
    expect(container.textContent).not.toContain('text overdrive')
  })
  it('shows saved requirement versions as readable evidence and retains trace identifiers', async () => {
    const data = { ...recommendation, requirement_versions: [{ key: 'engineMaxTorque', requirement_id: 'stable-r1', display_code: 'REQ-P01-B-003', revision: 2, value: 2800, unit: 'N·m' }] }
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(data)))
    const user = userEvent.setup()
    const { container } = render(<BasesPanel projectId="p1" />)
    await user.click(screen.getByRole('button', { name: '计算 Top-3' }))
    const region = await screen.findByRole('group', { name: '选型输入依据' })
    await user.click(within(region).getByText(/查看选型输入依据/))
    expect(within(region).getByText('REQ-P01-B-003')).toBeVisible()
    expect(within(region).getByText('V2')).toBeVisible()
    expect(within(region).getByText('2800 N·m')).toBeVisible()
    expect(within(region).getByText('stable-r1')).toBeInTheDocument()
    expect(container.textContent).not.toContain('"requirement_id"')
  })
  it('shows scoring evidence and variant/reuse classifications', async () => {
    let variantBody: unknown
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (
          url === '/api/projects/p1/recommend-bases' &&
          init?.method === 'POST'
        ) {
          return jsonResponse(recommendation)
        }
        if (
          url === '/api/projects/p1/variant-analysis' &&
          init?.method === 'POST'
        ) {
          variantBody = JSON.parse(String(init.body))
          return jsonResponse(variant)
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<BasesPanel projectId="p1" />)

    await user.click(
      screen.getByRole('button', { name: '计算 Top-3' }),
    )
    expect(await screen.findByText(/得分 88.0/)).toBeInTheDocument()
    expect(screen.getByText('档位数一致（12 档）')).toBeInTheDocument()
    expect(
      screen.getByText(/候选不足，如实显示/),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '关闭推荐结果' }))

    await user.type(
      screen.getByRole('textbox', { name: '变型分析基型编号' }),
      'JX-12A',
    )
    await user.click(
      screen.getByRole('button', { name: '运行变型分析' }),
    )

    expect(
      (await screen.findAllByText(/变型点 1 个/)).length,
    ).toBeGreaterThan(0)
    expect(screen.getByText('结构变更')).toBeInTheDocument()
    expect(screen.getByText('沿用')).toBeInTheDocument()
    expect(variantBody).toEqual({ base_display_code: 'JX-12A' })
  })
})
