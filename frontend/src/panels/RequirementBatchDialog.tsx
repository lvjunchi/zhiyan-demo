import { useEffect, useState } from 'react'
import { api } from '../api'
import { DetailOverlay } from '../components/DetailOverlay'
import { formatRequirementTarget } from '../formatters'
import type { Requirement, RequirementBatchPreview } from '../types'
import { Notice } from '../ui'
import { DEMO_ACTOR, DEMO_ROLE, toErrorMessage } from '../uiSupport'

export function RequirementBatchDialog({ projectId, requirements, returnFocus, onClose, onSaved }: {
  projectId:string;requirements:Requirement[];returnFocus:HTMLElement|null;onClose:()=>void;onSaved:(count:number)=>Promise<void>
}) {
  const [preview,setPreview]=useState<RequirementBatchPreview|null>(null)
  const [busy,setBusy]=useState(true)
  const [error,setError]=useState('')
  const [acknowledged,setAcknowledged]=useState(false)
  const [reload,setReload]=useState(0)
  useEffect(()=>{
    let active=true
    api.previewRequirementBatch(projectId,requirements.map(row=>({requirement_id:row.id,expected_revision:row.current_revision})))
      .then(value=>{if(active){setPreview(value);setError('')}}).catch((err:unknown)=>{if(active)setError(toErrorMessage(err))}).finally(()=>{if(active)setBusy(false)})
    return()=>{active=false}
  },[projectId,requirements,reload])
  async function submit(){
    if(!preview?.can_submit||!acknowledged)return
    setBusy(true);setError('')
    try{
      const result=await api.confirmRequirementBatch(projectId,{items:requirements.map(row=>({requirement_id:row.id,expected_revision:row.current_revision})),expected_preview_hash:preview.preview_hash,actor:DEMO_ACTOR,role:DEMO_ROLE,comment:'工程师批量核对需求原文与当前版本后确认'})
      await onSaved(result.confirmed_count);onClose()
    }catch(err){setError(toErrorMessage(err));setPreview(null);setAcknowledged(false)}
    finally{setBusy(false)}
  }
  return <DetailOverlay title="批量确认需求" variant="wide" eyebrow="需求审核 · 本批次范围预览" subtitle={`本次选择 ${requirements.length} 条需求；逐条记录审核，整批提交。`} returnFocus={returnFocus} onClose={onClose} locked={busy} pendingLabel="正在校验或保存本批次，请稍候…">
    {busy&&!preview&&<p role="status">正在核对版本、来源、字段与阻塞问题…</p>}
    {error&&<Notice kind="error">{error}<p>预览失效或列表已变化时，请关闭后刷新列表并重新选择。</p><button type="button" disabled={busy} onClick={()=>{setBusy(true);setPreview(null);setAcknowledged(false);setReload(value=>value+1)}}>重新预览本批次</button></Notice>}
    {preview&&<><p className="hint">只审核以下明确列出的版本。已驳回需求不自动改为通过；存在任一不可确认项时，本批次全部不提交。</p><div className="table-wrap"><table><thead><tr><th>需求</th><th>目标</th><th>版本</th><th>校验</th></tr></thead><tbody>{preview.rows.map(row=><tr key={row.requirement.id}><td>{row.requirement.display_code}<small className="muted">{row.requirement.parameter_name}</small></td><td>{formatRequirementTarget(row.requirement)}</td><td>V{row.requirement.current_revision}</td><td>{row.eligible?<span className="status confirmed">可确认</span>:<span className="status rejected">{row.reasons.join('；')}</span>}</td></tr>)}</tbody></table></div>
      {!preview.can_submit&&<Notice kind="info">请先处理阻塞，或返回列表调整本批次选择；不会跳过错误自动确认其余项。</Notice>}
      <label className="batch-acknowledgement"><input type="checkbox" aria-label="我已逐条核对本批次需求" checked={acknowledged} disabled={busy||!preview.can_submit} onChange={event=>setAcknowledged(event.target.checked)}/>我已逐条核对本批次需求的原文、目标及适用版本。</label></>}
    <div className="form-actions requirement-batch-actions"><button type="button" className="primary-action" disabled={busy||!preview?.can_submit||!acknowledged} onClick={()=>void submit()}>确认本批次需求</button><button type="button" className="secondary" disabled={busy} onClick={onClose}>取消批量确认</button></div>
  </DetailOverlay>
}
