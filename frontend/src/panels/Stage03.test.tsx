import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ParsingPanel } from './ParsingPanel'
import { SettingsPanel } from './SettingsPanel'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
const source = { id: 's1', project_id: 'p1', display_code: 'DOC-1', version: 'V1', parsed_at: null,
  parse_summary: { status: 'pending_parse', requirement_count: 0, pending_requirement_count: 0, issue_count: 0, open_issue_count: 0, closed_issue_count: 0 } }
const parsed = { source_document_id: 's1', project_id: 'p1', mode: 'rule', status: 'parsed', parsed_at: '2026-10-23T01:00:00+00:00', requirements: [], issues: [], references: [], missing_categories: [], unrecognized_clauses: [], already_parsed: false }
afterEach(() => vi.unstubAllGlobals())

it('shows actual import attempts separately from document parsing and requirement approval', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL) => {
    if (String(url).endsWith('/document-imports')) return json([
      { id: 'a', filename: '损坏.pdf', status: 'failed', stage: 'text_extraction', error_message: 'PDF结构损坏', created_at: '2026-10-23T01:00:00+00:00', source_document_id: null },
      { id: 'b', filename: '协议.docx', status: 'awaiting_review', stage: 'review_text', error_message: '', created_at: '2026-10-23T01:00:00+00:00', source_document_id: null },
    ])
    if (String(url).endsWith('/source-documents')) return json([{ ...source, parsed_at: '2026-10-23T01:00:00+00:00', parse_summary: { ...source.parse_summary, status: 'parsed', requirement_count: 3, pending_requirement_count: 3, open_issue_count: 2, issue_count: 2 } }])
    return json([])
  }))
  render(<ParsingPanel projectId="p1" />)
  const stats = await screen.findByRole('region', { name: '文档导入统计' })
  expect(await within(stats).findByLabelText('已解析文档')).toHaveTextContent('1')
  expect(within(stats).getByLabelText('处理失败')).toHaveTextContent('1')
  expect(within(stats).getByLabelText('待核对文档')).toHaveTextContent('1')
  expect(within(stats).getByLabelText('待审核需求')).toHaveTextContent('3')
  expect(within(stats).getByLabelText('待澄清问题')).toHaveTextContent('2')
  expect(screen.getByRole('heading', { name: '导入文档状态' })).toBeVisible()
  expect(screen.getByText('PDF结构损坏')).toBeVisible()
})

it('reports the exact failed stage and retries the archived document without creating another source', async () => {
  let creates = 0, parses = 0
  vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === 'POST' && String(url).endsWith('/source-documents')) { creates++; return json(source, 201) }
    if (String(url).endsWith('/parse')) { parses++; return parses === 1 ? json({ error: { message: '解析暂时不可用' } }, 503) : json(parsed) }
    return json([])
  }))
  const user = userEvent.setup()
  render(<ParsingPanel projectId="p1" />)
  await user.type(screen.getByLabelText('来源文档正文'), '发动机最大扭矩2600 N·m。')
  await user.click(screen.getByRole('button', { name: '导入并解析' }))
  const progress = screen.getByRole('region', { name: '协议处理进度' })
  expect(await within(progress).findByText(/需求解析失败/)).toBeVisible()
  expect(screen.getByRole('alert')).toHaveTextContent('解析暂时不可用')
  await user.click(screen.getByRole('button', { name: '重试已归档文档解析' }))
  expect(await within(progress).findByText('结果已保存，需求仍需人工审核')).toBeVisible()
  expect(creates).toBe(1); expect(parses).toBe(2)
})

it('preserves the previous preview and its original association when another file cannot be extracted', async () => {
  let attempt = 0, body: Record<string, unknown> = {}
  vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    if (String(url).includes('/extract?')) return ++attempt === 1 ? json({ import_id: 'i1', content: '发动机最大扭矩2600 N·m。', sha256: 'a'.repeat(64), warnings: [] }) : json({ error: { message: '扫描件无法提取文本' } }, 422)
    if (init?.method === 'POST' && String(url).endsWith('/source-documents')) { body = JSON.parse(String(init.body)); return json(source) }
    if (String(url).endsWith('/parse')) return json(parsed)
    return json([])
  }))
  const user = userEvent.setup()
  render(<ParsingPanel projectId="p1" />)
  await waitFor(()=>expect(screen.getByLabelText('选择协议文件')).toBeEnabled())
  await user.upload(screen.getByLabelText('选择协议文件'), new File(['first'], 'first.docx'))
  await screen.findByText(/文件文本已提取/)
  await waitFor(()=>expect(screen.getByLabelText('选择协议文件')).toBeEnabled())
  await user.upload(screen.getByLabelText('选择协议文件'), new File(['scan'], 'scan.pdf'))
  expect(await screen.findByRole('alert')).toHaveTextContent('扫描件无法提取文本')
  expect(screen.getByLabelText('来源文档正文')).toHaveValue('发动机最大扭矩2600 N·m。')
  expect(screen.getByText(/待归档：first.docx/)).toBeVisible()
  await user.click(screen.getByRole('button', { name: '导入并解析' }))
  await screen.findByText(/^已解析 DOC-1：/)
  expect(body.import_id).toBe('i1')
  expect(body.original_file).toMatchObject({ filename: 'first.docx' })
})

const clearPreview = { project: { id: 'p1', display_code: 'P01', name: '定制项目' }, affected_counts: { requirements: 6, source_documents: 1 }, retained_counts: { product_bases: 4, base_parts: 8 }, expected_state_hash: 'a'.repeat(64) }

it('opens saved document results in a modal and returns focus to the original document row', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL) => {
    if (String(url).endsWith('/source-documents')) return json([{ ...source, parsed_at: '2026-10-23T01:00:00+00:00', parse_summary: { ...source.parse_summary, status: 'parsed' } }])
    if (String(url).endsWith('/parse')) return json({ ...parsed, already_parsed: true })
    return json([])
  }))
  const user = userEvent.setup()
  render(<ParsingPanel projectId="p1" />)
  const importOverview = screen.getByRole('region', { name: '文档导入统计' })
  const trigger = await within(importOverview).findByRole('button', { name: '查看解析结果' })
  await user.click(trigger)
  const dialog = await screen.findByRole('dialog', { name: '文档解析结果' })
  expect(await within(dialog).findByText(/已完成解析/)).toBeVisible()
  await user.click(within(dialog).getByRole('button', { name: '关闭解析结果' }))
  expect(trigger).toHaveFocus()
  expect(screen.queryByRole('heading', { name: '解析结果' })).not.toBeInTheDocument()
})

it('previews project clearing, requires the project code and cancels without clearing', async () => {
  const fetcher = vi.fn(async (url: RequestInfo | URL) => String(url).endsWith('/clear-preview') ? json(clearPreview) : json({ status: 'ok', database: 'connected', schema_version: '016_document_imports' }))
  vi.stubGlobal('fetch', fetcher)
  const user = userEvent.setup()
  render(<SettingsPanel projectId="p1" />)
  const trigger = screen.getByRole('button', { name: '清空当前项目业务数据' })
  await user.click(trigger)
  const dialog = await screen.findByRole('dialog', { name: '清空当前项目业务数据' })
  expect(await within(dialog).findByText(/6 条需求/)).toBeVisible()
  const submit = within(dialog).getByRole('button', { name: '备份并清空当前项目' })
  expect(submit).toBeDisabled()
  await user.type(within(dialog).getByLabelText('输入项目编号确认'), 'WRONG')
  expect(submit).toBeDisabled()
  await user.click(within(dialog).getByRole('button', { name: '取消清空' }))
  expect(fetcher.mock.calls.some(([url]) => String(url).endsWith('/clear'))).toBe(false)
  expect(trigger).toHaveFocus()
})

it('requires fresh preview after clear failure and exposes the verified backup after success', async () => {
  let tries = 0, previews = 0
  const fetcher = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    if (String(url).endsWith('/clear-preview')) { previews++; return json(clearPreview) }
    if (String(url).endsWith('/clear')) { expect(JSON.parse(String(init?.body))).toMatchObject({ confirmation_code: 'P01', expected_state_hash: 'a'.repeat(64) }); return ++tries === 1 ? json({ error: { message: '预览后数据已变化' } }, 409) : json({ status: 'cleared', original_retained: true, backup_url: '/api/system/clear-backups/' + 'a'.repeat(32), backup_sha256: 'b'.repeat(64), reload_required: true }) }
    return json({ status: 'ok', database: 'connected', schema_version: '016_document_imports' })
  })
  vi.stubGlobal('fetch', fetcher)
  const user = userEvent.setup()
  render(<SettingsPanel projectId="p1" />)
  await user.click(screen.getByRole('button', { name: '清空当前项目业务数据' }))
  await user.type(await screen.findByLabelText('输入项目编号确认'), 'P01')
  await user.click(screen.getByRole('button', { name: '备份并清空当前项目' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('预览后数据已变化')
  expect(screen.getByRole('button', { name: '备份并清空当前项目' })).toBeDisabled()
  await user.click(screen.getByRole('button', { name: '重新预览影响范围' }))
  await user.type(screen.getByLabelText('输入项目编号确认'), 'P01')
  await user.click(screen.getByRole('button', { name: '备份并清空当前项目' }))
  expect(await screen.findByRole('link', { name: '下载清空前完整备份' })).toHaveAttribute('href', '/api/system/clear-backups/' + 'a'.repeat(32))
  expect(screen.getByRole('button', { name: '重新载入空白项目' })).toBeVisible()
  expect(previews).toBe(2)
})
