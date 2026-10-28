import type { ParseResult } from '../types'
import { modeLabel, parseStatusLabel } from '../businessPresentation'
import { formatTime } from '../uiSupport'

export function ParseResultView({ result }: { result: ParseResult }) {
  return <div className="result-box"><h3>解析结果</h3>
    <p>状态：{parseStatusLabel(result.status)} · 模式：{modeLabel(result.mode)} · 时间：{formatTime(result.parsed_at)}</p>
    <p>需求 {result.requirements.length} 条 · 问题 {result.issues.length} 条 · 缺失类别：{result.missing_categories.length ? result.missing_categories.join('、') : '无'}</p>
    {!!result.unrecognized_clauses.length && <p>未识别条款：{result.unrecognized_clauses.join('；')}</p>}
    <ul className="compact-list">{result.requirements.map(item => <li key={item.id}><span className="mono">{item.display_code}</span>{' '}{item.parameter_name} {item.operator} {item.value_text}{' '}{item.unit}<span className="muted">（{item.review_status === 'confirmed' ? '已确认' : item.review_status === 'rejected' ? '已驳回' : '待确认'}）</span></li>)}</ul>
  </div>
}
