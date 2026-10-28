import type { ModuleTabKey, NavigateTo } from '../navigation'
import type { PackageGateEntry } from '../types'

const OBJECT_MODULE: Record<string, ModuleTabKey> = {
  requirement: 'requirements', variant_point: 'bases', reusable_part_decision: 'bases',
  design_review: 'design', design_review_item: 'design', fmea_document: 'design', fmea_item: 'design',
  test_plan: 'testing', test_case: 'testing', sample_comparison: 'samples', sample_delivery: 'samples',
  consistency_check: 'consistency', conflict: 'consistency', consistency_conflict: 'consistency',
  issue: 'parsing', coordination_topic: 'coordination', coordination_metric_run: 'coordination',
}
const CHECK_MODULE: Record<string, ModuleTabKey> = {
  requirements_confirmed: 'requirements', engineering_decisions_confirmed: 'bases',
  test_plan_confirmed: 'testing', design_review_confirmed: 'design', dfmea_confirmed: 'design',
  coverage_complete: 'testing', verification_passed: 'testing', sample_comparison_confirmed: 'samples',
  consistency_cleared: 'consistency', issues_cleared: 'parsing', coordination_risk_accepted: 'coordination',
}
export function MaterialBlockers({ blockers, onNavigate }: { blockers: PackageGateEntry[]; onNavigate?: NavigateTo }) {
  return <div className="material-actions"><h3>材料准备待办</h3><p className="hint">依据最新材料包生成时的门禁快照。处理后返回此页生成新包重新检查。</p><ul>{blockers.map((item, index) => {
    const tab = OBJECT_MODULE[item.object_type ?? ''] ?? CHECK_MODULE[item.check]
    return <li key={`${item.code}-${item.object_id ?? 'missing'}-${index}`}><div><strong>{item.message}</strong>{item.revision && <small>待核对版本 V{item.revision}</small>}</div>{tab && onNavigate ? <button type="button" aria-label={`处理：${item.message}`} onClick={() => onNavigate(tab, { objectId: item.object_id, revision: item.revision, message: item.message })}>前往处理 →</button> : <span className="hint">{tab ? '请核对对应模块记录。' : '缺少可定位的关联信息，请核对门禁详情。'}</span>}</li>
  })}</ul></div>
}
