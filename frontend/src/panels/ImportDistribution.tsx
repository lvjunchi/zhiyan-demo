import type { DocumentImport, SourceDocument } from '../types'

const documentStates = [
  ['parsed','已解析','#178369'],
  ['pending_parse','已归档待解析','#2b70b8'],
  ['awaiting_review','未归档待核对','#bc7b18'],
  ['needs_manual_review','已解析需核对','#b45b2c'],
] as const
const attemptStates = [
  ['completed','处理完成','good'], ['awaiting_review','待核对正文','pending'],
  ['archived','已归档待解析','blue'], ['failed','处理失败','bad'], ['cancelled','已取消','muted'],
] as const

export function ImportDistribution({ documents, attempts, documentsAvailable, attemptsAvailable }: {
  documents: SourceDocument[]; attempts: DocumentImport[]; documentsAvailable: boolean; attemptsAvailable: boolean
}) {
  const pending = attempts.filter(item=>item.status==='awaiting_review'&&!item.source_document_id)
  const available = documentsAvailable && attemptsAvailable && documents.every(doc=>!!doc.parse_summary)
  const total = documents.length + pending.length
  const slices = documentStates.map(([key,label,color]) => ({ key,label,color,count:key==='awaiting_review'?pending.length:documents.filter(doc => doc.parse_summary?.status === key).length }))
  const description = `文件状态：${slices.map(item => `${item.label}${item.count}份`).join('，')}`
  let offset = 0
  return <section className="import-distribution-panel" role="region" aria-label="导入状态分布">
    <header><div><h3>导入状态分布</h3><p>文档与处理记录分别统计，重复选择或重试会产生历史记录。</p></div><span className="distribution-source">随实际操作更新</span></header>
    <div className="distribution-charts">
      <figure className="document-donut"><figcaption>文件状态 · 已归档与待核对</figcaption><div className="document-donut-content">
        <div className="document-donut-visual"><svg viewBox="0 0 120 120" role={available && total ? 'img' : undefined} aria-hidden={!available || !total || undefined} aria-label={available && total ? description : undefined}>
          <circle cx="60" cy="60" r="46" fill="none" stroke="#e6edf4" strokeWidth="12" />
          {available && total > 0 && slices.map(item => {
            const length = item.count / total * 100, start = offset
            offset += length
            return item.count ? <circle key={item.key} cx="60" cy="60" r="46" fill="none" stroke={item.color} strokeWidth="12" pathLength="100" strokeDasharray={`${length} ${100-length}`} strokeDashoffset={-start} transform="rotate(-90 60 60)" /> : null
          })}
        </svg><div className="document-donut-total"><strong>{available ? total : '—'}</strong><span>份文件任务</span></div></div>
        <div className="distribution-legend">{slices.map(item => <div key={item.key}><span><i style={{background:item.color}} />{item.label}</span><strong>{available ? item.count : '—'} <small>份</small></strong></div>)}</div>
      </div>{!available ? <p className="distribution-empty">文档解析统计暂不可用</p> : !total ? <p className="distribution-empty">暂无已导入文档</p> : <p className="distribution-note">{documents.length}份已归档，{pending.length}份未归档待核对；解析成功仍需审核需求。重复选择保留独立任务。</p>}</figure>
      <div className="attempt-bar-chart" role="group" aria-label="文件处理记录分布"><h4>文件处理记录 · {attemptsAvailable ? `${attempts.length} 次` : '暂不可用'}</h4>
        {!attemptsAvailable ? <p className="distribution-empty">文件处理统计暂不可用</p> : !attempts.length ? <div className="attempt-empty"><span aria-hidden="true">▥</span><p>暂无文件处理记录</p><small>选择协议文件后展示实际处理情况</small></div> : <div className="attempt-bars">{attemptStates.map(([key,label,tone]) => {
          const count = attempts.filter(item => item.status === key).length
          return <div key={key} className="attempt-bar-row" data-tone={tone} aria-label={`历史${label.replace('处理','')}记录`}><span>{label}</span><div className="attempt-bar-track" aria-hidden="true"><i style={{width:`${count / attempts.length * 100}%`}} /></div><strong>{count} <small>次</small></strong></div>
        })}</div>}
      </div>
    </div>
  </section>
}
