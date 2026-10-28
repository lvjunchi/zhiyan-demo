import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Requirement, RequirementRevision, SourceDocument } from '../types'
import { Notice } from '../ui'
import { toErrorMessage } from '../uiSupport'
import { DetailOverlay } from './DetailOverlay'

export function RequirementInspector({ requirement, projectId, returnFocus, onClose }: { requirement: Requirement; projectId: string; returnFocus: HTMLElement | null; onClose: () => void }) {
  const [versions, setVersions] = useState<RequirementRevision[]>([])
  const [source, setSource] = useState<SourceDocument | null>(null)
  const [leftVersion, setLeftVersion] = useState(0)
  const [rightVersion, setRightVersion] = useState(0)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    Promise.all([api.requirementRevisions(requirement.id), api.listSourceDocuments(projectId)]).then(([history, sources]) => {
      if (!Array.isArray(history) || !Array.isArray(sources)) throw new Error('来源或版本数据无效')
      if (active) {
        setVersions(history)
        setLeftVersion(history.at(-2)?.revision_no ?? history.at(-1)?.revision_no ?? 0)
        setRightVersion(history.at(-1)?.revision_no ?? 0)
        setSource(sources.find(item => item.id === requirement.source_document_id) ?? null)
      }
    }).catch((err: unknown) => { if (active) setError(toErrorMessage(err)) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [projectId, requirement.id, requirement.source_document_id, attempt])
  const left = versions.find(item => item.revision_no === leftVersion), right = versions.find(item => item.revision_no === rightVersion)
  const fields: { key: keyof Requirement; label: string }[] = [{ key: 'value_text', label: '目标值' }, { key: 'unit', label: '单位' }, { key: 'operator', label: '比较符' }, { key: 'source_location', label: '来源位置' }, { key: 'source_excerpt', label: '来源摘录' }]
  return <DetailOverlay variant="drawer" title="需求来源与版本对比" subtitle={`${requirement.display_code} · ${requirement.parameter_name}`} eyebrow="需求档案 · 来源与版本" returnFocus={returnFocus} onClose={onClose} footer="只读查看 · 关闭后保留列表筛选和位置">
    {error && <Notice kind="error">{error}</Notice>}
    {loading ? <p role="status">正在读取版本证据…</p> : error ? <button type="button" onClick={() => { setError(''); setLoading(true); setAttempt(value => value + 1) }}>重试读取证据</button> : <>
      <div className="source-evidence"><strong>{source ? `${source.display_code} · ${source.version}` : '来源文档缺失或未关联'}</strong><p>{requirement.source_location || '未记录来源位置'}</p><blockquote>{requirement.source_excerpt || '未记录原文摘录'}</blockquote>{source?.original_file ? <a href={`/api/source-documents/${encodeURIComponent(source.id)}/original`} download>下载归档原件：{source.original_file.filename}</a> : <p>仅留存正文，未归档原件</p>}{source?.original_text && <details><summary>查看留存正文</summary><pre>{source.original_text}</pre></details>}</div>
      {!!versions.length && <><div className="inline-controls"><label>对比前版本<select aria-label="对比前版本" value={leftVersion} onChange={event => setLeftVersion(Number(event.target.value))}>{versions.map(v => <option key={v.revision_no} value={v.revision_no}>V{v.revision_no}</option>)}</select></label><label>对比后版本<select aria-label="对比后版本" value={rightVersion} onChange={event => setRightVersion(Number(event.target.value))}>{versions.map(v => <option key={v.revision_no} value={v.revision_no}>V{v.revision_no}</option>)}</select></label></div><div className="table-wrap"><table><thead><tr><th>字段</th><th>V{leftVersion}</th><th>V{rightVersion}</th></tr></thead><tbody>{fields.map(field => <tr key={field.key} className={left?.snapshot[field.key] !== right?.snapshot[field.key] ? 'changed-field' : ''}><th>{field.label}</th><td>{String(left?.snapshot[field.key] ?? '未记录')}</td><td>{String(right?.snapshot[field.key] ?? '未记录')}</td></tr>)}</tbody></table></div></>}
      {!versions.length && !error && <p>没有可用的版本历史，不能推断旧版内容。</p>}
    </>}
  </DetailOverlay>
}
