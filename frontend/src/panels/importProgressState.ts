import type {DocumentImport,SourceDocument} from '../types'

export type ImportPhase = 'idle' | 'checking' | 'extracting' | 'reviewing' | 'archiving' | 'parsing' | 'saved'
export type ProgressSnapshot={phase:ImportPhase;failed:string;filename:string;textOnly?:boolean;statusText?:string}

// Read actual persisted stages; never cache a fake completion or restart processing.
export function recoverImportProgress(projectId:string,documents:SourceDocument[],attempts:DocumentImport[]):ProgressSnapshot|null{
  const sources=documents.filter(row=>row.project_id===projectId)
  const records=attempts.filter(row=>!row.project_id||row.project_id===projectId)
  const time=(value?:string|null)=>{const result=Date.parse(value??'');return Number.isFinite(result)?result:0}
  function sourceProgress(source:SourceDocument,filename:string,textOnly:boolean):ProgressSnapshot{
    return source.parsed_at?{phase:'saved',failed:'',filename,textOnly,
      ...(source.parse_summary?.status==='needs_manual_review'?{statusText:'解析记录已保存，但未提取到有效需求，仍需人工核对。'}
        :!source.parse_summary?{statusText:'解析结果已保存；需求审核状态请以需求清单为准。'}
        :source.parse_summary.pending_requirement_count===0?{statusText:'结果已保存；当前没有待审核需求。'}:{})}
      :{phase:'archiving',failed:'',filename,textOnly,statusText:'文档已归档，等待解析；请在文档列表点击“继续解析”。'}
  }
  const linked=new Set(records.map(row=>row.source_document_id))
  const snapshots:{id:string;time:number;value:ProgressSnapshot}[]=sources.filter(row=>!linked.has(row.id)).map(source=>({
    id:source.id,time:time(source.parsed_at??source.created_at),
    value:sourceProgress(source,`最近任务：${source.original_file?.filename??'正文录入'} · ${source.display_code} · ${source.version}`,!source.original_file),
  }))
  for(const attempt of records){
    const source=sources.find(row=>row.id===attempt.source_document_id)
    const filename=`最近任务：${attempt.filename}${source?` · ${source.display_code} · ${source.version}`:''}`
    let value:ProgressSnapshot
    if(attempt.status==='cancelled')value={phase:'idle',failed:'',filename,statusText:'该次核对已取消；历史记录保留，未作为已完成解析。'}
    else if(attempt.status==='failed')value={phase:attempt.stage==='file_check'?'checking':attempt.stage==='requirement_parse'?'parsing':'extracting',failed:attempt.error_message||'处理失败，原因未记录，请查看文件处理记录。',filename}
    else if(attempt.status==='awaiting_review')value={phase:'reviewing',failed:'',filename,statusText:'文件已提取，等待核对正文；可在文件处理记录中点击“继续核对”。'}
    else if(source)value=sourceProgress(source,filename,false)
    else value={phase:'idle',failed:'',filename,statusText:'处理记录已保存，来源文档状态暂未核对，请刷新导入状态。'}
    snapshots.push({id:attempt.id,time:Math.max(time(attempt.updated_at??attempt.created_at),time(source?.parsed_at)),value})
  }
  snapshots.sort((a,b)=>b.time-a.time||a.id.localeCompare(b.id))
  return snapshots[0]?.value??null
}
