import { readWorkspace } from './workspaceTypes'
import { readProjects, readRequirements, readTestPlan, readCoordination, readPackages, readPackage } from './responseValidation'
import type {
  ArtifactConfirmation,
  AuditEvent,
  ConfirmationPayload,
  Conflict,
  ConsistencyCheckPayload,
  CoordinationRecord,
  CoordinationTopic,
  DesignReviewPayload,
  DfmeaPayload,
  MaterialPackageDetail,
  ParseResult,
  ProjectOverview,
  RecommendationResult,
  Requirement,
  RequirementIssue,
  SampleComparison,
  SampleDelivery,
  SimilarProjectsResult,
  SourceDocument,
  SourceDocumentCreate,
  TestCase,
  TestPlanPayload,
  TestRun,
  TraceabilityMatrix,
  VariantAnalysisResult,
} from './types'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown

  constructor(
    status: number,
    code: string,
    message: string,
    details?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

function isObject(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null && !Array.isArray(value) }
function isRevision(value: unknown): value is number { return typeof value === 'number' && Number.isInteger(value) && value >= 1 }
function isEngineeringRecord(value: unknown): value is import('./types').EngineeringRecord {
  return isObject(value) && ['variant', 'part'].includes(String(value.kind)) && typeof value.id === 'string' && typeof value.project_id === 'string' && isRevision(value.revision)
    && (value.base_display_code === undefined || value.base_display_code === null || typeof value.base_display_code === 'string')
    && ['draft', 'pending_review', 'confirmed', 'rejected'].includes(String(value.review_status)) && ['current', 'stale'].includes(String(value.status))
    && (value.is_applicable === 0 || value.is_applicable === 1) && Array.isArray(value.dependency_versions)
    && value.dependency_versions.every(dep => isObject(dep) && ['requirement', 'variant'].includes(String(dep.object_type)) && typeof dep.object_id === 'string' && isRevision(dep.revision))
}

function readProgress(value:unknown,topicId:string):import('./types').ProgressPayload {
 if(!isObject(value)||value.topic_id!==topicId||!Array.isArray(value.rows)||!value.rows.every(row=>isObject(row)&&typeof row.id==='string'&&isRevision(row.revision)&&['participant','milestone','artifact_version','reported_at','evidence'].every(key=>typeof row[key]==='string')&&['planned_percent','actual_percent'].every(key=>typeof row[key]==='number'&&Number.isFinite(row[key])&&Number(row[key])>=0&&Number(row[key])<=100))||!isObject(value.assessment)||typeof value.assessment.rule_label!=='string'||!['low','medium','high','insufficient'].includes(String(value.assessment.risk_level))||typeof value.assessment.thresholds!=='string'||!Array.isArray(value.assessment.data_gaps)||!value.assessment.data_gaps.every(item=>typeof item==='string')||!Array.isArray(value.assessment.alerts)||!value.assessment.alerts.every(row=>isObject(row)&&typeof row.reason==='string'&&typeof row.kind==='string'&&typeof row.level==='string'&&typeof row.milestone==='string'&&['participants','evidence','reported_at'].every(key=>Array.isArray(row[key])&&(row[key] as unknown[]).every(item=>typeof item==='string'))))throw new Error('协同进度响应无效')
 return value as unknown as import('./types').ProgressPayload
}

async function parseError(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => null)
  const error = body?.error
  return new ApiError(
    response.status,
    error?.code ?? 'UNKNOWN_ERROR',
    error?.message ?? `请求失败（HTTP ${response.status}）`,
    error?.details,
  )
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })
  if (!response.ok) throw await parseError(response)
  if (response.status === 204) return undefined as T
  const body = await response.json().catch(() => null)
  if (body === null) throw new ApiError(
    response.status,
    'INVALID_RESPONSE',
    '服务端返回了无法解析的响应',
  )
  if (init?.method && init.method !== 'GET') window.dispatchEvent(new Event('zhiyan:data-changed'))
  return body as T
}

async function requestBlob(
  path: string,
  init?: RequestInit,
): Promise<{ blob: Blob; filename: string | null; sha256: string | null }> {
  const response = await fetch(path, init)
  if (!response.ok) throw await parseError(response)
  const disposition = response.headers.get('content-disposition') ?? ''
  const match = /filename\*=UTF-8''([^;]+)/.exec(disposition)
  return {
    blob: await response.blob(),
    filename: match ? decodeURIComponent(match[1]) : null,
    sha256: response.headers.get('x-content-sha256'),
  }
}

function post<T>(path: string, payload?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body: payload === undefined ? undefined : JSON.stringify(payload),
  })
}

export interface BackupPreview { counts: Record<string, number>; projects: { id: string; name: string; display_code: string }[]; snapshot_sha256: string; expected_state_hash: string }

export const api = {
  getWorkspace: async (projectId: string) => readWorkspace(await request<unknown>(`/api/projects/${projectId}/workspace`), projectId),
  downloadSystemBackup: () => requestBlob('/api/system/backup'),
  previewRestore: async (backup: unknown): Promise<BackupPreview> => {
    const value = await post<BackupPreview>('/api/system/restore-preview', { backup })
    if (!value || typeof value.counts !== 'object' || value.counts === null || !Object.values(value.counts).every(item => typeof item === 'number' && Number.isSafeInteger(item) && item >= 0) || !Array.isArray(value.projects) || !value.projects.every(item => typeof item.id === 'string' && typeof item.name === 'string' && typeof item.display_code === 'string') || typeof value.expected_state_hash !== 'string' || !/^[a-f0-9]{64}$/.test(value.expected_state_hash) || typeof value.snapshot_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(value.snapshot_sha256)) throw new Error('备份预览响应无效')
    return value
  },
  restoreBackup: async (payload: { backup: unknown; expected_state_hash: string; actor: string; role: string }) => {
    const result = await post<unknown>('/api/system/restore', payload)
    if (typeof result !== 'object' || result === null || !('status' in result) || result.status !== 'restored' || !('original_retained' in result) || result.original_retained !== true) throw new Error('恢复响应不完整，请检查运行状态后重新载入')
    return result
  },
  getHealth: async () => {
    const value = await request<unknown>('/api/health')
    if (typeof value !== 'object' || value === null || !('status' in value) || value.status !== 'ok' || !('database' in value) || value.database !== 'connected' || !('schema_version' in value) || typeof value.schema_version !== 'string') throw new Error('服务健康响应不完整，无法确认连接状态')
    return { status: value.status, database: value.database, schema_version: value.schema_version }
  },
  extractDocumentText: async (file: File, projectId?: string) => {
    if (!projectId && file.size > 8 * 1024 * 1024) throw new Error('文档大小不得超过 8 MiB')
    const path = projectId ? `/api/projects/${encodeURIComponent(projectId)}/document-imports/extract` : '/api/document-text'
    const value = await request<unknown>(`${path}?filename=${encodeURIComponent(file.name)}`, { method: 'POST', body: file, headers: { 'Content-Type': 'application/octet-stream' } })
    if (typeof value !== 'object' || value === null || !('content' in value) || typeof value.content !== 'string' || !('warnings' in value) || !Array.isArray(value.warnings) || !value.warnings.every((item: unknown) => typeof item === 'string')) throw new Error('文件提取响应无效')
    if (!('sha256' in value) || typeof value.sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(value.sha256)) throw new Error('原文件校验值缺失，无法关联归档')
    if (projectId && (!('import_id' in value) || typeof value.import_id !== 'string')) throw new Error('导入记录缺失，请重新选择文件')
    return { content: value.content, warnings: value.warnings as string[], sha256: value.sha256, import_id: 'import_id' in value && typeof value.import_id === 'string' ? value.import_id : undefined }
  },
  listDocumentImports: async (projectId: string) => {
    const value = await request<unknown>(`/api/projects/${encodeURIComponent(projectId)}/document-imports`)
    if (!Array.isArray(value) || !value.every(row => isObject(row) && typeof row.id === 'string' && typeof row.filename === 'string'
      && ['awaiting_review', 'failed', 'archived', 'completed', 'cancelled'].includes(String(row.status)) && typeof row.error_message === 'string' && typeof row.stage === 'string'
      && typeof row.created_at === 'string' && (row.source_document_id === null || typeof row.source_document_id === 'string'))) throw new Error('导入记录响应无效')
    return value as import('./types').DocumentImport[]
  },
  discardDocumentImport: (projectId: string, attemptId: string) => post<unknown>(`/api/projects/${encodeURIComponent(projectId)}/document-imports/${encodeURIComponent(attemptId)}/discard`, { expected_status: 'awaiting_review' }),
  previewProjectClear: async (projectId: string) => {
    const value = await post<unknown>(`/api/projects/${encodeURIComponent(projectId)}/clear-preview`)
    const counts = (item: unknown) => isObject(item) && Object.values(item).every(n => typeof n === 'number' && Number.isSafeInteger(n) && n >= 0)
    if (!isObject(value) || !isObject(value.project) || value.project.id !== projectId || typeof value.project.display_code !== 'string' || typeof value.project.name !== 'string'
      || !counts(value.affected_counts) || !counts(value.retained_counts) || typeof value.expected_state_hash !== 'string' || !/^[a-f0-9]{64}$/.test(value.expected_state_hash)) throw new Error('清空预览响应无效，未执行清空')
    return value as unknown as import('./types').ClearPreview
  },
  clearProject: async (projectId: string, payload: { expected_state_hash: string; confirmation_code: string; actor: string; role: string }) => {
    const value = await post<unknown>(`/api/projects/${encodeURIComponent(projectId)}/clear`, payload)
    if (!isObject(value) || value.status !== 'cleared' || value.original_retained !== true || typeof value.backup_url !== 'string' || !/^\/api\/system\/clear-backups\/[a-f0-9]{32}$/.test(value.backup_url)
      || typeof value.backup_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(value.backup_sha256)) throw new Error('清空响应不完整，请重新载入核对数据')
    return { backup_url: value.backup_url, backup_sha256: value.backup_sha256 }
  },
  listProjects: async () => readProjects(await request<unknown>('/api/projects')),
  getProjectOverview: (projectId: string) =>
    request<ProjectOverview>(`/api/projects/${projectId}/overview`),
  listRequirements: async (projectId: string) =>
    readRequirements(await request<unknown>(`/api/projects/${projectId}/requirements`)),
  requirementRevisions: async (requirementId: string) => {
    const value = await request<unknown>(`/api/requirements/${requirementId}/revisions`)
    if (!Array.isArray(value) || !value.every(row => isObject(row) && isRevision(row.revision_no) && isObject(row.snapshot))) throw new Error('需求版本响应无效')
    return value as import('./types').RequirementRevision[]
  },
  requirementConfirmations: async (requirementId: string) => {
    const value = await request<unknown>(`/api/requirements/${requirementId}/confirmations`)
    if (!Array.isArray(value) || !value.every(row => isObject(row)
      && typeof row.id === 'string' && row.object_id === requirementId && row.object_type === 'requirement'
      && isRevision(row.object_revision) && ['confirmed', 'rejected'].includes(String(row.decision))
      && typeof row.actor === 'string' && typeof row.role === 'string'
      && typeof row.comment === 'string' && typeof row.created_at === 'string')) throw new Error('需求审核记录响应无效')
    return value as AuditEvent[]
  },
  confirmRequirement: (
    requirementId: string,
    payload: ConfirmationPayload,
  ) =>
    request<AuditEvent>(
      `/api/requirements/${requirementId}/confirmations`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    ),
  previewRequirementBatch: async (projectId: string, items: {requirement_id:string;expected_revision:number}[]) => {
    const value = await post<unknown>(`/api/projects/${encodeURIComponent(projectId)}/requirements/batch-preview`,{items})
    if (!isObject(value) || value.project_id !== projectId || value.selected_count !== items.length || typeof value.preview_hash !== 'string' || !/^[a-f0-9]{64}$/.test(value.preview_hash)
      || typeof value.can_submit !== 'boolean' || !Array.isArray(value.rows) || value.rows.length !== items.length
      || !value.rows.every(row=>isObject(row) && isObject(row.requirement) && items.map(item=>item.requirement_id).includes(String(row.requirement.id)) && typeof row.eligible==='boolean' && Array.isArray(row.reasons) && row.reasons.every((reason:unknown)=>typeof reason==='string'))) throw new Error('批量审核预览响应无效')
    readRequirements(value.rows.map(row=>row.requirement))
    return value as unknown as import('./types').RequirementBatchPreview
  },
  confirmRequirementBatch: async (projectId:string, payload:{items:{requirement_id:string;expected_revision:number}[];expected_preview_hash:string;actor:string;role:string;comment:string}) => {
    const value = await post<unknown>(`/api/projects/${encodeURIComponent(projectId)}/requirements/batch-confirm`,payload)
    if (!isObject(value) || value.project_id !== projectId || value.confirmed_count !== payload.items.length || !Array.isArray(value.events) || value.events.length !== payload.items.length
      || !value.events.every(event=>isObject(event) && typeof event.id==='string' && event.decision==='confirmed' && payload.items.some(item=>item.requirement_id===event.object_id && item.expected_revision===event.object_revision))
      || new Set(value.events.map(event=>event.object_id)).size !== payload.items.length) throw new Error('批量审核返回不完整，请重新读取列表核对保存结果')
    return {confirmed_count:value.confirmed_count as number}
  },
  updateRequirement: (
    requirementId: string,
    payload: Record<string, unknown>,
  ) =>
    request<Requirement>(`/api/requirements/${requirementId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  createSourceDocument: (
    projectId: string,
    payload: SourceDocumentCreate,
  ) => post<SourceDocument>(
    `/api/projects/${projectId}/source-documents`,
    payload,
  ),
  listSourceDocuments: async (projectId: string) => {
    const value = await request<unknown>(`/api/projects/${projectId}/source-documents`)
    if (!Array.isArray(value) || !value.every(row => isObject(row) && typeof row.id === 'string' && typeof row.display_code === 'string' && typeof row.version === 'string'
      && (row.original_file == null || (isObject(row.original_file) && typeof row.original_file.filename === 'string' && typeof row.original_file.sha256 === 'string' && /^[0-9a-f]{64}$/.test(row.original_file.sha256) && typeof row.original_file.size_bytes === 'number' && row.original_file.size_bytes > 0 && typeof row.original_file.reviewed_text_changed === 'boolean')))) throw new Error('来源文档响应无效')
    if (!value.every(row => row.parse_summary === undefined || (isObject(row.parse_summary) && ['pending_parse', 'parsed', 'needs_manual_review'].includes(String(row.parse_summary.status))
      && ['requirement_count', 'pending_requirement_count', 'issue_count', 'open_issue_count', 'closed_issue_count'].every(key => typeof row.parse_summary[key] === 'number' && Number.isSafeInteger(row.parse_summary[key]) && row.parse_summary[key] >= 0)))) throw new Error('文档解析统计响应无效')
    return value as SourceDocument[]
  },
  getWorkflowSummary: async (projectId:string)=>{
    const value=await request<unknown>(`/api/projects/${encodeURIComponent(projectId)}/workflow-summary`)
    if(!isObject(value)||!isObject(value.testing)||!isObject(value.testing.review)||!isObject(value.testing.execution)||!Array.isArray(value.testing.cases)||!isObject(value.samples)||!Array.isArray(value.samples.rows)||!isObject(value.consistency)||!Array.isArray(value.consistency.scope)||!value.consistency.scope.every(item=>typeof item==='string')||!Array.isArray(value.consistency.changes))throw new Error('业务进度响应无效')
    const count=(item:unknown)=>typeof item==='number'&&Number.isInteger(item)&&item>=0
    if(!['total','stale','valid_coverage_cases'].every(key=>count((value.testing as Record<string,unknown>)[key]))||!['draft','pending_review','confirmed','rejected'].every(key=>count((value.testing as {review:Record<string,unknown>}).review[key]))||!['not_run','pass','fail','incomplete','invalid'].every(key=>count((value.testing as {execution:Record<string,unknown>}).execution[key]))||typeof value.testing.plan_status!=='string'||!value.testing.cases.every(row=>isObject(row)&&typeof row.id==='string'&&isRevision(row.revision)&&typeof row.execution==='string'&&typeof row.review_status==='string'&&typeof row.validity==='string'&&count(row.historical_runs))||!['total','compared','confirmed'].every(key=>count((value.samples as Record<string,unknown>)[key]))||!value.samples.rows.every(row=>isObject(row)&&typeof row.id==='string'&&typeof row.display_code==='string'&&typeof row.result==='string'&&typeof row.review_status==='string'&&count(row.open_issues)&&count(row.current_step)&&Array.isArray(row.steps)&&row.steps.every(step=>isObject(step)&&typeof step.label==='string'&&typeof step.done==='boolean'))||!value.consistency.changes.every(row=>isObject(row)&&['id','label','kind','parameter','before','after','unit','versions','state','evidence'].every(key=>typeof row[key]==='string')))throw new Error('业务进度数据无效')
    return value as unknown as import('./types').WorkflowSummary
  },
  getCoordinationProgress: async (topicId:string)=>readProgress(await request<unknown>(`/api/coordination-topics/${encodeURIComponent(topicId)}/progress`),topicId),
  saveCoordinationProgress: async (topicId:string,payload:{participant:string;milestone:string;planned_percent:number;actual_percent:number;artifact_version:string;reported_at:string;evidence:string;expected_revision:number;actor:string;role:string})=>readProgress(await post<unknown>(`/api/coordination-topics/${encodeURIComponent(topicId)}/progress`,payload),topicId),
  listPartChoices: async (projectId:string) => {
    const value=await request<unknown>(`/api/projects/${encodeURIComponent(projectId)}/part-candidates`)
    const states=['unselected','pending_review','confirmed','rejected','recheck']
    if(!isObject(value)||value.mode!=='rule'||typeof value.catalog_source!=='string'||!isObject(value.counts)||!states.every(key=>Number.isInteger(value.counts && (value.counts as Record<string,unknown>)[key]))||!Array.isArray(value.parts)||!value.parts.every(group=>isObject(group)&&isEngineeringRecord(group.record)&&(group.confirmation_blockers===undefined||(Array.isArray(group.confirmation_blockers)&&group.confirmation_blockers.every(reason=>typeof reason==='string')))&&group.record.project_id===projectId&&typeof (group.record as unknown as Record<string,unknown>).part_number==='string'&&states.includes(String(group.selection_state))&&(group.selected_candidate_id===null||typeof group.selected_candidate_id==='string')&&Array.isArray(group.candidates)&&group.candidates.every(candidate=>isObject(candidate)&&typeof candidate.id==='string'&&typeof candidate.model_code==='string'&&typeof candidate.part_name==='string'&&typeof candidate.image_key==='string'&&typeof candidate.source==='string'&&typeof candidate.material==='string'&&typeof candidate.limitations==='string'&&typeof candidate.rated_torque_nm==='number'&&Number.isFinite(candidate.rated_torque_nm)&&Number.isInteger(candidate.max_gears)&&['pass','fail','incomplete'].includes(String(candidate.fit))&&Array.isArray(candidate.checks)&&candidate.checks.every(check=>isObject(check)&&typeof check.requirement_id==='string'&&isRevision(check.revision)&&typeof check.parameter==='string'&&typeof check.unit==='string'&&typeof check.capacity==='number'&&['pass','fail','incomplete'].includes(String(check.result))))))throw new Error('零件选型响应无效，请重新读取')
    return value as unknown as import('./types').PartChoices
  },
  selectPartCandidate: async (objectId:string,payload:{candidate_id:string;expected_revision:number;actor:string;role:string;comment:string})=>{
    const value=await post<unknown>(`/api/engineering-records/part/${encodeURIComponent(objectId)}/selection`,payload)
    if(!isObject(value)||value.id!==objectId||!isRevision(value.revision)||typeof value.part_number!=='string')throw new Error('型号选择返回无效，请重新读取确认保存结果')
    return value as unknown as import('./types').EngineeringRecord & {part_number:string}
  },
  getDesignContext: async (projectId: string): Promise<{base_display_code:string|null;source:'variant_analysis'|'none'}> => {
    const value=await request<unknown>(`/api/projects/${projectId}/design-context`)
    if(!isObject(value)||(value.base_display_code!==null&&typeof value.base_display_code!=='string')||!['variant_analysis','none'].includes(String(value.source)))throw new Error('设计基型上下文无效')
    return value as {base_display_code:string|null;source:'variant_analysis'|'none'}
  },
  listEngineeringRecords: async (projectId: string) => {
    const value = await request<unknown>(`/api/projects/${projectId}/engineering-records`)
    if (!Array.isArray(value) || !value.every(isEngineeringRecord)) throw new Error('工程决策响应无效')
    return value
  },
  engineeringDetail: async (kind: 'variant' | 'part', objectId: string) => {
    const value = await request<unknown>(`/api/engineering-records/${kind}/${objectId}`)
    if (!isObject(value) || value.kind !== kind || !isEngineeringRecord(value.current) || value.current.id !== objectId || !Array.isArray(value.versions) || !value.versions.every(row => isObject(row) && isRevision(row.revision) && isObject(row.snapshot))
      || !Array.isArray(value.confirmations) || !value.confirmations.every(row => isObject(row) && typeof row.id === 'string' && typeof row.actor === 'string' && typeof row.decision === 'string' && isRevision(row.object_revision))) throw new Error('工程版本响应无效')
    return value as unknown as import('./types').EngineeringDetail
  },
  confirmEngineering: async (kind: 'variant' | 'part', objectId: string, payload: ConfirmationPayload) => {
    const value = await post<unknown>(`/api/engineering-records/${kind}/${objectId}/confirmations`, payload)
    if (!isObject(value) || typeof value.id !== 'string' || value.object_id !== objectId || value.object_revision !== payload.expected_revision || value.decision !== payload.decision) throw new Error('工程审核响应无效')
    return value
  },
  confirmEngineeringBatch: async (projectId:string,payload:{actor:string;role:string;items:{kind:'variant'|'part';object_id:string;expected_revision:number}[]}) => {
    const value=await post<unknown>(`/api/projects/${encodeURIComponent(projectId)}/engineering-confirmations`,payload)
    if(!isObject(value)||value.confirmed_count!==payload.items.length)throw new Error('批量审核响应无效，请重新读取已保存结果')
    return {confirmed_count:payload.items.length}
  },
  parseSourceDocument: (
    sourceDocumentId: string,
    displayCodeMap: Record<string, string>,
  ) => post<ParseResult>(
    `/api/source-documents/${sourceDocumentId}/parse`,
    { display_code_map: displayCodeMap },
  ),
  listIssues: (projectId: string) =>
    request<RequirementIssue[]>(`/api/projects/${projectId}/issues`),
  closeIssue: (issueId: string, payload: Record<string, unknown>) =>
    post<RequirementIssue>(`/api/issues/${issueId}/close`, payload),
  reopenIssue: (issueId: string, payload: Record<string, unknown>) =>
    post<RequirementIssue>(`/api/issues/${issueId}/reopen`, payload),

  recommendBases: (projectId: string, topN: number) =>
    post<RecommendationResult>(
      `/api/projects/${projectId}/recommend-bases`,
      { top_n: topN },
    ),
  runVariantAnalysis: (projectId: string, baseDisplayCode: string) =>
    post<VariantAnalysisResult>(
      `/api/projects/${projectId}/variant-analysis`,
      { base_display_code: baseDisplayCode },
    ),

  findSimilarProjects: (projectId: string, topN: number) =>
    post<SimilarProjectsResult>(
      `/api/projects/${projectId}/similar-projects`,
      { top_n: topN },
    ),
  generateDesignReview: (projectId: string, baseDisplayCode: string) =>
    post<DesignReviewPayload>(
      `/api/projects/${projectId}/design-review`,
      { base_display_code: baseDisplayCode },
    ),
  getDesignReview: (projectId: string) =>
    request<DesignReviewPayload>(`/api/projects/${projectId}/design-review`),
  confirmDesignReview: (
    reviewId: string,
    payload: Record<string, unknown>,
  ) => post<ArtifactConfirmation>(
    `/api/design-reviews/${reviewId}/confirmations`,
    payload,
  ),
  generateDfmea: (projectId: string, baseDisplayCode: string) =>
    post<DfmeaPayload>(`/api/projects/${projectId}/dfmea`, {
      base_display_code: baseDisplayCode,
    }),
  getDfmea: (projectId: string) =>
    request<DfmeaPayload>(`/api/projects/${projectId}/dfmea`),
  updateFmeaItem: (itemId: string, payload: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/api/fmea-items/${itemId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  confirmFmeaScores: (itemId: string, payload: Record<string, unknown>) =>
    post<Record<string, unknown>>(
      `/api/fmea-items/${itemId}/confirm-scores`,
      payload,
    ),
  confirmDfmea: (fmeaId: string, payload: Record<string, unknown>) =>
    post<ArtifactConfirmation>(
      `/api/fmea-documents/${fmeaId}/confirmations`,
      payload,
    ),

  generateTestPlan: (projectId: string) =>
    post<TestPlanPayload>(`/api/projects/${projectId}/test-plan`),
  getTestPlan: async (projectId: string) =>
    readTestPlan(await request<unknown>(`/api/projects/${projectId}/test-plan`)),
  confirmTestPlan: (planId: string, payload: Record<string, unknown>) =>
    post<ArtifactConfirmation>(
      `/api/test-plans/${planId}/confirmations`,
      payload,
    ),
  confirmTestCase: (caseId: string, payload: Record<string, unknown>) =>
    post<{ case: TestCase }>(
      `/api/test-cases/${caseId}/confirmations`,
      payload,
    ),
  updateTestCase: (caseId: string, payload: Record<string, unknown>) =>
    request<TestCase>(`/api/test-cases/${caseId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  recordTestRun: (caseId: string, payload: Record<string, unknown>) =>
    post<{ case: TestCase; run: TestRun }>(
      `/api/test-cases/${caseId}/runs`,
      payload,
    ),
  getTraceabilityMatrix: (projectId: string) =>
    request<TraceabilityMatrix>(
      `/api/projects/${projectId}/traceability-matrix`,
    ),

  listSampleDeliveries: (projectId: string) =>
    request<SampleDelivery[]>(
      `/api/projects/${projectId}/sample-deliveries`,
    ),
  createSampleDelivery: (
    projectId: string,
    payload: Record<string, unknown>,
  ) => post<SampleDelivery>(
    `/api/projects/${projectId}/sample-deliveries`,
    payload,
  ),
  getSampleComparison: (deliveryId: string) =>
    request<SampleComparison>(
      `/api/sample-deliveries/${deliveryId}/comparison`,
    ),
  createSampleComparison: (
    deliveryId: string,
    payload: Record<string, unknown>,
  ) => post<SampleComparison>(
    `/api/sample-deliveries/${deliveryId}/comparison`,
    payload,
  ),
  confirmSampleComparison: (
    comparisonId: string,
    payload: Record<string, unknown>,
  ) => post<ArtifactConfirmation>(
    `/api/sample-comparisons/${comparisonId}/confirmations`,
    payload,
  ),
  uploadSampleFile: (
    deliveryId: string,
    file: File,
    actor: string,
  ) => {
    const params = new URLSearchParams({ file_name: file.name, actor })
    return request<SampleDelivery>(
      `/api/sample-deliveries/${deliveryId}/file?${params.toString()}`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': file.type || 'application/octet-stream',
        },
        body: file,
      },
    )
  },

  runConsistencyCheck: (projectId: string) =>
    post<ConsistencyCheckPayload>(
      `/api/projects/${projectId}/consistency-checks`,
    ),
  getLatestConsistencyCheck: (projectId: string) =>
    request<ConsistencyCheckPayload>(
      `/api/projects/${projectId}/consistency-checks/latest`,
    ),
  listConflicts: (projectId: string) =>
    request<Conflict[]>(`/api/projects/${projectId}/conflicts`),
  confirmConsistencyCheck: (
    checkId: string,
    payload: Record<string, unknown>,
  ) => post<ArtifactConfirmation>(
    `/api/consistency-checks/${checkId}/confirmations`,
    payload,
  ),
  closeConflict: (conflictId: string, payload: Record<string, unknown>) =>
    post<Conflict>(`/api/conflicts/${conflictId}/close`, payload),

  getCoordinationOverview: async (projectId: string) =>
    readCoordination(await request<unknown>(
      `/api/projects/${projectId}/coordination-overview`,
    )),
  createCoordinationTopic: (
    projectId: string,
    payload: Record<string, unknown>,
  ) => post<CoordinationTopic>(
    `/api/projects/${projectId}/coordination-topics`,
    payload,
  ),
  createCoordinationRecord: (
    topicId: string,
    payload: Record<string, unknown>,
  ) => post<CoordinationRecord>(
    `/api/coordination-topics/${topicId}/records`,
    payload,
  ),
  calculateCoordinationMetrics: (
    topicId: string,
    payload: Record<string, unknown>,
  ) => post<Record<string, unknown>>(
    `/api/coordination-topics/${topicId}/metrics`,
    payload,
  ),
  acceptCoordinationRisk: (
    topicId: string,
    payload: Record<string, unknown>,
  ) => post<Record<string, unknown>>(
    `/api/coordination-topics/${topicId}/risk-acceptances`,
    payload,
  ),

  listMaterialPackages: async (projectId: string) =>
    readPackages(await request<unknown>(
      `/api/projects/${projectId}/material-packages`,
    )),
  createMaterialPackage: (
    projectId: string,
    payload: Record<string, unknown>,
  ) => post<MaterialPackageDetail>(
    `/api/projects/${projectId}/material-packages`,
    payload,
  ),
  getMaterialPackage: async (packageId: string) =>
    readPackage(await request<unknown>(`/api/material-packages/${packageId}`)),
  approveMaterialPackage: (
    packageId: string,
    payload: Record<string, unknown>,
  ) => post<MaterialPackageDetail>(
    `/api/material-packages/${packageId}/approvals`,
    payload,
  ),
  downloadMaterialPackage: (packageId: string) =>
    requestBlob(`/api/material-packages/${packageId}/download`),
}
