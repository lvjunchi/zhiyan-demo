import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type {
  ParseResult,
  Requirement,
  RequirementIssue,
} from '../types'
import { ParsingPanel } from './ParsingPanel'

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
  source_document_id: 'doc1',
  source_location: '§3.1',
  source_excerpt: '发动机最大扭矩 2600 N·m',
  review_status: 'draft',
  validity: 'current',
  current_revision: 1,
  created_at: '2026-10-19T00:00:00+00:00',
  updated_at: '2026-10-19T00:00:00+00:00',
}

const issue: RequirementIssue = {
  id: 'i1',
  project_id: 'p1',
  source_document_id: 'doc1',
  requirement_id: 'r1',
  parser_key: 'gearboxRatedInputTorque',
  issue_type: 'missing_reference',
  category: 'C',
  severity: 'high',
  message: '派生要求缺少上游来源',
  source_location: '§3.1',
  source_excerpt: '发动机最大扭矩 2600 N·m',
  blocking_reason: '缺少可追溯来源',
  suggestion: '补充引用关系',
  status: 'open',
  created_at: '2026-10-19T00:00:00+00:00',
  closed_at: null,
  close_reason: null,
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

describe('ParsingPanel', () => {
  it('opens issue evidence in a drawer, cancels without writing and isolates drafts by issue and project', async () => {
    const fetcher = vi.fn(async (url: RequestInfo | URL, _init?: RequestInit) => jsonResponse(String(url).endsWith('/issues') ? [issue, { ...issue, id: 'i2', message: '另一条待澄清问题' }] : []))
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()
    const { rerender } = render(<ParsingPanel projectId="p1" />)
    const trigger = (await screen.findAllByRole('button', { name: '关闭' }))[0]
    await user.click(trigger)
    const drawer = await screen.findByRole('dialog', { name: '问题处置' })
    expect(within(drawer).getByText('发动机最大扭矩 2600 N·m')).toBeInTheDocument()
    expect(within(drawer).getByText('缺少可追溯来源')).toBeInTheDocument()
    await user.type(within(drawer).getByLabelText('问题处置说明'), '补充引用后复核')
    await user.selectOptions(within(drawer).getByLabelText('问题处置类型'), 'evidence_added')
    await user.click(within(drawer).getByRole('button', { name: '关闭问题详情' }))
    expect(trigger).toHaveFocus()
    expect(fetcher.mock.calls.some(([, init]) => (init as RequestInit | undefined)?.method === 'POST')).toBe(false)
    await user.click(trigger)
    expect(screen.getByLabelText('问题处置说明')).toHaveValue('补充引用后复核')
    await user.click(screen.getByRole('button', { name: '关闭问题详情' }))
    await user.click(screen.getAllByRole('button', { name: '关闭' })[1])
    expect(screen.getByLabelText('问题处置说明')).toHaveValue('')
    expect(screen.getByLabelText('问题处置类型')).toHaveValue('manual_supplement')
    rerender(<ParsingPanel projectId="p2" />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
  it('keeps failed issue submission inside the drawer and retries with evidence intact', async () => {
    let attempts = 0
    vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).endsWith('/close') && init?.method === 'POST') return ++attempts === 1
        ? jsonResponse({ error: { message: '处置暂未保存' } }, 503)
        : jsonResponse({ ...issue, status: 'closed' })
      return jsonResponse(String(url).endsWith('/issues') ? [issue] : [])
    }))
    const user = userEvent.setup()
    render(<ParsingPanel projectId="p1" />)
    const trigger = await screen.findByRole('button', { name: '关闭' })
    await user.click(trigger)
    const drawer = await screen.findByRole('dialog', { name: '问题处置' })
    await user.type(within(drawer).getByLabelText('问题处置说明'), '补充引用')
    await user.type(within(drawer).getByLabelText('问题处置证据'), '补充协议第3页')
    await user.click(within(drawer).getByRole('button', { name: '确认关闭' }))
    expect(await within(drawer).findByRole('alert')).toHaveTextContent('处置暂未保存')
    expect(within(drawer).getByLabelText('问题处置证据')).toHaveValue('补充协议第3页')
    await user.click(within(drawer).getByRole('button', { name: '确认关闭' }))
    expect(await screen.findByText('问题已关闭并记录处置证据')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重开' })).toHaveFocus()
    expect(attempts).toBe(2)
  })
  it('keeps original bytes through reviewed import and exposes archived sources', async () => {
    let imported: Record<string, unknown> | undefined
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/extract?')) return jsonResponse({ import_id: 'attempt-1', content: '【TXT 行 1】\n发动机最大扭矩 2800 N·m。', warnings: [], sha256: 'a'.repeat(64) })
      if (url.endsWith('/source-documents') && init?.method === 'POST') {
        imported = JSON.parse(String(init.body))
        return jsonResponse({ id: 'doc1', display_code: 'DOC-P01-001' })
      }
      if (url.endsWith('/parse')) return jsonResponse({ requirements: [], issues: [], missing_categories: [], unrecognized_clauses: [], already_parsed: false })
      return jsonResponse([])
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<ParsingPanel projectId="p1" />)
    await waitFor(()=>expect(screen.getByLabelText('选择协议文件')).toBeEnabled())
  await user.upload(screen.getByLabelText('选择协议文件'), new File(['original'], 'protocol.txt'))
    await screen.findByText(/文件文本已提取/)
    await user.click(screen.getByRole('button', { name: '导入并解析' }))
    await screen.findByText(/已解析 DOC-P01-001/)
    expect(imported?.original_file).toEqual({ filename: 'protocol.txt', sha256: 'a'.repeat(64), data_base64: btoa('original') })
  })
  it('previews a selected document locally before importing and reports unreadable files', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      if (String(input).includes('/extract?')) return jsonResponse({ import_id: 'attempt-1', content: '【TXT 行 1】\n发动机最大扭矩 2800 N·m。', warnings: [], filename: 'protocol.txt', format: 'txt', mode: 'rule', sha256: 'a'.repeat(64) })
      return jsonResponse([])
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<ParsingPanel projectId="p1" />)
    await waitFor(()=>expect(screen.getByLabelText('选择协议文件')).toBeEnabled())
  await user.upload(screen.getByLabelText('选择协议文件'), new File(['发动机最大扭矩 2800 N·m。'], 'protocol.txt', { type: 'text/plain' }))
    expect(await screen.findByText(/文件文本已提取/)).toBeInTheDocument()
    expect(screen.getByLabelText('来源文档正文')).toHaveValue('【TXT 行 1】\n发动机最大扭矩 2800 N·m。')
    expect(fetchMock.mock.calls.some(([input, init]) => String(input).includes('/source-documents') && init?.method === 'POST')).toBe(false)
  })
  it('reopens a closed issue with an explicit reason', async () => {
    let current: RequirementIssue = {
      ...issue,
      status: 'closed',
      closed_at: '2026-10-19T01:00:00+00:00',
      close_reason: '人工补录',
    }
    let reopenBody: unknown

    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url === '/api/projects/p1/issues' && !init?.method) {
          return jsonResponse([current])
        }
        if (url === '/api/issues/i1/reopen' && init?.method === 'POST') {
          reopenBody = JSON.parse(String(init.body))
          current = {
            ...current,
            status: 'open',
            closed_at: null,
            close_reason: null,
          }
          return jsonResponse(current)
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<ParsingPanel projectId="p1" />)

    expect(await screen.findByText('已关闭')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '重开' }))
    expect(screen.getByRole('dialog', { name: '问题处置' })).toBeInTheDocument()
    await user.type(
      screen.getByRole('textbox', { name: '问题重开原因' }),
      '补充证据后仍需复核',
    )
    await user.click(screen.getByRole('button', { name: '确认重开' }))

    expect(
      await screen.findByText('问题已重新打开并记录原因'),
    ).toBeInTheDocument()
    expect(reopenBody).toMatchObject({
      expected_status: 'closed',
      actor: '演示工程师',
      role: 'design_engineer',
      reason: '补充证据后仍需复核',
    })
  })

  it('imports and parses a document, then closes a parsed issue with evidence', async () => {
    let issues: RequirementIssue[] = []
    let parseBody: unknown
    let closeBody: unknown

    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url === '/api/projects/p1/issues' && !init?.method) {
          return jsonResponse(issues)
        }
        if (
          url === '/api/projects/p1/source-documents' &&
          init?.method === 'POST'
        ) {
          return jsonResponse(
            {
              id: 'doc1',
              project_id: 'p1',
              display_code: 'DOC-P01-001',
              doc_type: 'protocol',
              version: 'V1',
              content_hash: 'a'.repeat(64),
              mode: 'manual',
              created_at: '2026-10-19T00:00:00+00:00',
              parsed_at: null,
            },
            201,
          )
        }
        if (
          url === '/api/source-documents/doc1/parse' &&
          init?.method === 'POST'
        ) {
          parseBody = JSON.parse(String(init.body))
          issues = [issue]
          const parsed: ParseResult = {
            source_document_id: 'doc1',
            project_id: 'p1',
            mode: 'rule',
            status: 'parsed',
            already_parsed: false,
            parsed_at: '2026-10-19T00:00:00+00:00',
            requirements: [requirement],
            issues: [issue],
            missing_categories: [],
            unrecognized_clauses: [],
            references: [],
          }
          return jsonResponse(parsed)
        }
        if (url === '/api/issues/i1/close' && init?.method === 'POST') {
          closeBody = JSON.parse(String(init.body))
          const closed: RequirementIssue = {
            ...issue,
            status: 'closed',
            closed_at: '2026-10-19T02:00:00+00:00',
            close_reason: '人工补录',
          }
          issues = [closed]
          return jsonResponse(closed)
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<ParsingPanel projectId="p1" />)

    await screen.findByText('暂无问题记录。')
    await user.click(
      screen.getByRole('button', { name: '填充合成示例' }),
    )
    await user.click(
      screen.getByRole('button', { name: '导入并解析' }),
    )

    expect(
      await screen.findByText(/生成 1 条需求、1 条问题/),
    ).toBeInTheDocument()
    expect(parseBody).toMatchObject({
      display_code_map: {
        engineMaxTorque: 'REQ-P01-B-003',
        gearCount: 'REQ-P01-C-001',
      },
    })
    expect(screen.getByText('派生要求缺少上游来源')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '关闭' }))
    await user.type(
      screen.getByRole('textbox', { name: '问题处置说明' }),
      '人工补充引用关系',
    )
    await user.type(
      screen.getByRole('textbox', { name: '问题处置证据' }),
      '补充协议 §3.1',
    )
    await user.click(
      screen.getByRole('button', { name: '确认关闭' }),
    )

    expect(
      await screen.findByText('问题已关闭并记录处置证据'),
    ).toBeInTheDocument()
    expect(closeBody).toMatchObject({
      expected_status: 'open',
      resolution_type: 'manual_supplement',
      resolution_note: '人工补充引用关系',
      evidence: '补充协议 §3.1',
    })
  })
})
