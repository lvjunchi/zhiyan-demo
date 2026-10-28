import { MODULE_TABS, type ModuleTabKey } from './navigation'

export interface WorkStage {
  key: ModuleTabKey
  label: string
  action: string
  record_count: number
  pending_count: number
  stale_count: number
  state: 'empty' | 'attention' | 'reviewed'
  notes: string[]
}
export interface ImpactReference {
  upstream_type: string
  upstream_id: string
  upstream_display_code?: string
  downstream_type: string
  downstream_id: string
  referenced_revision: number
  current_revision: number
  evidence: string
}
export interface ImpactObject {
  object_type: string
  object_id: string
  display_code: string
  revision: number
  review_status: string
  validity: string
  tab: ModuleTabKey
  applicable: boolean
  references: ImpactReference[]
}
export interface RequirementChange {
  requirement_id: string
  display_code: string
  parameter_name: string
  from_revision: number
  to_revision: number
  created_at: string
  before: Record<string, unknown>
  after: Record<string, unknown>
  impacts: ImpactObject[]
}
export interface WorkspaceData {
  project_id: string
  stages: WorkStage[]
  changes: RequirementChange[]
  scope_note: string
}
const object = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)
const strings = (v: Record<string, unknown>, keys: string[]) => keys.every(k => typeof v[k] === 'string')
const integer = (v: unknown, minimum = 0): v is number => typeof v === 'number' && Number.isSafeInteger(v) && v >= minimum
const tab = (v: unknown): v is ModuleTabKey => MODULE_TABS.some(t => t.key === v)
const reference = (v: unknown): v is ImpactReference => object(v) && strings(v, ['upstream_type', 'upstream_id', 'downstream_type', 'downstream_id', 'evidence']) && (v.upstream_display_code === undefined || typeof v.upstream_display_code === 'string') && integer(v.referenced_revision, 1) && integer(v.current_revision, 1)
const impact = (v: unknown): v is ImpactObject => object(v) && strings(v, ['object_type', 'object_id', 'display_code', 'review_status', 'validity']) && integer(v.revision, 1) && tab(v.tab) && typeof v.applicable === 'boolean' && Array.isArray(v.references) && v.references.every(reference)
const change = (v: unknown): v is RequirementChange => object(v) && strings(v, ['requirement_id', 'display_code', 'parameter_name', 'created_at']) && integer(v.from_revision, 1) && integer(v.to_revision, 1) && v.to_revision > v.from_revision && object(v.before) && object(v.after) && Array.isArray(v.impacts) && v.impacts.every(impact)
const stage = (v: unknown): v is WorkStage => object(v) && tab(v.key) && strings(v, ['label', 'action']) && ['empty', 'attention', 'reviewed'].includes(String(v.state)) && ['record_count', 'pending_count', 'stale_count'].every(k => integer(v[k])) && Array.isArray(v.notes) && v.notes.every(n => typeof n === 'string')
export function readWorkspace(value: unknown, projectId: string): WorkspaceData {
  if (!object(value) || value.project_id !== projectId || typeof value.scope_note !== 'string' || !Array.isArray(value.stages) || !value.stages.every(stage) || new Set(value.stages.map(s => s.key)).size !== value.stages.length || !Array.isArray(value.changes) || !value.changes.every(change)) throw new Error('项目操作进度响应无效，请重试')
  return { project_id: projectId, stages: value.stages, changes: value.changes, scope_note: value.scope_note }
}
