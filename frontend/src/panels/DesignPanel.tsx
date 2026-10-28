import { ArtifactPreview } from '../components/ArtifactPreview'
import { DetailOverlay } from '../components/DetailOverlay'
import { SavedRefreshNotice } from '../components/SavedRefresh'
import { useSavedRefresh } from '../useSavedRefresh'
import { VersionEvidence } from '../components/BusinessEvidence'
import { ReviewContents, FmeaContents } from '../components/OutputContents'
import { modeLabel } from '../businessPresentation'
import { useCallback, useEffect, useRef, useState } from 'react'
import { DEMO_SCORES } from '../demoInputs'
import { api } from '../api'
import type {
  DesignReviewPayload,
  DfmeaPayload,
  FmeaItem,
  SimilarProjectsResult,
} from '../types'
import { Empty, Notice } from '../ui'
import { DEMO_ACTOR, DEMO_ROLE, isNotFound, reviewStatusLabels, toErrorMessage } from '../uiSupport'

type ScoreDraft = {
  revision: number
  severity: string
  occurrence: string
  detection: string
}

function draftFromItem(item: FmeaItem): ScoreDraft {
  return {
    revision: item.revision,
    severity: item.severity === null ? '' : String(item.severity),
    occurrence: item.occurrence === null ? '' : String(item.occurrence),
    detection: item.detection === null ? '' : String(item.detection),
  }
}

function scoreProblem(draft: ScoreDraft): 'missing'|'invalid'|null {
  const values=[draft.severity,draft.occurrence,draft.detection]
  if(values.some(value=>value.trim()!==''&&(!Number.isInteger(Number(value))||Number(value)<1||Number(value)>10)))return 'invalid'
  return values.some(value=>!value.trim())?'missing':null
}

export function DesignPanel(props: Parameters<typeof DesignWorkspace>[0]) {
  return <DesignWorkspace key={props.projectId} {...props} />
}

function DesignWorkspace({ projectId }: { projectId: string }) {
  const [similar, setSimilar] = useState<SimilarProjectsResult | null>(null)
  const [review, setReview] = useState<DesignReviewPayload | null>(null)
  const [reviewBase, setReviewBase] = useState('')
  const [fmea, setFmea] = useState<DfmeaPayload | null>(null)
  const [fmeaBase, setFmeaBase] = useState('')
  const baseEdited=useRef({review:false,fmea:false})
  const [baseOrigin,setBaseOrigin]=useState('')
  const [scoreDrafts, setScoreDrafts] = useState<Record<string, ScoreDraft>>(
    {},
  )
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const savedRefresh = useSavedRefresh()
  const [similarOpen, setSimilarOpen] = useState(false)
  const [similarError, setSimilarError] = useState('')
  const [similarTrigger, setSimilarTrigger] = useState<HTMLElement | null>(null)

  const applyFmea = useCallback((payload: DfmeaPayload, savedItemId?: string) => {
    setFmea(payload)
    setScoreDrafts(current =>
      Object.fromEntries(
        payload.items.map((item) => [item.id, savedItemId && item.id !== savedItemId && current[item.id]?.revision === item.revision ? current[item.id] : draftFromItem(item)]),
      ),
    )
  }, [])

  function hasUnsavedScores(item: FmeaItem) {
    const draft = scoreDrafts[item.id]
    const stored = draftFromItem(item)
    return !!draft && (['severity', 'occurrence', 'detection'] as const).some(field => draft[field] !== stored[field])
  }

  useEffect(() => {
    let cancelled = false
    Promise.allSettled([
      api.getDesignReview(projectId),
      api.getDfmea(projectId),
      api.getDesignContext(projectId),
    ])
      .then(([reviewResult, fmeaResult, contextResult]) => {
        if (cancelled) return
        if (reviewResult.status === 'fulfilled') {
          setReview(reviewResult.value)
          if(!baseEdited.current.review)setReviewBase(reviewResult.value.review.base_display_code ?? '')
        } else if (!isNotFound(reviewResult.reason)) {
          setError(toErrorMessage(reviewResult.reason))
        }
        if (fmeaResult.status === 'fulfilled') {
          applyFmea(fmeaResult.value)
          if(!baseEdited.current.fmea)setFmeaBase(fmeaResult.value.fmea.base_display_code ?? '')
        } else if (!isNotFound(fmeaResult.reason)) {
          setError(toErrorMessage(fmeaResult.reason))
        }
        if(contextResult.status==='fulfilled'&&contextResult.value.base_display_code){
          const code=contextResult.value.base_display_code
          if(!baseEdited.current.review)setReviewBase(code)
          if(!baseEdited.current.fmea)setFmeaBase(code)
          setBaseOrigin(`已沿用最近变型分析的基型 ${code}，无需重复填写；也可手动调整。`)
        }else if(contextResult.status==='rejected')setBaseOrigin('基型联动暂未读取成功，可重新进入页面或手动填写。')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [projectId, applyFmea])

  async function handleSimilar(trigger?: HTMLElement) {
    if (savedRefresh.blocked) return
    if (trigger) setSimilarTrigger(trigger)
    setSimilarOpen(true); setSimilarError(''); setSimilar(null)
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const data = await api.findSimilarProjects(projectId, 3)
      setSimilar(data)
      setMessage(`相似项目匹配 ${data.matches.length} 个`)
    } catch (err) {
      setSimilarError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleGenerateReview() {
    if (savedRefresh.blocked) return
    if (!reviewBase.trim()) {
      setError('请填写基型显示编号')
      return
    }
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const data = await api.generateDesignReview(
        projectId,
        reviewBase.trim(),
      )
      setReview(data)
      setMessage(`设计评审 ${data.review.display_code} 已生成，状态为草案`)
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleConfirmReview() {
    if (savedRefresh.blocked) return
    if (!review) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await api.confirmDesignReview(review.review.id, {
        expected_revision: review.review.revision,
        actor: DEMO_ACTOR,
        role: DEMO_ROLE,
        decision: 'confirmed',
        comment: '设计评审清单人工确认',
      })
      await savedRefresh.afterSave('设计评审审核', async () => setReview(await api.getDesignReview(projectId)))
      setMessage('设计评审已确认')
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleGenerateFmea() {
    if (savedRefresh.blocked) return
    if (!fmeaBase.trim()) {
      setError('请填写基型显示编号')
      return
    }
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const data = await api.generateDfmea(projectId, fmeaBase.trim())
      applyFmea(data)
      setMessage(`DFMEA ${data.fmea.display_code} 已生成`)
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleSaveScores(item: FmeaItem) {
    if (savedRefresh.blocked) return
    const draft = scoreDrafts[item.id]
    if (!draft) return
    const values = [
      draft.severity,
      draft.occurrence,
      draft.detection,
    ].map((value) => Number(value))
    if (values.some((value) => !Number.isInteger(value) || value < 1 || value > 10)) {
      setError('S/O/D 必须是 1–10 的整数')
      return
    }
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await api.updateFmeaItem(item.id, {
        expected_revision: item.revision,
        actor: DEMO_ACTOR,
        role: DEMO_ROLE,
        severity: values[0],
        occurrence: values[1],
        detection: values[2],
      })
      await savedRefresh.afterSave('DFMEA评分', async () => applyFmea(await api.getDfmea(projectId), item.id))
      setMessage(`${item.display_code} 评分已保存，需人工确认后才计入 RPN`)
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleConfirmScores(item: FmeaItem) {
    if (savedRefresh.blocked) return
    if (hasUnsavedScores(item)) { setError('评分有未保存修改，请先保存评分。'); return }
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await api.confirmFmeaScores(item.id, {
        expected_revision: item.revision,
        actor: DEMO_ACTOR,
        role: DEMO_ROLE,
        comment: 'S/O/D 评分人工确认',
      })
      await savedRefresh.afterSave('DFMEA评分审核', async () => applyFmea(await api.getDfmea(projectId), item.id))
      setMessage(`${item.display_code} 评分已确认，RPN 按确认量表计算`)
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleConfirmFmea() {
    if (savedRefresh.blocked) return
    if (!fmea) return
    if (fmea.items.some(hasUnsavedScores)) { setError('评分有未保存修改，请先保存评分。'); return }
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await api.confirmDfmea(fmea.fmea.id, {
        expected_revision: fmea.fmea.revision,
        actor: DEMO_ACTOR,
        role: DEMO_ROLE,
        decision: 'confirmed',
        comment: 'DFMEA 人工确认',
      })
      await savedRefresh.afterSave('DFMEA审核', async () => applyFmea(await api.getDfmea(projectId)))
      setMessage('DFMEA 已确认')
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
      <SavedRefreshNotice state={savedRefresh} busy={busy} />

      <section className="panel">
        <div className="panel-heading">
          <h2>相似项目</h2>
          <span className="mode-badge">{modeLabel(similar?.mode)} · 历史项目库</span>
        </div>
        <div className="inline-controls">
          <button type="button" disabled={busy || savedRefresh.blocked} onClick={event => void handleSimilar(event.currentTarget)}>
            重新计算相似项目
          </button>
          {similar && <button type="button" className="secondary" disabled={busy || savedRefresh.blocked} onClick={event => { setSimilarTrigger(event.currentTarget); setSimilarOpen(true) }}>查看相似项目</button>}
          {similar && (
            <span className="muted">
              候选 {similar.candidate_count} 个 · 来源 {similar.source_label}
            </span>
          )}
        </div>
        {!loading && !similar && <Empty>暂无相似项目结果。</Empty>}
        {similarOpen && <DetailOverlay variant="wide" title="相似项目匹配结果" subtitle="匹配点、差异及缺失判据" eyebrow="设计知识 · 历史项目检索" locked={busy} pendingLabel="正在计算相似项目，请稍候…" returnFocus={similarTrigger} closeLabel="关闭相似项目" onClose={() => setSimilarOpen(false)}>
        {busy && <p role="status">正在匹配历史项目…</p>}
        {similarError && <><Notice kind="error">{similarError}</Notice><button type="button" onClick={() => void handleSimilar()}>重试匹配项目</button></>}
        {similar && <><p className="muted">{similar.source_label} · 候选 {similar.candidate_count} 个 · 返回 {similar.matches.length} 个{similar.candidate_shortage ? ' · 候选不足，如实显示' : ''}</p><VersionEvidence rows={similar.requirement_versions} title="匹配输入依据" /></>}
        {similar && similar.matches.length === 0 && (
          <Empty>历史项目库中没有匹配项。</Empty>
        )}
        {similar && similar.matches.length > 0 && (
          <div className="card-list">
            {similar.matches.map((match) => (
              <article className="card" key={match.history_project_id}>
                <header>
                  <strong>
                    <span className="mono">{match.display_code}</span>{' '}
                    {match.name}
                  </strong>
                  <span className="score">相似度 {match.score.toFixed(1)}</span>
                </header>
                <p className="muted">
                  {match.customer} · 来源 {match.source}
                </p>
                <p>
                  匹配点：{match.matched_points.join('、') || '无'}
                </p>
                <p>
                  差异：{match.differences.join('、') || '无'}
                </p>
                {match.missing_criteria.length > 0 && (
                  <p className="muted">
                    缺失判据：{match.missing_criteria.join('、')}
                  </p>
                )}
              </article>
            ))}
          </div>
        )}
        </DetailOverlay>}
      </section>

      {baseOrigin&&<p className="hint">{baseOrigin}</p>}
      <section className="panel" aria-label="设计评审工作区" data-object-id={review?.review.id}>
        <div className="panel-heading">
          <h2>设计评审清单</h2>
          {review && <ArtifactPreview title="设计评审" code={review.review.display_code} revision={review.review.revision} status={review.review.status} mode={review.mode}><ReviewContents data={review} /></ArtifactPreview>}
          {review && (
            <span className="count">
              {review.review.display_code} · V{review.review.revision} ·{' '}
              {reviewStatusLabels[
                review.review.status as keyof typeof reviewStatusLabels
              ] ?? review.review.status}
            </span>
          )}
        </div>
        <div className="inline-controls">
          <label>
            基型显示编号
            <input
              aria-label="设计评审基型编号"
              placeholder="上一步选用的基型，如 JX-12A"
              value={reviewBase}
              onChange={(event) => {baseEdited.current.review=true;setReviewBase(event.target.value)}}
            />
          </label>
          <button type="button" disabled={busy || savedRefresh.blocked} onClick={() => void handleGenerateReview()}>
            {review ? '重新生成' : '生成设计评审'}
          </button>
          {review && review.review.status !== 'confirmed' && (
            <button type="button" disabled={busy || savedRefresh.blocked} onClick={() => void handleConfirmReview()}>
              确认设计评审
            </button>
          )}
        </div>
        {review?.needs_reconfirmation && (
          <Notice kind="info">评审输入或内容已变化，请重新生成并复核确认。</Notice>
        )}
        {review?.missing_inputs.length ? (
          <Notice kind="info">
            缺失输入：{review.missing_inputs.join('；')}
          </Notice>
        ) : null}
        {!review ? (
          <Empty>尚未生成设计评审清单。</Empty>
        ) : (
          <div className="review-work-summary">
            <strong>{review.items.length} 项检查</strong>
            <p className="hint">完整检查项、标准、依赖需求和审核记录统一在“预览设计评审”中核对。</p>
            <div className="review-item-index" aria-label="评审条目索引">{review.items.map(item => <span key={item.id} className="mono" data-object-id={item.id} title={item.check_point}>{item.display_code}</span>)}</div>
          </div>
        )}
      </section>

      <section className="panel" data-object-id={fmea?.fmea.id}>
        <div className="panel-heading">
          <h2>DFMEA</h2>
          {fmea && <ArtifactPreview title="DFMEA" code={fmea.fmea.display_code} revision={fmea.fmea.revision} status={fmea.fmea.status} mode={fmea.mode}><FmeaContents data={fmea} /></ArtifactPreview>}
          {fmea && (
            <span className="count">
              {fmea.fmea.display_code} · V{fmea.fmea.revision} ·{' '}
              {reviewStatusLabels[
                fmea.fmea.status as keyof typeof reviewStatusLabels
              ] ?? fmea.fmea.status}
            </span>
          )}
        </div>
        <p className="hint">
          RPN = 已确认的 S × O × D。评分未确认时显示“待确认”，不会按行号或默认值编造。
        </p>
        <div className="inline-controls">
          <label>
            基型显示编号
            <input
              aria-label="DFMEA 基型编号"
              placeholder="与变型分析一致的基型，如 JX-12A"
              value={fmeaBase}
              onChange={(event) => {baseEdited.current.fmea=true;setFmeaBase(event.target.value)}}
            />
          </label>
          <button type="button" disabled={busy || savedRefresh.blocked} onClick={() => void handleGenerateFmea()}>
            {fmea ? '重新生成' : '生成 DFMEA'}
          </button>
          {fmea && fmea.fmea.status !== 'confirmed' && (
            <button type="button" disabled={busy || savedRefresh.blocked || fmea.items.some(item=>!item.scores_confirmed||hasUnsavedScores(item))} onClick={() => void handleConfirmFmea()}>
              确认 DFMEA
            </button>
          )}
        </div>
        {fmea&&<div className="inline-controls"><button type="button" className="demo-fill-button" disabled={busy||savedRefresh.blocked} onClick={()=>{
          setScoreDrafts(current=>({...current,...Object.fromEntries(fmea.items.flatMap(item=>{
            const scores=DEMO_SCORES[item.display_code]
            const draft=current[item.id]??draftFromItem(item)
            const blankDraft=[draft.severity,draft.occurrence,draft.detection].every(value=>!value.trim())
            return scores&&blankDraft&&item.severity===null&&item.occurrence===null&&item.detection===null?[[item.id,{revision:item.revision,severity:String(scores[0]),occurrence:String(scores[1]),detection:String(scores[2])}]]:[]
          }))}));setMessage('已填入合成评分草稿，尚未保存或确认；已有评分不覆盖。')
        }}>填入合成评分</button><span className="hint">来源：04_试验与评审样例 · 合成量表。仅填空白评分，保存后仍需人工确认。</span></div>}
        {fmea?.needs_reconfirmation && (
          <Notice kind="info">DFMEA 输入或内容已变化，请重新生成并复核确认。</Notice>
        )}
        {fmea?.missing_inputs.length ? (
          <Notice kind="info">
            缺失输入：{fmea.missing_inputs.join('；')}
          </Notice>
        ) : null}
        {!fmea ? (
          <Empty>尚未生成 DFMEA。</Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>编号</th>
                  <th>功能</th>
                  <th>失效模式</th>
                  <th>原因</th>
                  <th>影响</th>
                  <th>控制 / 措施</th>
                  <th>S</th>
                  <th>O</th>
                  <th>D</th>
                  <th>RPN</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {fmea.items.map((item) => {
                  const draft = scoreDrafts[item.id] ?? draftFromItem(item)
                  const problem=scoreProblem(draft)
                  const dirty=hasUnsavedScores(item)
                  return (
                    <tr key={item.id} data-object-id={item.id}>
                      <td className="mono">{item.display_code}</td>
                      <td className="source">{item.function_text}</td>
                      <td className="source">{item.failure_mode}</td>
                      <td className="source">{item.cause}</td>
                      <td className="source">{item.effect}</td>
                      <td className="source">
                        <span>{item.control}</span>
                        <small>措施：{item.action_text || '待定'}</small>
                      </td>
                      {(['severity', 'occurrence', 'detection'] as const).map(
                        (field) => (
                          <td key={field}>
                            <input
                              aria-label={`${item.display_code} ${field}`}
                              className="score-input"
                              type="number"
                              min={1}
                              step={1}
                              aria-invalid={problem==='invalid'||undefined}
                              disabled={busy||savedRefresh.blocked}
                              max={10}
                              value={draft[field]}
                              onChange={(event) =>
                                setScoreDrafts((current) => ({
                                  ...current,
                                  [item.id]: {
                                    ...draft,
                                    [field]: event.target.value,
                                  },
                                }))
                              }
                            />
                          </td>
                        ),
                      )}
                      <td className="fmea-rpn">
                        {problem==='invalid'?'数值无效':problem==='missing'?'待填写':dirty?'待保存':item.rpn_status==='confirmed'?item.rpn:'待确认'}
                      </td>
                      <td className="actions fmea-score-actions">
                        <button
                          type="button"
                          disabled={busy || savedRefresh.blocked || !!problem || !dirty}
                          onClick={() => void handleSaveScores(item)}
                        >
                          保存评分
                        </button>
                        <button
                          type="button"
                          className="secondary"
                          disabled={busy || savedRefresh.blocked || item.scores_confirmed || dirty || !!problem}
                          onClick={() => void handleConfirmScores(item)}
                        >
                          确认评分
                        </button>
                        {problem==='invalid'?<small className="score-validation">S/O/D 必须是 1–10 的整数</small>:problem==='missing'?<small>请填齐 S、O、D 后保存。</small>:dirty?<small>评分有未保存修改，请先保存评分。</small>:null}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}
