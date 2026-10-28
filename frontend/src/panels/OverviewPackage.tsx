import { Icon } from '../components/Icon'
import type { ProjectOverview } from '../types'
import { packageStatusLabels, formatTime } from '../uiSupport'
import './overview-package.css'

export function OverviewPackage({ value, onOpen }: {value: ProjectOverview['package']; onOpen: () => void}) {
  const outdated = value?.requires_regeneration
  const note = !value ? '汇总研制成果，生成快照后查看检查缺口。'
    : outdated ? '资料已变化，请重新生成材料包。'
    : value.status === 'human_approved' ? '人工审批已完成，材料快照已冻结。'
    : value.blocker_count ? '先处理阻断事项，再重新生成材料包。'
    : value.status === 'ready_to_submit' ? '检查满足提交条件，等待人工审批。'
    : '材料仍为草稿，请核对检查详情。'
  return <section className="dash-card dash-package dash-package-summary" aria-label="评审材料摘要">
    <header className="dash-card-head"><h3>评审材料</h3><span className="package-freeze" data-frozen={Boolean(value?.frozen_at)}>{value ? value.frozen_at ? '已冻结' : '尚未冻结' : '待生成'}</span></header>
    <div className="package-preview"><span className="package-symbol"><Icon name="packages" size={30}/></span><div><strong data-state={outdated ? 'outdated' : value?.status ?? 'empty'}>{!value ? '尚未生成材料包' : outdated ? '旧版材料 · 待更新' : packageStatusLabels[value.status]}</strong><small title={value ? `${value.display_code} · ${formatTime(value.created_at)}` : undefined}>{value?.display_code ?? '生成后保留版本与审核记录'}</small></div></div>
    <div className="package-checks" role="group" aria-label="材料包快照检查摘要" title={outdated ? '上次快照的检查结果，需要重新生成' : '生成材料包时保存的检查结果'}>
      <span className="package-check-label">{!value ? '检查结果待生成' : outdated ? '上次快照 · 待更新' : '生成时快照'}</span>
      <div className="package-counts"><div data-kind="blocker" data-open={Boolean(value?.blocker_count)}><strong>{value ? value.blocker_count : '—'}</strong>{' '}<span>项阻断</span></div><div data-kind="warning" data-open={Boolean(value?.warning_count)}><strong>{value ? value.warning_count : '—'}</strong>{' '}<span>项提示</span></div></div>
    </div>
    <p className="package-next" title={note}>{note}</p>
    <button type="button" className="package-open" onClick={onOpen}>查看评审材料<Icon name="arrow" size={14}/></button>
  </section>
}
