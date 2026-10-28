import { api } from './api'
import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { Project, ProjectOverview, Requirement } from './types'

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

const requirement: Requirement = {
  id: 'r1',
  project_id: 'p1',
  display_code: 'REQ-P01-B-003',
  category: 'B',
  parameter_name: '发动机最大扭矩',
  data_type: 'numeric',
  operator: '=',
  value_text: '2800',
  value_num: 2800,
  value_num_high: null,
  unit: 'N·m',
  raw_expression: '发动机最大扭矩 2800 N·m',
  source_document_id: 's1',
  source_location: '§3.1',
  source_excerpt: '发动机最大扭矩 2800 N·m',
  review_status: 'draft',
  validity: 'current',
  current_revision: 2,
  created_at: '2026-10-19T00:00:00+00:00',
  updated_at: '2026-10-19T00:00:00+00:00',
}

function overviewFor(source: Project): ProjectOverview {
  return {
    project: {
      id: source.id,
      display_code: source.display_code,
      name: source.name,
      customer: source.customer,
      product: source.product,
      stage: source.stage,
      updated_at: source.updated_at,
    },
    requirements: {
      total: 1,
      confirmed: 0,
      draft: 1,
      pending_review: 0,
      rejected: 0,
      stale: 0,
    },
    issues: {
      open: 0,
      closed: 0,
      open_by_severity: { blocking: 0, high: 0, medium: 0, low: 0 },
    },
    spectrum: {
      variant_points: 0,
      stale_variant_points: 0,
      reusable_parts: 0,
    },
    design_review: null,
    dfmea: null,
    traceability: null,
    samples: {
      delivery_count: 0,
      comparison_count: 0,
      latest_status: null,
      latest_result: null,
    },
    consistency: null,
    coordination: {
      topic_count: 0,
      record_count: 0,
      metrics_available: 0,
      highest_risk: 'insufficient',
      high_risk_topics: 0,
      rule_label: '协同响应规则 V1',
      source_label: '演示记录',
    },
    package: null,
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response
}

async function openRequirements() {
  const user = userEvent.setup()
  await user.click(
    await screen.findByRole('tab', { name: '需求清单' }),
  )
  return user
}

beforeEach(() => { vi.spyOn(api, 'getWorkspace').mockResolvedValue({ project_id: 'p1', stages: [], changes: [], scope_note: '合成测试' }) })

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('requirement workbench', () => {
  it('recovers from unavailable service through a visible retry without resetting project data', async () => {
    const projects = vi.spyOn(api, 'listProjects').mockRejectedValueOnce(new TypeError('Failed to fetch')).mockResolvedValueOnce([project])
    vi.spyOn(api, 'getProjectOverview').mockResolvedValue(overviewFor(project))
    const user = userEvent.setup()
    render(<App />)
    expect(await screen.findByText(/Start-Demo.cmd/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: '重试连接' }))
    expect(await screen.findByRole('heading', { name: project.name })).toBeVisible()
    expect(projects).toHaveBeenCalledTimes(2)
  })
  it('keeps the grouped sidebar in business order with materials after both cross-cutting engines', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse([project])).mockResolvedValueOnce(jsonResponse(overviewFor(project))))
    render(<App />)
    await screen.findByRole('heading', { name: project.name })
    expect(screen.getAllByRole('tab', { hidden: true }).map(tab => tab.textContent)).toEqual([
      '项目总览', '协议解析与澄清', '需求清单', '型谱选型与变型', '设计成果',
      '试验验证与追溯', '样件检验', '一致性检测', '协同风险', '评审材料', '系统设置',
    ])
  })
  it('shows the platform name and truck mark, and toggles groups without changing business state', async () => {
    vi.spyOn(api, 'listProjects').mockResolvedValue([project])
    vi.spyOn(api, 'getProjectOverview').mockResolvedValue(overviewFor(project))
    vi.spyOn(api, 'listRequirements').mockResolvedValue([requirement])
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: project.name })
    expect(screen.getByText('复杂高端装备智能定制与自主验证平台')).toBeVisible()
    const masthead = screen.getByRole('banner', { name: '平台品牌栏' })
    expect(within(masthead).getByText('复杂高端装备智能定制与自主验证平台')).toBeVisible()
    expect(within(masthead).getByText('智研引擎')).toBeVisible()
    expect(screen.getByRole('heading', { name: '项目总览' }).closest('header')).not.toHaveTextContent('复杂高端装备智能定制与自主验证平台')
    expect(screen.getByRole('img', { name: '重型商用车示意' })).toBeVisible()
    expect(screen.getByRole('img', { name: '重型商用车示意' }).tagName).toBe('IMG')
    const requirementsGroup = screen.getByRole('button', { name: '需求解析智能体' })
    const designGroup = screen.getByRole('button', { name: '变型设计智能体' })
    expect(requirementsGroup).toHaveAttribute('aria-expanded', 'true')
    expect(designGroup).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('tab', { name: '设计成果' })).not.toBeInTheDocument()
    await user.click(designGroup)
    expect(designGroup).toHaveAttribute('aria-expanded', 'true')
    expect(requirementsGroup).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByRole('tab', { name: '设计成果' })).toBeVisible()
    expect(screen.getByRole('heading', { name: project.name })).toBeVisible()
    designGroup.focus()
    await user.keyboard('{Enter}')
    expect(designGroup).toHaveAttribute('aria-expanded', 'false')
    await user.click(requirementsGroup)
    await user.click(screen.getByRole('tab', { name: '需求清单' }))
    expect(await screen.findByText('REQ-P01-B-003')).toBeVisible()
    expect(screen.getAllByText('复杂高端装备智能定制与自主验证平台')).toHaveLength(1)
    expect(screen.getByRole('heading', { name: '需求清单' }).closest('header')).not.toHaveTextContent('复杂高端装备智能定制与自主验证平台')
  })
  it('expands the destination group when a dashboard action navigates into a collapsed module', async () => {
    vi.spyOn(api, 'listProjects').mockResolvedValue([project])
    vi.spyOn(api, 'getProjectOverview').mockResolvedValue(overviewFor(project))
    vi.spyOn(api, 'listRequirements').mockResolvedValue([requirement])
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: project.name })
    const group = screen.getByRole('button', { name: '需求解析智能体' })
    await user.click(group)
    expect(group).toHaveAttribute('aria-expanded', 'false')
    await user.click(screen.getByRole('button', { name: '查看需求清单' }))
    expect(group).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('tab', { name: '需求清单' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByText('REQ-P01-B-003')).toBeVisible()
  })
  it('opens the single showcase project without exposing a project selector', async () => {
    const practice = { ...project, id: 'practice-id', display_code: 'P02', name: '现场演练项目' }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse([practice, project]))
      .mockResolvedValueOnce(jsonResponse(overviewFor(project)))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    expect(await screen.findByRole('heading', { name: project.name })).toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: '选择项目' })).not.toBeInTheDocument()
    expect(screen.queryByText('现场演练项目')).not.toBeInTheDocument()
    expect(screen.queryByText('项目编号：P01')).not.toBeInTheDocument()
    expect(screen.queryByText('P01 · 演示数据')).not.toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '需求清单' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual(['/api/projects', '/api/projects/p1/overview'])
  })
  it('loads the overview first, then the selected project requirements', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([project]))
      .mockResolvedValueOnce(jsonResponse(overviewFor(project)))
      .mockResolvedValueOnce(jsonResponse([requirement]))
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)

    expect(
      await screen.findByRole('heading', { name: project.name }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', {
        name: '项目总览',
      }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: '选择项目' })).not.toBeInTheDocument()

    await openRequirements()

    expect(await screen.findByText('REQ-P01-B-003')).toBeInTheDocument()
    expect(screen.getByText('发动机最大扭矩')).toBeInTheDocument()
    expect(screen.getByText('V2')).toBeInTheDocument()
    expect(screen.getByText('草案')).toBeInTheDocument()
    expect(screen.getByText('§3.1')).toBeInTheDocument()
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      '/api/projects',
      '/api/projects/p1/overview',
      '/api/projects/p1/requirements',
    ])
  })

  it('shows an empty state when no projects exist', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce(jsonResponse([])),
    )

    render(<App />)

    expect(
      await screen.findByText('尚未初始化演示项目，请先准备演示数据。'),
    ).toBeInTheDocument()
  })

  it('shows an empty requirement state for a project without requirements', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([project]))
      .mockResolvedValueOnce(jsonResponse(overviewFor(project)))
      .mockResolvedValueOnce(jsonResponse([]))
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)

    await openRequirements()

    expect(await screen.findByText('暂无需求。')).toBeInTheDocument()
  })

  it('shows an explicit missing source marker when source location is empty', async () => {
    const requirementWithoutSource: Requirement = {
      ...requirement,
      source_location: '',
      source_excerpt: '',
    }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([project]))
      .mockResolvedValueOnce(jsonResponse(overviewFor(project)))
      .mockResolvedValueOnce(jsonResponse([requirementWithoutSource]))
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)

    await openRequirements()

    expect(await screen.findByText('未记录')).toBeInTheDocument()
  })

  it('shows a fallback error message when the server returns no error body', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce(jsonResponse({}, 500)),
    )

    render(<App />)

    expect(
      await screen.findByText('请求失败（HTTP 500）'),
    ).toBeInTheDocument()
  })

  it('shows the network error message when the projects request fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValueOnce(new TypeError('Failed to fetch')),
    )

    render(<App />)

    expect(await screen.findByText('Failed to fetch')).toBeInTheDocument()
  })

  it('shows an error when requirements fail to load', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([project]))
      .mockResolvedValueOnce(jsonResponse(overviewFor(project)))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: 'PERSISTENCE_ERROR',
              message: '读取需求失败',
            },
          },
          500,
        ),
      )
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)

    await openRequirements()

    expect(await screen.findByText('读取需求失败')).toBeInTheDocument()
  })

  it('never falls back to the practice project when the showcase project is missing', async () => {
    const practice = { ...project, id: 'practice-id', display_code: 'P02', name: '现场演练项目' }
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse([practice]))
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    expect(await screen.findByText('尚未初始化演示项目，请先准备演示数据。')).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: '需求清单' })).not.toBeInTheDocument()
    expect(screen.queryByText('现场演练项目')).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('shows a generic error when confirmation fails for a non-version reason', async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url === '/api/projects') {
          return jsonResponse([project])
        }
        if (url === '/api/projects/p1/overview') {
          return jsonResponse(overviewFor(project))
        }
        if (url === '/api/projects/p1/requirements') {
          return jsonResponse([requirement])
        }
        if (url === '/api/requirements/r1/confirmations') {
          return jsonResponse(
            {
              error: {
                code: 'PERSISTENCE_ERROR',
                message: '保存确认失败',
              },
            },
            500,
          )
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)

    const user = await openRequirements()
    await screen.findByText('REQ-P01-B-003')
    await user.click(
      screen.getByRole('button', { name: '确认 REQ-P01-B-003' }),
    )

    expect(await screen.findByText('保存确认失败')).toBeInTheDocument()
  })

  it('shows a loading state while projects are loading', async () => {
    let resolveProjects!: (value: Response) => void
    const projectsPromise = new Promise<Response>((resolve) => {
      resolveProjects = resolve
    })
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(projectsPromise)
      .mockResolvedValueOnce(jsonResponse(overviewFor(project)))
      .mockResolvedValueOnce(jsonResponse([requirement]))
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)

    expect(screen.getByText('正在加载项目…')).toBeInTheDocument()

    await act(async () => {
      resolveProjects(jsonResponse([project]))
    })

    expect(
      await screen.findByRole('heading', { name: project.name }),
    ).toBeInTheDocument()

    await openRequirements()

    expect(await screen.findByText('REQ-P01-B-003')).toBeInTheDocument()
  })

  it('confirms a requirement with its current revision and refreshes the status', async () => {
    let requirements: Requirement[] = [requirement]
    let confirmationMethod: string | undefined
    let confirmationBody: unknown

    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url === '/api/projects') {
          return jsonResponse([project])
        }
        if (url === '/api/projects/p1/overview') {
          return jsonResponse(overviewFor(project))
        }
        if (url === '/api/projects/p1/requirements') {
          return jsonResponse(requirements)
        }
        if (url === '/api/requirements/r1/confirmations') {
          confirmationMethod = init?.method
          confirmationBody = JSON.parse(String(init?.body))
          requirements = [{ ...requirement, review_status: 'confirmed' }]
          return jsonResponse(
            { id: 'audit-1', action: 'requirement.confirmed' },
            201,
          )
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)

    const user = await openRequirements()
    await screen.findByText('REQ-P01-B-003')
    await user.click(
      screen.getByRole('button', { name: '确认 REQ-P01-B-003' }),
    )

    expect(await screen.findByRole('button', {name:'已确认 1 条'})).toBeInTheDocument()
    expect(confirmationMethod).toBe('POST')
    expect(confirmationBody).toMatchObject({
      expected_revision: 2,
      actor: '演示工程师',
      role: 'design_engineer',
      decision: 'confirmed',
    })
  })

  it('rejects a requirement and shows the rejected status', async () => {
    let requirements: Requirement[] = [requirement]
    let confirmationBody: unknown

    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url === '/api/projects') {
          return jsonResponse([project])
        }
        if (url === '/api/projects/p1/overview') {
          return jsonResponse(overviewFor(project))
        }
        if (url === '/api/projects/p1/requirements') {
          return jsonResponse(requirements)
        }
        if (url === '/api/requirements/r1/confirmations') {
          confirmationBody = JSON.parse(String(init?.body))
          requirements = [{ ...requirement, review_status: 'rejected' }]
          return jsonResponse(
            { id: 'audit-2', action: 'requirement.rejected' },
            201,
          )
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)

    const user = await openRequirements()
    await screen.findByText('REQ-P01-B-003')
    await user.click(
      screen.getByRole('button', { name: '驳回 REQ-P01-B-003' }),
    )
    await user.type(await screen.findByRole('textbox', { name: '驳回原因' }), '原文依据不足，请补充来源')
    await user.click(screen.getByRole('button', { name: '提交驳回' }))
    expect(await screen.findByText(/已驳回 REQ-P01-B-003/)).toBeInTheDocument()
    expect(confirmationBody).toMatchObject({
      expected_revision: 2,
      decision: 'rejected',
      comment: '原文依据不足，请补充来源',
    })
  })

  it('shows a version conflict message and keeps the requirement unchanged', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url === '/api/projects') {
        return jsonResponse([project])
      }
      if (url === '/api/projects/p1/overview') {
        return jsonResponse(overviewFor(project))
      }
      if (url === '/api/projects/p1/requirements') {
        return jsonResponse([requirement])
      }
      if (url === '/api/requirements/r1/confirmations') {
        return jsonResponse(
          {
            error: {
              code: 'VERSION_CONFLICT',
              message: '需求已被更新，请刷新后重试',
              details: { current_revision: 3 },
            },
          },
          409,
        )
      }
      return jsonResponse({}, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)

    const user = await openRequirements()
    await screen.findByText('REQ-P01-B-003')
    await user.click(
      screen.getByRole('button', { name: '确认 REQ-P01-B-003' }),
    )

    expect(await screen.findByText(/版本冲突/)).toBeInTheDocument()
    expect(screen.getByText('草案')).toBeInTheDocument()
  })

  it('lazily loads only the active tab and reloads requirements when switching back', async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url === '/api/projects') {
          return jsonResponse([project])
        }
        if (url === '/api/projects/p1/overview') {
          return jsonResponse(overviewFor(project))
        }
        if (url === '/api/projects/p1/requirements') {
          return jsonResponse([requirement])
        }
        if (url === '/api/projects/p1/issues' || url === '/api/projects/p1/source-documents') {
          return jsonResponse([])
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<App />)

    await screen.findByRole('heading', { name: project.name })
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      '/api/projects',
      '/api/projects/p1/overview',
    ])

    await user.click(screen.getByRole('tab', { name: '需求清单' }))
    await screen.findByText('REQ-P01-B-003')
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      '/api/projects',
      '/api/projects/p1/overview',
      '/api/projects/p1/requirements',
    ])

    await user.click(
      screen.getByRole('tab', { name: '协议解析与澄清' }),
    )
    expect(await screen.findByText('暂无问题记录。')).toBeInTheDocument()
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      '/api/projects',
      '/api/projects/p1/overview',
      '/api/projects/p1/requirements',
      '/api/projects/p1/document-imports',
      '/api/projects/p1/source-documents',
      '/api/projects/p1/issues',
    ])

    await user.click(screen.getByRole('tab', { name: '需求清单' }))
    expect(await screen.findByText('REQ-P01-B-003')).toBeInTheDocument()
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      '/api/projects',
      '/api/projects/p1/overview',
      '/api/projects/p1/requirements',
      '/api/projects/p1/document-imports',
      '/api/projects/p1/source-documents',
      '/api/projects/p1/issues',
      '/api/projects/p1/requirements',
    ])
  })
})
