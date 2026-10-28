import {render,screen,within} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {afterEach,expect,it,vi} from 'vitest'
import type {SourceDocument,DocumentImport} from '../types'
import {recoverImportProgress} from './importProgressState'
import {ParsingPanel} from './ParsingPanel'

const doc:SourceDocument={id:'s1',project_id:'p1',display_code:'DOC-1',version:'V1',doc_type:'protocol',mode:'manual',content_hash:'a'.repeat(64),created_at:'2026-10-26T01:00:00Z',parsed_at:'2026-10-26T01:01:00Z',original_file:{filename:'协议.docx',sha256:'a'.repeat(64),size_bytes:100,reviewed_text_changed:false},parse_summary:{status:'parsed',requirement_count:19,pending_requirement_count:19,issue_count:0,open_issue_count:0,closed_issue_count:0}}
const attempt:DocumentImport={id:'a1',filename:'协议.docx',status:'completed',stage:'saved',error_message:'',created_at:doc.created_at,source_document_id:doc.id}
afterEach(()=>vi.unstubAllGlobals())

it('restores a completed source and identifies its document instead of an empty new task',()=>{
 expect(recoverImportProgress('p1',[doc],[attempt])).toMatchObject({phase:'saved',filename:expect.stringContaining('协议.docx')})
})
it('keeps the latest failure or pending task distinct from a previous completion',()=>{
 const newer={...attempt,id:'a2',source_document_id:null,created_at:'2026-10-26T02:00:00Z',filename:'新文件.pdf'}
 expect(recoverImportProgress('p1',[doc],[attempt,{...newer,status:'failed',stage:'text_extraction',error_message:'扫描件无法提取'}])).toMatchObject({phase:'extracting',failed:'扫描件无法提取'})
 expect(recoverImportProgress('p1',[doc],[attempt,{...newer,status:'awaiting_review'}])).toMatchObject({phase:'reviewing'})
 expect(recoverImportProgress('p1',[doc],[attempt,{...newer,status:'cancelled'}])?.phase).not.toBe('saved')
})
it('does not pretend an archived source is parsed and handles manual text without file steps',()=>{
 expect(recoverImportProgress('p1',[{...doc,parsed_at:null,parse_summary:{...doc.parse_summary!,status:'pending_parse'}}],[])).toMatchObject({phase:'archiving'})
 expect(recoverImportProgress('p1',[{...doc,original_file:null}],[])).toMatchObject({phase:'saved',textOnly:true})
 expect(recoverImportProgress('p1',[{...doc,parse_summary:{...doc.parse_summary!,pending_requirement_count:0}}],[])).toMatchObject({phase:'saved',statusText:'结果已保存；当前没有待审核需求。'})
 expect(recoverImportProgress('p2',[doc],[])).toBeNull()
 expect(recoverImportProgress('p1',[],[])).toBeNull()
})
it('recovers completion on return, gives new input priority and resets across projects',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:RequestInfo|URL)=>new Response(JSON.stringify(String(url).includes('/p1/source-documents')?[doc]:[]))))
 const user=userEvent.setup();const view=render(<ParsingPanel projectId="p1"/>)
 const progress=screen.getByRole('region',{name:'协议处理进度'})
 expect(await within(progress).findByText('结果已保存，需求仍需人工审核')).toBeVisible()
 expect(progress.querySelectorAll('li.is-done')).toHaveLength(5)
 expect(within(progress).getByText(/最近.*DOC-1/)).toBeVisible()
 await user.type(screen.getByLabelText('来源文档正文'),'新的协议正文')
 expect(within(progress).getByText(/文本已就绪/)).toBeVisible()
 view.rerender(<ParsingPanel projectId="p2"/>)
 expect(await within(screen.getByRole('region',{name:'协议处理进度'})).findByText('选择文件或粘贴正文开始')).toBeVisible()
})
it('does not show stale completion when the source request fails',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:RequestInfo|URL)=>new Response(JSON.stringify(String(url).endsWith('/source-documents')?{error:{message:'读取失败'}}:[]),{status:String(url).endsWith('/source-documents')?503:200})))
 render(<ParsingPanel projectId="p1"/>)
 await screen.findByText(/文档状态未能读取/)
 expect(within(screen.getByRole('region',{name:'协议处理进度'})).queryByText('结果已保存，需求仍需人工审核')).not.toBeInTheDocument()
})
