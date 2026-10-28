export type ReviewStatus =
  | 'draft'
  | 'pending_review'
  | 'confirmed'
  | 'rejected'

export type Validity = 'current' | 'stale'
export type ExecutionResult =
  | 'pass'
  | 'fail'
  | 'incomplete'
  | 'invalid'
  | 'not_run'
export type Severity = 'blocking' | 'high' | 'medium' | 'low'
export type RiskLevel = 'high' | 'medium' | 'low' | 'insufficient'
export type Mode = 'rule' | 'mock' | 'manual'

export interface EngineeringRecord {
  part_number?: string
  kind: 'variant' | 'part'
  id: string
  project_id: string
  base_display_code?: string | null
  revision: number
  review_status: string
  status: string
  is_applicable: number
  display_code?: string
  parameter_name?: string
  part_display_code?: string
  part_name?: string
  dependency_versions: { object_type: string; object_id: string; revision: number }[]
}
export interface EngineeringDetail {
  kind: 'variant' | 'part'
  current: EngineeringRecord
  versions: { revision: number; snapshot: Record<string, unknown> }[]
  confirmations: { id: string; actor: string; role: string; decision: string; comment: string; object_revision: number; created_at: string }[]
}

export interface Project {
  id: string
  display_code: string
  name: string
  customer: string
  product: string
  stage: string
  created_at: string
  updated_at: string
}

export interface OverviewArtifact {
  display_code: string
  status: string
  revision: number
  item_count: number
  missing_inputs: string[]
  needs_reconfirmation: boolean
  mode: Mode
}

export interface ProjectOverview {
  cockpit?: {
    parameters: {
      requirement_id: string
      key: string | null
      display_code: string
      label: string
      operator: string
      value_text: string
      unit: string
      revision: number
      review_status: ReviewStatus
      validity: Validity
    }[]
    traceability_items: OverviewTraceItem[]
    resources: { source_documents: number; product_bases: number; history_projects: number }
    risk_topics: {
      id: string
      name: string
      mode: Mode
      created_at: string
      risk_level: RiskLevel
      reasons: string[]
      average_response_hours: number | null
      iteration_count: number | null
      absence_rate: number | null
      response_latencies_hours: number[]
      window_start: string
      window_end: string
      headline?: string | null
      source_label?: string | null
      rule_label?: string | null
      progress?: ProgressPayload
      records?: CoordinationRecord[]
      expected_participants?: string[]
      rule_conditions?: { key: string; label: string; actual: number | null; threshold: number; hit: boolean; available: boolean }[]
      metric_details?: {response_sample_size: number | null; expected_participants: string[] | null; actual_participants: string[] | null; absent_participants: string[] | null; data_gaps: string[] | null}
    }[]
    recent_activity: Pick<AuditEvent, 'id' | 'project_id' | 'object_type' | 'object_id' | 'object_revision' | 'action' | 'actor' | 'created_at'>[]
  }
  project: {
    id: string
    display_code: string
    name: string
    customer: string
    product: string
    stage: string
    updated_at: string
  }
  requirements: {
    total: number
    confirmed: number
    draft: number
    pending_review: number
    rejected: number
    stale: number
  }
  issues: {
    open: number
    closed: number
    open_by_severity: Record<Severity, number>
  }
  spectrum: {
    variant_points: number
    stale_variant_points: number
    reusable_parts: number
  }
  design_review: OverviewArtifact | null
  dfmea:
    | (OverviewArtifact & { pending_score_count: number })
    | null
  traceability: {
    mode: Mode
    scope_label: string
    denominator: number
    covered_count: number
    coverage_percentage: number
    execution_summary: Record<string, number>
  } | null
  samples: {
    delivery_count: number
    comparison_count: number
    latest_status: string | null
    latest_result: ExecutionResult | null
  }
  consistency: {
    check: {
      display_code: string
      status: string
      validity: Validity
      revision: number
      summary: Record<string, unknown>
    }
    open_conflicts: number
    blocking_open: number
    review_pending: number
  } | null
  coordination: {
    topic_count: number
    record_count: number
    metrics_available: number
    highest_risk: RiskLevel
    high_risk_topics: number
    rule_label: string
    source_label: string
  }
  package: {
    requires_regeneration?: boolean
    id: string
    display_code: string
    status: 'draft' | 'ready_to_submit' | 'human_approved'
    blocker_count: number
    warning_count: number
    snapshot_hash: string
    created_at: string
    frozen_at: string | null
  } | null
}

export interface Requirement {
  id: string
  project_id: string
  display_code: string
  category: string
  parameter_name: string
  data_type: string
  operator: string
  value_text: string
  value_num: number | null
  value_num_high: number | null
  unit: string
  raw_expression: string
  source_document_id: string | null
  source_location: string
  source_excerpt: string
  review_status: ReviewStatus
  validity: Validity
  current_revision: number
  parser_key?: string
  condition_text?: string
  created_at: string
  updated_at: string
}

export interface ConfirmationPayload {
  expected_revision: number
  actor: string
  role: string
  decision: 'confirmed' | 'rejected'
  comment: string
}

export interface AuditEvent {
  id: string
  project_id: string
  object_type: string
  object_id: string
  object_revision: number | null
  action: string
  actor: string
  role: string
  decision: string | null
  comment: string
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  created_at: string
}

export interface SourceDocumentCreate {
  import_id?: string
  original_file?: { filename: string; data_base64: string; sha256: string }
  display_code: string
  doc_type:
    | 'protocol'
    | 'change_notice'
    | 'drawing'
    | 'test_report'
    | 'communication'
    | 'other'
  version: string
  content: string
  mode: Mode
}

export interface SourceDocument {
  parse_summary?: { status: 'pending_parse' | 'parsed' | 'needs_manual_review'; requirement_count: number; pending_requirement_count: number; issue_count: number; open_issue_count: number; closed_issue_count: number }
  original_text?: string
  original_file?: { filename: string; sha256: string; size_bytes: number; reviewed_text_changed: boolean } | null
  id: string
  project_id: string
  display_code: string
  doc_type: string
  version: string
  content_hash: string
  mode: Mode
  created_at: string
  parsed_at: string | null
}

export interface DocumentImport {
  project_id?: string; updated_at?: string
  sha256?: string; size_bytes?: number
  id: string; filename: string; status: 'awaiting_review' | 'failed' | 'archived' | 'completed' | 'cancelled'
  stage: string; error_message: string; created_at: string; source_document_id: string | null
}
export interface ClearPreview {
  project: { id: string; display_code: string; name: string }
  affected_counts: Record<string, number>; retained_counts: Record<string, number>; expected_state_hash: string
}

export interface RequirementRevision {
  revision_no: number
  snapshot: Partial<Requirement>
  source_location?: string
  source_excerpt?: string
}

export interface RequirementBatchPreview {
  project_id: string; selected_count: number; preview_hash: string; can_submit: boolean
  rows: { requirement: Requirement; eligible: boolean; reasons: string[] }[]
}

export interface RequirementIssue {
  id: string
  project_id: string
  source_document_id: string | null
  requirement_id: string | null
  parser_key: string
  issue_type: string
  category: string
  severity: string
  message: string
  source_location: string
  source_excerpt: string
  blocking_reason: string
  suggestion: string
  status: 'open' | 'closed'
  created_at: string
  closed_at: string | null
  close_reason: string | null
}

export interface ParseResult {
  source_document_id: string
  project_id: string
  mode: Mode
  status: string
  already_parsed: boolean
  parsed_at: string
  requirements: Requirement[]
  issues: RequirementIssue[]
  missing_categories: string[]
  unrecognized_clauses: string[]
  references: Record<string, unknown>[]
}

export interface CriterionResult {
  criterion: string
  requirement_value: string | null
  candidate_value: string | null
  weight: number
  score: number | null
  satisfied: boolean | null
  hard_constraint: boolean
  reason: string
  source: string
}

export interface CandidateBase {
  id: string
  display_code: string
  name: string
  transmission_type: string
  gear_count: number
  rated_input_torque: number
  first_gear_ratio: number
  top_gear_type: string
  has_pto: boolean
  weight_kg: number
  source: string
}

export interface BaseEvaluation {
  base: CandidateBase
  score: number
  hard_failures: string[]
  satisfied_items: string[]
  unsatisfied_items: string[]
  missing_items: string[]
  criteria: CriterionResult[]
}

export interface RecommendationResult {
  project_id: string
  top_n: number
  candidate_count: number
  candidate_shortage: boolean
  missing_requirements: string[]
  requirement_versions: Record<string, unknown>[]
  top3: BaseEvaluation[]
}

export interface VariantPoint {
  id: string
  project_id: string
  base_id: string
  display_code: string
  parameter_key: string
  parameter_name: string
  base_value: string
  requirement_value: string
  variant_type: string
  affected_parts: string[]
  upstream_requirement_ids: string[]
  basis: string
  status: Validity
  created_at: string
  updated_at: string
}

export interface ReusablePartDecision {
  id: string
  project_id: string
  base_id: string
  variant_point_id: string | null
  part_display_code: string
  part_name: string
  part_number: string
  classification: 'carryover' | 'modify' | 'new_design'
  reason: string
  source: string
  variant_keys: string[]
  status: Validity
  created_at: string
  updated_at: string
}

export interface VariantAnalysisResult {
  project_id: string
  base: CandidateBase
  variants: VariantPoint[]
  stale_variants: VariantPoint[]
  reusable_parts: ReusablePartDecision[]
  stale_reusable_parts: ReusablePartDecision[]
  pending_items: string[]
  requirement_versions: Record<string, unknown>[]
}

export interface SimilarMatch {
  history_project_id: string
  display_code: string
  name: string
  customer: string
  score: number
  matched_points: string[]
  differences: string[]
  missing_criteria: string[]
  criteria: CriterionResult[]
  source: string
  notes: string
}

export interface SimilarProjectsResult {
  project_id: string
  mode: Mode
  source_label: string
  candidate_count: number
  top_n: number
  candidate_shortage: boolean
  missing_criteria: string[]
  requirement_versions: Record<string, unknown>[]
  matches: SimilarMatch[]
}

export interface DesignReviewItem {
  id: string
  display_code: string
  revision: number
  status: string
  check_point: string
  standard_basis: string
  responsible_role: string
  dependencies: Record<string, unknown>[]
}

export interface ArtifactConfirmation {
  id: string
  actor: string
  role: string
  decision: string
  comment: string
  created_at: string
  [key: string]: unknown
}

export interface DesignReviewPayload {
  review: {
    id: string
    project_id: string
    display_code: string
    base_display_code: string | null
    revision: number
    status: string
    created_at: string
    updated_at: string
  }
  items: DesignReviewItem[]
  inputs_snapshot: Record<string, unknown>
  missing_inputs: string[]
  confirmations: ArtifactConfirmation[]
  needs_reconfirmation: boolean
  mode: Mode
}

export interface FmeaItem {
  id: string
  display_code: string
  revision: number
  status: string
  function_text: string
  failure_mode: string
  cause: string
  effect: string
  control: string
  action_text: string
  severity: number | null
  occurrence: number | null
  detection: number | null
  scores_confirmed: boolean
  rpn: number | null
  rpn_status: 'confirmed' | 'pending_confirmation' | 'incomplete'
  dependencies: Record<string, unknown>[]
}

export interface DfmeaPayload {
  fmea: {
    id: string
    project_id: string
    display_code: string
    base_display_code: string | null
    revision: number
    status: string
    scale: Record<string, string>
    created_at: string
    updated_at: string
  }
  items: FmeaItem[]
  inputs_snapshot: Record<string, unknown>
  missing_inputs: string[]
  confirmations: ArtifactConfirmation[]
  needs_reconfirmation: boolean
  mode: Mode
}

export interface RequirementRef {
  requirement_id: string
  display_code?: string
  revision: number
  current_revision: number | null
}

export interface TestRun {
  id: string
  case_id: string
  case_revision: number
  run_no: number
  status: string
  result: ExecutionResult
  mode: Mode
  conditions_text: string
  evidence: string
  load_basis_numeric: number | null
  backup_coefficient: number | null
  manual_result: string | null
  reasons: string[]
  reason: string
  measured_values: Record<string, unknown>
  actor: string
  role: string
  created_at: string
}

export interface TestCase {
  id: string
  plan_id: string
  display_code: string
  case_key: string
  case_kind: string
  title: string
  purpose: string
  revision: number
  review_status: ReviewStatus
  validity: Validity
  conditions_text: string
  load_conditions_text: string
  acceptance_criteria: string
  load_basis_requirement_id: string | null
  minimum_coefficient: number | null
  requirement_refs: RequirementRef[]
  fmea_refs: Record<string, unknown>[]
  complete: boolean
  coverage_valid: boolean
  runs: TestRun[]
}

export interface TestPlanPayload {
  needs_reconfirmation?: boolean
  mode: Mode
  source_label: string
  plan: {
    id: string
    display_code: string
    revision: number
    status: string
    purpose: string
    conditions_text: string
    sample_description: string
    load_conditions_text: string
    acceptance_criteria: string
    source_label: string
    created_at: string
    updated_at: string
  }
  cases: TestCase[]
  confirmations: ArtifactConfirmation[]
}

export interface MatrixItem {
  key: string
  label: string
  requirement_id: string | null
  display_code: string | null
  requirement_revision: number | null
  covered: boolean
  coverage_valid: boolean
  valid_case_ids: string[]
  pending_case_ids: string[]
  execution: ExecutionResult
  reason: string
  latest_runs: {
    id: string
    run_no: number
    status: string
    result: ExecutionResult
    case_revision: number
    mode: Mode
    created_at: string
  }[]
}

export interface OverviewTraceItem extends MatrixItem {
  design_items?: {
    id: string
    display_code: string
    check_point: string
    standard_basis: string
    revision: number
    requirement_revision: number
    status: ReviewStatus
    validity: Validity
  }[]
  test_cases?: Pick<TestCase, 'id' | 'display_code' | 'title' | 'revision' | 'review_status' | 'validity' | 'conditions_text' | 'load_conditions_text' | 'acceptance_criteria' | 'requirement_refs' | 'coverage_valid' | 'runs'>[]
}

export interface TraceabilityMatrix {
  mode: Mode
  scope_label: string
  denominator: number
  covered_count: number
  coverage_percentage: number
  items: MatrixItem[]
  uncovered: MatrixItem[]
  pending_review: Record<string, unknown>[]
  execution_summary: Record<string, number>
}

export interface DrawingParameter {
  id?: string
  parameter_key: string
  parameter_name: string
  expected_value: number
  tolerance: number
  unit: string
  source_note: string
}

export interface SampleFileInfo {
  file_name: string
  content_type: string
  content_hash: string
  size_bytes: number
  uploaded_by: string
  uploaded_at: string
}

export interface SampleDelivery {
  id: string
  project_id: string
  display_code: string
  supplier: string
  part_display_code: string
  drawing_display_code: string
  drawing_revision: string
  delivered_at: string
  quantity: number
  notes: string
  mode: Mode
  source_label: string
  drawing_parameters: DrawingParameter[]
  file_uploaded: boolean
  file: SampleFileInfo | null
  created_at: string
  updated_at: string
}

export interface SampleFinding {
  parameter_key: string
  parameter_name: string
  expected_value: number | null
  tolerance: number | null
  measured_value: number | null
  unit: string
  result: ExecutionResult
  reason: string
}

export interface SampleComparison {
  comparison: {
    id: string
    project_id: string
    sample_id: string
    display_code: string
    revision: number
    status: string
    mode: Mode
    overall_result: ExecutionResult
    findings: SampleFinding[]
    visual_check: {
      mode?: string
      result?: string
      note?: string
    }
    evidence: string
    created_at: string
    updated_at: string
  }
  issues: RequirementIssue[]
  confirmations: ArtifactConfirmation[]
  mode: Mode
  source_label: string
}

export interface ConsistencyCheckSummary {
  id: string
  project_id: string
  display_code: string
  check_no: number
  revision: number
  status: string
  validity: Validity
  mode: Mode
  source_label: string
  created_at: string
  updated_at: string
  summary: Record<string, unknown>
}

export interface ConflictEvent {
  id: string
  action: string
  actor: string
  role: string
  note: string
  evidence: string
  created_at: string
}

export interface Conflict {
  id: string
  project_id: string
  display_code: string
  revision: number
  conflict_type: string
  severity: Severity
  status: 'open' | 'closed'
  detected: boolean
  title: string
  detail: string
  object_type: string
  object_id: string
  object_revision: number | null
  object_review_status: string | null
  first_seen_at: string
  last_seen_at: string
  recheck_status: string
  resolution_type: string | null
  resolution_note: string | null
  evidence_text: string | null
  accepted_risk: boolean
  closed_by: string | null
  closed_at: string | null
  blocking: boolean
  review_pending: boolean
  evidence: Record<string, unknown>
  events: ConflictEvent[]
}

export interface ConsistencyCheckPayload {
  check: ConsistencyCheckSummary
  conflicts: Conflict[]
}

export interface CoordinationRecord {
  id: string
  topic_id: string
  external_id: string
  record_type: 'message' | 'reopened'
  sender: string
  content_summary: string
  sent_at: string
  reply_to_external_id: string | null
  created_at: string
}

export interface CoordinationMetricRun {
  validity: Validity
  inputs_sha256: string
  id: string
  topic_id: string
  run_no: number
  rule_label: string
  mode: Mode
  source_label: string
  inputs: Record<string, unknown>
  metrics: Record<string, number | string | null>
  risk: Record<string, unknown>
  cost: Record<string, unknown>
  created_at: string
}

export interface RiskAcceptance {
  id: string
  topic_id: string
  metric_run_id: string
  risk_level: RiskLevel | null
  actor: string
  role: string
  note: string
  created_at: string
}

export interface CoordinationTopic {
  id: string
  project_id: string
  display_code: string
  name: string
  expected_participants: string[]
  window_start: string
  window_end: string
  mode: Mode
  created_at: string
  records: CoordinationRecord[]
  record_count: number
  latest_metrics: CoordinationMetricRun | null
  risk_acceptances: RiskAcceptance[]
}

export interface CoordinationOverview {
  project_id: string
  rule_label: string
  source_label: string
  topic_count: number
  record_count: number
  metrics_available: number
  highest_risk: RiskLevel
  topics: CoordinationTopic[]
}

export interface PackageGateEntry {
  code: string
  message: string
  check: string
  object_type?: string
  object_id?: string
  revision?: number
  details?: Record<string, unknown>
}

export interface PackageGateCheck {
  key: string
  label: string
  status: 'pass' | 'fail' | 'not_applicable'
  summary: string
  failures: PackageGateEntry[]
}

export interface PackageGate {
  status: 'ready' | 'blocked'
  ready: boolean
  checks: PackageGateCheck[]
  blockers: PackageGateEntry[]
  warnings: PackageGateEntry[]
  summary: {
    check_count: number
    passed_check_count: number
    not_applicable_check_count: number
    blocker_count: number
    warning_count: number
  }
}

export interface MaterialPackageSummary {
  requires_regeneration?: boolean
  id: string
  project_id: string
  display_code: string
  package_no: number
  status: 'draft' | 'ready_to_submit' | 'human_approved'
  mode: Mode
  include_originals: boolean
  snapshot_hash: string
  zip_sha256: string
  zip_size: number
  created_by: string
  created_at: string
  frozen_at: string | null
  gate: PackageGate
}

export interface MaterialPackageDetail extends MaterialPackageSummary {
  snapshot: Record<string, unknown>
  manifest: Record<string, unknown>
  approval: Record<string, unknown> | null
}
export interface PartCandidate {
 id:string;model_code:string;part_name:string;rated_torque_nm:number;max_gears:number;material:string;image_key:string;source:string;fit:'pass'|'fail'|'incomplete';limitations:string
 checks:{requirement_id:string;revision:number;display_code:string;parameter:string;required:number|null;unit:string;capacity:number;comparison:string;result:string;review_status:string}[]
}
export interface PartChoice {record:EngineeringRecord & {part_number:string};candidates:PartCandidate[];selected_candidate_id:string|null;selection_state:'unselected'|'pending_review'|'confirmed'|'rejected'|'recheck';confirmation_blockers?:string[]}
export interface PartChoices {parts:PartChoice[];counts:Record<PartChoice['selection_state'],number>;mode:'rule';catalog_source:string}
export interface WorkflowSummary {
 testing:{total:number;review:Record<string,number>;stale:number;valid_coverage_cases:number;execution:Record<string,number>;cases:{id:string;revision:number;execution:string;review_status:string;validity:string;historical_runs:number}[];plan_status:string}
 samples:{total:number;compared:number;confirmed:number;rows:{id:string;display_code:string;steps:{label:string;done:boolean}[];current_step:number;result:string;review_status:string;open_issues:number}[]}
 consistency:{scope:string[];changes:{id:string;label:string;kind:string;parameter:string;before:string;after:string;unit:string;versions:string;state:string;evidence:string}[]}
}
export interface ProgressRow {id:string;revision:number;participant:string;milestone:string;planned_percent:number;actual_percent:number;artifact_version:string;reported_at:string;evidence:string}
export interface ProgressPayload {topic_id:string;rows:ProgressRow[];assessment:{rule_label:string;risk_level:string;alerts:{kind:string;level:string;milestone:string;participants:string[];reason:string;evidence:string[];reported_at:string[]}[];data_gaps:string[];thresholds:string}}
