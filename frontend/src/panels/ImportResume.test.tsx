import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { IDBFactory } from 'fake-indexeddb'
import { ParsingPanel } from './ParsingPanel'
import { flushImportDrafts, readImportDrafts } from '../importDrafts'

const json=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status})
const attempt={id:'preview-1',filename:'协议.docx',sha256:'a'.repeat(64),size_bytes:8,status:'awaiting_review',stage:'review_text',error_message:'',created_at:'2026-10-25T08:00:00+00:00',source_document_id:null}
let records:typeof attempt[], creates:number, extracts:number, archived:Record<string,unknown>|null
beforeEach(()=>{
 vi.stubGlobal('indexedDB',new IDBFactory());records=[];creates=0;extracts=0;archived=null
 vi.stubGlobal('fetch',vi.fn(async(url:RequestInfo|URL,init?:RequestInit)=>{
  const route=String(url)
  if(route.includes('/extract?')){extracts++;records=[attempt];return json({import_id:attempt.id,content:'发动机最大扭矩2600 N·m。',sha256:attempt.sha256,warnings:[]})}
  if(route.includes('/api/document-text?'))return json({content:'发动机最大扭矩2600 N·m。',sha256:attempt.sha256,warnings:[]})
  if(route.endsWith('/document-imports'))return json(route.includes('/p2/')?[]:records)
  if(route.endsWith('/source-documents')&&init?.method==='POST'){creates++;archived=JSON.parse(String(init.body));records=[];return json({id:'source-1',display_code:'DOC-CHECK',version:'V2'},201)}
  if(route.endsWith('/parse'))return json({status:'parsed',mode:'rule',parsed_at:'2026-10-25T08:00:00+00:00',requirements:[],issues:[],missing_categories:[],unrecognized_clauses:[],already_parsed:false})
  if(route.endsWith('/discard')){records=[];return json({...attempt,status:'cancelled'})}
  return json([])
 }))
})
afterEach(async()=>{await flushImportDrafts();vi.unstubAllGlobals()})

it('restores reviewed text, metadata, mapping and original after leaving the module, without another extraction',async()=>{
 const user=userEvent.setup(), first=render(<ParsingPanel projectId="p1"/>)
 await waitFor(()=>expect(screen.getByLabelText('选择协议文件')).toBeEnabled())
 await user.clear(screen.getByLabelText('来源文档编号'));await user.type(screen.getByLabelText('来源文档编号'),'DOC-CHECK')
 await user.upload(screen.getByLabelText('选择协议文件'),new File(['original'],'协议.docx'))
 await screen.findByText(/文件文本已提取/)
 await user.clear(screen.getByLabelText('来源文档版本'));await user.type(screen.getByLabelText('来源文档版本'),'V2')
 await user.type(screen.getByLabelText('来源文档正文'),' 人工核对补充。')
 await user.click(screen.getByText('高级选项：自定义显示编号（可选）'))
 await user.type(screen.getByLabelText('显示编号映射'),'engineMaxTorque=REQ-P01-B-003')
 first.unmount()
 render(<ParsingPanel projectId="p1"/>)
 await waitFor(()=>expect(screen.getByLabelText('来源文档正文')).toHaveValue('发动机最大扭矩2600 N·m。 人工核对补充。'))
 expect(screen.getByLabelText('来源文档编号')).toHaveValue('DOC-CHECK')
 expect(screen.getByLabelText('来源文档版本')).toHaveValue('V2')
 expect(screen.getByLabelText('显示编号映射')).toHaveValue('engineMaxTorque=REQ-P01-B-003')
 await user.click(screen.getByRole('button',{name:'继续核对'}))
 await waitFor(()=>expect(screen.getByRole('button',{name:'导入并解析'})).toBeEnabled())
 await user.click(screen.getByRole('button',{name:'导入并解析'}))
 await screen.findByText(/^已解析 DOC-CHECK/)
 expect(extracts).toBe(1);expect(creates).toBe(1)
 expect(archived).toMatchObject({import_id:'preview-1',display_code:'DOC-CHECK',version:'V2',original_file:{filename:'协议.docx',data_base64:btoa('original')}})
 expect(await readImportDrafts('p1')).toEqual([])
},15000)

it('keeps drafts isolated by project and removes a cancelled preview from subsequent visits',async()=>{
 const user=userEvent.setup(), view=render(<ParsingPanel projectId="p1"/>)
 await waitFor(()=>expect(screen.getByLabelText('选择协议文件')).toBeEnabled())
 await user.upload(screen.getByLabelText('选择协议文件'),new File(['original'],'协议.docx'))
 await screen.findByText(/文件文本已提取/)
 view.rerender(<ParsingPanel projectId="p2"/>)
 await waitFor(()=>expect(screen.getByLabelText('来源文档正文')).toBeEnabled())
 expect(screen.getByLabelText('来源文档正文')).toHaveValue('')
 view.rerender(<ParsingPanel projectId="p1"/>)
 await waitFor(()=>expect(screen.getByLabelText('来源文档正文')).toHaveValue('发动机最大扭矩2600 N·m。'))
 await user.click(screen.getByRole('button',{name:'取消待核对'}))
 await waitFor(()=>expect(screen.getByLabelText('来源文档正文')).toHaveValue(''))
 view.unmount();render(<ParsingPanel projectId="p1"/>)
 await waitFor(()=>expect(screen.getByLabelText('来源文档正文')).toBeEnabled())
 expect(screen.getByLabelText('来源文档正文')).toHaveValue('');expect(creates).toBe(0)
})

it('offers continuation for legacy records and never silently creates another processing attempt',async()=>{
 records=[attempt]
 render(<ParsingPanel projectId="p1"/>)
 const row=await screen.findByRole('row',{name:/协议.docx/})
 expect(within(row).getByRole('button',{name:'继续核对'})).toBeEnabled()
 await userEvent.click(within(row).getByRole('button',{name:'继续核对'}))
 expect(await screen.findByRole('button',{name:'选择原文件恢复核对'})).toBeVisible()
 expect(creates).toBe(0);expect(extracts).toBe(0)
 await userEvent.upload(screen.getByLabelText('选择协议文件'),new File(['original'],'协议.docx'))
 await screen.findByText(/文件文本已提取/)
 await userEvent.click(screen.getByRole('button',{name:'导入并解析'}))
 await screen.findByText(/^已解析 DOC-CHECK/)
 expect(archived).toMatchObject({import_id:attempt.id});expect(extracts).toBe(0)
})

it('does not resurrect a cancelled or already archived attempt from browser storage',async()=>{
 const user=userEvent.setup(), view=render(<ParsingPanel projectId="p1"/>)
 await waitFor(()=>expect(screen.getByLabelText('选择协议文件')).toBeEnabled())
 await user.upload(screen.getByLabelText('选择协议文件'),new File(['original'],'协议.docx'))
 await screen.findByText(/文件文本已提取/)
 view.unmount();await flushImportDrafts();records=[]
 render(<ParsingPanel projectId="p1"/>)
 await waitFor(()=>expect(screen.getByLabelText('来源文档正文')).toBeEnabled())
 expect(screen.getByLabelText('来源文档正文')).toHaveValue('');expect(creates).toBe(0)
})

it('viewing another archived result never rebinds the unsaved preview to that document',async()=>{
 const user=userEvent.setup(), base=globalThis.fetch
 vi.stubGlobal('fetch',vi.fn(async(url:RequestInfo|URL,init?:RequestInit)=>{
  if(String(url).endsWith('/source-documents')&&!init?.method)return json([{id:'older-source',display_code:'DOC-OLD',version:'V1',parsed_at:'2026-10-24T00:00:00+00:00',parse_summary:{status:'parsed',requirement_count:1,pending_requirement_count:1,issue_count:0,open_issue_count:0,closed_issue_count:0}}])
  return base(url,init)
 }))
 const view=render(<ParsingPanel projectId="p1"/>)
 await waitFor(()=>expect(screen.getByLabelText('选择协议文件')).toBeEnabled())
 await user.upload(screen.getByLabelText('选择协议文件'),new File(['original'],'协议.docx'))
 await screen.findByText(/文件文本已提取/)
 await user.click(screen.getByRole('button',{name:'查看解析结果'}))
 const dialog=await screen.findByRole('dialog',{name:'文档解析结果'})
 await within(dialog).findByText(/已完成解析/)
 await user.click(screen.getByRole('button',{name:'关闭解析结果'}))
 view.unmount();render(<ParsingPanel projectId="p1"/>)
 await waitFor(()=>expect(screen.getByLabelText('来源文档正文')).toHaveValue('发动机最大扭矩2600 N·m。'))
 expect(screen.getByText(/待归档：协议.docx/)).toBeVisible()
 expect(creates).toBe(0)
})
