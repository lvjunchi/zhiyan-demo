import type { ModuleTabKey } from '../navigation'
import type { ProjectOverview } from '../types'
import { packageStatusLabels } from '../uiSupport'

export interface OverviewLocation { phase: number; label: string; detail: string; tab: ModuleTabKey }

/** Locate saved outputs for navigation; this never approves an object or evaluates a gate. */
export function locateOverview(data: ProjectOverview): OverviewLocation {
  const pack = data.package
  if (pack) return { phase: 4, label: '评审交付', detail: `${packageStatusLabels[pack.status]}${pack.requires_regeneration ? ' · 待更新' : ''}`, tab: 'packages' }
  const coverage = data.traceability
  if (coverage) return { phase: 3, label: '试验验证', detail: `有效覆盖 ${coverage.covered_count}/${coverage.denominator} · 执行通过 ${coverage.execution_summary.pass ?? 0}/${coverage.denominator}`, tab: 'testing' }
  if (data.samples.delivery_count) return { phase: 3, label: '样件检验', detail: `已登记 ${data.samples.delivery_count} 批样件`, tab: 'samples' }
  if (data.design_review || data.dfmea) return { phase: 2, label: '设计成果', detail: '设计评审与 DFMEA 分别审核', tab: 'design' }
  if (data.spectrum.variant_points || data.spectrum.reusable_parts) return { phase: 2, label: '变型设计', detail: `${data.spectrum.variant_points} 项变型 · ${data.spectrum.reusable_parts} 项零件决策`, tab: 'bases' }
  if (data.requirements.total) return { phase: 1, label: '需求确认', detail: `已确认 ${data.requirements.confirmed}/${data.requirements.total} 项需求`, tab: 'requirements' }
  return { phase: 0, label: '协议导入', detail: data.cockpit?.resources.source_documents ? '已登记文档，等待解析需求' : '等待导入协议', tab: 'parsing' }
}
