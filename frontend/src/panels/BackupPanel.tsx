import { useEffect, useRef, useState } from 'react'
import { api, type BackupPreview } from '../api'
import { downloadSystemBackup } from '../dataTransfer'
import { Notice } from '../ui'
import { DEMO_ACTOR, DEMO_ROLE, toErrorMessage } from '../uiSupport'
import { Icon } from '../components/Icon'
import { clearImportDrafts } from '../importDrafts'

export function BackupPanel({ focusRequest = 0 }: { focusRequest?: number }) {
  const [backup, setBackup] = useState<unknown>(null)
  const [preview, setPreview] = useState<BackupPreview | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [restored, setRestored] = useState(false)
  const section = useRef<HTMLElement | null>(null)
  useEffect(() => { if (focusRequest) section.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' }) }, [focusRequest])
  async function download() {
    setBusy(true); setError(''); setMessage('')
    try { await downloadSystemBackup(); setMessage('完整数据备份已下载，包含版本、审核和已归档文件。') }
    catch (err) { setError(toErrorMessage(err)) }
    finally { setBusy(false) }
  }
  async function previewFile(file: File) {
    setBusy(true); setError(''); setMessage(''); setPreview(null); setBackup(null); setConfirmed(false); setRestored(false)
    try {
      if (file.size > 45 * 1024 * 1024) throw new Error('备份文件超过 45 MiB 上限')
      let value: unknown
      try { value = JSON.parse(await file.text()) } catch { throw new Error('备份文件不是有效 JSON') }
      const checked = await api.previewRestore(value)
      setBackup(value); setPreview(checked)
    } catch (err) { setError(toErrorMessage(err)) }
    finally { setBusy(false) }
  }
  async function restore() {
    if (!preview || !confirmed) return
    setBusy(true); setError(''); setMessage('')
    try {
      await api.restoreBackup({ backup, expected_state_hash: preview.expected_state_hash, actor: DEMO_ACTOR, role: DEMO_ROLE })
      setRestored(true); setPreview(null); setBackup(null)
      setMessage('恢复成功，已切换到恢复副本；原数据库保留，重新载入后查看恢复数据。')
      try { await clearImportDrafts() } catch (err) { setError(`业务备份已恢复，但当前浏览器草稿清理失败：${toErrorMessage(err)}。请勿沿用恢复前的未归档草稿。`) }
    } catch (err) { setError(toErrorMessage(err)); setConfirmed(false) }
    finally { setBusy(false) }
  }
  return <section className="panel settings-card settings-backup" id="backup-section" ref={section}><header><div><h2>数据备份与恢复</h2><p>保存完整数据快照，支持比赛前备份和演示后恢复。</p></div><Icon name="download" size={24} /></header>
    <div className="backup-options"><div><span className="backup-action-icon"><Icon name="download" size={21} /></span><strong>备份当前数据</strong><p>保存版本、审核和已归档文件，可在排练或修改前留存完整快照。</p><button type="button" onClick={() => void download()} disabled={busy}>备份 JSON</button></div><div><span className="backup-action-icon"><Icon name="consistency" size={21} /></span><strong>校验并恢复备份</strong><p>校验后切换到恢复副本，原数据库保留。支持当前系统版本的备份。</p><label className="backup-file">选择备份文件<input aria-label="选择备份文件" type="file" accept=".json" disabled={busy} onChange={event => { const file = event.target.files?.[0]; if (file) void previewFile(file); event.target.value = '' }} /></label></div></div>
    <details className="initial-showcase-help"><summary>如何恢复最初的完整展示？</summary><p>先点击“备份 JSON”保存当前进度，再在“选择备份文件”中选择项目目录下的 <code>data/initial-showcase/initial-backup.json</code>。核对预览、勾选确认，点击“确认恢复并切换数据”，最后重新载入工作台。</p><p className="hint">这是整库快照恢复，会切换所有项目及关联成果，不会合并到当前协议。重新演示则使用“清空当前项目业务数据”后导入新协议。</p></details>
    {error && <Notice kind="error">{error}</Notice>}{message && <Notice kind="success">{message}</Notice>}
    {preview && <div className="backup-preview"><strong>校验通过，尚未恢复</strong><p>{preview.counts.projects ?? 0} 个项目 · {preview.counts.requirements ?? 0} 条需求 · {preview.counts.audit_events ?? 0} 条审计记录</p><ul>{preview.projects.map(project => <li key={project.id}>{project.name}</li>)}</ul><small>校验值：{preview.snapshot_sha256}</small><label><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />我已核对备份，确认切换当前工作数据；原库保留。</label><button type="button" disabled={busy || !confirmed} onClick={() => void restore()}>确认恢复并切换数据</button></div>}
    {restored && <button type="button" className="secondary" onClick={() => window.location.reload()}>重新载入工作台</button>}
  </section>
}
