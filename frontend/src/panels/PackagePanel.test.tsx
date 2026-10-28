import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type {
  MaterialPackageDetail,
  PackageGate,
} from '../types'
import { PackagePanel } from './PackagePanel'

const draftGate: PackageGate = {
  status: 'blocked',
  ready: false,
  checks: [
    {
      key: 'consistency_cleared',
      label: '一致性检查已确认且无未关闭阻断冲突',
      status: 'fail',
      summary: '',
      failures: [
        {
          code: 'BLOCKING_CONFLICT_OPEN',
          message: '阻断冲突 CF-P01-001 尚未关闭',
          check: 'consistency_cleared',
        },
      ],
    },
  ],
  blockers: [
    {
      code: 'BLOCKING_CONFLICT_OPEN',
      message: '阻断冲突 CF-P01-001 尚未关闭',
      check: 'consistency_cleared',
    },
  ],
  warnings: [],
  summary: {
    check_count: 1,
    passed_check_count: 0,
    not_applicable_check_count: 0,
    blocker_count: 1,
    warning_count: 0,
  },
}

const readyGate: PackageGate = {
  ...draftGate,
  status: 'ready',
  ready: true,
  checks: [
    {
      key: 'consistency_cleared',
      label: '一致性检查已确认且无未关闭阻断冲突',
      status: 'pass',
      summary: '',
      failures: [],
    },
  ],
  blockers: [],
  summary: {
    check_count: 1,
    passed_check_count: 1,
    not_applicable_check_count: 0,
    blocker_count: 0,
    warning_count: 0,
  },
}

function makePackage(
  status: MaterialPackageDetail['status'],
  gate: PackageGate,
): MaterialPackageDetail {
  return {
    id: 'pkg1',
    project_id: 'p1',
    display_code: 'MP-P01-001',
    package_no: 1,
    status,
    mode: 'rule',
    include_originals: false,
    snapshot_hash: 'a'.repeat(64),
    zip_sha256: 'b'.repeat(64),
    zip_size: 1024,
    created_by: '演示工程师',
    created_at: '2026-10-19T00:00:00+00:00',
    frozen_at: status === 'human_approved' ? '2026-10-19T01:00:00+00:00' : null,
    gate,
    snapshot: {},
    manifest: { files: [] },
    approval: null,
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response
}

function zipResponse(): Response {
  return {
    ok: true,
    status: 200,
    headers: {
      get: (name: string) => {
        if (name === 'content-disposition') {
          return "attachment; filename*=UTF-8''MP-P01-001.zip"
        }
        if (name === 'x-content-sha256') return 'b'.repeat(64)
        return null
      },
    },
    blob: async () => new Blob(['zip-content']),
  } as unknown as Response
}

beforeEach(() => {
  Object.defineProperty(URL, 'createObjectURL', {
    value: vi.fn(() => 'blob:demo'),
    configurable: true,
  })
  Object.defineProperty(URL, 'revokeObjectURL', {
    value: vi.fn(),
    configurable: true,
  })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('PackagePanel', () => {
  it('keeps a generated package after refresh fails and retries reads without another generation', async () => {
    let saved = false
    let refreshFails = true
    const draft = makePackage('draft', draftGate)
    const fetcher = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') { saved = true; return jsonResponse(draft, 201) }
      if (saved && refreshFails) return jsonResponse({ error: { message: '刷新暂不可用' } }, 503)
      return jsonResponse(String(url).endsWith('/material-packages') ? (saved ? [draft] : []) : draft)
    })
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()
    render(<PackagePanel projectId="p1" />)
    await screen.findByText('尚无材料包。')
    await user.click(screen.getByRole('button', { name: '生成材料包' }))
    expect(await screen.findByText(/已保存，列表刷新失败/)).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: '当前材料准备' })).getByText('MP-P01-001')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '生成材料包' })).toBeDisabled()
    refreshFails = false
    await user.click(screen.getByRole('button', { name: '重试刷新材料' }))
    expect(await screen.findByRole('cell', { name: 'MP-P01-001' })).toBeInTheDocument()
    expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  })
  it('retains the approval response when the following list read fails', async () => {
    const ready = makePackage('ready_to_submit', readyGate)
    let approved = false
    const fetcher = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') { approved = true; return jsonResponse(makePackage('human_approved', readyGate), 201) }
      if (approved) return jsonResponse({ error: { message: '刷新暂不可用' } }, 503)
      return jsonResponse(String(url).endsWith('/material-packages') ? [ready] : ready)
    })
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()
    render(<PackagePanel projectId="p1" />)
    await user.type(await screen.findByRole('textbox', { name: '材料包审批意见' }), '已核对快照及全部证据')
    await user.click(screen.getByRole('button', { name: '核对哈希后批准' }))
    expect(await screen.findByText(/已保存，列表刷新失败/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '核对哈希后批准' })).not.toBeInTheDocument()
    expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  })
  it('keeps the preparation workspace actionable and puts detailed checks and hashes only in the view dialog', async () => {
    const draft = makePackage('draft', draftGate)
    const navigate = vi.fn()
    vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL) => jsonResponse(String(url).endsWith('/material-packages') ? [draft] : draft)))
    const user = userEvent.setup()
    render(<PackagePanel projectId="p1" onNavigate={navigate} />)
    const preparation = await screen.findByRole('region', { name: '当前材料准备' })
    expect(within(preparation).getByText('MP-P01-001')).toBeInTheDocument()
    expect(within(preparation).getByText('0/1 项检查通过')).toBeInTheDocument()
    expect(within(preparation).queryByRole('table')).not.toBeInTheDocument()
    expect(within(preparation).queryByText(/快照哈希|ZIP SHA-256|BLOCKING_CONFLICT_OPEN/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '预览材料快照' })).not.toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: '下载 ZIP' })).toHaveLength(1)
    await user.click(within(preparation).getByRole('button', { name: '处理：阻断冲突 CF-P01-001 尚未关闭' }))
    expect(navigate).toHaveBeenCalledWith('consistency', expect.objectContaining({ message: '阻断冲突 CF-P01-001 尚未关闭' }))
    await user.click(screen.getByRole('button', { name: '查看' }))
    const dialog = await screen.findByRole('dialog', { name: '材料包详情 · MP-P01-001' })
    expect(await within(dialog).findByText('生成时快照')).toBeInTheDocument()
    expect(within(dialog).getByText('一致性检查已确认且无未关闭阻断冲突')).toBeInTheDocument()
    expect(within(dialog).getByText(`ZIP SHA-256：${draft.zip_sha256}`)).toBeInTheDocument()
  })
  it('keeps preparation blockers visible when no navigation handler is supplied', async () => {
    const draft = makePackage('draft', draftGate)
    vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL) => jsonResponse(String(url).endsWith('/material-packages') ? [draft] : draft)))
    render(<PackagePanel projectId="p1" />)
    const preparation = await screen.findByRole('region', { name: '当前材料准备' })
    expect(within(preparation).getByText('阻断冲突 CF-P01-001 尚未关闭')).toBeInTheDocument()
    expect(within(preparation).queryByRole('button', { name: '核对哈希后批准' })).not.toBeInTheDocument()
  })
  it('keeps the latest package visible and opens historical snapshots in a dialog without changing current gate work', async () => {
    const latest = { ...makePackage('draft', draftGate), id: 'pkg3', display_code: 'MP-P01-003', package_no: 3 }
    const old = { ...makePackage('ready_to_submit', readyGate), requires_regeneration: true }
    const fetcher = vi.fn(async (url: RequestInfo | URL, _init?: RequestInit) => jsonResponse(
      String(url).endsWith('/material-packages') ? [latest, old] : String(url).endsWith('/pkg3') ? latest : old,
    ))
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()
    const { rerender } = render(<PackagePanel projectId="p1" />)
    await screen.findByRole('region', { name: '当前材料准备' })
    expect(screen.queryByRole('cell', { name: 'MP-P01-001' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '展开历史材料包（1）' }))
    const oldRow = screen.getByRole('cell', { name: 'MP-P01-001' }).closest('tr')!
    const trigger = within(oldRow).getByRole('button', { name: '查看' })
    await user.click(trigger)
    const dialog = await screen.findByRole('dialog', { name: '材料包详情 · MP-P01-001' })
    expect(await within(dialog).findByText('此包为旧版门禁快照，需重新生成后复核。')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: '当前材料准备' })).getByText('MP-P01-003')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: '关闭材料详情' }))
    expect(trigger).toHaveFocus()
    expect(fetcher.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false)
    rerender(<PackagePanel projectId="p2" />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
  it('shows view failures inside the dialog and retries without leaving stale content', async () => {
    const draft = makePackage('draft', draftGate)
    let reads = 0
    vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL) => {
      if (String(url).endsWith('/material-packages')) return jsonResponse([draft])
      return ++reads === 2 ? jsonResponse({ error: { message: '材料详情暂不可读' } }, 503) : jsonResponse(draft)
    }))
    const user = userEvent.setup()
    render(<PackagePanel projectId="p1" />)
    await screen.findByRole('region', { name: '当前材料准备' })
    await user.click(screen.getByRole('button', { name: '查看' }))
    const dialog = await screen.findByRole('dialog', { name: '材料包详情 · MP-P01-001' })
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('材料详情暂不可读')
    expect(within(dialog).queryByText('生成时快照')).not.toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: '重试加载材料' }))
    expect(await within(dialog).findByText('生成时快照')).toBeInTheDocument()
    expect(reads).toBe(3)
  })
  it('keeps legacy gate results historical and prevents approval under the new contract', async () => {
    const legacy = { ...makePackage('ready_to_submit', readyGate), requires_regeneration: true }
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => jsonResponse(String(input).endsWith('/material-packages') ? [legacy] : legacy)))
    render(<PackagePanel projectId="p1" />)
    expect(within(await screen.findByRole('table', { name: '材料包列表' })).getByText('旧版门禁 · 请重新生成')).toBeInTheDocument()
    expect(screen.queryByRole('cell', { name: '可提交' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '核对哈希后批准' })).not.toBeInTheDocument()
  })
  it('generates a draft package and opens its gate detail', async () => {
    const draft = makePackage('draft', draftGate)
    let generated = false
    let createBody: unknown

    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url === '/api/projects/p1/material-packages' && !init?.method) {
          return jsonResponse(generated ? [draft] : [])
        }
        if (
          url === '/api/projects/p1/material-packages' &&
          init?.method === 'POST'
        ) {
          createBody = JSON.parse(String(init.body))
          generated = true
          return jsonResponse(draft, 201)
        }
        if (url === '/api/material-packages/pkg1' && !init?.method) {
          return jsonResponse(draft)
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<PackagePanel projectId="p1" />)

    expect(await screen.findByText('尚无材料包。')).toBeInTheDocument()
    await user.click(
      screen.getByRole('button', { name: '生成材料包' }),
    )

    expect(
      await screen.findByText(/已生成草稿：仍有阻断项/),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', {
        name: '当前材料准备',
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('0/1 项检查通过')).toBeInTheDocument()
    expect(createBody).toMatchObject({
      include_originals: false,
      actor: '演示工程师',
    })

    await user.click(screen.getByRole('button', { name: '查看' }))
    expect(
      screen.getByRole('heading', {
        name: '当前材料准备',
      }),
    ).toBeInTheDocument()
  })

  it('shows draft blockers and exports a ZIP with snapshot hash feedback', async () => {
    const draft = makePackage('draft', draftGate)
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url === '/api/projects/p1/material-packages' && !init?.method) {
          return jsonResponse([draft])
        }
        if (url === '/api/material-packages/pkg1' && !init?.method) {
          return jsonResponse(draft)
        }
        if (
          url === '/api/material-packages/pkg1/download' &&
          !init?.method
        ) {
          return zipResponse()
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<PackagePanel projectId="p1" />)

    await screen.findByRole('cell', { name: 'MP-P01-001' })
    expect(within(await screen.findByRole('region', { name: '当前材料准备' })).getByText('草稿')).toBeInTheDocument()
    expect(
      (await screen.findAllByText(/阻断冲突 CF-P01-001 尚未关闭/)).length,
    ).toBeGreaterThan(0)

    const downloadButtons = screen.getAllByRole('button', {
      name: '下载 ZIP',
    })
    await user.click(downloadButtons[0])

    expect(
      await screen.findByText(/导出成功不等于可提交/),
    ).toBeInTheDocument()
  })

  it('approves a ready package with the frozen snapshot hash', async () => {
    const ready = makePackage('ready_to_submit', readyGate)
    const approved = makePackage('human_approved', readyGate)
    let approvalBody: unknown
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url === '/api/projects/p1/material-packages' && !init?.method) {
          return jsonResponse([ready])
        }
        if (url === '/api/material-packages/pkg1' && !init?.method) {
          return jsonResponse(ready)
        }
        if (
          url === '/api/material-packages/pkg1/approvals' &&
          init?.method === 'POST'
        ) {
          approvalBody = JSON.parse(String(init.body))
          return jsonResponse(approved, 201)
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<PackagePanel projectId="p1" />)

    expect((await screen.findAllByText('可提交')).length).toBeGreaterThan(0)
    await user.type(
      screen.getByRole('textbox', { name: '材料包审批意见' }),
      '人工核对快照后批准',
    )
    await user.click(
      screen.getByRole('button', { name: '核对哈希后批准' }),
    )

    expect(
      await screen.findByText('快照已冻结并完成人工批准'),
    ).toBeInTheDocument()
    expect(approvalBody).toMatchObject({
      expected_snapshot_hash: 'a'.repeat(64),
      actor: '演示工程师',
      comment: '人工核对快照后批准',
    })
  })
})
