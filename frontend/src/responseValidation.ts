import type { CoordinationOverview, MaterialPackageDetail, MaterialPackageSummary, Project, Requirement, TestPlanPayload } from './types'

type JsonObject = Record<string, unknown>
const object = (value: unknown): value is JsonObject => typeof value === 'object' && value !== null && !Array.isArray(value)
const strings = (row: JsonObject, keys: string[]) => keys.every(key => typeof row[key] === 'string')
const array = (value: unknown): value is unknown[] => Array.isArray(value)
const count = (value: unknown) => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
const revision = (value: unknown) => count(value) && Number(value) > 0
const review = (value: unknown) => ['draft', 'pending_review', 'confirmed', 'rejected'].includes(String(value))
const validity = (value: unknown) => ['current', 'stale'].includes(String(value))
const hash = (value: unknown) => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)
const identity = (value: unknown): value is JsonObject => object(value) && strings(value, ['id', 'display_code'])
const artifact = (value: unknown): value is JsonObject => identity(value) && revision(value.revision)

function checked<T>(value: unknown, valid: boolean, label: string): T {
  if (!valid) throw new Error(`${label}响应无效，请刷新或检查本地服务`)
  return value as T
}

export function readProjects(value: unknown): Project[] {
  return checked(value, array(value) && value.every(row => identity(row) && strings(row, ['name', 'customer', 'product'])), '项目')
}

export function readRequirements(value: unknown): Requirement[] {
  return checked(value, array(value) && value.every(row => identity(row) && revision(row.current_revision)
    && review(row.review_status) && validity(row.validity) && strings(row, ['parameter_name', 'data_type', 'operator', 'value_text', 'unit'])), '需求')
}

export function readTestPlan(value: unknown): TestPlanPayload {
  const valid = object(value) && artifact(value.plan) && review(value.plan.status) && array(value.confirmations)
    && array(value.cases) && value.cases.every(row => artifact(row) && review(row.review_status) && validity(row.validity)
      && strings(row, ['title', 'conditions_text', 'load_conditions_text', 'acceptance_criteria'])
      && array(row.requirement_refs) && row.requirement_refs.every(ref => object(ref) && typeof ref.requirement_id === 'string' && revision(ref.revision))
      && array(row.fmea_refs) && row.fmea_refs.every(ref => object(ref) && typeof ref.fmea_item_id === 'string' && revision(ref.revision))
      && array(row.runs))
  return checked(value, valid, '试验方案')
}

export function readCoordination(value: unknown): CoordinationOverview {
  const valid = object(value) && typeof value.project_id === 'string' && count(value.topic_count) && count(value.metrics_available)
    && ['high', 'medium', 'low', 'insufficient'].includes(String(value.highest_risk)) && array(value.topics)
    && value.topics.every(row => identity(row) && array(row.expected_participants) && row.expected_participants.every(item => typeof item === 'string')
      && array(row.records) && array(row.risk_acceptances) && (row.latest_metrics === null || (object(row.latest_metrics)
        && typeof row.latest_metrics.id === 'string' && object(row.latest_metrics.metrics) && object(row.latest_metrics.risk) && object(row.latest_metrics.cost)
        && validity(row.latest_metrics.validity) && hash(row.latest_metrics.inputs_sha256))))
  return checked(value, valid, '协同')
}

function packageSummary(value: unknown): value is JsonObject {
  return identity(value) && typeof value.project_id === 'string' && revision(value.package_no)
    && ['draft', 'ready_to_submit', 'human_approved'].includes(String(value.status))
    && hash(value.snapshot_hash) && hash(value.zip_sha256) && count(value.zip_size)
}

export function readPackages(value: unknown): MaterialPackageSummary[] {
  return checked(value, array(value) && value.every(packageSummary), '材料列表')
}

export function readPackage(value: unknown): MaterialPackageDetail {
  return checked(value, packageSummary(value) && object(value.snapshot) && object(value.manifest) && array(value.manifest.files)
    && object(value.gate) && array(value.gate.checks) && array(value.gate.blockers) && array(value.gate.warnings)
    && object(value.gate.summary) && count(value.gate.summary.check_count) && count(value.gate.summary.passed_check_count), '材料详情')
}
