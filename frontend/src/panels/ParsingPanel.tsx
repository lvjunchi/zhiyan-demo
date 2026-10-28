import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { readImportDrafts, removeImportDraft, saveImportDraft, type ImportDraft } from '../importDrafts'
import type { FormEvent } from 'react'
import { api, ApiError } from '../api'
import { DetailOverlay } from '../components/DetailOverlay'
import { DocumentImportStatus } from './DocumentImportStatus'
import { ImportProgress } from './ImportProgress'
import { recoverImportProgress, type ImportPhase } from './importProgressState'
import { ParseResultView } from './ParseResultView'
import './document-import.css'
import type {
  ParseResult,
  RequirementIssue,
  SourceDocumentCreate,
  SourceDocument,
  DocumentImport,
} from '../types'
import { Empty, Notice } from '../ui'
import { DEMO_ACTOR, DEMO_ROLE, docTypeLabels, severityLabels, toErrorMessage } from '../uiSupport'

const SAMPLE_CONTENT =
  '3.1 发动机最大扭矩 2600 N·m。\n4.2 12 档 AMT。'
const SAMPLE_MAPPING =
  'engineMaxTorque=REQ-P01-B-003\ngearCount=REQ-P01-C-001'

function parseMapping(text: string): Record<string, string> {
  const result: Record<string, string> = {}
  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim()
    if (!line) continue
    const separator = line.indexOf('=')
    if (separator <= 0) continue
    const key = line.slice(0, separator).trim()
    const code = line.slice(separator + 1).trim()
    if (key && code) result[key] = code
  }
  return result
}

export function ParsingPanel(props: Parameters<typeof ParsingWorkspace>[0]) {
  return <ParsingWorkspace key={props.projectId} {...props} />
}

function ParsingWorkspace({ projectId }: { projectId: string }) {
  const [displayCode, setDisplayCode] = useState('DOC-P01-001')
  const [docType, setDocType] =
    useState<SourceDocumentCreate['doc_type']>('protocol')
  const [version, setVersion] = useState('V1')
  const [content, setContent] = useState('')
  const [mappingText, setMappingText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [parseResult, setParseResult] = useState<ParseResult | null>(null)
  const [parsePreviewOpen, setParsePreviewOpen] = useState(false)
  const [parseResultOrigin, setParseResultOrigin] = useState<'import' | 'document'>('import')
  const [parseTrigger, setParseTrigger] = useState<HTMLElement | null>(null)
  const [original, setOriginal] = useState<SourceDocumentCreate['original_file']>()
  const [documents, setDocuments] = useState<SourceDocument[]>([])
  const [documentsError, setDocumentsError] = useState('')
  const [attempts, setAttempts] = useState<DocumentImport[]>([])
  const [attemptsError, setAttemptsError] = useState('')
  const [documentsReady,setDocumentsReady]=useState(false)
  const [attemptsReady,setAttemptsReady]=useState(false)
  const [importId, setImportId] = useState<string>()
  const [phase, setPhase] = useState<ImportPhase>('idle')
  const [phaseFailure, setPhaseFailure] = useState('')
  const [pendingSource, setPendingSource] = useState<{ document: SourceDocument; mapping: Record<string, string> } | null>(null)
  const [draftReady, setDraftReady] = useState(false)
  const [hasDraft, setHasDraft] = useState(false)
  const [draftSourceId, setDraftSourceId] = useState<string>()
  const [draftSaved, setDraftSaved] = useState(false)
  const [draftWarning, setDraftWarning] = useState('')
  const [resumeAttempt, setResumeAttempt] = useState<DocumentImport | null>(null)
  const importSection = useRef<HTMLElement>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const applyDraft = useCallback((draft: ImportDraft, document?: SourceDocument) => {
    setDisplayCode(draft.displayCode); setDocType(draft.docType); setVersion(draft.version)
    setContent(draft.content); setMappingText(draft.mappingText); setOriginal(draft.original); setImportId(draft.importId)
    setPendingSource(document ? { document, mapping: parseMapping(draft.mappingText) } : null)
    setDraftSourceId(document?.id)
    setPhase(document ? 'parsing' : 'reviewing'); setPhaseFailure(document ? '已恢复归档草稿，可重试解析。' : '')
    setHasDraft(true); setDraftSaved(false); setResumeAttempt(null); setError(''); setParseResult(null)
  }, [])
  useEffect(() => {
    let active = true
    async function restore() {
      const drafts = await readImportDrafts(projectId)
      if (!drafts.length) return
      const current = await api.listDocumentImports(projectId)
      const sources = drafts.some(draft => draft.sourceId) ? await api.listSourceDocuments(projectId) : []
      for (const draft of drafts) {
        const attempt = current.find(row => row.id === draft.importId)
        const source = sources.find(row => row.id === draft.sourceId)
        const valid = draft.sourceId ? source && !source.parsed_at && (!draft.importId || attempt?.source_document_id === draft.sourceId)
          : !draft.importId || attempt?.status === 'awaiting_review' && !attempt.source_document_id
        if (!valid) { await removeImportDraft(projectId, draft.importId); continue }
        if (active) { applyDraft(draft, source); setMessage('已恢复上次核对草稿，可继续修改或提交解析。') }
        break
      }
    }
    void restore().catch((err: unknown) => { if (active) setDraftWarning(`核对草稿未能恢复：${toErrorMessage(err)}。可从待核对记录重新继续。`) }).finally(() => { if (active) setDraftReady(true) })
    return () => { active = false }
  }, [projectId, applyDraft])
  useEffect(() => {
    if (!draftReady || !hasDraft) return
    let active = true
    void saveImportDraft({ projectId, importId, displayCode, docType, version, content, mappingText, original, sourceId: draftSourceId, updatedAt: new Date().toISOString() })
      .then(() => { if (active) { setDraftSaved(true); setDraftWarning('') } })
      .catch((err: unknown) => { if (active) setDraftWarning(`草稿未能保存：${toErrorMessage(err)}。离开前请先归档，或保留原文件以便重新核对。`) })
    return () => { active = false }
  }, [draftReady, hasDraft, projectId, importId, displayCode, docType, version, content, mappingText, original, draftSourceId])
  async function forgetDraft(id?: string) {
    try { await removeImportDraft(projectId, id) }
    catch (err) { setDraftWarning(`业务操作已完成，但草稿清理失败：${toErrorMessage(err)}`) }
  }
  async function resumePreview(attempt: DocumentImport) {
    setBusy(true); setError(''); setMessage('')
    try {
      const current = (await api.listDocumentImports(projectId)).find(row => row.id === attempt.id)
      if (!current || current.status !== 'awaiting_review' || current.source_document_id) throw new Error('该待核对记录已变化，请刷新导入状态。')
      const cached = await readImportDrafts(projectId).catch((err: unknown) => { setDraftWarning(`草稿未能读取：${toErrorMessage(err)}。请重新选择原文件恢复。`); return [] })
      const draft = cached.find(row => row.importId === attempt.id)
      if (draft) { applyDraft(draft); setMessage('已恢复核对草稿，可继续核对正文并提交解析。') }
      else {
        setHasDraft(false); setDraftSaved(false); setContent(''); setOriginal(undefined); setImportId(undefined); setMappingText('')
        setPendingSource(null); setDraftSourceId(undefined); setPhase('idle'); setPhaseFailure(''); setDisplayCode('DOC-P01-001'); setDocType('protocol'); setVersion('V1')
        setResumeAttempt(current); setMessage('请选择同一原文件恢复核对；这条旧记录未保存正文或当前浏览器没有草稿。重新提取会沿用该记录，不会新增一次导入；文档编号、版本和映射请重新核对。')
      }
      importSection.current?.scrollIntoView?.({ block: 'start', behavior: 'smooth' })
    } catch (err) { setError(toErrorMessage(err)) }
    finally { setBusy(false) }
  }
  const loadAttempts = useCallback(async () => {
    try { setAttempts(await api.listDocumentImports(projectId)); setAttemptsError('') }
    catch (err) { setAttemptsError(toErrorMessage(err)) }
    finally {setAttemptsReady(true)}
  }, [projectId])
  useEffect(() => { let active = true; api.listDocumentImports(projectId).then(data => { if (active) setAttempts(data) }).catch((err: unknown) => { if (active) setAttemptsError(toErrorMessage(err)) }).finally(()=>{if(active)setAttemptsReady(true)}); return () => { active = false } }, [projectId])

  const loadDocuments = useCallback(async () => {
    try {
      const sources = await api.listSourceDocuments(projectId)
      if (!Array.isArray(sources)) throw new Error('来源文档响应无效')
      setDocuments(sources); setDocumentsError('')
    } catch (err) { setDocumentsError(toErrorMessage(err)) }
    finally {setDocumentsReady(true)}
  }, [projectId])
  useEffect(() => {
    let active = true
    api.listSourceDocuments(projectId).then(sources => {
      if (!Array.isArray(sources)) throw new Error('来源文档响应无效')
      if (active) { setDocuments(sources); setDocumentsError('') }
    }).catch((err: unknown) => { if (active) setDocumentsError(toErrorMessage(err)) }).finally(()=>{if(active)setDocumentsReady(true)})
    return () => { active = false }
  }, [projectId])

  const [issues, setIssues] = useState<RequirementIssue[]>([])
  const [issuesLoading, setIssuesLoading] = useState(true)
  const [issuesError, setIssuesError] = useState('')
  const [selectedIssueId, setSelectedIssueId] = useState('')
  const [issueOpen, setIssueOpen] = useState(false)
  const [issueError, setIssueError] = useState('')
  const [issueTrigger, setIssueTrigger] = useState<HTMLElement | null>(null)
  const [resolutionType, setResolutionType] = useState('manual_supplement')
  const [resolutionNote, setResolutionNote] = useState('')
  const [evidence, setEvidence] = useState('')
  const [reopenReason, setReopenReason] = useState('')

  const loadIssues = useCallback(async () => {
    const data = await api.listIssues(projectId)
    setIssues(data)
    return data
  }, [projectId])

  async function refreshIssues() {
    try { await loadIssues(); setIssuesError('') }
    catch (err) { setIssuesError(toErrorMessage(err)) }
  }

  useEffect(() => {
    let cancelled = false
    api
      .listIssues(projectId)
      .then((data) => {
        if (!cancelled) setIssues(data)
      })
      .catch((err: unknown) => {
        if (!cancelled) setIssuesError(toErrorMessage(err))
      })
      .finally(() => {
        if (!cancelled) setIssuesLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [projectId])

  const selectedIssue = useMemo(
    () => issues.find((item) => item.id === selectedIssueId) ?? null,
    [issues, selectedIssueId],
  )

  async function handleImport(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    setMessage('')
    setParseResult(null)
    setParseResultOrigin('import')
    setPhase('archiving'); setPhaseFailure('')
    try {
      const document = await api.createSourceDocument(projectId, {
        display_code: displayCode.trim(),
        doc_type: docType,
        version: version.trim(),
        content,
        mode: 'manual',
        original_file: original,
        import_id: original ? importId : undefined,
      })
      const mapping = parseMapping(mappingText)
      setPendingSource({ document, mapping })
      setDraftSourceId(document.id)
      setPhase('parsing')
      const parsed = await api.parseSourceDocument(document.id, mapping)
      setParseResult(parsed)
      setPendingSource(null); setPhase('saved')
      setHasDraft(false); setDraftSaved(false); setDraftSourceId(undefined)
      await forgetDraft(importId)
      await refreshIssues()
      setMessage(
        `已解析 ${document.display_code}：生成 ${parsed.requirements.length} 条需求、` +
          `${parsed.issues.length} 条问题（${parsed.already_parsed ? '已存在，未重复导入' : '首次导入'}）`,
      )
    } catch (err) {
      setError(toErrorMessage(err)); setPhaseFailure(toErrorMessage(err))
    } finally {
      await loadDocuments(); await loadAttempts()
      setBusy(false)
    }
  }

  async function previewFile(file: File) {
    setBusy(true); setError(''); setMessage(''); setPhase('checking'); setPhaseFailure('')
    try {
      setPhase('extracting')
      const target = resumeAttempt
      const extracted = await api.extractDocumentText(file, target ? undefined : projectId)
      if (target && (file.name !== target.filename || !target.sha256 || extracted.sha256 !== target.sha256)) throw new Error('所选文件与这条待核对记录不一致，请选择同一原文件；原记录未改变。')
      const data = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onerror = () => reject(new Error('原文件读取失败，请重新选择'))
        reader.onload = () => typeof reader.result === 'string' ? resolve(reader.result.split(',')[1]) : reject(new Error('原文件读取失败'))
        reader.readAsDataURL(file)
      })
      const nextOriginal = { filename: file.name, data_base64: data, sha256: extracted.sha256 }
      const nextImportId = target?.id ?? extracted.import_id
      try {
        await saveImportDraft({ projectId, importId: nextImportId, displayCode, docType, version, content: extracted.content, mappingText, original: nextOriginal, updatedAt: new Date().toISOString() })
        if (!importId) await forgetDraft()
      } catch (err) { setDraftWarning(`草稿未能保存：${toErrorMessage(err)}。离开前请先归档，或保留原文件以便重新核对。`) }
      setOriginal(nextOriginal)
      setImportId(nextImportId); setPhase('reviewing'); setPendingSource(null); setDraftSourceId(undefined)
      setContent(extracted.content)
      setHasDraft(true); setDraftSaved(false); setResumeAttempt(null)
      setMessage(`文件文本已提取：${file.name}。核对正文和位置标记后点击“导入并解析”。${extracted.warnings.join('；')}`)
    } catch (err) {
      if (err instanceof ApiError && typeof err.details === 'object' && err.details !== null && 'stage' in err.details && err.details.stage === 'file_check') setPhase('checking')
      setError(toErrorMessage(err)); setPhaseFailure(toErrorMessage(err))
    }
    finally { await loadAttempts(); setBusy(false) }
  }

  async function parseArchived(document: SourceDocument, mapping: Record<string, string> = {}) {
    setBusy(true); setError(''); setMessage(''); setPhase('parsing'); setPhaseFailure('')
    setPendingSource({ document, mapping })
    try {
      const parsed = await api.parseSourceDocument(document.id, mapping)
      setParseResult(parsed); setPendingSource(null); setPhase('saved')
      if (draftSourceId === document.id) { setHasDraft(false); setDraftSaved(false); setDraftSourceId(undefined); await forgetDraft(importId) }
      setMessage(`已解析 ${document.display_code}：生成 ${parsed.requirements.length} 条需求、${parsed.issues.length} 条问题（${parsed.already_parsed ? '已存在，未重复导入' : '首次导入'}）`)
      await refreshIssues()
    } catch (err) { setError(toErrorMessage(err)); setPhaseFailure(toErrorMessage(err)) }
    finally { await loadDocuments(); await loadAttempts(); setBusy(false) }
  }

  async function discardPreview(attemptId: string) {
    setBusy(true); setError(''); setMessage('')
    try {
      await api.discardDocumentImport(projectId, attemptId)
      await forgetDraft(attemptId)
      if (importId === attemptId) { setHasDraft(false); setDraftSaved(false); setImportId(undefined); setOriginal(undefined); setContent(''); setMappingText(''); setPhase('idle'); setPhaseFailure(''); setPendingSource(null); setDraftSourceId(undefined) }
      if (resumeAttempt?.id === attemptId) setResumeAttempt(null)
      setMessage('已取消待核对记录，历史保留；尚未生成需求。')
    } catch (err) { setError(toErrorMessage(err)) }
    finally { await loadAttempts(); setBusy(false) }
  }

  async function handleCloseIssue(event: FormEvent) {
    event.preventDefault()
    if (!selectedIssue) return
    setBusy(true)
    setIssueError('')
    setMessage('')
    try {
      const updated = await api.closeIssue(selectedIssue.id, {
        expected_status: 'open',
        actor: DEMO_ACTOR,
        role: DEMO_ROLE,
        resolution_type: resolutionType,
        resolution_note: resolutionNote.trim(),
        evidence: evidence.trim(),
      })
      setIssues(current => current.map(item => item.id === updated.id ? updated : item))
      void loadDocuments()
      setIssueOpen(false)
      setSelectedIssueId('')
      setResolutionNote('')
      setEvidence('')
      setMessage('问题已关闭并记录处置证据')
    } catch (err) {
      setIssueError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleReopenIssue(event: FormEvent) {
    event.preventDefault()
    if (!selectedIssue) return
    setBusy(true)
    setIssueError('')
    setMessage('')
    try {
      const updated = await api.reopenIssue(selectedIssue.id, {
        expected_status: 'closed',
        actor: DEMO_ACTOR,
        role: DEMO_ROLE,
        reason: reopenReason.trim(),
      })
      setIssues(current => current.map(item => item.id === updated.id ? updated : item))
      setIssueOpen(false)
      setSelectedIssueId('')
      setReopenReason('')
      setMessage('问题已重新打开并记录原因')
      void loadDocuments()
    } catch (err) {
      setIssueError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const restoredProgress=draftReady&&documentsReady&&attemptsReady&&phase==='idle'&&!content.trim()&&!hasDraft&&!resumeAttempt&&!documentsError&&!attemptsError
    ?recoverImportProgress(projectId,documents,attempts):null
  const currentProgress={phase:phase==='idle'&&content.trim()?'reviewing' as const:phase,failed:phaseFailure,
    filename:original?.filename??pendingSource?.document.display_code??(content.trim()?`正文录入 · ${displayCode}`:''),
    textOnly:!!content.trim()&&!original&&phase!=='checking'&&phase!=='extracting'}
  return (
    <>
      {error && <Notice kind="error">{error}</Notice>}
      {message && <Notice kind="success">{message}</Notice>}

      <section className="panel" ref={importSection}>
        <div className="panel-heading">
          <h2>来源文档导入与规则解析</h2>
          <span className="mode-badge">规则计算 · 本地离线</span>
        </div>
        <p className="hint">
          主要支持 Word（.docx）和文本 PDF，也可选择 UTF-8 TXT 或直接粘贴文本；保留页码、段落或行号。老版 .doc 请先另存为 .docx，扫描 PDF 不支持 OCR。
          重复、矛盾、缺失条款会保留为问题，不会只取首个匹配。
        </p>
        <ImportProgress {...restoredProgress??currentProgress} />
        {draftWarning && <p className="hint draft-warning">{draftWarning}</p>}
        {draftSaved && <p className="hint">核对草稿已保存在当前浏览器，切换模块或刷新后可继续。归档前草稿不包含在业务备份中。</p>}
        {resumeAttempt && <div className="import-retry"><strong>恢复待核对文件：{resumeAttempt.filename}</strong><p>请选择同一原文件重新提取正文；旧版未保存的手工修改无法恢复。</p><button type="button" className="secondary" disabled={busy} onClick={() => fileInput.current?.click()}>选择原文件恢复核对</button><button type="button" className="secondary" disabled={busy} onClick={() => setResumeAttempt(null)}>取消恢复</button></div>}
        {pendingSource && phaseFailure && <div className="import-retry"><strong>文档已归档，解析尚未完成</strong><p>无需重复创建来源文档，可继续解析已保存的正文。</p><button type="button" disabled={busy} onClick={() => void parseArchived(pendingSource.document, pendingSource.mapping)}>重试已归档文档解析</button></div>}
        <form
          className="form-grid"
          onSubmit={(event) => void handleImport(event)}
        >
          <fieldset className="import-fields" disabled={busy || !draftReady || !!pendingSource}>
          <label className="wide document-upload">选择协议文件
            <input ref={fileInput} aria-label="选择协议文件" type="file" accept=".txt,.pdf,.docx" disabled={busy} onChange={(event) => { const file = event.target.files?.[0]; if (file) void previewFile(file); event.target.value = '' }} />
            <small>最大 8 MiB。先核对文本，导入时同时归档原文件及校验值；人工修改的正文与原文件分别保存。</small>
            {original && <small>待归档：{original.filename} <button type="button" className="secondary" onClick={() => { setOriginal(undefined); setImportId(undefined); setHasDraft(true); setDraftSaved(false) }}>取消原件关联</button></small>}
          </label>
          <label>
            文档编号
            <input
              aria-label="来源文档编号"
              value={displayCode}
              onChange={(event) => { setDisplayCode(event.target.value); setHasDraft(true); setDraftSaved(false) }}
              required
            />
          </label>
          <label>
            文档类型
            <select
              aria-label="来源文档类型"
              value={docType}
              onChange={(event) => {
                setHasDraft(true); setDraftSaved(false); setDocType(
                  event.target.value as SourceDocumentCreate['doc_type'],
                )
              }}
            >
              {Object.entries(docTypeLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            文档版本
            <input
              aria-label="来源文档版本"
              value={version}
              onChange={(event) => { setVersion(event.target.value); setHasDraft(true); setDraftSaved(false) }}
              required
            />
          </label>
          <label className="wide">
            文档正文（文本）
            <textarea
              aria-label="来源文档正文"
              rows={6}
              value={content}
              onChange={(event) => { setContent(event.target.value); setHasDraft(true); setDraftSaved(false);setPhase(current=>current==='saved'?'reviewing':current) }}
              required
            />
          </label>
          <details className="wide import-numbering" open={mappingText.trim() ? true : undefined}>
            <summary>高级选项：自定义显示编号（可选）</summary>
            <p className="hint">普通导入自动生成编号，无需导入 08_需求编号映射.txt。仅需与演示说明的固定编号一致时，才粘贴映射；不改变需求身份与版本追溯。</p>
          <label>
            显示编号映射（每行 key=编号）
            <textarea
              aria-label="显示编号映射"
              rows={3}
              value={mappingText}
              onChange={(event) => { setMappingText(event.target.value); setHasDraft(true); setDraftSaved(false) }}
              placeholder={'engineMaxTorque=REQ-P01-B-003'}
            />
          </label>
          </details>
          <div className="form-actions">
            <button type="submit" disabled={busy}>
              导入并解析
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setContent(SAMPLE_CONTENT)
                setOriginal(undefined)
                setImportId(undefined); setPhase('reviewing'); setPhaseFailure('')
                setMappingText(SAMPLE_MAPPING)
                setImportId(undefined); setDraftSourceId(undefined); setResumeAttempt(null); setHasDraft(true); setDraftSaved(false)
              }}
            >
              填充合成示例
            </button>
          </div>
          </fieldset>
        </form>

        {parseResult && parseResultOrigin === 'import' && !parsePreviewOpen && <ParseResultView result={parseResult} />}
      </section>

      <DocumentImportStatus documents={documents} attempts={attempts} documentsError={documentsError} attemptsError={attemptsError} busy={busy} onRefresh={() => { void loadDocuments(); void loadAttempts() }} onParse={(document, trigger) => { setParseTrigger(trigger); setParseResult(null); setParseResultOrigin('document'); setParsePreviewOpen(true); void parseArchived(document) }} onDiscard={attemptId => void discardPreview(attemptId)} onResume={attempt => void resumePreview(attempt)} />

      {parsePreviewOpen && <DetailOverlay variant="wide" title="文档解析结果" eyebrow="来源文档 · 当前已保存结果" returnFocus={parseTrigger} closeLabel="关闭解析结果" locked={busy} pendingLabel="正在读取解析结果…" onClose={() => setParsePreviewOpen(false)}>
        {error && <Notice kind="error">{error}{pendingSource && <button type="button" disabled={busy} onClick={() => void parseArchived(pendingSource.document, pendingSource.mapping)}>重试读取解析结果</button>}</Notice>}
        {busy && !parseResult && <p role="status">正在读取解析结果…</p>}
        {parseResult && <ParseResultView result={parseResult} />}
      </DetailOverlay>}

      <section className="panel">
        <div className="panel-heading">
          <h2>导入问题与澄清</h2>
          <span className="count">{issues.length} 条</span>
        </div>
        {issuesError && <Notice kind="error">问题列表读取失败：{issuesError}<button type="button" className="secondary" onClick={() => void refreshIssues()}>重试读取问题</button></Notice>}
        {issuesLoading ? (
          <Empty>正在加载问题…</Empty>
        ) : issues.length === 0 ? (
          <Empty>暂无问题记录。</Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>类型</th>
                  <th>严重度</th>
                  <th>类别</th>
                  <th>问题</th>
                  <th>来源</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {issues.map((issue) => (
                  <tr key={issue.id} data-object-id={issue.id}>
                    <td className="mono">{issue.issue_type}</td>
                    <td>
                      {severityLabels[
                        issue.severity as keyof typeof severityLabels
                      ] ?? issue.severity}
                    </td>
                    <td>{issue.category || '—'}</td>
                    <td className="source">
                      <span>{issue.message}</span>
                      <small>
                        建议：{issue.suggestion || '—'}
                        {issue.blocking_reason
                          ? ` · 阻塞：${issue.blocking_reason}`
                          : ''}
                      </small>
                    </td>
                    <td className="source">
                      <span>{issue.source_location || '未记录'}</span>
                      <small>{issue.source_excerpt}</small>
                    </td>
                    <td>
                      <span
                        className={`status ${
                          issue.status === 'closed' ? 'confirmed' : 'rejected'
                        }`}
                      >
                        {issue.status === 'closed' ? '已关闭' : '开放'}
                      </span>
                    </td>
                    <td className="actions">
                      <button
                        type="button"
                        disabled={busy}
                        onClick={event => {
                          setIssueTrigger(event.currentTarget)
                          setIssueOpen(true)
                          if (selectedIssueId !== issue.id) {
                            setResolutionType('manual_supplement')
                            setResolutionNote('')
                            setEvidence('')
                            setReopenReason('')
                            setIssueError('')
                          }
                          setSelectedIssueId(issue.id)
                        }}
                      >
                        {issue.status === 'closed' ? '重开' : '关闭'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {issueOpen && selectedIssue && (
          <DetailOverlay variant="drawer" title="问题处置" eyebrow="协议解析与澄清 · 问题闭环" subtitle={selectedIssue.message} returnFocus={issueTrigger} closeLabel="关闭问题详情" locked={busy} onClose={() => setIssueOpen(false)} footer="关闭仅收起详情，不提交处置；同一问题的本页未提交输入保留。">
          <section className="source-evidence" aria-label="问题来源与证据">
            <h3>来源与阻塞依据</h3>
            <p className="muted">{selectedIssue.status === 'open' ? '开放' : '已关闭'} · {severityLabels[selectedIssue.severity as keyof typeof severityLabels] ?? selectedIssue.severity} · {selectedIssue.category || '未分类'}</p>
            <p>原文位置：{selectedIssue.source_location || '未记录'}</p>
            <blockquote>{selectedIssue.source_excerpt || '缺少原文摘录，请补充来源'}</blockquote>
            <p>阻塞原因：<span>{selectedIssue.blocking_reason || '未记录'}</span></p>
            <p>建议：{selectedIssue.suggestion || '未记录'}</p>
            {selectedIssue.close_reason && <p>上次处置：{selectedIssue.close_reason}</p>}
            <details className="business-evidence"><summary>查看追溯标识</summary><p className="muted">问题 ID：{selectedIssue.id}<br />来源文档：{selectedIssue.source_document_id || '缺失'}<br />关联需求：{selectedIssue.requirement_id || '未关联'}</p></details>
          </section>
          {issueError && <Notice kind="error">{issueError}</Notice>}
          <form
            className="inline-action"
            onSubmit={(event) =>
              void (selectedIssue.status === 'open'
                ? handleCloseIssue(event)
                : handleReopenIssue(event))
            }
          >
            <h3>
              {selectedIssue.status === 'open' ? '关闭' : '重开'}问题：
              {selectedIssue.message}
            </h3>
            {selectedIssue.status === 'open' ? (
              <div className="form-grid">
                <label>
                  处置类型
                  <select
                    aria-label="问题处置类型"
                    value={resolutionType}
                    onChange={(event) =>
                      setResolutionType(event.target.value)
                    }
                  >
                    <option value="manual_supplement">人工补录</option>
                    <option value="evidence_added">补充证据</option>
                    <option value="requirement_clarified">需求澄清</option>
                    <option value="accepted_risk">接受风险</option>
                  </select>
                </label>
                <label className="wide">
                  处置说明
                  <input
                    aria-label="问题处置说明"
                    value={resolutionNote}
                    onChange={(event) =>
                      setResolutionNote(event.target.value)
                    }
                    required
                  />
                </label>
                <label className="wide">
                  证据
                  <input
                    aria-label="问题处置证据"
                    value={evidence}
                    onChange={(event) => setEvidence(event.target.value)}
                    required
                  />
                </label>
              </div>
            ) : (
              <label>
                重开原因
                <input
                  aria-label="问题重开原因"
                  value={reopenReason}
                  onChange={(event) => setReopenReason(event.target.value)}
                  required
                />
              </label>
            )}
            <div className="form-actions">
              <button type="submit" disabled={busy}>
                {selectedIssue.status === 'open' ? '确认关闭' : '确认重开'}
              </button>
            </div>
          </form>
          </DetailOverlay>
        )}
      </section>
    </>
  )
}
