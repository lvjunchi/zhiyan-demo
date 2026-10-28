import type { Requirement,TestCase } from '../types'

// A convenience draft from the exact referenced revision, never a pass decision.
export function executionLoadPreset(testCase:Pick<TestCase,'requirement_refs'|'load_basis_requirement_id'>,requirements:Pick<Requirement,'id'|'project_id'|'current_revision'|'review_status'|'validity'|'unit'|'value_num'>[],projectId:string):string {
  const reference=testCase.requirement_refs.find(ref=>ref.requirement_id===testCase.load_basis_requirement_id)
  const source=requirements.find(req=>req.id===testCase.load_basis_requirement_id&&req.project_id===projectId)
  if(!reference||!source||source.current_revision!==reference.revision||source.review_status!=='confirmed'||source.validity!=='current'||source.unit!=='N·m'||typeof source.value_num!=='number'||!Number.isFinite(source.value_num)||source.value_num<=0)return ''
  return String(source.value_num)
}
