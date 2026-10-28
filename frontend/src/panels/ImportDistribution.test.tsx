import { render, screen, within } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import type { SourceDocument, DocumentImport } from '../types'
import { DocumentImportStatus } from './DocumentImportStatus'

const base: SourceDocument = { id:'s1', project_id:'p1', display_code:'DOC-1', doc_type:'protocol', version:'V1', content_hash:'a'.repeat(64), mode:'manual', created_at:'2026-10-23T01:00:00+00:00', parsed_at:'2026-10-23T01:00:00+00:00', parse_summary:{ status:'parsed', requirement_count:2, pending_requirement_count:2, issue_count:1, open_issue_count:1, closed_issue_count:0 } }
function show(documents: SourceDocument[], attempts: DocumentImport[] = [], documentsError = '', attemptsError = '') {
  return render(<DocumentImportStatus view="summary" documents={documents} attempts={attempts} documentsError={documentsError} attemptsError={attemptsError} busy={false} onRefresh={vi.fn()} onParse={vi.fn()} onDiscard={vi.fn()} onResume={vi.fn()} />)
}

it('keeps the distribution visible before any document is imported with an honest empty state', () => {
  show([])
  const chart = screen.getByRole('region', { name:'导入状态分布' })
  expect(within(chart).getByText('暂无已导入文档')).toBeVisible()
  expect(within(chart).getByText('暂无文件处理记录')).toBeVisible()
  expect(within(chart).queryByText('100%')).not.toBeInTheDocument()
})

it('separates archived document distribution from file processing attempts and their different totals', () => {
  const documents = [base, { ...base, id:'s2', parsed_at:null, parse_summary:{ ...base.parse_summary!, status:'pending_parse' as const } }, { ...base, id:'s3', parse_summary:{ ...base.parse_summary!, status:'needs_manual_review' as const, requirement_count:0, pending_requirement_count:0 } }]
  const attempts: DocumentImport[] = ['failed','completed','awaiting_review','cancelled'].map((status,i) => ({ id:`a${i}`, filename:`file${i}.pdf`, status:status as DocumentImport['status'], stage:'saved', error_message:'', created_at:base.created_at, source_document_id:null }))
  show(documents, attempts)
  const chart = screen.getByRole('region', { name:'导入状态分布' })
  expect(within(chart).getByRole('img', { name:'文件状态：已解析1份，已归档待解析1份，未归档待核对1份，已解析需核对1份' })).toBeVisible()
  const history = within(chart).getByRole('group', { name:'文件处理记录分布' })
  expect(within(history).getByLabelText('历史失败记录')).toHaveTextContent('1 次')
  expect(within(history).getByLabelText('历史已取消记录')).toHaveTextContent('1 次')
  expect(within(chart).getByText('文档与处理记录分别统计，重复选择或重试会产生历史记录。')).toBeVisible()
})

it('shows unavailable data rather than converting missing statistics into empty or successful charts', () => {
  show([base], [], '服务未连接', '导入记录读取失败')
  const chart = screen.getByRole('region', { name:'导入状态分布' })
  expect(within(chart).getByText('文档解析统计暂不可用')).toBeVisible()
  expect(within(chart).getByText('文件处理统计暂不可用')).toBeVisible()
  expect(within(chart).queryByText('暂无已导入文档')).not.toBeInTheDocument()
  expect(within(chart).queryByRole('img', { name:/有需求结果/ })).not.toBeInTheDocument()
})
