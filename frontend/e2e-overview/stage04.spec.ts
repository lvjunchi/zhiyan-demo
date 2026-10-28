import { expect, test } from '@playwright/test'
import { openWorkspaceTab } from '../e2e-support/navigation'
const evidence = process.env.ZHIYAN_EVIDENCE_DIR ?? 'test-results/overview/screenshots'

test('batch preview retains exact scope, audits and a dialog revision', async ({ page, request }) => {
  const original = await (await request.get('/api/system/backup')).json()
  const identity={actor:'隔离批量界面验收',role:'design_engineer'}
  try {
  await page.goto('/')
  const project = (await (await request.get('/api/projects')).json())[0]
  const post=async(url:string,data:unknown={})=>{const response=await request.post(url,{data});expect(response.ok(),await response.text()).toBe(true);return response.json()}
  const clear=await post(`/api/projects/${project.id}/clear-preview`)
  await post(`/api/projects/${project.id}/clear`,{...identity,confirmation_code:project.display_code,expected_state_hash:clear.expected_state_hash})
  const source=await post(`/api/projects/${project.id}/source-documents`,{display_code:'DOC-BATCH-UI09',doc_type:'protocol',version:'V1',mode:'manual',content:'发动机最大扭矩2600 N·m。变速器12档。'})
  await post(`/api/source-documents/${source.id}/parse`)
  const rows = await (await request.get(`/api/projects/${project.id}/requirements`)).json() as {id:string;display_code:string;parser_key:string;current_revision:number}[]
  const selected = rows.filter(row => ['engineMaxTorque','gearCount'].includes(row.parser_key))
  expect(selected).toHaveLength(2)
  const before = await (await request.get('/api/system/backup')).json()
  await openWorkspaceTab(page, '需求清单')
  for (const row of selected) await page.getByLabel(`选择 ${row.display_code}`, {exact:true}).check()
  const trigger = page.getByRole('button', {name:'预览一键确认范围'})
  await trigger.click()
  let dialog = page.getByRole('dialog', {name:'批量确认需求'})
  await expect(dialog.getByText('可确认', {exact:true})).toHaveCount(2)
  await expect(dialog.getByRole('button', {name:'确认本批次需求'})).toBeDisabled()
  expect((await (await request.get('/api/system/backup')).json()).sha256).toBe(before.sha256)
  await dialog.getByRole('button', {name:'取消批量确认'}).click()
  await expect(trigger).toBeFocused()
  await trigger.click()
  dialog = page.getByRole('dialog', {name:'批量确认需求'})
  await dialog.getByLabel('我已逐条核对本批次需求').check()
  const confirm=dialog.getByRole('button',{name:'确认本批次需求',exact:true})
  const cancel=dialog.getByRole('button',{name:'取消批量确认',exact:true})
  expect((await confirm.boundingBox())!.x).toBeLessThan((await cancel.boundingBox())!.x)
  expect(await confirm.evaluate(el=>getComputedStyle(el).backgroundColor)).toBe('rgb(35, 102, 178)')
  expect(await cancel.evaluate(el=>getComputedStyle(el).backgroundColor)).toBe('rgb(244, 248, 253)')
  await page.setViewportSize({width:390,height:844})
  expect(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth)).toBe(true)
  expect((await confirm.boundingBox())!.x).toBeLessThan((await cancel.boundingBox())!.x)
  await dialog.screenshot({path:`${evidence}/batch-actions-mobile.png`})
  await page.setViewportSize({width:1440,height:900})
  await page.screenshot({path:`${evidence}/batch-preview.png`, fullPage:true})
  await dialog.getByRole('button', {name:'确认本批次需求'}).click()
  await expect(dialog).toHaveCount(0)
  await expect(page.getByRole('status').filter({hasText:'已批量确认 2 条'})).toBeVisible()
  for (const row of selected) {
    const events = await (await request.get(`/api/requirements/${row.id}/confirmations`)).json()
    expect(events).toHaveLength(1)
    expect(events[0]).toMatchObject({object_id:row.id,object_revision:row.current_revision,decision:'confirmed'})
  }
  await page.getByRole('button', {name:'按已确认筛选'}).click()
  await expect(page.locator('.requirement-sheet tbody tr')).toHaveCount(2)
  const engine = selected.find(row => row.parser_key==='engineMaxTorque')!
  await page.getByRole('button', {name:`修订 ${engine.display_code}`, exact:true}).click()
  const revision = page.getByRole('dialog', {name:'修订需求', exact:true})
  await revision.getByLabel('修订后的数值').fill('2800')
  await revision.getByRole('button', {name:'提交修订'}).click()
  await expect(revision).toHaveCount(0)
  expect(await (await request.get(`/api/requirements/${engine.id}`)).json()).toMatchObject({current_revision:engine.current_revision+1,review_status:'draft',value_text:'2800'})
  await page.getByLabel('定位需求编号').fill(engine.display_code)
  await page.getByRole('button', {name:'定位需求', exact:true}).click()
  await expect(page.locator(`tr[data-object-id="${engine.id}"]`)).toHaveAttribute('data-located','true')
  await page.screenshot({path:`${evidence}/requirements-sheet.png`, fullPage:true})
  await page.setViewportSize({width:390,height:844})
  expect(await page.evaluate(() => document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await page.getByRole('button', {name:`修订 ${engine.display_code}`, exact:true}).click()
  const mobile = page.getByRole('dialog', {name:'修订需求', exact:true})
  await expect(mobile).toBeVisible()
  expect(await mobile.evaluate(el => el.scrollWidth<=el.clientWidth)).toBe(true)
  await page.screenshot({path:`${evidence}/requirements-revision-mobile.png`, fullPage:true})
  }finally{
    const current=await(await request.get('/api/system/backup')).json()
    const restored=await request.post('/api/system/restore',{data:{backup:original,expected_state_hash:current.sha256,...identity}})
    expect(restored.ok(),await restored.text()).toBe(true)
  }
})
