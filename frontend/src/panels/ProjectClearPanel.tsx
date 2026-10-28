import { useState } from 'react'
import { api } from '../api'
import { DetailOverlay } from '../components/DetailOverlay'
import { Icon } from '../components/Icon'
import { clearImportDrafts } from '../importDrafts'
import type { ClearPreview } from '../types'
import { Notice } from '../ui'
import { DEMO_ACTOR, DEMO_ROLE, toErrorMessage } from '../uiSupport'
import './document-import.css'

export function ProjectClearPanel({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false)
  const [trigger, setTrigger] = useState<HTMLElement | null>(null)
  const [preview, setPreview] = useState<ClearPreview | null>(null)
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<{ backup_url: string; backup_sha256: string } | null>(null)
  async function load() {
    setBusy(true); setPreview(null); setCode(''); setError('')
    try { setPreview(await api.previewProjectClear(projectId)) }
    catch (err) { setError(toErrorMessage(err)) }
    finally { setBusy(false) }
  }
  async function clear() {
    if (!preview || code !== preview.project.display_code) return
    setBusy(true); setError('')
    try {
      const saved = await api.clearProject(projectId, { expected_state_hash: preview.expected_state_hash, confirmation_code: code, actor: DEMO_ACTOR, role: DEMO_ROLE })
      setResult(saved); setPreview(null); setOpen(false)
      try { await clearImportDrafts(projectId) } catch (err) { setError(`项目已清空，但当前浏览器草稿清理失败：${toErrorMessage(err)}。请勿恢复清空前的未归档草稿。`) }
    } catch (err) { setError(toErrorMessage(err)); setPreview(null); setCode('') }
    finally { setBusy(false) }
  }
  return <section className="panel settings-card project-clear-card">
    <header><div className="settings-section-heading"><span className="settings-card-icon project-clear-icon"><Icon name="alert" size={20} /></span><div><h2>重新开始项目</h2><p>清空当前项目导入内容及关联成果，以便重新导入协议。</p></div></div></header>
    <div className="project-clear-overview"><div className="project-clear-assurances"><span>操作前自动备份</span><span>基础库与配置保留</span><span>其他项目保留</span></div>
    {!result && <button type="button" className="project-clear-trigger" onClick={event => { setTrigger(event.currentTarget); setOpen(true); void load() }}><Icon name="alert" size={16} /><span>清空当前项目业务数据</span><Icon name="arrow" size={16} /></button>}
    </div>
    {result && <div className="clear-success"><strong>当前项目已清空，清空前备份已保存</strong><p>重新载入后进入空白项目，可重新选择协议。原数据库仍保留。</p><div className="form-actions"><a href={result.backup_url} download>下载清空前完整备份</a><button type="button" onClick={() => window.location.reload()}>重新载入空白项目</button></div><details><summary>备份校验值</summary><code>{result.backup_sha256}</code></details></div>}
    {open && <DetailOverlay title="清空当前项目业务数据" eyebrow="数据管理 · 影响范围确认" returnFocus={trigger} locked={busy} pendingLabel="正在备份、校验并处理，请勿关闭…" onClose={() => setOpen(false)} footer={<div className="clear-footer"><span>先备份并校验，再清空当前项目。</span><div className="form-actions"><button type="button" className="secondary" disabled={busy} onClick={() => setOpen(false)}>取消清空</button><button type="button" className="danger-button" disabled={busy || !preview || code !== preview.project.display_code} onClick={() => void clear()}>备份并清空当前项目</button></div></div>}>
      {error && <Notice kind="error">{error}</Notice>}
      {busy && !preview && <p role="status">正在核对当前项目与影响范围…</p>}
      {preview && <><h3>{preview.project.name} · {preview.project.display_code}</h3><div className="clear-impact"><strong>将清空</strong><p>{preview.affected_counts.source_documents ?? 0} 份文档 · {preview.affected_counts.requirements ?? 0} 条需求</p><p>以及该项目的设计、试验执行、样件、问题、协同记录、审核和材料包等关联成果。</p></div><div className="clear-retained"><strong>将保留</strong><p>型谱 {preview.retained_counts.product_bases ?? 0} 个 · 基础零件 {preview.retained_counts.base_parts ?? 0} 项；其他项目与本机显示设置保留。</p><p>系统先保存完整备份，清空结果写入独立副本，原数据库保留。备份失败时不切换。</p></div><details><summary>查看各类记录影响数量</summary><dl className="clear-counts">{Object.entries(preview.affected_counts).map(([key, count]) => <div key={key}><dt>{key}</dt><dd>{count}</dd></div>)}</dl></details><label className="clear-confirm">输入项目编号 <strong>{preview.project.display_code}</strong> 确认<input aria-label="输入项目编号确认" autoComplete="off" value={code} onChange={event => setCode(event.target.value)} /></label></>}
      {!preview && !busy && <button type="button" className="secondary" onClick={() => void load()}>重新预览影响范围</button>}
    </DetailOverlay>}
  </section>
}
