import { DEMO_COORDINATION } from '../demoInputs'
import { communicationPreset,isDemoTopic } from './coordinationDemo'
import { CoordinationProgress } from '../components/CoordinationProgress'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api'
import { DetailOverlay } from '../components/DetailOverlay'
import { SavedRefreshNotice } from '../components/SavedRefresh'
import { useSavedRefresh } from '../useSavedRefresh'
import type {
  CoordinationOverview,
  CoordinationTopic,
} from '../types'
import { Empty, Notice } from '../ui'
import { DEMO_ACTOR, DEMO_ROLE, riskLabels, toErrorMessage, formatTime } from '../uiSupport'
import { modeLabel, ratioLabel, businessText } from '../businessPresentation'

function metricValue(
  metrics: Record<string, number | string | null>,
  key: string,
): string {
  const value = metrics[key]
  if (value === null || value === undefined) return '数据不足'
  return businessText(value)
}

export function CoordinationPanel(props: Parameters<typeof CoordinationWorkspace>[0]) {
  return <CoordinationWorkspace key={props.projectId} {...props} />
}

function CoordinationWorkspace({ projectId }: { projectId: string }) {
  const [overview, setOverview] = useState<CoordinationOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const savedRefresh = useSavedRefresh()

  const [topicName, setTopicName] = useState(DEMO_COORDINATION.name)
  const [participants, setParticipants] = useState(DEMO_COORDINATION.participants.join(', '))
  const [windowStart, setWindowStart] = useState(DEMO_COORDINATION.windowStart)
  const [windowEnd, setWindowEnd] = useState(DEMO_COORDINATION.windowEnd)

  const [activeTopicId, setActiveTopicId] = useState('')
  const [recordsOpen, setRecordsOpen] = useState(false)
  const [recordsTrigger, setRecordsTrigger] = useState<HTMLElement | null>(null)
  const [recordError, setRecordError] = useState('')
  const [recordMessage, setRecordMessage] = useState('')
  const [recordRefreshFailed, setRecordRefreshFailed] = useState(false)
  const [importIntent, setImportIntent] = useState(false)
  const externalInput = useRef<HTMLInputElement>(null)
  const [externalId, setExternalId] = useState('')
  const [recordType, setRecordType] =
    useState<'message' | 'reopened'>('message')
  const [sender, setSender] = useState('')
  const [summary, setSummary] = useState('')
  const [sentAt, setSentAt] = useState('')
  const [replyTo, setReplyTo] = useState('')
  const [laborHours, setLaborHours] = useState(DEMO_COORDINATION.laborHours)
  const [hourlyRate, setHourlyRate] = useState(DEMO_COORDINATION.hourlyRate)
  const [acceptNotes, setAcceptNotes] = useState<Record<string, string>>({})

  const loadOverview = useCallback(async () => {
    const data = await api.getCoordinationOverview(projectId)
    setOverview(data)
    return data
  }, [projectId])

  useEffect(() => {
    let cancelled = false
    api
      .getCoordinationOverview(projectId)
      .then((data) => {
        if (!cancelled) setOverview(data)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(toErrorMessage(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [projectId])

  function toIso(value: string): string {
    return new Date(value).toISOString()
  }
  function applyPreset(topic:CoordinationTopic,reply:boolean,rootId?:string){
    const preset=communicationPreset(topic,reply,rootId)
    if(!preset){setRecordError(reply?'请先保存窗口内的发起消息，再填写关联回复。':'当前议题窗口或参与方不足，请人工填写记录。');return}
    setExternalId(preset.externalId);setRecordType('message');setSender(preset.sender)
    setSummary(preset.summary);setSentAt(preset.sentAt);setReplyTo(preset.replyTo);setRecordError('')
  }

  async function handleCreateTopic(event: FormEvent) {
    event.preventDefault()
    if (savedRefresh.blocked) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const topic = await api.createCoordinationTopic(projectId, {
        name: topicName.trim(),
        expected_participants: participants
          .split(/[,，、;；\n]+/)
          .map((item) => item.trim())
          .filter(Boolean),
        window_start: toIso(windowStart),
        window_end: toIso(windowEnd),
      })
      await savedRefresh.afterSave('协同议题创建', loadOverview)
      setTopicName('')
      setParticipants('')
      setMessage(`协同议题 ${topic.display_code} 已创建`)
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleCreateRecord(event: FormEvent) {
    event.preventDefault()
    if (savedRefresh.blocked) return
    if (!activeTopic) return
    setBusy(true)
    setRecordError('')
    setRecordMessage('')
    const savedExternalId=externalId.trim(),wasRoot=!replyTo.trim()
    try {
      await api.createCoordinationRecord(activeTopic.id, {
        external_id: externalId.trim(),
        record_type: recordType,
        sender: sender.trim(),
        content_summary: summary.trim(),
        sent_at: toIso(sentAt),
        reply_to_external_id: replyTo.trim() || null,
      })
      setExternalId('')
      setSummary('')
      setReplyTo('')
      setRecordMessage('协同记录已导入')
      try {
        const updated=await loadOverview()
        const topic=updated.topics.find(item=>item.id===activeTopic.id)
        if(topic&&isDemoTopic(topic)&&wasRoot)applyPreset(topic,true,savedExternalId)
        setRecordRefreshFailed(false)
      } catch (err) {
        setRecordRefreshFailed(true)
        setRecordError(`记录已保存，但列表刷新失败：${toErrorMessage(err)}。请重新读取记录，勿重复导入。`)
      }
    } catch (err) {
      setRecordError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function refreshRecords() {
    setBusy(true)
    try {
      await loadOverview()
      setRecordRefreshFailed(false)
      setRecordError('')
    } catch (err) { setRecordError(`读取记录失败：${toErrorMessage(err)}`) }
    finally { setBusy(false) }
  }

  function openRecords(topic: CoordinationTopic, trigger: HTMLElement, importing: boolean) {
    if (activeTopicId !== topic.id) {
      setExternalId(''); setRecordType('message'); setSender('')
      setSummary(''); setSentAt(''); setReplyTo('')
      setRecordError(''); setRecordMessage(''); setRecordRefreshFailed(false)
    }
    if(importing&&isDemoTopic(topic)&&(activeTopicId!==topic.id||(!externalId&&!sender&&!summary&&!sentAt&&!replyTo))){
      const hasUnanswered=topic.records.some(record=>record.record_type==='message'&&!record.reply_to_external_id&&!topic.records.some(other=>other.reply_to_external_id===record.external_id))
      applyPreset(topic,hasUnanswered)
    }
    setActiveTopicId(topic.id)
    setRecordsTrigger(trigger)
    setImportIntent(importing)
    setRecordsOpen(true)
  }

  async function handleCalculate(topic: CoordinationTopic) {
    if (savedRefresh.blocked) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await api.calculateCoordinationMetrics(topic.id, {
        labor_hours: laborHours === '' ? null : Number(laborHours),
        hourly_rate: hourlyRate === '' ? null : Number(hourlyRate),
      })
      await savedRefresh.afterSave('协同指标计算', loadOverview)
      setMessage(`${topic.display_code} 指标已重算并记录输入快照`)
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleAcceptRisk(topic: CoordinationTopic) {
    if (savedRefresh.blocked) return
    const run = topic.latest_metrics
    if (!run) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await api.acceptCoordinationRisk(topic.id, {
        metric_run_id: run.id,
        actor: DEMO_ACTOR,
        role: DEMO_ROLE,
        note: (acceptNotes[topic.id] ?? DEMO_COORDINATION.acceptance).trim(),
      })
      await savedRefresh.afterSave('协同风险接受', loadOverview)
      setMessage(`${topic.display_code} 风险接受已留痕`)
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const activeTopic =
    overview?.topics.find((topic) => topic.id === activeTopicId) ?? null

  return (
    <>
      {error && <Notice kind="error">{error}</Notice>}
      {message && <Notice kind="success">{message}</Notice>}
      <SavedRefreshNotice state={savedRefresh} busy={busy} />

      <section className="panel">
        <div className="panel-heading">
          <h2>协同看板</h2>
          <span className="mode-badge">规则计算 · 输入可重算</span>
        </div>
        <p className="hint">
          响应时延、反复与缺席率由带时间戳记录计算；未知值显示“数据不足”，
          不按零处理。评分与单价均可下钻查看输入。
        </p>
        {overview ? (
          <div className="metric-grid">
            <div className="metric">
              <span>议题</span>
              <strong>{overview.topic_count}</strong>
            </div>
            <div className="metric">
              <span>记录</span>
              <strong>{overview.record_count}</strong>
            </div>
            <div className="metric">
              <span>已计算指标</span>
              <strong>{overview.metrics_available}</strong>
            </div>
            <div className="metric">
              <span>最高风险</span>
              <strong>{riskLabels[overview.highest_risk]}</strong>
            </div>
          </div>
        ) : (
          !loading && <Empty>暂无协同数据。</Empty>
        )}
        {loading && <Empty>正在加载协同看板…</Empty>}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <h2>创建协同议题</h2>
        </div>
        <p className="hint">已预填合成演示样例，可编辑；点击创建、保存或接受后才产生业务记录，不会自动确认。</p>
        <form
          className="form-grid"
          onSubmit={(event) => void handleCreateTopic(event)}
        >
          <label>
            议题名称
            <input
              aria-label="协同议题名称"
              value={topicName}
              onChange={(event) => setTopicName(event.target.value)}
              required
            />
          </label>
          <label>
            应参与方（逗号分隔）
            <input
              aria-label="协同应参与方"
              value={participants}
              onChange={(event) => setParticipants(event.target.value)}
              placeholder="设计,工艺,试验"
              required
            />
          </label>
          <label>
            统计窗口开始
            <input
              aria-label="协同窗口开始"
              type="datetime-local"
              value={windowStart}
              onChange={(event) => setWindowStart(event.target.value)}
              required
            />
          </label>
          <label>
            统计窗口结束
            <input
              aria-label="协同窗口结束"
              type="datetime-local"
              value={windowEnd}
              onChange={(event) => setWindowEnd(event.target.value)}
              required
            />
          </label>
          <div className="form-actions">
            <button type="submit" disabled={busy || savedRefresh.blocked}>
              创建议题
            </button>
          </div>
        </form>
      </section>

      {overview && overview.topics.length > 0 && (
        <section className="panel">
          <div className="panel-heading">
            <h2>协同议题与指标</h2>
            <span className="count">{overview.topics.length} 个</span>
          </div>
          {overview.topics.map((topic) => {
            const stale = topic.latest_metrics?.validity === 'stale'
            const metrics = topic.latest_metrics?.metrics ?? {}
            const risk = topic.latest_metrics?.risk ?? {}
            const cost = topic.latest_metrics?.cost ?? {}
            const riskLevel =
              typeof risk.risk_level === 'string' ? risk.risk_level : null
            const needsAcceptance =
              riskLevel === 'high' || riskLevel === 'insufficient'
            const accepted = topic.risk_acceptances.some(
              (item) =>
                item.metric_run_id === topic.latest_metrics?.id,
            )
            return (
              <article
                className="card"
                key={topic.id}
                aria-label={`协同议题 ${topic.display_code}`}
              >
                <header>
                  <strong>
                    <span className="mono">{topic.display_code}</span>{' '}
                    {topic.name}
                  </strong>
                  <span className="muted">
                    窗口 {formatTime(topic.window_start)} → {formatTime(topic.window_end)}
                  </span>
                </header>
                <p className="muted">
                  应参与方：{topic.expected_participants.join('、')} ·
                  记录 {topic.record_count} 条 · 来源 {modeLabel(topic.mode)}
                </p>
                <div className="coordination-topic-actions" role="group" aria-label="议题沟通操作"><span>沟通记录</span><div className="coordination-topic-buttons">
                  <button type="button" disabled={busy || savedRefresh.blocked} onClick={event => openRecords(topic, event.currentTarget, true)}>导入沟通记录</button>
                  <button type="button" className="secondary" disabled={busy || savedRefresh.blocked} onClick={event => openRecords(topic, event.currentTarget, false)}>查看沟通记录</button>
                </div></div>
                <CoordinationProgress key={topic.id} topicId={topic.id} participants={topic.expected_participants} onChanged={async()=>{await loadOverview()}}/>
                {stale ? <Notice kind="info">沟通记录已变化，指标待重算；历史计算和风险接受记录保留，重算后需重新核对。</Notice> : topic.latest_metrics ? (
                  <>
                    <div className="metric-row">
                      <span>
                        平均响应时延：
                        {metricValue(metrics, 'average_response_hours')} 小时
                      </span>
                      <span>
                        响应样本：
                        {metricValue(metrics, 'response_sample_size')}
                      </span>
                      <span>
                        待响应：{metricValue(metrics, 'pending_count')}
                      </span>
                      <span>
                        反复：{metricValue(metrics, 'iteration_count')}
                      </span>
                      <span>
                        缺席率：{ratioLabel(metrics.absence_rate)}
                      </span>
                      <span>
                        无对应响应：{metricValue(metrics, 'orphan_response_count')}
                      </span>
                    </div>
                    <p>
                      风险：{riskLabels[riskLevel as keyof typeof riskLabels] ?? '数据不足'}
                      {risk.score !== undefined && risk.score !== null
                        ? ` · 评分 ${businessText(risk.score)}`
                        : ' · 评分不可用'}
                      {Array.isArray(risk.reasons) && risk.reasons.length > 0
                        ? ` · 依据：${risk.reasons.join('；')}`
                        : ''}
                    </p>
                    <p className="muted">
                      成本：{businessText(cost.amount)}{' '}
                      {cost.currency === 'CNY' ? '元' : businessText(cost.currency)} ·{' '}
                      {businessText(cost.basis)}
                    </p>
                    {Array.isArray(metrics.data_gaps) &&
                      metrics.data_gaps.length > 0 && (
                        <p className="muted">
                          数据缺口：{metrics.data_gaps.join('；')}
                        </p>
                      )}
                    {needsAcceptance && (
                      <div className="inline-controls">
                        <input
                          aria-label={`风险接受理由 ${topic.display_code}`}
                          value={acceptNotes[topic.id] ?? DEMO_COORDINATION.acceptance}
                          onChange={(event) =>
                            setAcceptNotes((current) => ({
                              ...current,
                              [topic.id]: event.target.value,
                            }))
                          }
                          placeholder="填写明确接受理由"
                          disabled={accepted}
                        />
                        <button
                          type="button"
                          disabled={busy || savedRefresh.blocked || accepted}
                          onClick={() => void handleAcceptRisk(topic)}
                        >
                          {accepted ? '已接受风险' : '接受风险'}
                        </button>
                      </div>
                    )}
                  </>
                ) : (
                  <p className="muted">尚无指标计算。</p>
                )}

                <div className="inline-controls">
                  <label>
                    工时（小时）
                    <input
                      aria-label={`工时 ${topic.display_code}`}
                      type="number"
                      min={0}
                      value={laborHours}
                      onChange={(event) =>
                        setLaborHours(event.target.value)
                      }
                    />
                  </label>
                  <label>
                    演示费率（元/小时）
                    <input
                      aria-label={`费率 ${topic.display_code}`}
                      type="number"
                      min={0}
                      value={hourlyRate}
                      onChange={(event) =>
                        setHourlyRate(event.target.value)
                      }
                    />
                  </label>
                  <button
                    type="button"
                    disabled={busy || savedRefresh.blocked}
                    onClick={() => void handleCalculate(topic)}
                  >
                    重算指标
                  </button>
                  <span className="hint">合成成本样例：3小时 × 120元/小时，可修改或清空；点击重算后才保存计算快照。</span>
                </div>
              </article>
            )
          })}
        </section>
      )}

      {recordsOpen && activeTopic && (
        <DetailOverlay variant="drawer" title={`议题沟通记录 · ${activeTopic.display_code}`} subtitle={activeTopic.name} eyebrow="协同风险 · 记录与依据" returnFocus={recordsTrigger} initialFocus={importIntent ? externalInput : undefined} closeLabel="关闭沟通详情" locked={busy} onClose={() => setRecordsOpen(false)} footer="关闭不导入记录；保存后请回到议题重算指标，已有指标仍是原计算快照。">
          <section className="source-evidence" aria-label="议题范围">
            <h3>议题范围</h3>
            <p>应参与方：{activeTopic.expected_participants.join('、') || '未记录'}</p>
            <p className="muted">窗口 {formatTime(activeTopic.window_start)} → {formatTime(activeTopic.window_end)}</p>
            <p className="muted">来源 {modeLabel(activeTopic.mode)} · 已保存 {activeTopic.record_count} 条记录</p>
          </section>
          <section aria-label="已保存的沟通记录">
            <h3>沟通记录</h3>
            {activeTopic.records.length === 0 ? <p className="muted">暂无记录。</p> : <ol className="communication-timeline">
              {activeTopic.records.map(record => <li key={record.id}>
                <div><strong>{record.external_id}</strong><span>{record.record_type === 'reopened' ? '重开事件' : '消息'}</span></div>
                <p className="muted">{record.sender} · {formatTime(record.sent_at)}</p>
                <p>{record.content_summary || '未填写摘要'}</p>
                {record.reply_to_external_id && <p className="muted">响应记录：{record.reply_to_external_id}</p>}
              </li>)}
            </ol>}
          </section>
          {recordMessage && <Notice kind="success">{recordMessage}</Notice>}
          {recordError && <Notice kind="error">{recordError}</Notice>}
          {recordRefreshFailed && <button type="button" className="secondary" disabled={busy || savedRefresh.blocked} onClick={() => void refreshRecords()}>重新读取记录</button>}
          <h3 className="section-title">导入沟通记录</h3>
          <div className="inline-controls"><button type="button" className="secondary" disabled={busy||recordRefreshFailed||savedRefresh.blocked} onClick={()=>applyPreset(activeTopic,false)}>填入发起消息样例</button><button type="button" className="secondary" disabled={busy||recordRefreshFailed||savedRefresh.blocked} onClick={()=>applyPreset(activeTopic,true)}>填入回复消息样例</button><span className="hint">来源：06_协同记录与进度样例（合成）。预填可修改，点击“导入记录”后才保存。</span></div>
          <form
            className="form-grid"
            onSubmit={(event) => void handleCreateRecord(event)}
          >
            <label>
              外部记录编号
              <input
                ref={externalInput}
                aria-label="协同记录外部编号"
                value={externalId}
                onChange={(event) => setExternalId(event.target.value)}
                required
              />
            </label>
            <label>
              记录类型
              <select
                aria-label="协同记录类型"
                value={recordType}
                onChange={(event) =>
                  setRecordType(event.target.value as typeof recordType)
                }
              >
                <option value="message">消息</option>
                <option value="reopened">重开事件</option>
              </select>
            </label>
            <label>
              发送方
              <input
                aria-label="协同记录发送方"
                value={sender}
                onChange={(event) => setSender(event.target.value)}
                required
              />
            </label>
            <label>
              发送时间（窗口内）
              <input
                aria-label="协同记录发送时间"
                type="datetime-local"
                value={sentAt}
                onChange={(event) => setSentAt(event.target.value)}
                required
              />
            </label>
            <label className="wide">
              内容摘要
              <input
                aria-label="协同记录摘要"
                value={summary}
                onChange={(event) => setSummary(event.target.value)}
              />
            </label>
            <label>
              响应的外部编号（回复时填写）
              <input
                aria-label="协同记录响应对象"
                placeholder="发起消息留空；回复时填写原消息编号"
                value={replyTo}
                onChange={(event) => setReplyTo(event.target.value)}
              />
              <small className="hint">发起消息无需填写响应编号；回复时关联已保存的原消息。</small>
            </label>
            <div className="form-actions">
              <button type="submit" disabled={busy || savedRefresh.blocked || recordRefreshFailed}>
                导入记录
              </button>
            </div>
          </form>
        </DetailOverlay>
      )}
    </>
  )
}
