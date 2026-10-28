import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AuditEvent, Project, Requirement } from '../types'
import { api } from '../api'
import { RequirementsPanel } from './RequirementsPanel'

const project: Project = {
  id: 'p1',
  display_code: 'P01',
  name: '演示项目',
  customer: '客户',
  product: '变速器',
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
  value_text: '2600',
  value_num: 2600,
  value_num_high: null,
  unit: 'N·m',
  raw_expression: '发动机最大扭矩 2600 N·m',
  source_document_id: 's1',
  source_location: '§3.1',
  source_excerpt: '发动机最大扭矩 2600 N·m',
  review_status: 'draft',
  validity: 'current',
  current_revision: 1,
  created_at: '2026-10-19T00:00:00+00:00',
  updated_at: '2026-10-19T00:00:00+00:00',
}

const audit: AuditEvent = {
  id: 'audit-r1', project_id: 'p1', object_type: 'requirement', object_id: 'r1', object_revision: 1,
  action: 'requirement.confirmed', actor: '工程师甲', role: 'design_engineer', decision: 'confirmed',
  comment: '已核对协议原文', before: null, after: null, created_at: '2026-10-22T07:00:00+00:00',
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
  vi.restoreAllMocks()
})

describe('RequirementsPanel', () => {
  it('starts with the pending queue, counts all review groups and moves a confirmed item without deleting it', async () => {
    let rows: Requirement[] = [requirement, { ...requirement, id: 'r2', display_code: 'REQ-2', review_status: 'pending_review' }, { ...requirement, id: 'r3', display_code: 'REQ-3', review_status: 'rejected' }]
    vi.spyOn(api, 'listRequirements').mockImplementation(async () => structuredClone(rows))
    const save = vi.spyOn(api, 'confirmRequirement').mockImplementation(async (_id, payload) => {
      rows = rows.map(row => row.id === 'r1' ? { ...row, review_status: payload.decision } : row)
      return audit
    })
    const user = userEvent.setup()
    render(<RequirementsPanel project={project} />)
    expect(await screen.findByRole('button', { name: '待审核 2 条' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByText('REQ-3', { selector: 'td' })).not.toBeInTheDocument()
    await user.click(screen.getByLabelText('确认 REQ-P01-B-003'))
    expect(await screen.findByText(/已确认 REQ-P01-B-003.*已确认列表/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '待审核 1 条' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByText(requirement.display_code, { selector: 'td' })).not.toBeInTheDocument()
    expect(save).toHaveBeenCalledWith('r1', expect.objectContaining({ expected_revision: 1, decision: 'confirmed' }))
    await user.click(screen.getByRole('button', { name: '已确认 1 条' }))
    expect(screen.getByText(requirement.display_code, { selector: 'td' })).toBeInTheDocument()
    expect(screen.queryByLabelText('确认 REQ-P01-B-003')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('驳回 REQ-P01-B-003')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '查看 REQ-P01-B-003 审核记录' })).toBeInTheDocument()
    await user.click(screen.getByLabelText('修订 REQ-P01-B-003'))
    expect(within(screen.getByRole('dialog', {name:'修订需求'})).queryByText(/已确认 REQ-P01-B-003/)).not.toBeInTheDocument()
    await user.click(within(screen.getByRole('dialog')).getByRole('button', {name:'关闭详情'}))
    await user.click(screen.getByRole('button', { name: '全部需求 3 条' }))
    expect(screen.getAllByRole('row')).toHaveLength(4)
  })

  it('preserves an optional rejection reason after save failure and records it when the retry succeeds', async () => {
    let current = requirement
    vi.spyOn(api, 'listRequirements').mockImplementation(async () => [current])
    const save = vi.spyOn(api, 'confirmRequirement').mockRejectedValueOnce(new Error('审核服务暂不可用')).mockImplementation(async (_id, payload) => {
      current = { ...requirement, review_status: 'rejected' }
      return { ...audit, decision: payload.decision, comment: payload.comment }
    })
    const user = userEvent.setup()
    render(<RequirementsPanel project={project} />)
    const trigger = await screen.findByLabelText('驳回 REQ-P01-B-003')
    await user.click(trigger)
    let dialog = screen.getByRole('dialog', { name: '驳回需求' })
    await user.clear(within(dialog).getByLabelText('驳回原因'))
    await user.type(within(dialog).getByLabelText('驳回原因'), '协议数值冲突，请澄清后重新提交')
    await user.click(within(dialog).getByRole('button', { name: '提交驳回' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('审核服务暂不可用')
    expect(within(dialog).getByLabelText('驳回原因')).toHaveValue('协议数值冲突，请澄清后重新提交')
    await user.click(within(dialog).getByRole('button', { name: '关闭详情' }))
    expect(trigger).toHaveFocus()
    await user.click(trigger)
    dialog = screen.getByRole('dialog', { name: '驳回需求' })
    expect(within(dialog).getByLabelText('驳回原因')).toHaveValue('协议数值冲突，请澄清后重新提交')
    await user.click(within(dialog).getByRole('button', { name: '提交驳回' }))
    expect(await screen.findByText(/已驳回 REQ-P01-B-003.*待修订/)).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(save).toHaveBeenLastCalledWith('r1', expect.objectContaining({ expected_revision: 1, decision: 'rejected', comment: '协议数值冲突，请澄清后重新提交' }))
    await user.click(screen.getByRole('button', { name: '已驳回 1 条' }))
    await user.click(screen.getByLabelText('修订 REQ-P01-B-003'))
    expect(screen.getByLabelText('选择要修订的需求')).toHaveValue('r1')
    expect(screen.getByLabelText('修订后的数值')).toHaveFocus()
  })

  it('keeps a failed or version-conflicting decision in the pending queue', async () => {
    vi.spyOn(api, 'listRequirements').mockResolvedValue([requirement])
    vi.spyOn(api, 'confirmRequirement').mockRejectedValue(new Error('版本冲突：需求已被更新'))
    const user = userEvent.setup()
    render(<RequirementsPanel project={project} />)
    await user.click(await screen.findByLabelText('确认 REQ-P01-B-003'))
    expect(await screen.findByRole('alert')).toHaveTextContent('版本冲突')
    expect(screen.getByText(requirement.display_code, { selector: 'td' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '待审核 1 条' })).toBeInTheDocument()
    expect(screen.getByLabelText('确认 REQ-P01-B-003')).toBeEnabled()
    expect(screen.getByLabelText('驳回 REQ-P01-B-003')).toBeEnabled()
  })

  it('distinguishes a saved decision from a failed refresh and only retries the read', async () => {
    const load = vi.spyOn(api, 'listRequirements').mockResolvedValueOnce([requirement]).mockRejectedValueOnce(new Error('列表暂不可读')).mockResolvedValue([{ ...requirement, review_status: 'confirmed' }])
    const save = vi.spyOn(api, 'confirmRequirement').mockResolvedValue(audit)
    const user = userEvent.setup()
    render(<RequirementsPanel project={project} />)
    await user.click(await screen.findByLabelText('确认 REQ-P01-B-003'))
    expect(await screen.findByRole('alert')).toHaveTextContent('审核已保存，但列表刷新失败')
    expect(screen.getByLabelText('确认 REQ-P01-B-003')).toBeDisabled()
    expect(screen.queryByText(/已移至已确认列表/)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '重新读取需求列表' }))
    expect(await screen.findByRole('button', { name: '已确认 1 条' })).toBeInTheDocument()
    expect(save).toHaveBeenCalledTimes(1)
    expect(load).toHaveBeenCalledTimes(3)
  })

  it('returns a revised rejected requirement to pending only after the backend creates a draft revision', async () => {
    let current: Requirement = { ...requirement, review_status: 'rejected' }
    vi.spyOn(api, 'listRequirements').mockImplementation(async () => [current])
    vi.spyOn(api, 'updateRequirement').mockImplementation(async (_id, payload) => {
      if (payload.value_text === '2800') current = { ...current, value_text: '2800', current_revision: 2, review_status: 'draft' }
      return current
    })
    const user = userEvent.setup()
    render(<RequirementsPanel project={project} />)
    await user.click(await screen.findByRole('button', { name: '已驳回 1 条' }))
    await user.click(screen.getByLabelText('修订 REQ-P01-B-003'))
    await user.click(screen.getByRole('button', { name: '提交修订' }))
    expect(await screen.findByText(/未发生实质变化.*已驳回/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '待审核 0 条' })).toBeInTheDocument()
    await user.clear(screen.getByLabelText('修订后的数值'))
    await user.type(screen.getByLabelText('修订后的数值'), '2800')
    await user.click(screen.getByRole('button', { name: '提交修订' }))
    expect(await screen.findByText(/已更新为 V2.*待审核/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '待审核 1 条' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('V2', { selector: 'td' })).toBeInTheDocument()
    expect(screen.getByLabelText('确认 REQ-P01-B-003')).toBeEnabled()
  })

  it('retains read-only audit history across revisions and retries history failures without writing', async () => {
    vi.spyOn(api, 'listRequirements').mockResolvedValue([{ ...requirement, review_status: 'confirmed', current_revision: 2 }])
    let reads = 0
    const fetchMock = vi.fn(async () => {
      if (++reads === 1) throw new Error('审核记录暂不可用')
      return jsonResponse([{ ...audit, decision: 'rejected', action: 'requirement.rejected', comment: '旧版单位需要澄清' }, { ...audit, id: 'audit-r2', object_revision: 2 }])
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<RequirementsPanel project={project} />)
    await user.click(await screen.findByRole('button', { name: '已确认 1 条' }))
    const trigger = screen.getByRole('button', { name: '查看 REQ-P01-B-003 审核记录' })
    await user.click(trigger)
    const drawer = screen.getByRole('dialog', { name: '需求审核记录' })
    expect(await within(drawer).findByRole('alert')).toHaveTextContent('审核记录暂不可用')
    await user.click(within(drawer).getByRole('button', { name: '重试读取审核记录' }))
    expect(await within(drawer).findByText('旧版单位需要澄清')).toBeInTheDocument()
    expect(within(drawer).getByText('已核对协议原文')).toBeInTheDocument()
    expect(within(drawer).getByText(/V1.*历史版本/)).toBeInTheDocument()
    expect(within(drawer).getByText(/V2.*当前版本/)).toBeInTheDocument()
    expect(fetchMock.mock.calls).toHaveLength(2)
    await user.click(within(drawer).getByRole('button', { name: '关闭详情' }))
    expect(trigger).toHaveFocus()
  })

  it('reveals a linked confirmed requirement despite the default pending view', async () => {
    vi.spyOn(api, 'listRequirements').mockResolvedValue([{ ...requirement, review_status: 'confirmed' }])
    render(<RequirementsPanel project={project} focusRequirementId="r1" />)
    expect(await screen.findByText(requirement.display_code, { selector: 'td' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '全部需求 1 条' })).toHaveAttribute('aria-pressed', 'true')
  })
  it('opens source and version evidence in a drawer and returns to the filtered list', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/revisions')) return jsonResponse([1, 2].map(revision_no => ({ revision_no, snapshot: { ...requirement, value_text: revision_no === 1 ? '2600' : '2800' } })))
      if (url.endsWith('/source-documents')) return jsonResponse([{ id: 's1', display_code: 'DOC-01', version: 'V1', original_text: '协议正文', original_file: null }])
      return jsonResponse([requirement])
    }))
    const user = userEvent.setup()
    const { container } = render(<RequirementsPanel project={project} />)
    await user.type(await screen.findByLabelText('搜索需求'), '发动机')
    const trigger = await screen.findByRole('button', { name: '查看 REQ-P01-B-003 来源与版本' })
    await user.click(trigger)
    const drawer = await screen.findByRole('dialog', { name: '需求来源与版本对比' })
    expect(drawer).toHaveClass('detail-overlay--drawer')
    expect(await within(drawer).findByText('DOC-01 · V1')).toBeInTheDocument()
    expect(within(drawer).getByLabelText('对比前版本')).toHaveValue('1')
    expect(within(drawer).getByLabelText('对比后版本')).toHaveValue('2')
    expect(container.querySelector('.evidence-inspector')).toBeNull()
    await user.click(within(drawer).getByRole('button', { name: '关闭详情' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByLabelText('搜索需求')).toHaveValue('发动机')
    expect(trigger).toHaveFocus()
  })
  it('retries a failed source lookup within the drawer without writing data', async () => {
    let attempts = 0
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/revisions')) {
        if (++attempts === 1) throw new Error('版本证据暂不可用')
        return jsonResponse([{ revision_no: 1, snapshot: requirement }])
      }
      if (url.endsWith('/source-documents')) return jsonResponse([])
      return jsonResponse([requirement])
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<RequirementsPanel project={project} />)
    await user.click(await screen.findByRole('button', { name: '查看 REQ-P01-B-003 来源与版本' }))
    const drawer = await screen.findByRole('dialog', { name: '需求来源与版本对比' })
    expect(await within(drawer).findByRole('alert')).toHaveTextContent('版本证据暂不可用')
    await user.click(within(drawer).getByRole('button', { name: '重试读取证据' }))
    expect(await within(drawer).findByLabelText('对比前版本')).toHaveValue('1')
    expect(fetchMock.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true)
  })
  it('isolates unsaved edits when the project identity changes', async () => {
    const second = { ...requirement, id: 'r2', project_id: 'p2', display_code: 'REQ-P02-C-001', parameter_name: '档位数', value_text: '12', value_num: 12, unit: '档' }
    vi.stubGlobal('fetch', vi.fn(async (url: string) => jsonResponse(url.includes('/p2/') ? [second] : [requirement])))
    const user = userEvent.setup()
    const { rerender } = render(<RequirementsPanel project={project} />)
    await screen.findByText('REQ-P01-B-003')
    await user.click(screen.getByLabelText('修订 REQ-P01-B-003'))
    await user.clear(screen.getByLabelText('修订后的数值'))
    await user.type(screen.getByLabelText('修订后的数值'), '2800')
    await user.type(screen.getByLabelText('修订来源说明'), '只属于原项目的修订依据')
    rerender(<RequirementsPanel project={{ ...project, id: 'p2', display_code: 'P02' }} />)
    await screen.findByText('REQ-P02-C-001')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(screen.getByLabelText('修订 REQ-P02-C-001'))
    expect(screen.getByLabelText('修订后的数值')).toHaveValue('12')
    expect(screen.getByLabelText('修订来源说明')).toHaveValue('')
    expect(screen.queryByText('REQ-P01-B-003')).not.toBeInTheDocument()
  })
  it('keeps an unsaved revision draft when an independent review refreshes the list', async () => {
    let current = requirement
    vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') current = { ...requirement, review_status: 'confirmed' }
      return jsonResponse([structuredClone(current)])
    }))
    const user = userEvent.setup()
    render(<RequirementsPanel project={project} />)
    await user.click(await screen.findByLabelText('修订 REQ-P01-B-003'))
    const input = screen.getByLabelText('修订后的数值')
    await waitFor(() => expect(input).toHaveValue('2600'))
    await user.clear(input); await user.type(input, '2800')
    await user.click(screen.getByRole('button', {name:'关闭详情'}))
    await user.click(screen.getByLabelText('确认 REQ-P01-B-003'))
    await screen.findByText(/已确认 REQ-P01-B-003.*已确认列表/)
    await user.click(screen.getByRole('button', {name:'已确认 1 条'}))
    await user.click(screen.getByLabelText('修订 REQ-P01-B-003'))
    expect(screen.getByLabelText('修订后的数值')).toHaveValue('2800')
  })
  it('filters the visible list without changing totals and opens source/version evidence', async () => {
    const second = { ...requirement, id: 'r2', display_code: 'REQ-P01-C-001', parameter_name: '档位数', source_excerpt: '档位数 12 档', review_status: 'confirmed' }
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/revisions')) return jsonResponse([{ revision_no: 1, snapshot: { value_text: '2600', unit: 'N·m' }, source_location: '3.1', source_excerpt: '发动机最大扭矩 2600 N·m' }])
      if (url.endsWith('/source-documents')) return jsonResponse([{ id: 's1', display_code: 'DOC-01', version: 'V1', original_text: '协议正文', original_file: null }])
      return jsonResponse([requirement, second])
    }))
    const user = userEvent.setup()
    render(<RequirementsPanel project={project} />)
    await screen.findByText('REQ-P01-B-003')
    await user.type(screen.getByLabelText('搜索需求'), '发动机')
    expect(screen.queryByText('REQ-P01-C-001', { selector: 'td' })).not.toBeInTheDocument()
    expect(screen.getByText('显示 1 / 2 条')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '已确认 1 条' }))
    expect(screen.getByText('没有符合筛选条件的需求。')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '全部需求 2 条' }))
    await user.click(screen.getByRole('button', { name: '查看 REQ-P01-B-003 来源与版本' }))
    expect(await screen.findByText('DOC-01 · V1')).toBeInTheDocument()
    expect(screen.getByText('仅留存正文，未归档原件')).toBeInTheDocument()
  })
  it('updates a requirement with expected revision and refreshes validity', async () => {
    let current: Requirement = requirement
    let patchBody: unknown
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url === '/api/projects/p1/requirements' && !init?.method) {
          return jsonResponse([current])
        }
        if (
          url === '/api/requirements/r1' &&
          init?.method === 'PATCH'
        ) {
          patchBody = JSON.parse(String(init.body))
          current = {
            ...requirement,
            value_text: '2800',
            current_revision: 2,
            validity: 'current',
          }
          return jsonResponse(current)
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<RequirementsPanel project={project} />)

    await screen.findByText('发动机最大扭矩')
    await user.click(screen.getByLabelText('修订 REQ-P01-B-003'))
    const input = screen.getByRole('textbox', {
      name: '修订后的数值',
    })
    // Wait for the load effect to seed the form before editing; otherwise
    // the effect can overwrite the typed value and submit the old revision.
    await waitFor(() => expect(input).toHaveValue('2600'))
    fireEvent.change(input, { target: { value: '2800' } })
    expect(input).toHaveValue('2800')
    const sourceInput = screen.getByRole('textbox', {
      name: '修订来源说明',
    })
    fireEvent.change(sourceInput, {
      target: { value: '合成变更记录 CN-01' },
    })
    expect(sourceInput).toHaveValue('合成变更记录 CN-01')
    await user.click(screen.getByRole('button', { name: '提交修订' }))

    expect(
      await screen.findByText(/已更新为 V2/),
    ).toBeInTheDocument()
    expect(patchBody).toMatchObject({
      expected_revision: 1,
      value_text: '2800',
      source_excerpt: '合成变更记录 CN-01',
    })
  })

  it('shows a version conflict and keeps the row unchanged', async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url === '/api/projects/p1/requirements' && !init?.method) {
          return jsonResponse([requirement])
        }
        if (url === '/api/requirements/r1' && init?.method === 'PATCH') {
          return jsonResponse(
            {
              error: {
                code: 'VERSION_CONFLICT',
                message: '需求已被更新',
              },
            },
            409,
          )
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<RequirementsPanel project={project} />)

    await screen.findByText('发动机最大扭矩')
    await user.click(screen.getByLabelText('修订 REQ-P01-B-003'))
    const input = screen.getByRole('textbox', {
      name: '修订后的数值',
    })
    fireEvent.change(input, { target: { value: '2800' } })
    await user.click(screen.getByRole('button', { name: '提交修订' }))

    expect(await screen.findByText(/版本冲突：需求已被更新/)).toBeInTheDocument()
    expect(screen.getByText('V1')).toBeInTheDocument()
  })
})

it('rejects a pending requirement with an empty optional reason',async()=>{
 vi.spyOn(api,'listRequirements').mockResolvedValue([requirement])
 const save=vi.spyOn(api,'confirmRequirement').mockResolvedValue(audit)
 const user=userEvent.setup();render(<RequirementsPanel project={project}/>)
 await user.click(await screen.findByLabelText('驳回 REQ-P01-B-003'))
 await user.click(within(screen.getByRole('dialog',{name:'驳回需求'})).getByRole('button',{name:'提交驳回'}))
 expect(save).toHaveBeenCalledWith('r1',expect.objectContaining({decision:'rejected',comment:''}))
})
