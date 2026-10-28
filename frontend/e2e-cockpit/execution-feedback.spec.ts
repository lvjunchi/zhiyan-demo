import { expect,test } from '@playwright/test'
import { openWorkspaceTab } from '../e2e-support/navigation'
import type { Requirement,TestPlanPayload,CoordinationTopic } from '../src/types'
const evidence=process.env.ZHIYAN_EVIDENCE_DIR??'test-results/screenshots'
const actor={actor:'本地隔离复演',role:'design_engineer'}

test('focuses execution entry, prefills the referenced load and saves only after explicit submission',async({page,request})=>{
 const backup=await(await request.get('/api/system/backup')).json()
 try{
  const project=(await(await request.get('/api/projects')).json())[0]
  const plan=await(await request.get(`/api/projects/${project.id}/test-plan`)).json() as TestPlanPayload
  const staticCase=plan.cases.find(row=>row.case_kind==='static_torsion')!
  expect(staticCase.review_status).toBe('confirmed')
  const requirements=await(await request.get(`/api/projects/${project.id}/requirements`)).json() as Requirement[]
  const load=requirements.find(row=>row.id===staticCase.load_basis_requirement_id)!.value_num
  let writes=0;page.on('request',req=>{if(req.method()==='POST'&&req.url().endsWith(`/test-cases/${staticCase.id}/runs`))writes++})
  await page.goto('/');await openWorkspaceTab(page,'试验验证与追溯')
  const row=page.getByRole('row').filter({has:page.getByRole('cell',{name:staticCase.display_code,exact:true})})
  const passBadge=row.locator('.run-result-badge--pass')
  await expect(passBadge).toContainText('已执行 · 通过')
  expect(await passBadge.evaluate(el=>getComputedStyle(el).color)).toBe('rgb(16, 123, 85)')
  await row.getByRole('button',{name:'记录执行',exact:true}).click()
  const form=page.getByRole('form',{name:`执行记录 ${staticCase.display_code}`})
  const runDialog=page.getByRole('dialog',{name:`记录执行：${staticCase.display_code}`,exact:true})
  await expect(runDialog).toBeVisible()
  await expect(form.getByLabel('执行工况',{exact:true})).toBeFocused()
  await expect(form.getByLabel('加载基准 N·m')).toHaveValue(String(load))
  await expect(form.getByLabel('后备系数')).toHaveValue('2.6')
  await expect(row.getByRole('button',{name:'记录执行',exact:true})).toHaveAttribute('aria-expanded','true')
  expect(writes).toBe(0)
  await form.screenshot({path:`${evidence}/execution-prefilled.png`})
  await page.setViewportSize({width:390,height:844})
  await form.getByLabel('后备系数').fill('2.4')
  await runDialog.getByRole('button',{name:'关闭执行记录',exact:true}).click()
  await expect(runDialog).toHaveCount(0)
  await expect(row.getByRole('button',{name:'记录执行',exact:true})).toBeFocused()
  await row.getByRole('button',{name:'记录执行',exact:true}).click()
  await expect(form.getByLabel('后备系数')).toHaveValue('2.4')
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await page.screenshot({path:`${evidence}/execution-entry-mobile.png`})
  await form.getByRole('button',{name:'提交执行记录',exact:true}).click()
  await expect(runDialog).toHaveCount(0)
  await expect(page.getByRole('status').filter({hasText:/第 .*次执行：未通过/})).toBeVisible()
  expect(writes).toBe(1)
  await expect(row.locator('.run-result-badge--fail')).toContainText('已执行 · 未通过')
  expect(await row.locator('.run-result-badge--fail').evaluate(el=>getComputedStyle(el).color)).toBe('rgb(179, 45, 72)')
  await row.screenshot({path:`${evidence}/execution-fail-badge.png`})
  const after=await(await request.get(`/api/projects/${project.id}/test-plan`)).json() as TestPlanPayload
  const saved=after.cases.find(row=>row.id===staticCase.id)!
  expect(saved.runs).toHaveLength(staticCase.runs.length+1)
  expect(saved.runs.at(-1)).toMatchObject({backup_coefficient:2.4,load_basis_numeric:load,result:'fail',case_revision:staticCase.revision})
 }finally{
  const current=await(await request.get('/api/system/backup')).json()
  const restored=await request.post('/api/system/restore',{data:{backup,expected_state_hash:current.sha256,...actor}})
  expect(restored.ok(),await restored.text()).toBe(true)
 }
})

test('prefills a demo conversation and links the reply to the actually saved edited root id',async({page,request})=>{
 const backup=await(await request.get('/api/system/backup')).json()
 try{
  const project=(await(await request.get('/api/projects')).json())[0]
  const created=await request.post(`/api/projects/${project.id}/coordination-topics`,{data:{name:'合成设计冻结交付协同',expected_participants:['A 主机方','B 研发方'],window_start:'2026-10-19T16:00:00Z',window_end:'2026-10-23T16:00:00Z'}})
  expect(created.ok(),await created.text()).toBe(true)
  const topic=await created.json() as CoordinationTopic
  await page.goto('/');await openWorkspaceTab(page,'协同风险')
  const article=page.getByRole('article',{name:`协同议题 ${topic.display_code}`,exact:true})
  const actions=article.getByRole('group',{name:'议题沟通操作'})
  const progress=article.getByRole('region',{name:'参与方计划与实际进度'})
  const progressButton=progress.getByRole('button',{name:'登记参与方进度',exact:true})
  await expect(progressButton).toBeEnabled()
  expect((await actions.boundingBox())!.y).toBeLessThan((await progress.boundingBox())!.y)
  expect(await progressButton.evaluate(el=>getComputedStyle(el).backgroundColor)).toBe('rgb(35, 102, 178)')
  await article.screenshot({path:`${evidence}/coordination-top-actions.png`})
  await page.setViewportSize({width:390,height:844})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await actions.getByRole('button',{name:'导入沟通记录',exact:true}).scrollIntoViewIfNeeded()
  await page.screenshot({path:`${evidence}/coordination-top-actions-mobile.png`})
  await page.setViewportSize({width:1440,height:900})
  await article.getByRole('button',{name:'导入沟通记录',exact:true}).click()
  const dialog=page.getByRole('dialog',{name:`议题沟通记录 · ${topic.display_code}`,exact:true})
  await expect(dialog.getByLabel('协同记录外部编号')).toHaveValue('DEMO-MSG-01')
  await expect(dialog.getByLabel('协同记录响应对象')).toHaveValue('')
  await expect(dialog.getByText('发起消息无需填写响应编号；回复时关联已保存的原消息。')).toBeVisible()
  await dialog.getByLabel('协同记录外部编号').fill('CUSTOM-ROOT-01')
  await dialog.getByRole('button',{name:'导入记录',exact:true}).click()
  await expect(dialog.getByLabel('协同记录外部编号')).toHaveValue('DEMO-MSG-02')
  await expect(dialog.getByLabel('协同记录响应对象')).toHaveValue('CUSTOM-ROOT-01')
  await dialog.screenshot({path:`${evidence}/communication-auto-reply.png`})
  await dialog.getByRole('button',{name:'导入记录',exact:true}).click()
  await expect(dialog.getByText('响应记录：CUSTOM-ROOT-01',{exact:true})).toBeVisible()
  await dialog.getByRole('button',{name:'关闭沟通详情'}).click()
  await article.getByRole('button',{name:'重算指标',exact:true}).click()
  await expect(article.getByText(/平均响应时延：2 小时/)).toBeVisible()
 }finally{
  const current=await(await request.get('/api/system/backup')).json()
  const restored=await request.post('/api/system/restore',{data:{backup,expected_state_hash:current.sha256,...actor}})
  expect(restored.ok(),await restored.text()).toBe(true)
 }
})
