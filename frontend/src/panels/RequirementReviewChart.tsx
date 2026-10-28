import type { Requirement } from '../types'

type ReviewFilter = 'pending' | 'confirmed' | 'rejected' | 'all'

export function RequirementReviewChart({ rows, onFilter, unavailable, activeFilter = 'all' }: {
  rows: Requirement[]
  onFilter: (filter: ReviewFilter) => void
  unavailable: boolean
  activeFilter?: ReviewFilter
}) {
  const states = [
    { key: 'pending', label: '待审核', color: '#bc7b18', count: rows.filter(row => ['draft', 'pending_review'].includes(row.review_status)).length },
    { key: 'confirmed', label: '已确认', color: '#178369', count: rows.filter(row => row.review_status === 'confirmed').length },
    { key: 'rejected', label: '已驳回', color: '#cc4658', count: rows.filter(row => row.review_status === 'rejected').length },
  ] as const
  const stale = rows.filter(row => row.validity === 'stale').length
  const confirmedShare = rows.length ? new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(states[1].count / rows.length * 100) : null
  const description = `需求审核分布：${states.map(item => `${item.label}${item.count}条`).join('，')}`
  let offset = 0

  return <section className="panel requirement-review-chart" role="region" aria-label="需求审核状态统计">
    <div className="panel-heading"><h2>需求审核状态统计</h2><div className="review-chart-actions"><span className="count">{unavailable ? '待刷新' : `${rows.length} 条需求`}</span><button type="button" className="secondary" disabled={unavailable} onClick={() => onFilter('all')}>查看全部需求</button></div></div>
    {unavailable ? <p className="hint">统计暂不可用，请先刷新需求列表。</p> : <div className="review-chart-layout">
      <figure className="review-donut">
        <div className="review-donut-visual">
          <svg viewBox="0 0 120 120" role={rows.length ? 'img' : undefined} aria-label={rows.length ? description : undefined} aria-hidden={!rows.length || undefined}>
            <circle cx="60" cy="60" r="46" fill="none" stroke="#e6edf4" strokeWidth="11" />
            {rows.length > 0 && states.map(item => {
              const length = item.count / rows.length * 100, start = offset
              offset += length
              return item.count ? <circle key={item.key} cx="60" cy="60" r="46" fill="none" stroke={item.color} strokeWidth="11" pathLength="100" strokeDasharray={`${length} ${100 - length}`} strokeDashoffset={-start} transform="rotate(-90 60 60)" /> : null
            })}
          </svg>
          <div className="review-donut-total"><strong>{rows.length}</strong><span>条需求</span></div>
        </div>
        <figcaption>{confirmedShare === null ? '暂无需求' : `已确认占比 ${confirmedShare}%`}</figcaption>
      </figure>
      <div className="review-chart-details">
        <p className="hint">点击状态筛选需求</p>
        <div className="review-status-cards">{states.map(({ key, label, count }) => <button type="button" key={key} aria-label={`按${label}筛选`} aria-pressed={activeFilter === key} data-tone={key} onClick={() => onFilter(key)}><span><i aria-hidden="true" />{label}</span><strong>{count}<small> 条</small></strong></button>)}</div>
        <p className="review-validity-note"><span data-warning={stale > 0}>{stale} 条待复核</span><small>有效性单独统计，可与审核状态重叠</small></p>
      </div>
    </div>}
  </section>
}
