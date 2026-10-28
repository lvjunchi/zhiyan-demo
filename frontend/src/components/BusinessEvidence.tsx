import { businessText, versionLabel, engineeringValue } from '../businessPresentation'
import { displayCount } from '../consistencyPresentation'
import { executionLabels } from '../uiSupport'
import './businessEvidence.css'

const fieldLabels: Record<string, string> = {
  comparison: '比较关系', relation: '约束关系', reason: '检查依据', evaluation: '比较结论',
  requirement_id: '需求追溯标识', source_document_id: '来源文档标识', source_excerpt: '来源摘录',
  left_display_code: '左侧需求编号', left_value: '左侧记录值', left_unit: '左侧单位',
  right_display_code: '右侧需求编号', right_value: '右侧记录值', right_unit: '右侧单位',
  current_value: '当前记录值', numbers_in_excerpt: '摘录中的数值',
  case_id: '用例追溯标识', case_display_code: '用例编号', case_revision: '当前用例版本', run_case_revision: '执行绑定版本',
  run_id: '执行追溯标识', load_basis_numeric: '执行加载基准', expected_value: '要求加载值', expected_unit: '要求单位',
  backup_coefficient: '记录后备系数', minimum_coefficient: '最低后备系数',
  display_code: '业务编号', revision: '记录版本', parameter_name: '工程参数', unit: '单位', value: '记录值',
  upstream_revision: '上游版本', referenced_revision: '引用版本', current_revision: '当前版本',
  object_id: '对象追溯标识', object_type: '对象类型', evidence: '证据', sample: '样件',
}
const valueLabels: Record<string, string> = { satisfied: '满足约束', violated: '存在偏差', invalid: '无效', incomplete: '证据不足', unsupported: '规则不支持' }

function EvidenceValue({ value, field }: { value: unknown; field?: string }) {
  if (Array.isArray(value)) return value.length ? <ul className="evidence-list">{value.map((item, index) => <li key={index}><EvidenceValue value={item} /></li>)}</ul> : <>未记录条目</>
  if (typeof value === 'object' && value !== null) {
    const entries = Object.entries(value)
    return entries.length ? <dl className="evidence-fields">{entries.map(([key, item], index) => <div key={key} data-source-field={key}><dt title={key}>{fieldLabels[key] ?? `补充依据 ${index + 1}`}</dt><dd><EvidenceValue value={item} field={key} /></dd></div>)}</dl> : <>未记录字段</>
  }
  return <>{field === 'evaluation' && typeof value === 'string' ? valueLabels[value] ?? '结论未识别' : businessText(value)}</>
}

export function EvidenceDetails({ data, title = '检查依据' }: { data: Record<string, unknown>; title?: string }) {
  const count = Object.keys(data).length
  return <details className="business-evidence" aria-label={title}><summary>查看{title} · {count} 项</summary><div className="business-evidence-body">{count ? <EvidenceValue value={data} /> : <p>未记录检查依据，请核对来源。</p>}</div></details>
}

export function VersionEvidence({ rows, title = '输入版本依据' }: { rows: Record<string, unknown>[]; title?: string }) {
  return <details className="business-evidence version-evidence" aria-label={title}><summary>查看{title} · {rows.length} 项</summary><div className="business-evidence-body">{rows.length ? <div className="table-wrap"><table><thead><tr><th>需求编号</th><th>引用版本</th><th>记录目标</th><th>追溯标识</th></tr></thead><tbody>{rows.map((row, index) => <tr key={`${businessText(row.requirement_id)}-${index}`}><td>{businessText(row.display_code)}</td><td>{versionLabel(row.revision)}</td><td>{engineeringValue(row.value_text ?? row.value_num ?? row.value)}{typeof row.unit === 'string' && row.unit ? ` ${row.unit}` : ''}</td><td className="record-identity">{businessText(row.requirement_id)}</td></tr>)}</tbody></table></div> : <p>未记录输入版本，请核对来源。</p>}</div></details>
}

export function ExecutionSummary({ counts }: { counts: Record<string, number> }) {
  return <section className="execution-summary" aria-label="执行结果汇总"><span>执行结果</span><dl>{Object.entries(counts).map(([key, count]) => <div key={key}><dt>{executionLabels[key as keyof typeof executionLabels] ?? '其他结果'}</dt><dd>{displayCount(count)}</dd></div>)}</dl><small>执行结果与用例覆盖分别统计</small></section>
}
