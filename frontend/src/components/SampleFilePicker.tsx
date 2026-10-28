import { useEffect, useRef, useState, type RefObject } from 'react'
import { toErrorMessage } from '../uiSupport'
import './sample-file-picker.css'

export function SampleFilePicker({file,onFile,disabled=false,label,zoneLabel='样件原件拖放区',inputRef}: {
  file: File|null; onFile: (file:File|null)=>void; disabled?:boolean; label:string; zoneLabel?:string; inputRef?:RefObject<HTMLInputElement|null>
}) {
  const nativeInput=useRef<HTMLInputElement>(null)
  const input=inputRef??nativeInput
  const [loadingRequest,setLoadingRequest]=useState<number|null>(null)
  const loading=loadingRequest!==null
  const [error,setError]=useState('')
  const [dragging,setDragging]=useState(false)
  const epoch=useRef(0)
  useEffect(()=>()=>{epoch.current++},[])
  useEffect(()=>{if(disabled)epoch.current++},[disabled])
  useEffect(()=>{
    if(!input.current)return
    if(!file){input.current.value='';return}
    if(typeof DataTransfer!=='undefined'){
      const transfer=new DataTransfer();transfer.items.add(file);input.current.files=transfer.files
    }
  },[file,input])
  function choose(next:File|null){epoch.current++;setLoadingRequest(null);setDragging(false);setError('');onFile(next)}
  async function chooseDemo(){
    const request=++epoch.current;setLoadingRequest(request);setDragging(false);setError('')
    try{
      const response=await fetch('/demo/sample-dimensions.svg')
      if(!response.ok||!response.headers.get('Content-Type')?.includes('image/svg+xml'))throw new Error('本地演示图纸读取失败，请重新选择文件')
      const bytes=await response.arrayBuffer()
      if(request===epoch.current)onFile(new File([bytes],'07_样件尺寸示意.svg',{type:'image/svg+xml'}))
    }catch(err){if(request===epoch.current)setError(toErrorMessage(err))}
    finally{setLoadingRequest(current=>current===request?null:current)}
  }
  return <div role="group" aria-label={zoneLabel} className={`sample-file-picker${dragging&&!disabled?' is-dragging':''}`} onDragOver={event=>{event.preventDefault();if(!disabled)setDragging(true)}} onDragLeave={()=>setDragging(false)} onDrop={event=>{
    event.preventDefault();setDragging(false)
    if(disabled)return
    const files=event.dataTransfer.files
    if(files.length!==1){setError('每次请选择一个文件');return}
    choose(files[0])
  }}>
    <div className="sample-file-picker-actions"><input ref={input} type="file" aria-label={label} disabled={disabled} onChange={event=>choose(event.target.files?.[0]??null)}/><button type="button" className="demo-fill-button" disabled={disabled||loading} onClick={()=>void chooseDemo()}>{loading?'正在读取图纸…':'使用演示图纸'}</button></div>
    {file?<div className="sample-file-selection"><span>已选择：{file.name}</span><button type="button" className="secondary" disabled={disabled} onClick={()=>choose(null)}>移除文件</button></div>:<p className="hint">可将一个文件拖到这里，或选择本地文件。演示图纸为本地合成SVG原件。</p>}
    {error&&<p role="alert" className="error">{error}</p>}
  </div>
}
