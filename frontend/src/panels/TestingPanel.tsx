import { TestCaseRevisionDialog } from '../components/TestCaseRevisionDialog'
import { WorkflowOverview } from '../components/WorkflowOverview'
import { ArtifactPreview } from '../components/ArtifactPreview'
import { DetailOverlay } from '../components/DetailOverlay'
import { SavedRefreshNotice } from '../components/SavedRefresh'
import { useSavedRefresh } from '../useSavedRefresh'
import { PlanContents } from '../components/OutputContents'
import { ExecutionSummary } from '../components/BusinessEvidence'
import { modeLabel } from '../businessPresentation'
import { useCallback, useEffect, useMemo, useState, useRef, useId } from 'react'
import { executionLoadPreset } from './executionPreset'
import { DEMO_STATIC_TORSION } from '../demoInputs'
import './testing-entry.css'
import type { FormEvent } from 'react'
import { api } from '../api'
import type {
  TestCase,
  TestPlanPayload,
  TraceabilityMatrix,
} from '../types'
import { Empty, Notice } from '../ui'
import { DEMO_ACTOR, DEMO_ROLE, executionLabels, isNotFound, reviewStatusLabels, toErrorMessage, validityLabels } from '../uiSupport'

type RunDraft = {
  conditions: string
  evidence: string | undefined
  manualResult: 'pass' | 'fail' | 'incomplete' | 'invalid'
  loadBasis: string
  backupCoefficient: string
}

const EMPTY_RUN: RunDraft = {
  conditions: '合成台架工况',
  evidence: undefined,
  manualResult: 'pass',
  loadBasis: '',
  backupCoefficient: '',
}

function caseStatusLabel(status: string): string {
  return reviewStatusLabels[status as keyof typeof reviewStatusLabels] ?? status
}

export function TestingPanel(props: Parameters<typeof TestingWorkspace>[0]) {
  return <TestingWorkspace key={props.projectId} {...props} />
}

function TestingWorkspace({ projectId }: { projectId: string }) {
  const [plan, setPlan] = useState<TestPlanPayload | null>(null)
  const [matrix, setMatrix] = useState<TraceabilityMatrix | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const savedRefresh = useSavedRefresh()
  const [selectedCaseId, setSelectedCaseId] = useState('')
  const [runDraft, setRunDraft] = useState<RunDraft>(EMPTY_RUN)
  const conditionsInput=useRef<HTMLInputElement>(null)
  const runRequest=useRef(0)
  const [openedRunKey,setOpenedRunKey]=useState('')
  const loadEdited=useRef(false)
  const [runOpen,setRunOpen]=useState(false)
  const [runTrigger,setRunTrigger]=useState<HTMLElement|null>(null)
  const [runPresetLoading,setRunPresetLoading]=useState(false)
  const [runPresetNote,setRunPresetNote]=useState('')
  const runFormId=useId()
  useEffect(()=>()=>{runRequest.current++},[])
  const [editingCase,setEditingCase]=useState<TestCase|null>(null)
  const [editorTrigger,setEditorTrigger]=useState<HTMLElement|null>(null)
  const [rejection,setRejection]=useState<{kind:'plan'|'case';id:string;revision:number;label:string;trigger:HTMLElement}|null>(null)
  const [rejectionReason,setRejectionReason]=useState('')
  const [rejectionError,setRejectionError]=useState('')

  async function handleReject() {
    if (!rejection || busy || savedRefresh.blocked) return
    setBusy(true);setRejectionError('');setMessage('')
    try {
      const payload={expected_revision:rejection.revision,actor:DEMO_ACTOR,role:DEMO_ROLE,decision:'rejected',comment:rejectionReason.trim()}
      if(rejection.kind==='plan') await api.confirmTestPlan(rejection.id,payload)
      else await api.confirmTestCase(rejection.id,payload)
      const label=rejection.label
      setRejection(null);setRejectionReason('')
      await savedRefresh.afterSave(`${label} 驳回`,refresh)
      setMessage(`${label} 已驳回；修改后以新版本重新审核，历史执行保留。`)
    } catch(err) {setRejectionError(toErrorMessage(err))}
    finally {setBusy(false)}
  }

  const loadPlan = useCallback(async () => {
    try {
      const data = await api.getTestPlan(projectId)
      setPlan(data)
      return data
    } catch (err) {
      if (isNotFound(err)) {
        setPlan(null)
        return null
      }
      throw err
    }
  }, [projectId])

  const loadMatrix = useCallback(async () => {
    const data = await api.getTraceabilityMatrix(projectId)
    setMatrix(data)
    return data
  }, [projectId])

  useEffect(() => {
    let cancelled = false
    Promise.allSettled([api.getTestPlan(projectId), api.getTraceabilityMatrix(projectId)]).then(([planResult, matrixResult]) => {
      if (cancelled) return
      if (planResult.status === 'fulfilled') setPlan(planResult.value)
      else if (!isNotFound(planResult.reason)) setError(toErrorMessage(planResult.reason))
      if (matrixResult.status === 'fulfilled') setMatrix(matrixResult.value)
      else setError(toErrorMessage(matrixResult.reason))
      setLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [projectId])

  const selectedCase = useMemo(
    () =>
      plan?.cases.find((item) => item.id === selectedCaseId) ??
      null,
    [plan, selectedCaseId],
  )

  async function refresh() {
    await Promise.all([loadPlan(), loadMatrix()])
  }

  const syntheticEvidence=selectedCase?`合成执行记录 ${selectedCase.display_code} · V${selectedCase.revision}（演示样例，待操作者核对）`:''

  async function handleGenerate() {
    if (savedRefresh.blocked) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const data = await api.generateTestPlan(projectId)
      setPlan(data)
      await savedRefresh.afterSave('试验方案生成', loadMatrix)
      setMessage(`试验方案 ${data.plan.display_code} 已生成`)
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleConfirmPlan() {
    if (savedRefresh.blocked) return
    if (!plan) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await api.confirmTestPlan(plan.plan.id, {
        expected_revision: plan.plan.revision,
        actor: DEMO_ACTOR,
        role: DEMO_ROLE,
        decision: 'confirmed',
        comment: '试验方案人工确认',
      })
      await savedRefresh.afterSave('试验方案审核', refresh)
      setMessage('试验方案已确认')
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleConfirmCase(testCase: TestCase) {
    if (savedRefresh.blocked) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await api.confirmTestCase(testCase.id, {
        expected_revision: testCase.revision,
        actor: DEMO_ACTOR,
        role: DEMO_ROLE,
        decision: 'confirmed',
        comment: '试验用例人工确认',
      })
      await savedRefresh.afterSave(`${testCase.display_code} 审核`, refresh)
      setMessage(`${testCase.display_code} 已确认`)
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleRebase(testCase: TestCase) {
    if (savedRefresh.blocked) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const updated = await api.updateTestCase(testCase.id, {
        expected_revision: testCase.revision,
        actor: DEMO_ACTOR,
        role: DEMO_ROLE,
        rebase_requirements: true,
        comment: '按当前需求版本重新基线',
      })
      await savedRefresh.afterSave(`${testCase.display_code} 重新基线`, refresh)
      setMessage(
        `${updated.display_code} 已重基到 V${updated.revision}，需重新确认`,
      )
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleRecordRun(event: FormEvent) {
    event.preventDefault()
    if (busy || savedRefresh.blocked || !runOpen) return
    if (!selectedCase || selectedCase.review_status!=='confirmed' || selectedCase.validity!=='current' || openedRunKey!==`${selectedCase.id}:${selectedCase.revision}`) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const payload: Record<string, unknown> = {
        expected_revision: selectedCase.revision,
        actor: DEMO_ACTOR,
        role: DEMO_ROLE,
        conditions: runDraft.conditions.trim(),
        evidence: (runDraft.evidence??syntheticEvidence).trim(),
      }
      if (selectedCase.case_kind === 'static_torsion') {
        payload.load_basis_numeric = Number(runDraft.loadBasis)
        payload.backup_coefficient = Number(runDraft.backupCoefficient)
      } else {
        payload.manual_result = runDraft.manualResult
      }
      const data = await api.recordTestRun(selectedCase.id, payload)
      await savedRefresh.afterSave(`${selectedCase.display_code} 执行记录`, refresh)
      setRunDraft((current) => ({ ...current, evidence: undefined }))
      setMessage(
        `${selectedCase.display_code} 第 ${data.run.run_no} 次执行：` +
          executionLabels[data.run.result] +
          `（${data.run.reasons.join('；')}）`,
      )
      setRunOpen(false)
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function openRunForm(testCase: TestCase,trigger:HTMLElement) {
    setRunTrigger(trigger);setRunOpen(true);setError('');setMessage('')
    const key=`${testCase.id}:${testCase.revision}`
    if(openedRunKey===key)return
    setOpenedRunKey(key)
    const epoch=++runRequest.current
    setSelectedCaseId(testCase.id)
    loadEdited.current=false;setRunPresetNote('')
    setRunDraft({...EMPTY_RUN,backupCoefficient:testCase.case_kind==='static_torsion'?DEMO_STATIC_TORSION.backupCoefficient:''})
    if(testCase.case_kind!=='static_torsion'){setRunPresetLoading(false);return}
    setRunPresetLoading(true)
    try{
      const requirements=await api.listRequirements(projectId)
      if(epoch!==runRequest.current)return
      const value=executionLoadPreset(testCase,requirements,projectId)
      if(!loadEdited.current)setRunDraft(current=>({...current,loadBasis:value}))
      setRunPresetNote(value?'加载值引用本用例关联的已确认需求；后备系数2.6为合成样例，可修改。':'未找到与本用例版本匹配的已确认加载依据，请人工核对填写。')
    }catch(err){if(epoch===runRequest.current)setRunPresetNote(`加载依据读取失败，请手动填写或重新打开页面重试：${toErrorMessage(err)}`)}
    finally{if(epoch===runRequest.current)setRunPresetLoading(false)}
  }

  return (
    <>
      {error && !runOpen && <Notice kind="error">{error}</Notice>}
      {message && <Notice kind="success">{message}</Notice>}
      <SavedRefreshNotice state={savedRefresh} busy={busy} />

      {editingCase&&<TestCaseRevisionDialog key={editingCase.id} testCase={editingCase} returnFocus={editorTrigger} onClose={()=>setEditingCase(null)} onSaved={async row=>{await savedRefresh.afterSave(`${row.display_code} 用例修订`,refresh);setMessage(`${row.display_code} 修订已保存为V${row.revision}，请核对当前审核状态并重新执行。`)}}/>}
      <WorkflowOverview projectId={projectId} section="testing" refreshKey={JSON.stringify([plan,matrix])}/>

      <section className="panel" data-object-id={plan?.plan.id}>
        <div className="panel-heading">
          <h2>试验方案与用例</h2>
          {plan && <ArtifactPreview title="试验方案" code={plan.plan.display_code} revision={plan.plan.revision} status={plan.plan.status} mode={plan.mode}><PlanContents data={plan} /></ArtifactPreview>}
          {plan && (
            <span className="count">
              {plan.plan.display_code} · V{plan.plan.revision} ·{' '}
              {reviewStatusLabels[plan.plan.status as keyof typeof reviewStatusLabels] ?? plan.plan.status}
            </span>
          )}
        </div>
        <p className="hint">
          有效用例 = 已确认 + 当前版本 + 条件/加载/判定完整；覆盖与执行、通过分开统计。
          {plan?.source_label ? ` 来源：${plan.source_label}。` : ''}
        </p>
        <div className="inline-controls">
          <button type="button" disabled={busy || savedRefresh.blocked} onClick={() => void handleGenerate()}>
            {plan ? '重新生成试验方案' : '生成试验方案'}
          </button>
          {plan && ['draft','pending_review'].includes(plan.plan.status) && (
            <button type="button" disabled={busy || savedRefresh.blocked} onClick={() => void handleConfirmPlan()}>
              确认试验方案
            </button>
          )}
          {plan && ['draft','pending_review'].includes(plan.plan.status) && <button type="button" className="secondary danger-action" disabled={busy||savedRefresh.blocked} onClick={event=>{setRejection({kind:'plan',id:plan.plan.id,revision:plan.plan.revision,label:'试验方案',trigger:event.currentTarget});setRejectionReason('');setRejectionError('')}}>驳回试验方案</button>}
        </div>
        {plan?.needs_reconfirmation && <Notice kind="info">方案引用的需求或 FMEA 已变化，请重新生成方案，并对受影响用例重新基线、确认和执行。</Notice>}

        {loading ? (
          <Empty>正在加载试验方案…</Empty>
        ) : !plan ? (
          <Empty>尚未生成试验方案。</Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>编号</th>
                  <th>用例</th>
                  <th>版本</th>
                  <th>审核</th>
                  <th>有效性</th>
                  <th>条件/判定</th>
                  <th>最近执行</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {plan.cases.map((testCase) => {
                  const latest =
                    testCase.runs.length > 0
                      ? testCase.runs[testCase.runs.length - 1]
                      : null
                  const historical=!!latest&&(latest.case_revision!==testCase.revision||testCase.validity!=='current')
                  return (
                    <tr key={testCase.id} data-object-id={testCase.id}>
                      <td className="mono">{testCase.display_code}</td>
                      <td className="source">
                        <span>{testCase.title}</span>
                        <small>
                          {testCase.conditions_text} /{' '}
                          {testCase.acceptance_criteria || '判定缺失'}
                        </small>
                      </td>
                      <td>V{testCase.revision}</td>
                      <td>
                        <span className={`status ${testCase.review_status}`}>
                          {caseStatusLabel(testCase.review_status)}
                        </span>
                      </td>
                      <td>
                        <span className={`validity ${testCase.validity}`}>
                          {validityLabels[testCase.validity]}
                        </span>
                      </td>
                      <td>
                        {testCase.complete ? '完整' : '不完整'} ·{' '}
                        {testCase.coverage_valid ? '覆盖有效' : '覆盖无效'}
                      </td>
                      <td className="source">
                        {latest ? (
                          <>
                            <span className={`run-result-badge run-result-badge--${historical?'history':latest.status==='completed'?latest.result:'not-run'}`}>
                              <span aria-hidden="true">{historical?'◷':latest.result==='pass'?'✓':latest.result==='fail'?'✕':'!'}</span>
                              {historical?'历史执行':latest.status==='completed'?'已执行':'执行记录'} · {executionLabels[latest.result]??'结果未记录'}
                            </span>
                            <small>第 {latest.run_no} 次 · V{latest.case_revision} · {modeLabel(latest.mode)}</small>
                            <small>
                              {latest.reason}
                            </small>
                          </>
                        ) : (
                          <span className="run-result-badge run-result-badge--not-run"><span aria-hidden="true">○</span> 未执行</span>
                        )}
                      </td>
                      <td className="actions">
                        <button type="button" className="secondary" aria-label={`修订用例 ${testCase.display_code}`} disabled={busy||savedRefresh.blocked} onClick={event=>{setEditorTrigger(event.currentTarget);setEditingCase(testCase)}}>修订用例</button>
                        {['draft','pending_review'].includes(testCase.review_status) && (
                          <button
                            type="button"
                            disabled={busy || savedRefresh.blocked}
                            onClick={() => void handleConfirmCase(testCase)}
                          >
                            确认用例
                          </button>
                        )}
                        {['draft','pending_review'].includes(testCase.review_status) && <button type="button" className="secondary danger-action" aria-label={`驳回用例 ${testCase.display_code}`} disabled={busy||savedRefresh.blocked||testCase.validity!=='current'} onClick={event=>{setRejection({kind:'case',id:testCase.id,revision:testCase.revision,label:testCase.display_code,trigger:event.currentTarget});setRejectionReason('');setRejectionError('')}}>驳回用例</button>}
                        {testCase.validity === 'stale' && (
                          <button
                            type="button"
                            disabled={busy || savedRefresh.blocked}
                            onClick={() => void handleRebase(testCase)}
                          >
                            重基需求
                          </button>
                        )}
                        <button
                          type="button"
                          className={openedRunKey===`${testCase.id}:${testCase.revision}`?'demo-fill-button':'secondary'}
                          aria-controls={runFormId}
                          aria-expanded={runOpen&&openedRunKey===`${testCase.id}:${testCase.revision}`}
                          aria-haspopup="dialog"
                          disabled={
                            busy ||
                            savedRefresh.blocked ||
                            testCase.review_status !== 'confirmed' ||
                            testCase.validity !== 'current'
                          }
                          onClick={event => void openRunForm(testCase,event.currentTarget)}
                        >
                          记录执行
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {runOpen&&selectedCase&&<DetailOverlay title={`记录执行：${selectedCase.display_code}`} subtitle={`${selectedCase.title} · V${selectedCase.revision}`} eyebrow="试验执行 · 结果与证据" locked={busy} returnFocus={runTrigger} initialFocus={conditionsInput} closeLabel="关闭执行记录" footer="关闭不提交执行；同一用例版本的未提交输入在本页保留。" onClose={()=>{setRunOpen(false);setError('')}}>
          {error&&<Notice kind="error">{error}</Notice>}
          {openedRunKey===`${selectedCase.id}:${selectedCase.revision}`&&selectedCase.review_status==='confirmed'&&selectedCase.validity==='current'?(
            <form
              id={runFormId}
              aria-label={`执行记录 ${selectedCase.display_code}`}
              className="run-dialog-form"
              onSubmit={(event) => void handleRecordRun(event)}
            >
              {selectedCaseId&&<p className="hint" role="status">正在填写 {selectedCase.display_code} · V{selectedCase.revision} 的执行记录；点击“提交执行记录”后才会保存。</p>}
              {runPresetLoading?<p role="status">正在读取当前加载依据…</p>:runPresetNote&&<p className="hint">{runPresetNote}</p>}
              <p className="hint">
                {selectedCase.case_kind === 'static_torsion'
                  ? '该用例同时检查当前加载基准与无量纲后备系数；旧基准或低于系数门槛均判失败。'
                  : '人工判定必须提交结论与可核对证据。'}
              </p>
              <div className="form-grid">
                <label className="wide">
                  执行工况
                  <input
                    aria-label="执行工况"
                    ref={conditionsInput}
                    value={runDraft.conditions}
                    onChange={(event) =>
                      setRunDraft((current) => ({
                        ...current,
                        conditions: event.target.value,
                      }))
                    }
                    required
                  />
                </label>
                <label className="wide">
                  执行证据
                  <input
                    aria-label="执行证据"
                    value={runDraft.evidence??syntheticEvidence}
                    onChange={(event) =>
                      setRunDraft((current) => ({
                        ...current,
                        evidence: event.target.value,
                      }))
                    }
                    placeholder="例如：合成执行记录 RUN-001"
                    required
                  />
                </label>
                {selectedCase.case_kind === 'static_torsion' ? (
                  <>
                    <label>
                      当前加载基准（N·m）
                      <input
                        aria-label="加载基准 N·m"
                        type="number"
                        step="any"
                        value={runDraft.loadBasis}
                        onChange={(event) => {
                          loadEdited.current=true
                          setRunDraft((current) => ({
                            ...current,
                            loadBasis: event.target.value,
                          }))
                        }}
                        required
                      />
                    </label>
                    <label>
                      后备系数
                      <input
                        aria-label="后备系数"
                        type="number"
                        step="any"
                        value={runDraft.backupCoefficient}
                        onChange={(event) =>
                          setRunDraft((current) => ({
                            ...current,
                            backupCoefficient: event.target.value,
                          }))
                        }
                        required
                      />
                    </label>
                  </>
                ) : (
                  <label>
                    人工结论
                    <select
                      aria-label="人工结论"
                      value={runDraft.manualResult}
                      onChange={(event) =>
                        setRunDraft((current) => ({
                          ...current,
                          manualResult: event.target
                            .value as RunDraft['manualResult'],
                        }))
                      }
                    >
                      <option value="pass">通过</option>
                      <option value="fail">未通过</option>
                      <option value="incomplete">证据不足</option>
                      <option value="invalid">无效</option>
                    </select>
                  </label>
                )}
              </div>
              <div className="form-actions">
                <button type="submit" className="primary-action" disabled={busy || savedRefresh.blocked}>
                  提交执行记录
                </button>
                <button type="button" className="secondary" disabled={busy} onClick={()=>{setRunOpen(false);setError('')}}>取消</button>
              </div>
            </form>
          ):<Notice kind="info">该用例版本或审核状态已变化，请关闭后重新核对。</Notice>}
        </DetailOverlay>}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <h2>追溯矩阵</h2>
          {matrix && (
            <span className="count">
              {matrix.covered_count}/{matrix.denominator} · 覆盖率{' '}
              {matrix.coverage_percentage}%
            </span>
          )}
        </div>
        {matrix ? (
          <>
            <p className="hint">
              范围：{matrix.scope_label}
            </p>
            <ExecutionSummary counts={matrix.execution_summary} />
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>验证范围</th>
                    <th>需求</th>
                    <th>覆盖</th>
                    <th>执行</th>
                    <th>原因</th>
                  </tr>
                </thead>
                <tbody>
                  {matrix.items.map((item) => (
                    <tr key={item.key}>
                      <td>{item.label}</td>
                      <td className="mono">
                        {item.display_code ?? '未关联'}
                      </td>
                      <td>
                        {item.covered ? '已覆盖' : '未覆盖'}
                        {!item.covered && item.pending_case_ids.length > 0
                          ? `（待确认 ${item.pending_case_ids.length}）`
                          : ''}
                      </td>
                      <td>{executionLabels[item.execution]}</td>
                      <td className="source">{item.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <Empty>正在加载追溯矩阵…</Empty>
        )}
      </section>
      {rejection && <DetailOverlay title={rejection.kind==='plan'?'驳回试验方案':'驳回试验用例'} subtitle={`${rejection.label} · V${rejection.revision}`} eyebrow="试验审核 · 退回修订" locked={busy} returnFocus={rejection.trigger} onClose={()=>setRejection(null)}>
        <p className="hint">填写需要补充或修改的内容。驳回仅记录当前版本的审核决定；修订或重新生成新版本后再审核。</p>
        {rejectionError&&<Notice kind="error">{rejectionError}</Notice>}
        <form className="form-grid" onSubmit={event=>{event.preventDefault();void handleReject()}}><label className="wide">驳回原因（选填）<textarea aria-label="驳回原因" rows={4} maxLength={2000} value={rejectionReason} onChange={event=>setRejectionReason(event.target.value)} disabled={busy}/></label><div className="form-actions"><button type="submit" className="danger-action" disabled={busy||savedRefresh.blocked}>提交驳回</button></div></form>
      </DetailOverlay>}
    </>
  )
}
