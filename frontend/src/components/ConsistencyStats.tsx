import { conflictTypeLabels, displayCount, isCount } from '../consistencyPresentation'
import { severityLabels } from '../uiSupport'
import './consistencyStats.css'

function entries(value: unknown): [string, unknown][] {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? Object.entries(value) : []
}

export function ConsistencyStats({ summary }: { summary: Record<string, unknown> }) {
  const metrics = [
    ['total', '本次检出', summary.total === undefined ? summary.conflict_count : summary.total],
    ['blocking_open', '未关闭阻断', summary.blocking_open],
    ['open', '开放', summary.open],
    ['review_pending', '待审核', summary.review_pending],
    ['closed', '已关闭', summary.closed],
    ['accepted_risk', '接受风险关闭', summary.accepted_risk],
  ] as const
  const total = isCount(summary.total) ? summary.total : isCount(summary.conflict_count) ? summary.conflict_count : 0
  const bar = (count:unknown)=><span className="consistency-distribution-bar" aria-hidden="true"><i style={{width:`${isCount(count)&&total?Math.min(100,count/total*100):0}%`}}/></span>
  const severities = entries(summary.by_severity)
  const types = entries(summary.by_type)
  const incomplete = metrics.some(([, , count]) => !isCount(count))
    || [...severities, ...types].some(([, count]) => !isCount(count))
  return <section className="consistency-statistics" aria-label="一致性检查统计">
    <dl className="consistency-metrics">{metrics.map(([key, label, count]) =>
      <div key={key} data-metric={key}><dt>{label}</dt><dd>{displayCount(count)}</dd></div>,
    )}</dl>
    <div className="consistency-distributions">
      <section aria-label="本次检出严重度分布"><h3>本次检出 · 严重度</h3>
        {severities.length ? <dl>{severities.map(([key, count]) => <div key={key} data-tone={key}><dt>{severityLabels[key as keyof typeof severityLabels] ?? '其他级别'}</dt><dd>{bar(count)}<strong>{displayCount(count)}</strong></dd></div>)}</dl> : <p>未记录严重度分布</p>}
      </section>
      <section aria-label="本次检出类型分布"><h3>本次检出 · 问题类型</h3>
        {types.length ? <dl>{types.map(([key, count]) => <div key={key}><dt>{conflictTypeLabels[key] ?? '其他类型'}</dt><dd>{bar(count)}<strong>{displayCount(count)}</strong></dd></div>)}</dl> : <p>未记录类型分布</p>}
      </section>
    </div>
    <div className="consistency-recheck" aria-label="复检处置摘要"><span>复检仍检出 <strong>{displayCount(summary.detected)}</strong></span><span>未再检出但仍开放 <strong>{displayCount(summary.not_detected_open)}</strong></span></div>
    {incomplete && <p className="consistency-incomplete" role="status">部分统计未记录或格式无效，显示“—”，请核对检查报告。</p>}
    <p className="hint">严重度与问题类型对应该次报告的检出结果；开放、关闭及审核数量采用后端返回的处置汇总。报告版本或输入变化后，请运行检查重新核对。</p>
  </section>
}
