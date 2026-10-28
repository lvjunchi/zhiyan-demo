import { useState } from 'react'
import type { WorkflowSummary } from '../types'
import { DetailOverlay } from './DetailOverlay'

type Change = WorkflowSummary['consistency']['changes'][number]

export function ChangeSheet({changes}:{changes:Change[]}){
  const [query,setQuery]=useState(''),[kind,setKind]=useState('all')
  const [selected,setSelected]=useState<Change|null>(null),[opener,setOpener]=useState<HTMLElement|null>(null)
  const visible=changes.filter(row=>(kind==='all'||kind===row.kind)&&[row.label,row.kind,row.parameter,row.before,row.after,row.versions,row.evidence].join(' ').toLowerCase().includes(query.trim().toLowerCase()))
  return <>
    <div className="change-sheet-toolbar"><label>搜索<input aria-label="搜索参数版本变化" value={query} onChange={event=>setQuery(event.target.value)} placeholder="对象、参数、型号或依据"/></label><label>类型<select aria-label="变化类型筛选" value={kind} onChange={event=>setKind(event.target.value)}><option value="all">全部类型</option>{[...new Set(changes.map(row=>row.kind))].map(value=><option key={value}>{value}</option>)}</select></label><span>显示 {visible.length} / {changes.length} 条 · 只读追溯表</span></div>
    <div className="change-sheet table-wrap"><table aria-label="参数版本变化表"><colgroup>{[5,14,12,18,18,13,20].map((width,index)=><col key={index} style={{width:`${width}%`}}/>)}</colgroup><thead><tr className="sheet-letters" aria-hidden="true">{['#','A','B','C','D','E','F'].map(value=><th key={value}>{value}</th>)}</tr><tr><th>序号</th><th>对象 / 类型</th><th>比较参数</th><th>基准 / 变更前</th><th>当前 / 实测</th><th>版本</th><th>依据</th></tr></thead><tbody>{visible.map(row=><tr key={row.id}><th scope="row">{changes.findIndex(item=>item.id===row.id)+1}</th><td><strong>{row.label}</strong><small>{row.kind}</small></td><td>{row.parameter}</td><td title={`${row.before} ${row.unit}`}>{row.before} {row.unit}</td><td className="comparison-new" title={`${row.after} ${row.unit}`}>{row.after} {row.unit}</td><td>{row.versions}</td><td><span className="sheet-evidence" title={row.evidence}>{row.evidence}</span><button type="button" className="secondary" aria-label={`查看 ${row.label} 变化依据`} onClick={event=>{setOpener(event.currentTarget);setSelected(row)}}>查看依据</button></td></tr>)}</tbody></table></div>
    {!visible.length&&<p className="empty">没有匹配的变化记录</p>}
    <p className="hint">表格可横向滚动，表头固定；修改参数或版本请进入对应业务模块，完整证据可点“查看依据”。</p>
    {selected&&<DetailOverlay title={`变化依据 · ${selected.label}`} subtitle={`${selected.kind} · ${selected.versions}`} returnFocus={opener} onClose={()=>setSelected(null)}><p>{selected.parameter}：{selected.before} {selected.unit} → {selected.after} {selected.unit}</p><p>{selected.evidence||'未记录变化依据'}</p></DetailOverlay>}
  </>
}
