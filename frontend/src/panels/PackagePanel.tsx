import { PackageContents } from '../components/OutputContents'
import { DetailOverlay } from '../components/DetailOverlay'
import { modeLabel } from '../businessPresentation'
import { useCallback, useEffect, useId, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api'
import { MaterialBlockers } from '../components/MaterialBlockers'
import type { NavigateTo } from '../navigation'
import type {
  MaterialPackageDetail,
  MaterialPackageSummary,
} from '../types'
import { Empty, Notice } from '../ui'
import { DEMO_ACTOR, DEMO_ROLE, formatTime, packageStatusLabels, toErrorMessage } from '../uiSupport'

export function PackagePanel(props: Parameters<typeof PackageWorkspace>[0]) {
  return <PackageWorkspace key={props.projectId} {...props} />
}

function PackageWorkspace({ projectId, onNavigate }: { projectId: string; onNavigate?: NavigateTo }) {
  const [packages, setPackages] = useState<MaterialPackageSummary[]>([])
  const [detail, setDetail] = useState<MaterialPackageDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [refreshError, setRefreshError] = useState('')
  const [includeOriginals, setIncludeOriginals] = useState(false)
  const [comment, setComment] = useState('')
  const [showHistory, setShowHistory] = useState(false)
  const historyId = useId()
  const [previewTarget, setPreviewTarget] = useState<Pick<MaterialPackageSummary, 'id' | 'display_code'> | null>(null)
  const [preview, setPreview] = useState<MaterialPackageDetail | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState('')
  const [previewTrigger, setPreviewTrigger] = useState<HTMLElement | null>(null)
  const previewRequest = useRef({ sequence: 0 })

  const loadPackages = useCallback(async () => {
    const data = await api.listMaterialPackages(projectId)
    const loaded = data.length > 0 ? await api.getMaterialPackage(data[0].id) : null
    setPackages(data)
    setDetail(loaded)
    return data
  }, [projectId])

  async function refreshSavedPackage(saved: MaterialPackageDetail) {
    setDetail(saved)
    setPackages(items => [saved, ...items.filter(item => item.id !== saved.id)].sort((a, b) => b.package_no - a.package_no))
    try {
      await loadPackages()
      setRefreshError('')
    } catch (err) {
      setRefreshError(`材料 ${saved.display_code} 已保存，列表刷新失败：${toErrorMessage(err)}`)
    }
  }

  async function retryRefresh() {
    setBusy(true)
    try { await loadPackages(); setRefreshError('') }
    catch (err) { setRefreshError(`已保存，列表刷新失败：${toErrorMessage(err)}`) }
    finally { setBusy(false) }
  }

  useEffect(() => {
    let cancelled = false
    const requestScope = previewRequest.current
    api
      .listMaterialPackages(projectId)
      .then(async (data) => {
        if (cancelled) return
        setPackages(data)
        if (data.length > 0) {
          const loaded = await api.getMaterialPackage(data[0].id)
          if (!cancelled) setDetail(loaded)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(toErrorMessage(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
      requestScope.sequence++
    }
  }, [projectId])

  async function handleGenerate(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const created = await api.createMaterialPackage(projectId, {
        include_originals: includeOriginals,
        actor: DEMO_ACTOR,
      })
      await refreshSavedPackage(created)
      setMessage(
        created.status === 'ready_to_submit'
          ? `材料包 ${created.display_code} 门禁通过，可提交（尚未人工批准）`
          : `材料包 ${created.display_code} 已生成草稿：仍有阻断项`,
      )
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleView(item: Pick<MaterialPackageSummary, 'id' | 'display_code'>, trigger?: HTMLElement) {
    const request = ++previewRequest.current.sequence
    if (trigger) setPreviewTrigger(trigger)
    setPreviewTarget(item)
    setPreview(null)
    setPreviewLoading(true)
    setPreviewError('')
    try {
      const loaded = await api.getMaterialPackage(item.id)
      if (request === previewRequest.current.sequence) setPreview(loaded)
    } catch (err) {
      if (request === previewRequest.current.sequence) setPreviewError(toErrorMessage(err))
    } finally {
      if (request === previewRequest.current.sequence) setPreviewLoading(false)
    }
  }

  function closePreview() {
    previewRequest.current.sequence++
    setPreviewTarget(null)
    setPreview(null)
    setPreviewLoading(false)
  }

  async function handleDownload(packageId: string) {
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const { blob, filename, sha256 } = await api.downloadMaterialPackage(
        packageId,
      )
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename ?? `${packageId}.zip`
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
      setMessage(
        `已下载 ${filename ?? '材料包'}（${blob.size} 字节，SHA-256 ` +
          `${sha256?.slice(0, 16) ?? '未知'}…）。导出成功不等于可提交。`,
      )
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleApprove(event: FormEvent) {
    event.preventDefault()
    if (!detail) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const approved = await api.approveMaterialPackage(detail.id, {
        expected_snapshot_hash: detail.snapshot_hash,
        actor: DEMO_ACTOR,
        role: DEMO_ROLE,
        comment: comment.trim(),
      })
      await refreshSavedPackage(approved)
      setComment('')
      setMessage('快照已冻结并完成人工批准')
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      {error && <Notice kind="error">{error}</Notice>}
      {message && <Notice kind="success">{message}</Notice>}
      {refreshError && <Notice kind="info">{refreshError}。请先刷新核对，避免重复提交。<button type="button" disabled={busy} onClick={() => void retryRefresh()}>重试刷新材料</button></Notice>}

      <section className="panel">
        <div className="panel-heading">
          <h2>评审材料包</h2>
          <span className="mode-badge">快照 · 可复现导出</span>
        </div>
        <p className="hint">
          材料包保留生成时快照与校验值；草稿可导出并列明缺口，
          门禁通过后仍需人工批准冻结。JSON 备份不等同于材料包。
        </p>
        <form
          className="inline-controls"
          onSubmit={(event) => void handleGenerate(event)}
        >
          <label>
            <input
              type="checkbox"
              checked={includeOriginals}
              onChange={(event) =>
                setIncludeOriginals(event.target.checked)
              }
            />
            附带来源正文、已归档原件与样件文件
          </label>
          <small className="hint">附件包含登记正文及实际已归档原文件；历史仅正文的文档不会补造原件。</small>
          <button type="submit" disabled={busy || !!refreshError}>
            生成材料包
          </button>
        </form>

        {loading ? (
          <Empty>正在加载材料包…</Empty>
        ) : packages.length === 0 ? (
          <Empty>尚无材料包。</Empty>
        ) : (
          <>
          {packages.length > 1 && <div className="inline-controls"><button type="button" className="secondary" aria-expanded={showHistory} aria-controls={historyId} onClick={() => setShowHistory(value => !value)}>{showHistory ? '收起' : '展开'}历史材料包（{packages.length - 1}）</button><span className="muted">默认展示最新材料包；历史快照保留，可展开查看和下载。</span></div>}
          <div className="table-wrap">
            <table id={historyId} aria-label="材料包列表">
              <thead>
                <tr>
                  <th>编号</th>
                  <th>状态</th>
                  <th>门禁</th>
                  <th>生成</th>
                  <th>哈希</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {(showHistory ? packages : packages.slice(0, 1)).map((item) => (
                  <tr key={item.id} data-object-id={item.id}>
                    <td className="mono">{item.display_code}</td>
                    <td>
                      <span
                        className={`status ${
                          item.status === 'human_approved'
                            ? 'confirmed'
                            : item.status === 'ready_to_submit'
                              ? 'pending_review'
                              : 'draft'
                        }`}
                      >
                        {item.requires_regeneration ? '旧版门禁 · 请重新生成' : packageStatusLabels[item.status] ?? item.status}
                      </span>
                    </td>
                    <td>
                      {item.requires_regeneration ? '历史门禁，需重新检查' : item.gate.ready
                        ? '可提交'
                        : `阻断 ${item.gate.blockers.length} 项`}
                      {item.gate.warnings.length > 0
                        ? ` · 警告 ${item.gate.warnings.length} 项`
                        : ''}
                    </td>
                    <td className="source">
                      <span>{formatTime(item.created_at)}</span>
                      <small>
                        创建人 {item.created_by} ·{' '}
                        {item.include_originals ? '含原件' : '不含原件'}
                      </small>
                    </td>
                    <td className="mono" title={item.snapshot_hash}>
                      {item.snapshot_hash.slice(0, 12)}…
                    </td>
                    <td className="actions">
                      <button
                        type="button"
                        disabled={busy}
                        onClick={event => void handleView(item, event.currentTarget)}
                      >
                        查看
                      </button>
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy}
                        onClick={() => void handleDownload(item.id)}
                      >
                        下载 ZIP
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </>
        )}
      </section>

      {previewTarget && <DetailOverlay variant="wide" title={`材料包详情 · ${previewTarget.display_code}`} eyebrow="评审材料 · 快照与门禁" subtitle={preview ? `${preview.requires_regeneration ? '旧版门禁 · 需重新生成' : packageStatusLabels[preview.status]} · ${modeLabel(preview.mode)}` : '读取材料快照与门禁依据'} returnFocus={previewTrigger} closeLabel="关闭材料详情" onClose={closePreview} footer="只读材料快照 · 查看历史不切换当前门禁待办 · Esc 关闭返回原记录">
        {previewLoading && <p role="status">正在读取材料详情…</p>}
        {previewError && <><Notice kind="error">{previewError}</Notice><button type="button" onClick={() => void handleView(previewTarget)}>重试加载材料</button></>}
        {preview && <div className="material-package-contents"><p className="muted preview-hash">ZIP SHA-256：{preview.zip_sha256}</p><p className="table-scroll-hint">左右滑动表格查看完整检查与文件清单。</p><PackageContents data={preview} />{preview.gate.warnings.length > 0 && <section className="preview-section"><h3>补充提示</h3><ul>{preview.gate.warnings.map((warning, index) => <li key={`${warning.code}-${index}`}>{warning.message}</li>)}</ul></section>}</div>}
      </DetailOverlay>}

      {detail && (
        <section className="panel material-preparation" aria-label="当前材料准备">
          <div className="panel-heading">
            <h2>当前材料准备</h2>
            <span className={`status ${detail.status === 'human_approved' ? 'confirmed' : detail.status === 'ready_to_submit' ? 'pending_review' : 'draft'}`}>
              {detail.requires_regeneration ? '旧版门禁 · 请重新生成' : packageStatusLabels[detail.status]}
            </span>
          </div>
          <div className="material-preparation-summary">
            <div><strong>{detail.display_code}</strong><p className="muted">{formatTime(detail.created_at)} 生成 · {detail.frozen_at ? `${formatTime(detail.frozen_at)} 冻结` : '尚未冻结'}</p></div>
            <div className="material-preparation-counts">
              <strong>{detail.gate.summary.passed_check_count}/{detail.gate.summary.check_count} 项检查通过</strong>
              <span>阻断 {detail.gate.blockers.length} 项</span>
              <span>提示 {detail.gate.warnings.length} 项</span>
            </div>
          </div>
          <p className="hint">本区处理最新材料包的准备事项与审批。完整检查、快照校验值和文件清单，请从上方列表点击“查看”。</p>
          {detail.requires_regeneration && <Notice kind="info">该包使用旧版门禁，请核对当前成果并生成新材料包；历史快照仍可查看和下载。</Notice>}
          {detail.gate.blockers.length > 0 && <MaterialBlockers blockers={detail.gate.blockers} onNavigate={onNavigate} />}
          {detail.status === 'ready_to_submit' && !detail.requires_regeneration && (
            <form className="inline-action" onSubmit={event => void handleApprove(event)}>
              <h3>人工批准（冻结当前快照）</h3>
              <p className="hint">请先从列表“查看”核对当前快照与门禁，再填写意见批准；批准后冻结本材料包。</p>
              <label className="wide">审批意见<input aria-label="材料包审批意见" value={comment} onChange={event => setComment(event.target.value)} required /></label>
              <div className="form-actions"><button type="submit" disabled={busy || !!refreshError}>核对哈希后批准</button></div>
            </form>
          )}
          {detail.status === 'draft' && <Notice kind="info">当前为草稿，可下载供核对。处理待办后请重新生成材料包，再检查提交条件。</Notice>}
          {detail.status === 'human_approved' && <Notice kind="success">已完成人工批准，快照已冻结。</Notice>}
        </section>
      )}
    </>
  )
}
