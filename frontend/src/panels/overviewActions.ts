import type { ProjectOverview } from '../types'
import type { TabKey } from '../navigation'

export interface OverviewAction { title: string; detail: string; tab: TabKey; tone: 'amber' | 'red' | 'blue' | 'green' }

/** Navigation suggestions from returned statuses; never evaluates an engineering gate. */
export function nextOverviewAction(data: ProjectOverview): OverviewAction {
  const req = data.requirements
  if (!req.total) return { title: data.cockpit?.resources.source_documents ? '解析已导入文档' : '导入技术协议', detail: '从协议原文建立需求与来源证据', tab: 'parsing', tone: 'blue' }
  if (req.stale) return { title: `${req.stale} 项需求待复核`, detail: '核对变更后的当前版本', tab: 'requirements', tone: 'amber' }
  if (req.draft + req.pending_review) return { title: `${req.draft + req.pending_review} 项需求待审核`, detail: `${req.confirmed} 项已确认 · ${req.rejected} 项已驳回`, tab: 'requirements', tone: 'amber' }
  if (req.rejected) return { title: `${req.rejected} 项驳回需求待修订`, detail: '查看驳回意见并修订', tab: 'requirements', tone: 'red' }
  if (data.issues.open) return { title: `${data.issues.open} 项条款待澄清`, detail: '核对原文、补录依据并关闭问题', tab: 'parsing', tone: 'amber' }
  if (data.spectrum.stale_variant_points) return { title: '变型成果待重新分析', detail: `${data.spectrum.stale_variant_points} 项旧版变型点`, tab: 'bases', tone: 'amber' }
  if (!data.spectrum.reusable_parts && !data.spectrum.variant_points) return { title: '选择基型并运行变型分析', detail: '对比需求与受控候选，形成零件决策', tab: 'bases', tone: 'blue' }
  if (!data.design_review || !data.dfmea || data.design_review.needs_reconfirmation || data.dfmea.needs_reconfirmation || data.design_review.status !== 'confirmed' || data.dfmea.status !== 'confirmed' || data.dfmea.pending_score_count) return { title: '完善设计评审与 DFMEA', detail: '分别审核当前版本和风险评分', tab: 'design', tone: 'amber' }
  const trace = data.traceability
  if (!trace) return { title: '生成试验方案与用例', detail: '建立工况、判定标准和需求引用', tab: 'testing', tone: 'blue' }
  if (trace.covered_count < trace.denominator) return { title: `${trace.denominator - trace.covered_count} 条验证要求尚未覆盖`, detail: '覆盖与执行分别计算，需有效用例', tab: 'testing', tone: 'amber' }
  if (trace.execution_summary.fail || trace.execution_summary.invalid) return { title: '处理当前验证异常', detail: '查看未通过或无效执行的具体依据', tab: 'testing', tone: 'red' }
  if ((trace.execution_summary.pass ?? 0) < trace.denominator) return { title: '补齐当前试验执行证据', detail: '已覆盖不等于执行通过', tab: 'testing', tone: 'amber' }
  if (!data.consistency || data.consistency.check.validity === 'stale') return { title: '运行当前版本一致性检测', detail: '检查参数、版本、引用及工况', tab: 'consistency', tone: 'blue' }
  if (data.consistency.open_conflicts || data.consistency.review_pending || data.consistency.check.status !== 'confirmed') return { title: '审核一致性报告并处理冲突', detail: `${data.consistency.blocking_open} 项阻断 · ${data.consistency.review_pending} 项待审核`, tab: 'consistency', tone: data.consistency.blocking_open ? 'red' : 'amber' }
  if (data.coordination.high_risk_topics) return { title: '查看协同高风险处置', detail: `${data.coordination.high_risk_topics} 个高风险议题 · 处理与接受需留痕`, tab: 'coordination', tone: 'amber' }
  const pack = data.package
  if (!pack || pack.requires_regeneration) return { title: '生成当前版本评审材料', detail: '实际就绪状态以材料包门禁为准', tab: 'packages', tone: 'blue' }
  if (pack.blocker_count) return { title: `${pack.blocker_count} 项材料阻断待处理`, detail: '打开当前门禁查看具体缺口', tab: 'packages', tone: 'red' }
  return { title: pack.status === 'human_approved' ? '查看已冻结评审材料' : '查看材料审核与提交状态', detail: '材料状态取自后端，不自动批准', tab: 'packages', tone: pack.status === 'human_approved' ? 'green' : 'blue' }
}
