import { parseParameters,measurementValue } from './sampleInput'
import { WorkflowOverview } from '../components/WorkflowOverview'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { modeLabel } from '../businessPresentation'
import type { FormEvent } from 'react'
import { api } from '../api'
import { DEMO_SAMPLE } from '../demoInputs'
import { samplePreset } from './samplePresets'
import { SampleFilePicker } from '../components/SampleFilePicker'
import { DetailOverlay } from '../components/DetailOverlay'
import { SavedRefreshNotice } from '../components/SavedRefresh'
import { useSavedRefresh } from '../useSavedRefresh'
import type {
  SampleComparison,
  SampleDelivery,
} from '../types'
import { Empty, Notice } from '../ui'
import { DEMO_ACTOR, DEMO_ROLE, executionLabels, isNotFound, toErrorMessage, reviewStatusLabels } from '../uiSupport'

const PARAMETER_PLACEHOLDER =
  'bore|内孔直径|120|0.05|mm|图纸尺寸 120±0.05'


export function SamplesPanel(props: Parameters<typeof SamplesWorkspace>[0]) {
  return <SamplesWorkspace key={props.projectId} {...props} />
}

function SamplesWorkspace({ projectId }: { projectId: string }) {
  const [deliveries, setDeliveries] = useState<SampleDelivery[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const savedRefresh = useSavedRefresh()

  const [supplier, setSupplier] = useState('')
  const [partCode, setPartCode] = useState('')
  const [drawingCode, setDrawingCode] = useState('')
  const [drawingRevision, setDrawingRevision] = useState('A')
  const [deliveredAt, setDeliveredAt] = useState('')
  const [quantity, setQuantity] = useState('1')
  const [notes, setNotes] = useState('')
  const [parametersText, setParametersText] = useState('')
  const [registrationFile,setRegistrationFile]=useState<File|null>(null)
  const registrationInput=useRef<HTMLInputElement>(null)

  const [selectedId, setSelectedId] = useState('')
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [recompareOpen,setRecompareOpen]=useState(false)
  const [detailsTrigger, setDetailsTrigger] = useState<HTMLElement | null>(null)
  const [comparisonAttempt, setComparisonAttempt] = useState(0)
  const [comparisonLoadError, setComparisonLoadError] = useState('')
  const [comparison, setComparison] = useState<SampleComparison | null>(null)
  const [comparisonLoading, setComparisonLoading] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [measurements, setMeasurements] = useState<Record<string, string>>({})
  const [visualMode, setVisualMode] = useState<'mock' | 'manual'>('manual')
  const [visualResult, setVisualResult] =
    useState<'pass' | 'fail' | 'incomplete' | 'invalid'>('pass')
  const [visualNote, setVisualNote] = useState('合成样件外观检查')
  const [evidence, setEvidence] = useState('')
  const draftBaseline=useRef('')

  const selectedDelivery = useMemo(
    () => deliveries.find((item) => item.id === selectedId) ?? null,
    [deliveries, selectedId],
  )

  useEffect(()=>{
    if(!selectedDelivery)return
    const baseline=JSON.stringify([selectedDelivery.id,selectedDelivery.drawing_revision,selectedDelivery.drawing_parameters])
    if(draftBaseline.current===baseline)return
    draftBaseline.current=baseline
    const preset=samplePreset(selectedDelivery.drawing_parameters)
    setMeasurements(preset.measurements);setEvidence(preset.evidence)
    setVisualMode('manual');setVisualResult('pass')
    setVisualNote(preset.count?'合成目视记录，由操作者明确录入':'合成样件外观检查')
  },[selectedDelivery])

  const loadDeliveries = useCallback(async () => {
    const data = await api.listSampleDeliveries(projectId)
    setDeliveries(data)
    return data
  }, [projectId])

  useEffect(() => {
    let cancelled = false
    api
      .listSampleDeliveries(projectId)
      .then((data) => {
        if (!cancelled) setDeliveries(data)
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

  useEffect(() => {
    if (!selectedDelivery) return
    let cancelled = false
    api
      .getSampleComparison(selectedDelivery.id)
      .then((data) => {
        if (!cancelled) {
          setComparison(data)
          setComparisonLoadError('')
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setComparison(null)
        setComparisonLoadError(isNotFound(err) ? '' : toErrorMessage(err))
      })
      .finally(() => {
        if (!cancelled) setComparisonLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedDelivery, comparisonAttempt])

  function selectDelivery(id: string, trigger?: HTMLElement | null) {
    if (trigger) setDetailsTrigger(trigger)
    setDetailsOpen(true); setError(''); setMessage('')
    if (id === selectedId) return
    setSelectedId(id); setRecompareOpen(false); setComparison(null); setMeasurements({}); setComparisonLoading(true); setComparisonLoadError(''); setFile(null); setEvidence('')
    setVisualMode('manual'); setVisualResult('pass'); setVisualNote('合成样件外观检查')
  }

  async function handleCreateDelivery(event: FormEvent) {
    event.preventDefault()
    if (savedRefresh.blocked) return
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null
    setBusy(true)
    setError('')
    setMessage('')
    let created:SampleDelivery|null=null
    const uploadFile=registrationFile
    try {
      const parameters = parseParameters(parametersText)
      if (parameters.length === 0) {
        throw new Error('至少填写一项图纸参数')
      }
      const delivery = await api.createSampleDelivery(projectId, {
        supplier: supplier.trim(),
        part_display_code: partCode.trim(),
        drawing_display_code: drawingCode.trim(),
        drawing_revision: drawingRevision.trim(),
        delivered_at: deliveredAt,
        quantity: Number(quantity),
        notes: notes.trim(),
        drawing_parameters: parameters,
      })
      created=delivery
      // The registration is committed; any upload retry belongs to this delivery.
      setSupplier('');setPartCode('');setDrawingCode('');setNotes('');setParametersText('')
      setRegistrationFile(null)
      if(registrationInput.current)registrationInput.current.value=''
      setDeliveries(items => [delivery, ...items.filter(item => item.id !== delivery.id)])
      await savedRefresh.afterSave('样件交付登记', loadDeliveries)
      selectDelivery(delivery.id, trigger)
      if(uploadFile){
        setFile(uploadFile)
        await api.uploadSampleFile(delivery.id,uploadFile,DEMO_ACTOR)
        await savedRefresh.afterSave('登记后上传样件文件',loadDeliveries)
        setFile(null);setRegistrationFile(null)
      }
      setMessage(`样件交付 ${delivery.display_code} 已登记`)
    } catch (err) {
      setError(`${created?'交付已登记，后续上传或刷新未完成；请在明细重试，勿重复登记。':''}${toErrorMessage(err)}`)
    } finally {
      setBusy(false)
    }
  }

  function fillDelivery(){
    setSupplier(DEMO_SAMPLE.supplier);setPartCode(DEMO_SAMPLE.partCode);setDrawingCode(DEMO_SAMPLE.drawingCode)
    setDrawingRevision(DEMO_SAMPLE.drawingRevision);setDeliveredAt(DEMO_SAMPLE.deliveredAt);setQuantity(DEMO_SAMPLE.quantity)
    setNotes(DEMO_SAMPLE.notes);setParametersText(DEMO_SAMPLE.parameters)
  }

  function fillMeasurements(failed:boolean){
    if(!selectedDelivery)return
    const preset=samplePreset(selectedDelivery.drawing_parameters,failed)
    if(!preset.count){setError('当前图纸参数与05合成样例不匹配，请人工填写实测。');return}
    setMeasurements(current=>({...current,...preset.measurements}))
    setVisualMode('manual');setVisualResult('pass');setVisualNote('合成目视记录，由操作者明确录入')
    setEvidence(preset.evidence)
    setError('');setMessage(`已填入${preset.count}项匹配参数的合成实测，尚未提交比对；请核对其余参数。`)
  }

  async function handleUpload() {
    if (savedRefresh.blocked) return
    if (!selectedDelivery || !file) {
      setError('请选择要上传的文件')
      return
    }
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await api.uploadSampleFile(selectedDelivery.id, file, DEMO_ACTOR)
      await savedRefresh.afterSave('样件文件上传', loadDeliveries)
      setFile(null)
      setMessage('样件文件已上传并记录 SHA-256')
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleCreateComparison(event: FormEvent) {
    event.preventDefault()
    if (savedRefresh.blocked) return
    if (!selectedDelivery) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const parameters = selectedDelivery.drawing_parameters.map(
        (parameter) => ({
          parameter_key: parameter.parameter_key,
          measured_value: measurementValue(measurements[parameter.parameter_key]),
          unit: parameter.unit,
        }),
      )
      const data = await api.createSampleComparison(selectedDelivery.id, {
        ...(comparison ? { expected_revision: comparison.comparison.revision } : {}),
        actor: DEMO_ACTOR,
        role: DEMO_ROLE,
        parameters,
        visual_check: {
          mode: visualMode,
          result: visualResult,
          note: visualNote.trim(),
        },
        evidence: evidence.trim(),
      })
      setComparison(data)
      setRecompareOpen(false)
      await savedRefresh.afterSave('样件比对', loadDeliveries)
      setMessage(
        `样件比对 ${data.comparison.display_code}：` +
          executionLabels[data.comparison.overall_result],
      )
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleConfirmComparison() {
    if (savedRefresh.blocked) return
    if (!comparison) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await api.confirmSampleComparison(comparison.comparison.id, {
        expected_revision: comparison.comparison.revision,
        actor: DEMO_ACTOR,
        role: DEMO_ROLE,
        decision: 'confirmed',
        comment: '样件比对人工确认',
      })
      setDetailsOpen(false)
      if (selectedDelivery) {
        await savedRefresh.afterSave('样件比对审核', async () => setComparison(await api.getSampleComparison(selectedDelivery.id)))
      }
      setMessage('样件比对已确认')
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      {error && !detailsOpen && <Notice kind="error">{error}</Notice>}
      {message && !detailsOpen && <Notice kind="success">{message}</Notice>}
      {!detailsOpen && <SavedRefreshNotice state={savedRefresh} busy={busy} />}

      <WorkflowOverview projectId={projectId} section="samples" refreshKey={JSON.stringify([deliveries,comparison])}/>

      <section className="panel">
        <div className="panel-heading">
          <h2>样件交付与比对</h2>
          <span className="count">{deliveries.length} 条</span>
        </div>
        <p className="hint">
          图纸参数、实测值、公差与外观检查均保留；证据不足显示“证据不足”，
          不按通过处理。视觉判断明确标注模拟或人工模式。可在登记时一并上传原件，也可登记后从列表补充上传。
        </p>

        <details className="disclosure" open={!deliveries.length ? true : undefined}>
          <summary>登记样件交付</summary>
          <div className="inline-controls"><button type="button" className="demo-fill-button" disabled={busy||savedRefresh.blocked} onClick={fillDelivery}>填入样件合成样例</button><span className="hint">来源：05_样件与实测样例。仅填表，可编辑；可使用下方演示图纸，提交后才登记。</span></div>
          <form
            className="form-grid"
            onSubmit={(event) => void handleCreateDelivery(event)}
          >
            <label>
              供应商
              <input
                aria-label="样件供应商"
                value={supplier}
                onChange={(event) => setSupplier(event.target.value)}
                required
              />
            </label>
            <label>
              零件编号
              <input
                aria-label="样件零件编号"
                value={partCode}
                onChange={(event) => setPartCode(event.target.value)}
                required
              />
            </label>
            <label>
              图纸编号
              <input
                aria-label="样件图纸编号"
                value={drawingCode}
                onChange={(event) => setDrawingCode(event.target.value)}
                required
              />
            </label>
            <label>
              图纸版本
              <input
                aria-label="样件图纸版本"
                value={drawingRevision}
                onChange={(event) => setDrawingRevision(event.target.value)}
                required
              />
            </label>
            <label>
              交付日期
              <input
                aria-label="样件交付日期"
                type="date"
                value={deliveredAt}
                onChange={(event) => setDeliveredAt(event.target.value)}
                required
              />
            </label>
            <label>
              数量
              <input
                aria-label="样件数量"
                type="number"
                min={1}
                value={quantity}
                onChange={(event) => setQuantity(event.target.value)}
              />
            </label>
            <label className="wide">
              备注
              <input
                aria-label="样件备注"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </label>
            <label className="wide">
              图纸参数（每行：key|名称|期望值|公差|单位|备注）
              <textarea
                aria-label="图纸参数"
                rows={3}
                value={parametersText}
                onChange={(event) => setParametersText(event.target.value)}
                placeholder={PARAMETER_PLACEHOLDER}
                required
              />
            </label>
            <div className="form-actions sample-registration-actions">
              <SampleFilePicker inputRef={registrationInput} file={registrationFile} onFile={setRegistrationFile} label="登记时选择样件文件" zoneLabel="登记原件拖放区" disabled={busy||savedRefresh.blocked}/>
              {!registrationFile&&<button type="submit" disabled={busy || savedRefresh.blocked}>
                登记交付
              </button>}
              <button type="submit" disabled={busy||savedRefresh.blocked||!registrationFile}>登记并上传文件</button>
            </div>
          </form>
        </details>

        {loading ? (
          <Empty>正在加载样件交付…</Empty>
        ) : deliveries.length === 0 ? (
          <Empty>暂无样件交付记录。</Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>编号</th>
                  <th>供应商</th>
                  <th>零件 / 图纸</th>
                  <th>交付</th>
                  <th>图纸参数</th>
                  <th>文件</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {deliveries.map((delivery) => (
                  <tr key={delivery.id} data-object-id={delivery.id}>
                    <td className="mono">{delivery.display_code}</td>
                    <td>{delivery.supplier}</td>
                    <td className="source">
                      <span>
                        {delivery.part_display_code} ·{' '}
                        {delivery.drawing_display_code} rev{' '}
                        {delivery.drawing_revision}
                      </span>
                      <small>{delivery.notes || '无备注'}</small>
                    </td>
                    <td>
                      {delivery.delivered_at} · {delivery.quantity} 件
                    </td>
                    <td>{delivery.drawing_parameters.length} 项</td>
                    <td>
                      {delivery.file
                        ? `${delivery.file.file_name}（${delivery.file.size_bytes} B）`
                        : '未上传'}
                    </td>
                    <td className="actions">
                      <button type="button" className="secondary" aria-label={`上传文件 ${delivery.display_code}`} onClick={event=>selectDelivery(delivery.id,event.currentTarget)}>{delivery.file_uploaded?'查看文件':'上传文件'}</button>
                      <button
                        type="button"
                        onClick={event => {
                          selectDelivery(delivery.id, event.currentTarget)
                        }}
                      >
                        查看 / 比对
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {selectedDelivery && detailsOpen && (
        <DetailOverlay key={selectedDelivery.id} variant="wide" title={`样件明细：${selectedDelivery.display_code}`} subtitle={`${selectedDelivery.supplier} · ${selectedDelivery.part_display_code} · ${selectedDelivery.drawing_display_code} / ${selectedDelivery.drawing_revision}`} eyebrow="样件检验 · 图纸与实测比对" locked={busy} returnFocus={detailsTrigger} closeLabel="关闭样件详情" onClose={() => { if (!busy) { setDetailsOpen(false); setError(''); setMessage('') } }} footer="关闭不提交或确认比对 · 同一样件的未提交输入保留在本次页面中">
          {error && <Notice kind="error">{error}</Notice>}
          {message && <Notice kind="success">{message}</Notice>}
          <SavedRefreshNotice state={savedRefresh} busy={busy} />
          {selectedDelivery.file_uploaded?<div className="sample-original-summary" aria-label="已上传样件原件"><span className="muted">已上传：{selectedDelivery.file?.file_name} · SHA-256 {selectedDelivery.file?.content_hash.slice(0,16)}…</span><a href={`/api/sample-deliveries/${encodeURIComponent(selectedDelivery.id)}/file`} download>下载样件原件</a></div>:<>
          <h3>第二步：上传图纸 / 样件原件</h3>
          <p className="hint">选择文件后点击上传；原件与参数分别保存，不会自动识别图纸尺寸。</p>
          <div className="inline-controls">
            <SampleFilePicker file={file} onFile={setFile} label="选择样件文件" disabled={busy||savedRefresh.blocked}/>
            <button
              type="button"
              disabled={busy || savedRefresh.blocked || selectedDelivery.file_uploaded || !file}
              onClick={() => void handleUpload()}
            >
              上传样件文件
            </button>
          </div>
          </>}

          <p className="table-scroll-hint">表格可左右滑动，查看完整参数与差异。</p>

          {comparisonLoading ? (
            <Empty>正在加载比对记录…</Empty>
          ) : comparisonLoadError ? <><Notice kind="error">{comparisonLoadError}</Notice><button type="button" onClick={() => { setComparisonLoadError(''); setComparisonLoading(true); setComparisonAttempt(value => value + 1) }}>重试加载比对</button></> : comparison && !recompareOpen ? (
            <div className="result-box">
              <h3>
                比对 {comparison.comparison.display_code} · V
                {comparison.comparison.revision} ·{' '}
                {executionLabels[comparison.comparison.overall_result]}
              </h3>
              <p className="muted">
                状态 {reviewStatusLabels[comparison.comparison.status as keyof typeof reviewStatusLabels] ?? '审核状态未记录'} · 模式{' '}
                {modeLabel(comparison.mode)} · 证据：{comparison.comparison.evidence}
              </p>
              <p className="hint">期望值、公差和单位来自已保存比对记录，登记图纸参数不会改写此结果。</p>
              <div className="table-wrap"><table className="inner-table" aria-label="样件比对结果">
                <thead>
                  <tr>
                    <th>参数</th>
                    <th>期望</th>
                    <th>公差</th>
                    <th>单位</th>
                    <th>实测</th>
                    <th>结论</th>
                    <th>原因</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.comparison.findings.map((finding) => (
                    <tr key={finding.parameter_key}>
                      <td>{finding.parameter_name}</td>
                      <td>{finding.parameter_key === 'visualCheck' ? '不适用' : finding.expected_value ?? '缺失'}</td>
                      <td>{finding.parameter_key === 'visualCheck' ? '不适用' : finding.tolerance != null ? `±${finding.tolerance}` : '未记录'}</td>
                      <td>{finding.unit || '—'}</td>
                      <td>{finding.parameter_key === 'visualCheck' ? '不适用' : finding.measured_value ?? '缺失'}</td>
                      <td><span className={`sample-finding sample-finding--${finding.result}`}>{executionLabels[finding.result]}</span></td>
                      <td className="source">{finding.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
              <p>
                外观检查（{modeLabel(comparison.comparison.visual_check.mode)}）：
                {executionLabels[comparison.comparison.visual_check.result as keyof typeof executionLabels] ?? '未记录'} ·{' '}
                {comparison.comparison.visual_check.note ?? ''}
              </p>
              <details className="business-evidence" aria-label="登记图纸来源"><summary>查看登记图纸来源 · {selectedDelivery.drawing_display_code} / {selectedDelivery.drawing_revision}</summary><div className="business-evidence-body"><p className="muted">以下为交付登记的图纸来源，已保存的比对基准以结果表为准。</p><ul>{selectedDelivery.drawing_parameters.map(parameter => <li key={parameter.parameter_key}>{parameter.parameter_name}：{parameter.source_note || '未记录来源'}</li>)}</ul></div></details>
              <button type="button" className="secondary" disabled={busy||savedRefresh.blocked} onClick={()=>setRecompareOpen(true)}>记录复检</button>
              {comparison.comparison.status !== 'confirmed' && (
                <div className="form-actions">
                  <button
                    type="button"
                    disabled={busy || savedRefresh.blocked}
                    onClick={() => void handleConfirmComparison()}
                  >
                    确认比对
                  </button>
                </div>
              )}
            </div>
          ) : (
            <form
              className="inline-action"
              onSubmit={(event) => void handleCreateComparison(event)}
            >
              <h3>{comparison?`记录复检 · 生成V${comparison.comparison.revision+1}`:"新建比对"}</h3>{comparison&&<button type="button" className="secondary" disabled={busy} onClick={()=>setRecompareOpen(false)}>取消复检</button>}
              <div className="inline-controls"><button type="button" className="demo-fill-button" disabled={busy||savedRefresh.blocked} onClick={()=>fillMeasurements(false)}>填入合成合格实测</button><button type="button" className="secondary danger-action" disabled={busy||savedRefresh.blocked} onClick={()=>fillMeasurements(true)}>填入合成超差实测</button></div>
              <p className="hint">与05样例的名称标识、期望值、公差及单位匹配的参数已预填合成实测和证据，可编辑；未匹配项需人工补充。预填不等于提交或确认，也不表示从原件识别了尺寸。</p>
              <p className="hint">本次依据登记图纸 {selectedDelivery.drawing_display_code} / {selectedDelivery.drawing_revision} 填写实测值。</p>
              <div className="table-wrap"><table aria-label="样件参数与实测">
                <thead><tr><th>参数</th><th>期望值</th><th>公差</th><th>单位</th><th>实测值</th><th>图纸来源</th></tr></thead>
                <tbody>{selectedDelivery.drawing_parameters.map(parameter => <tr key={parameter.parameter_key}>
                  <td>{parameter.parameter_name}</td><td>{parameter.expected_value}</td><td>±{parameter.tolerance}</td><td>{parameter.unit || '—'}</td>
                  <td><input aria-label={`实测 ${parameter.parameter_name}`} type="number" step="any" value={measurements[parameter.parameter_key] ?? ''} onChange={event => setMeasurements(current => ({ ...current, [parameter.parameter_key]: event.target.value }))} required /></td>
                  <td className="source">{parameter.source_note || '未记录'}</td>
                </tr>)}</tbody>
              </table></div>
              <div className="form-grid">
                <label>
                  外观检查模式
                  <select
                    aria-label="外观检查模式"
                    value={visualMode}
                    onChange={(event) =>
                      setVisualMode(
                        event.target.value as 'mock' | 'manual',
                      )
                    }
                  >
                    <option value="manual">人工</option>
                    <option value="mock">模拟视觉</option>
                  </select>
                </label>
                <label>
                  外观检查结论
                  <select
                    aria-label="外观检查结论"
                    value={visualResult}
                    onChange={(event) =>
                      setVisualResult(
                        event.target.value as typeof visualResult,
                      )
                    }
                  >
                    <option value="pass">通过</option>
                    <option value="fail">未通过</option>
                    <option value="incomplete">证据不足</option>
                    <option value="invalid">无效</option>
                  </select>
                </label>
                <label className="wide">
                  外观检查说明
                  <input
                    aria-label="外观检查说明"
                    value={visualNote}
                    onChange={(event) => setVisualNote(event.target.value)}
                    required
                  />
                </label>
                <label className="wide">
                  证据
                  <input
                    aria-label="比对证据"
                    value={evidence}
                    onChange={(event) => setEvidence(event.target.value)}
                    required
                  />
                </label>
              </div>
              <div className="form-actions">
                <button type="submit" disabled={busy || savedRefresh.blocked}>
                  提交比对
                </button>
              </div>
            </form>
          )}
        </DetailOverlay>
      )}
    </>
  )
}
