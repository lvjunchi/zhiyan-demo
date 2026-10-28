import { useState } from 'react'
import { api } from '../api'
import { PartChoicesPanel } from './PartChoicesPanel'
import { ProductImage } from '../components/ProductImage'
import { EngineeringRecords } from '../components/EngineeringRecords'
import { VersionEvidence } from '../components/BusinessEvidence'
import { DetailOverlay } from '../components/DetailOverlay'
import { criterionLabels, engineeringValue, ratioLabel } from '../businessPresentation'
import type {
  RecommendationResult,
  VariantAnalysisResult,
} from '../types'
import { Empty, Notice } from '../ui'
import { classificationLabels, toErrorMessage, variantTypeLabels } from '../uiSupport'

export function BasesPanel({ projectId }: { projectId: string }) {
  return <BasesWorkspace key={projectId} projectId={projectId} />
}
function BasesWorkspace({ projectId }: { projectId: string }) {
  const [topN, setTopN] = useState('3')
  const [recommendation, setRecommendation] =
    useState<RecommendationResult | null>(null)
  const [baseCode, setBaseCode] = useState('')
  const [variant, setVariant] = useState<VariantAnalysisResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [engineeringRefresh, setEngineeringRefresh] = useState(0)
  const [partReviewRefresh, setPartReviewRefresh] = useState(0)
  const [recommendOpen, setRecommendOpen] = useState(false)
  const [recommendError, setRecommendError] = useState('')
  const [recommendTrigger, setRecommendTrigger] = useState<HTMLElement | null>(null)
  const [variantOpen, setVariantOpen] = useState(false)
  const [variantError, setVariantError] = useState('')
  const [variantTrigger, setVariantTrigger] = useState<HTMLElement | null>(null)

  async function handleRecommend(trigger?: HTMLElement) {
    if (trigger) setRecommendTrigger(trigger)
    setRecommendOpen(true); setRecommendError(''); setRecommendation(null)
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const data = await api.recommendBases(projectId, Number(topN))
      setRecommendation(data)
      setMessage(
        `按受控候选与评分口径计算，返回 ${data.top3.length} 个候选` +
          (data.candidate_shortage ? '（候选不足，如实显示）' : ''),
      )
    } catch (err) {
      setRecommendError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleVariant(trigger?: HTMLElement) {
    if (!baseCode.trim()) {
      setError('请先填写基型显示编号')
      return
    }
    if (trigger) setVariantTrigger(trigger)
    setVariantOpen(true)
    setVariantError('')
    setVariant(null)
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const data = await api.runVariantAnalysis(
        projectId,
        baseCode.trim(),
      )
      setVariant(data)
      setEngineeringRefresh(value => value + 1)
      setMessage(
        `变型点 ${data.variants.length} 个，可复用件 ${data.reusable_parts.length} 项`,
      )
    } catch (err) {
      setVariantError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      {error && <Notice kind="error">{error}</Notice>}
      {message && <Notice kind="success">{message}</Notice>}

      <section className="panel">
        <div className="panel-heading">
          <h2>型谱 Top-3</h2>
          <span className="mode-badge">规则计算 · 受控候选</span>
        </div>
        <p className="hint">
          评分由已确认需求与受控型谱候选计算，逐项依据、硬约束与缺失项均真实展示；
          候选不足三项时如实显示，不补齐。
        </p>
        <div className="inline-controls">
          <label>
            返回数量
            <input
              aria-label="型谱返回数量"
              type="number"
              min={1}
              max={10}
              value={topN}
              onChange={(event) => setTopN(event.target.value)}
            />
          </label>
          <button type="button" disabled={busy} onClick={event => void handleRecommend(event.currentTarget)}>
            计算 Top-3
          </button>
          {recommendation && <><button type="button" className="secondary" disabled={busy} onClick={event => { setRecommendTrigger(event.currentTarget); setRecommendOpen(true) }}>查看推荐结果</button><span className="muted">最近计算 · 返回 {recommendation.top3.length} 个候选</span></>}
        </div>

        {recommendOpen && <DetailOverlay variant="wide" title="型谱推荐结果" subtitle="受控候选 · 评分依据与硬约束" eyebrow="型谱选型 · Top-3" locked={busy} pendingLabel="正在计算推荐，请稍候…" returnFocus={recommendTrigger} closeLabel="关闭推荐结果" onClose={() => setRecommendOpen(false)} footer="选用基型仅填入变型分析；运行分析和人工审核需分别操作。">
        {busy && <p role="status">正在计算候选与评分依据…</p>}
        {recommendError && <><Notice kind="error">{recommendError}</Notice><button type="button" onClick={() => void handleRecommend()}>重试计算推荐</button></>}
        {recommendation && !busy && (
          <>
            <p className="hint">
              受控候选 {recommendation.candidate_count} 个 ·
              评分依据来自以下已保存的需求版本
            </p>
            <VersionEvidence rows={recommendation.requirement_versions} title="选型输入依据" />
            {recommendation.missing_requirements.length > 0 && (
              <Notice kind="error">
                缺少匹配需求：
                {recommendation.missing_requirements.map(key => criterionLabels[key] ?? key).join('、')}
              </Notice>
            )}
            {recommendation.top3.length === 0 ? (
              <Empty>没有满足条件的候选。</Empty>
            ) : (
              <div className="card-list">
                {recommendation.top3.map((evaluation, index) => (
                  <article className="card" key={evaluation.base.id}>
                    <div style={{width:180,maxWidth:"100%"}}><ProductImage/></div><p className="hint">产品参考图 · 非候选型号实物照片</p>
                    <header>
                      <strong>
                        #{index + 1}{' '}
                        <span className="mono">
                          {evaluation.base.display_code}
                        </span>{' '}
                        {evaluation.base.name}
                      </strong>
                      <span className="score">
                        得分 {evaluation.score.toFixed(1)}
                      </span>
                    </header>
                    <p className="muted">
                      {evaluation.base.transmission_type} ·{' '}
                      {evaluation.base.gear_count} 档 · 额定输入扭矩{' '}
                      {evaluation.base.rated_input_torque} N·m ·{' '}
                      {evaluation.base.weight_kg} kg · 来源{' '}
                      {evaluation.base.source}
                    </p>
                    <button type="button" onClick={() => { setBaseCode(evaluation.base.display_code); setRecommendOpen(false) }}>选用 {evaluation.base.display_code}</button>
                    {evaluation.hard_failures.length > 0 && (
                      <p className="danger">
                        硬约束不满足：{evaluation.hard_failures.map(key => criterionLabels[key] ?? key).join('、')}
                      </p>
                    )}
                    {evaluation.missing_items.length > 0 && (
                      <p className="muted">
                        缺失依据：{evaluation.missing_items.map(key => criterionLabels[key] ?? key).join('、')}
                      </p>
                    )}
                    <details className="business-evidence"><summary>查看评分依据</summary><div className="business-evidence-body table-wrap"><table className="inner-table">
                      <thead>
                        <tr>
                          <th>评分项</th>
                          <th>需求值</th>
                          <th>候选值</th>
                          <th>权重</th>
                          <th>得分</th>
                          <th>依据</th>
                        </tr>
                      </thead>
                      <tbody>
                        {evaluation.criteria.map((criterion) => (
                          <tr key={criterion.criterion}>
                            <td title={criterion.criterion}>{criterionLabels[criterion.criterion] ?? criterion.criterion}</td>
                            <td>{engineeringValue(criterion.requirement_value)}</td>
                            <td>{engineeringValue(criterion.candidate_value)}</td>
                            <td>{ratioLabel(criterion.weight)}</td>
                            <td>{criterion.score !== null && Number.isFinite(criterion.score) ? criterion.score.toFixed(1) : '缺失'}</td>
                            <td className="source">
                              <span>{criterion.reason}</span>
                              <small>{criterion.source}</small>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table></div></details>
                  </article>
                ))}
              </div>
            )}
          </>
        )}
        </DetailOverlay>}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <h2>变型点与可复用件</h2>
        </div>
        <p className="hint">基型编号是型谱中的型号，例如 JX-12A；可在“型谱推荐结果”中点击“选用”自动填写。它不是需求编号或零件型号。变型点由基型与需求差异计算，复用件保留来源与依据。</p>
        <div className="inline-controls">
          <label>
            基型显示编号
            <input
              aria-label="变型分析基型编号"
              value={baseCode}
              onChange={(event) => setBaseCode(event.target.value)}
              placeholder="填写型谱中的基型编号"
            />
          </label>
          <button type="button" disabled={busy} onClick={event => void handleVariant(event.currentTarget)}>
            运行变型分析
          </button>
          {variant && <><button type="button" className="secondary" disabled={busy} onClick={event => { setVariantTrigger(event.currentTarget); setVariantOpen(true) }}>查看变型结果</button><span className="muted">基型 {variant.base.display_code} · 变型点 {variant.variants.length} 个 · 可复用件 {variant.reusable_parts.length} 项</span></>}
        </div>

        {variantOpen && <DetailOverlay variant="wide" title="变型分析结果" subtitle="基型差异 · 变型点与可复用件依据" eyebrow="变型设计 · 工程决策" locked={busy} pendingLabel="正在运行变型分析，请稍候…" returnFocus={variantTrigger} closeLabel="关闭变型结果" onClose={() => setVariantOpen(false)} footer="结果保留本次分析依据；关闭后可查看已保存的工程决策，并分别审核当前版本。">
        {busy && <p role="status">正在比对基型与需求，并保存分析结果…</p>}
        {variantError && <><Notice kind="error">{variantError}</Notice><button type="button" onClick={() => void handleVariant()}>重试变型分析</button></>}
        {variant && !busy && (
          <>
            <p className="hint">
              基型 {variant.base.display_code} {variant.base.name} ·
              额定输入扭矩 {variant.base.rated_input_torque} N·m ·
              变型点 {variant.variants.length} 个 ·
              失效变型点 {variant.stale_variants.length} 个
            </p>
            <VersionEvidence rows={variant.requirement_versions} title="变型输入依据" />
            <p className="table-scroll-hint">左右滑动表格查看全部参数、依据与来源。</p>
            {variant.pending_items.length > 0 && (
              <Notice kind="info">
                待人工确认：{variant.pending_items.join('；')}
              </Notice>
            )}
            {variant.variants.length === 0 ? (
              <Empty>未计算出变型点。</Empty>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>编号</th>
                      <th>参数</th>
                      <th>基型值</th>
                      <th>需求值</th>
                      <th>类型</th>
                      <th>影响部件</th>
                      <th>依据</th>
                    </tr>
                  </thead>
                  <tbody>
                    {variant.variants.map((item) => (
                      <tr key={item.id}>
                        <td className="mono">{item.display_code}</td>
                        <td>{item.parameter_name}</td>
                        <td>{item.base_value || '—'}</td>
                        <td>{item.requirement_value || '—'}</td>
                        <td>
                          {variantTypeLabels[item.variant_type] ??
                            item.variant_type}
                        </td>
                        <td>{item.affected_parts.join('、') || '—'}</td>
                        <td className="source">{item.basis}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <h3 className="section-title">可复用件决策</h3>
            {variant.reusable_parts.length === 0 ? (
              <Empty>暂无可复用件决策。</Empty>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>零件号</th>
                      <th>名称</th>
                      <th>原编号</th>
                      <th>分类</th>
                      <th>原因</th>
                      <th>来源</th>
                    </tr>
                  </thead>
                  <tbody>
                    {variant.reusable_parts.map((item) => (
                      <tr key={item.id}>
                        <td className="mono">
                          {item.part_display_code}
                        </td>
                        <td>{item.part_name}</td>
                        <td>{item.part_number}</td>
                        <td>
                          {classificationLabels[item.classification] ??
                            item.classification}
                        </td>
                        <td className="source">{item.reason}</td>
                        <td className="source">{item.source}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
        </DetailOverlay>}
      </section>
      <EngineeringRecords projectId={projectId} refreshKey={engineeringRefresh} onChanged={()=>setPartReviewRefresh(value=>value+1)} />
      <PartChoicesPanel projectId={projectId} refreshKey={engineeringRefresh + partReviewRefresh} onChanged={()=>setEngineeringRefresh(value=>value+1)}/>
    </>
  )
}
