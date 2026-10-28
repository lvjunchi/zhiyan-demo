import {expect,test} from '@playwright/test'
import {readFile} from 'node:fs/promises'
import {createHash} from 'node:crypto'
import {openWorkspaceTab} from '../e2e-support/navigation'
const evidence=process.env.ZHIYAN_EVIDENCE_DIR??'test-results/overview/screenshots'
const protocol='../演示导入文件/综合演示/01_综合技术协议_V1.docx'

test('continues the same reviewed file across navigation and refresh, recovers legacy attempts and cancels without resurrection',async({page,request})=>{
 test.setTimeout(90000)
 const errors:string[]=[];let extracts=0
 const before=await(await request.get('/api/system/backup')).json()
 try {
 page.on('pageerror',error=>errors.push(error.message))
 page.on('request',req=>{if(req.url().includes('/document-imports/extract?'))extracts++})
 const projects=await(await request.get('/api/projects')).json() as {id:string}[]
 const pid=projects[0].id
 const attempts=async()=>await(await request.get(`/api/projects/${pid}/document-imports`)).json() as {id:string;status:string;source_document_id:string|null}[]
 const requirements=async()=>await(await request.get(`/api/projects/${pid}/requirements`)).json() as {review_status:string}[]
 const mapping=(await readFile('../演示导入文件/综合演示/08_需求编号映射.txt','utf-8')).replace(/\r\n/g,'\n')
 await page.goto('/');await openWorkspaceTab(page,'协议解析与澄清')
 await expect(page.getByLabel('选择协议文件')).toBeEnabled()
 await page.getByLabel('选择协议文件').setInputFiles(protocol)
 await expect(page.getByText(/文件文本已提取/)).toBeVisible()
 const reviewed=(await page.getByLabel('来源文档正文').inputValue())+'\n人工核对备注：本次为离线合成演示。'
 await page.getByLabel('来源文档编号').fill('DOC-RESUME-001')
 await page.getByLabel('来源文档版本').fill('V2')
 await page.getByLabel('来源文档正文').fill(reviewed)
 await page.getByText('高级选项：自定义显示编号（可选）',{exact:true}).click()
 await page.getByLabel('显示编号映射').fill(mapping)
 const first=(await attempts())[0]
 expect(first.status).toBe('awaiting_review');expect(await requirements()).toHaveLength(0)
 await openWorkspaceTab(page,'需求清单');await openWorkspaceTab(page,'协议解析与澄清')
 await expect(page.getByLabel('来源文档正文')).toHaveValue(reviewed)
 await expect(page.getByLabel('来源文档编号')).toHaveValue('DOC-RESUME-001')
 await expect(page.getByLabel('显示编号映射')).toHaveValue(mapping)
 await page.reload();await openWorkspaceTab(page,'协议解析与澄清')
 await expect(page.getByLabel('来源文档正文')).toHaveValue(reviewed)
 await expect(page.getByLabel('来源文档版本')).toHaveValue('V2')
 await page.getByRole('button',{name:'继续核对',exact:true}).click()
 await expect(page.getByLabel('来源文档正文')).toHaveValue(reviewed)
 expect(extracts).toBe(1);expect(await attempts()).toHaveLength(1);expect(await requirements()).toHaveLength(0)
 await page.screenshot({path:`${evidence}/resume-restored.png`,fullPage:true})

 // A previous browser/version has only the server-side attempt, without a local draft.
 await expect(page.getByText(/核对草稿已保存在当前浏览器/)).toBeVisible()
 await page.evaluate(()=>new Promise<void>((resolve,reject)=>{const request=indexedDB.open('zhiyan-import-drafts-v1',1);request.onsuccess=()=>{const db=request.result,tx=db.transaction(['drafts','originals'],'readwrite');tx.objectStore('drafts').clear();tx.objectStore('originals').clear();tx.oncomplete=()=>{db.close();resolve()};tx.onabort=()=>reject(tx.error)}}))
 await page.reload();await openWorkspaceTab(page,'协议解析与澄清')
 await expect(page.getByLabel('来源文档正文')).toBeEnabled()
 await expect(page.getByLabel('来源文档正文')).toHaveValue('')
 await page.getByRole('button',{name:'继续核对',exact:true}).click()
 await expect(page.getByRole('button',{name:'选择原文件恢复核对'})).toBeVisible()
 await page.getByLabel('选择协议文件').setInputFiles({name:'01_综合技术协议_V1.docx',mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',buffer:await readFile('../演示导入文件/01_重型变速器技术协议_V1.docx')})
 await expect(page.getByRole('alert')).toContainText('不一致')
 expect(await attempts()).toHaveLength(1);expect(await requirements()).toHaveLength(0)
 await page.getByLabel('选择协议文件').setInputFiles(protocol)
 await expect(page.getByText(/文件文本已提取/)).toBeVisible()
 expect(extracts).toBe(1);expect((await attempts())[0].id).toBe(first.id)
 await page.getByLabel('来源文档编号').fill('DOC-RESUME-001')
 await page.getByText('高级选项：自定义显示编号（可选）',{exact:true}).click()
 await page.getByLabel('显示编号映射').fill(mapping)
 await page.getByRole('button',{name:'导入并解析',exact:true}).click()
 await expect(page.getByText(/^已解析 DOC-RESUME-001：/)).toBeVisible()
 const rows=await requirements();expect(rows).toHaveLength(19);expect(rows.every(row=>row.review_status==='draft')).toBe(true)
 const done=(await attempts())[0];expect(done.id).toBe(first.id);expect(done.status).toBe('completed')
 const original=await request.get(`/api/source-documents/${done.source_document_id}/original`)
 expect(createHash('sha256').update(await original.body()).digest('hex')).toBe(createHash('sha256').update(await readFile(protocol)).digest('hex'))
 await openWorkspaceTab(page,'需求清单');await openWorkspaceTab(page,'协议解析与澄清')
 const progress=page.getByRole('region',{name:'协议处理进度'})
 await expect(progress.getByText('结果已保存，需求仍需人工审核')).toBeVisible()
 await expect(progress.getByText(/最近任务：.*DOC-RESUME-001/)).toBeVisible()
 await expect(progress.locator('li.is-done')).toHaveCount(5)
 await page.reload();await openWorkspaceTab(page,'协议解析与澄清')
 await expect(page.getByLabel('来源文档正文')).toBeEnabled();await expect(page.getByLabel('来源文档正文')).toHaveValue('')
 await expect(progress.locator('li.is-done')).toHaveCount(5)
 await progress.screenshot({path:`${evidence}/progress-restored.png`,style:'.platform-masthead{visibility:hidden}'})
 await page.getByLabel('选择协议文件').setInputFiles(protocol)
 await expect(page.getByText(/文件文本已提取/)).toBeVisible()
 await expect(progress.locator('li[aria-current=step]')).toContainText('核对正文')
 await expect(progress.locator('li.is-done')).toHaveCount(2)
 await page.setViewportSize({width:390,height:844})
 const cancel=page.getByRole('button',{name:'取消待核对',exact:true})
 await expect(page.getByRole('button',{name:'继续核对',exact:true})).toBeVisible()
 await page.screenshot({path:`${evidence}/resume-mobile.png`,fullPage:true})
 await cancel.click();await expect(page.getByLabel('来源文档正文')).toHaveValue('')
 await page.reload();await openWorkspaceTab(page,'协议解析与澄清')
 await expect(page.getByLabel('来源文档正文')).toBeEnabled();await expect(page.getByLabel('来源文档正文')).toHaveValue('')
 await expect(progress.locator('li.is-done')).toHaveCount(0)
 await expect(progress.getByText(/该次核对已取消/)).toBeVisible()
 expect(await requirements()).toHaveLength(19);expect((await attempts()).filter(row=>row.status==='cancelled')).toHaveLength(1)
 expect(errors).toEqual([])
 } finally {
  const preview=await request.post('/api/system/restore-preview',{data:{backup:before}})
  expect(preview.status()).toBe(200)
  const checked=await preview.json()
  expect((await request.post('/api/system/restore',{data:{backup:before,expected_state_hash:checked.expected_state_hash,actor:'隔离测试',role:'恢复夹具'}})).status()).toBe(200)
 }
})

test('clearing a project removes its unarchived browser drafts as well as pending server records',async({page,request})=>{
 const before=await(await request.get('/api/system/backup')).json()
 try{
  await page.goto('/');await openWorkspaceTab(page,'协议解析与澄清')
  await expect(page.getByLabel('选择协议文件')).toBeEnabled()
  await page.getByLabel('选择协议文件').setInputFiles(protocol)
  await expect(page.getByText(/核对草稿已保存在当前浏览器/)).toBeVisible()
  await openWorkspaceTab(page,'系统设置')
  await page.getByRole('button',{name:'清空当前项目业务数据',exact:true}).click()
  const dialog=page.getByRole('dialog',{name:'清空当前项目业务数据'})
  await dialog.getByLabel('输入项目编号确认').fill('P01')
  await dialog.getByRole('button',{name:'备份并清空当前项目'}).click()
  await expect(page.getByText('当前项目已清空，清空前备份已保存')).toBeVisible()
  await page.getByRole('button',{name:'重新载入空白项目'}).click()
  await openWorkspaceTab(page,'协议解析与澄清')
  await expect(page.getByLabel('来源文档正文')).toBeEnabled()
  await expect(page.getByLabel('来源文档正文')).toHaveValue('')
  await expect(page.getByRole('button',{name:'继续核对',exact:true})).toHaveCount(0)
 }finally{
  const preview=await request.post('/api/system/restore-preview',{data:{backup:before}}),checked=await preview.json()
  expect((await request.post('/api/system/restore',{data:{backup:before,expected_state_hash:checked.expected_state_hash,actor:'隔离测试',role:'恢复夹具'}})).status()).toBe(200)
 }
})
