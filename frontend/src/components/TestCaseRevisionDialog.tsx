import { useRef,useState,type FormEvent } from 'react'
import { api } from '../api'
import type { TestCase } from '../types'
import { DetailOverlay } from './DetailOverlay'
import { Notice } from '../ui'
import { DEMO_ACTOR,DEMO_ROLE,toErrorMessage } from '../uiSupport'
export function TestCaseRevisionDialog({testCase,returnFocus,onClose,onSaved}:{testCase:TestCase;returnFocus:HTMLElement|null;onClose:()=>void;onSaved:(row:TestCase)=>Promise<void>}){
 const [conditions,setConditions]=useState(testCase.conditions_text),[load,setLoad]=useState(testCase.load_conditions_text),[criteria,setCriteria]=useState(testCase.acceptance_criteria),[comment,setComment]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('')
 const criterionInput=useRef<HTMLTextAreaElement>(null)
 async function submit(event:FormEvent){event.preventDefault();if(busy)return;setBusy(true);setError('');let saved=false
  try{const row=await api.updateTestCase(testCase.id,{expected_revision:testCase.revision,actor:DEMO_ACTOR,role:DEMO_ROLE,conditions_text:conditions.trim(),load_conditions_text:load.trim(),acceptance_criteria:criteria.trim(),comment:comment.trim()});saved=true;await onSaved(row);onClose()}
  catch(err){if(saved){setError(`修订已保存，刷新失败，请关闭后重新读取方案：${toErrorMessage(err)}`)}else setError(toErrorMessage(err))}finally{setBusy(false)}
 }
 return <DetailOverlay title="修订试验用例" variant="wide" eyebrow="试验验证 · 条件与判据" subtitle={`${testCase.display_code} · ${testCase.title} · 当前V${testCase.revision}`} returnFocus={returnFocus} initialFocus={criterionInput} locked={busy} onClose={onClose} footer="实质修订产生新版本，需重新确认和执行；历史审核与结果保留。">{error&&<Notice kind="error">{error}</Notice>}<form className="form-grid" onSubmit={event=>void submit(event)}><label className="wide">试验条件<textarea aria-label="用例试验条件" rows={3} value={conditions} onChange={event=>setConditions(event.target.value)} required/></label><label className="wide">加载工况<textarea aria-label="用例加载工况" rows={3} value={load} onChange={event=>setLoad(event.target.value)} required/></label><label className="wide">通过判据<textarea ref={criterionInput} aria-label="用例通过判据" rows={4} value={criteria} onChange={event=>setCriteria(event.target.value)} disabled={testCase.case_kind==='static_torsion'}/></label>{testCase.case_kind==='static_torsion'&&<p className="hint">静扭判定采用当前加载基准和已冻结的后备系数门槛 {testCase.minimum_coefficient}，此处只读。需求变更后先重新基线。</p>}<label className="wide">修订依据<textarea aria-label="用例修订依据" rows={3} value={comment} onChange={event=>setComment(event.target.value)} required placeholder="填写补充协议、标准或澄清记录编号及结论"/></label><div className="form-actions"><button type="submit" disabled={busy||!comment.trim()}>保存用例修订</button></div></form></DetailOverlay>
}
