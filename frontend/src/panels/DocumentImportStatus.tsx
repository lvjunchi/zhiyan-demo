import type { DocumentImport, SourceDocument } from '../types'
import { formatTime } from '../uiSupport'
import { Empty, Notice } from '../ui'
import { ImportDistribution } from './ImportDistribution'

export function DocumentImportStatus({ documents, attempts, documentsError, attemptsError, onRefresh, onParse, onDiscard, onResume, busy, view = 'both' }: {
  documents: SourceDocument[]; attempts: DocumentImport[]; documentsError: string; attemptsError: string
  onRefresh: () => void; onParse: (document: SourceDocument, trigger: HTMLElement) => void; busy: boolean
  onDiscard: (attemptId: string) => void
  onResume: (attempt: DocumentImport) => void
  view?: 'summary' | 'documents' | 'both'
}) {
  const hasCounts = !documentsError && documents.every(doc => doc.parse_summary)
  const completed = documents.filter(doc => doc.parsed_at).length
  const pending = attempts.filter(item=>item.status==='awaiting_review'&&!item.source_document_id)
  const review = documents.filter(doc => doc.parse_summary?.status === 'needs_manual_review').length + pending.length
  const metrics = [
    ['已解析文档', documentsError ? '—' : completed, 'good'],
    ['处理失败', attemptsError ? '—' : attempts.filter(item => item.status === 'failed').length, 'bad'],
    ['待核对文档', attemptsError || !hasCounts ? '—' : review, 'pending'],
    ['待解析文档', documentsError ? '—' : documents.filter(doc => !doc.parsed_at).length, 'pending'],
    ['待审核需求', hasCounts ? documents.reduce((n, doc) => n + (doc.parse_summary?.pending_requirement_count ?? 0), 0) : '—', 'pending'],
    ['待澄清问题', hasCounts ? documents.reduce((n, doc) => n + (doc.parse_summary?.open_issue_count ?? 0), 0) : '—', 'bad'],
  ] as const
  return <section className="panel import-summary import-management" role="region" aria-label="文档导入统计">
    {view !== 'documents' && <div className="import-overview">
      <div className="panel-heading"><h2>导入概况</h2><button type="button" className="secondary" disabled={busy} onClick={onRefresh}>刷新导入状态</button></div>
      <div className="import-metrics">{metrics.map(([label, value, tone]) => <div key={label} aria-label={label} data-tone={tone}><span>{label}</span><strong>{value}</strong></div>)}</div>
      <p className="hint">文件完成解析后，需求仍需人工审核。失败统计为系统已记录的处理尝试，重试后保留历史；待核对包括未归档预览和未提取到需求的文档。</p>
      {documentsError && <Notice kind="error">文档状态未能读取：{documentsError}</Notice>}
      {attemptsError && <Notice kind="error">处理记录未能读取：{attemptsError}</Notice>}
    </div>}
    {view !== 'summary' && <section className="import-documents" aria-label="导入文档状态">
      <div className="panel-heading"><h3>导入文档状态</h3><span className="count">{documentsError||attemptsError ? '状态未知' : `${documents.length} 份已归档 · ${completed} 份已解析 · ${pending.length} 份未归档待核对`}</span></div>
      {!documentsError && !documents.length && <Empty>暂无来源文档，选择协议并核对正文后导入。</Empty>}
      {!!documents.length && <div className="table-wrap"><table><thead><tr><th>文档／文件</th><th>版本</th><th>处理状态</th><th>需求／待审核</th><th>待处理问题</th><th>操作</th></tr></thead><tbody>{documents.map(doc => <tr key={doc.id}>
        <td className="source"><strong>{doc.display_code}</strong><small>{doc.original_file?.filename ?? '文本录入 · 未归档原件'}</small>{doc.original_file?.reviewed_text_changed && <small>正文经人工核对调整，原件独立保留</small>}</td>
        <td>{doc.version}</td><td><span className={`status ${!doc.parsed_at || doc.parse_summary?.status === 'needs_manual_review' ? 'pending_review' : 'confirmed'}`}>{!doc.parsed_at ? '已归档 · 待解析' : doc.parse_summary?.status === 'needs_manual_review' ? '已解析 · 需人工核对' : '已解析'}</span><small className="muted">{doc.parsed_at ? formatTime(doc.parsed_at) : '尚未生成解析结果'}</small></td>
        <td>{doc.parse_summary ? `${doc.parse_summary.requirement_count} / ${doc.parse_summary.pending_requirement_count}` : '—'}</td><td>{doc.parse_summary?.open_issue_count ?? '—'}</td>
        <td className="actions"><button type="button" className="secondary" disabled={busy} onClick={event => onParse(doc, event.currentTarget)}>{doc.parsed_at ? '查看解析结果' : '继续解析'}</button>{doc.original_file && <a href={`/api/source-documents/${encodeURIComponent(doc.id)}/original`} download>下载原件</a>}</td>
      </tr>)}</tbody></table></div>}
    </section>}
    {view !== 'documents' && <ImportDistribution documents={documents} attempts={attempts} documentsAvailable={hasCounts} attemptsAvailable={!attemptsError} />}
    {view !== 'summary' && <>
      {!!attempts.filter(item => !item.source_document_id || item.status === 'failed').length && <details className="import-attempts" open><summary>文件处理记录 · 待核对与失败原因</summary><div className="table-wrap"><table><thead><tr><th>文件</th><th>状态</th><th>所在阶段／原因</th><th>时间／操作</th></tr></thead><tbody>{attempts.filter(item => !item.source_document_id || item.status === 'failed').map(item => <tr key={item.id}><td>{item.filename}</td><td><span className={`status ${item.status === 'failed' ? 'rejected' : 'pending_review'}`}>{item.status === 'failed' ? '处理失败' : item.status === 'cancelled' ? '已取消核对' : '待核对正文'}</span></td><td className="source"><span>{item.stage === 'cancelled' ? '已取消' : item.stage === 'requirement_parse' ? '需求解析' : item.stage === 'review_text' ? '核对正文' : '文件检查／文本提取'}</span><small>{item.error_message || (item.status === 'cancelled' ? '历史记录保留，不计入待核对数量。' : '尚未提交归档；可继续核对。草稿保存在当前浏览器，旧记录按提示重选原文件。')}</small></td><td>{formatTime(item.created_at)}{item.status === 'awaiting_review' && <span className="import-attempt-actions"><button type="button" disabled={busy} onClick={() => onResume(item)}>继续核对</button><button type="button" className="secondary" disabled={busy} onClick={() => onDiscard(item.id)}>取消待核对</button></span>}</td></tr>)}</tbody></table></div></details>}
    </>}
  </section>
}
