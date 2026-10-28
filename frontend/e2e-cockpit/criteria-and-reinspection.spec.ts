import {test,expect} from '@playwright/test'
import {openWorkspaceTab} from '../e2e-support/navigation'
const evidence=process.env.ZHIYAN_EVIDENCE_DIR??'test-results/screenshots'
test('trial criteria and sample reinspection create reviewable new versions in dialogs',async({page,request})=>{
 const backup=await(await request.get('/api/system/backup')).json()
 try{
 const project=(await(await request.get('/api/projects')).json())[0]
 const plan=await(await request.get(`/api/projects/${project.id}/test-plan`)).json()
 const durability=plan.cases.find((row:{display_code:string})=>row.display_code==='TC-004')
 await page.goto('/');await openWorkspaceTab(page,'试验验证与追溯')
 await page.getByRole('button',{name:'修订用例 TC-004',exact:true}).click()
 const editor=page.getByRole('dialog',{name:'修订试验用例'})
 await editor.getByLabel('用例通过判据').fill('合成补充规程：等效台架1200h无失效')
 await editor.getByLabel('用例修订依据').fill('CN-UI07 合成澄清记录')
 await page.screenshot({path:`${evidence}/case-criteria-dialog.png`})
 await editor.getByRole('button',{name:'保存用例修订'}).click()
 await expect(editor).toHaveCount(0)
 const updated=await(await request.get(`/api/projects/${project.id}/test-plan`)).json()
 const current=updated.cases.find((row:{id:string})=>row.id===durability.id)
 expect(current.revision).toBe(durability.revision+1);expect(current.review_status).toBe('draft')
 expect(current.runs.map((row:{id:string})=>row.id)).toEqual(durability.runs.map((row:{id:string})=>row.id))
 await openWorkspaceTab(page,'样件检验')
 const deliveries=await(await request.get(`/api/projects/${project.id}/sample-deliveries`)).json()
 const before=await(await request.get(`/api/sample-deliveries/${deliveries[0].id}/comparison`)).json()
 await page.getByRole('button',{name:'查看 / 比对',exact:true}).first().click()
 const sample=page.getByRole('dialog',{name:`样件明细：${deliveries[0].display_code}`})
 await sample.getByRole('button',{name:'记录复检',exact:true}).click()
 await sample.getByLabel('实测 孔位',{exact:true}).fill('120.3')
 await sample.getByLabel('实测 轴径',{exact:true}).fill('45.01')
 await sample.getByLabel('比对证据').fill('DEMO-UI07 新合成测量记录')
 await sample.getByRole('button',{name:'提交比对',exact:true}).click()
 await expect(sample.getByRole('table',{name:'样件比对结果'})).toBeVisible()
 const after=await(await request.get(`/api/sample-deliveries/${deliveries[0].id}/comparison`)).json()
 expect(after.comparison.revision).toBe(before.comparison.revision+1)
 expect(after.comparison.status).toBe('draft')
 await page.setViewportSize({width:390,height:844})
 expect(await sample.evaluate(el=>el.scrollWidth<=el.clientWidth)).toBe(true)
 await page.screenshot({path:`${evidence}/sample-reinspection-mobile.png`})
 }finally{
 const current=await(await request.get('/api/system/backup')).json()
 const restore=await request.post('/api/system/restore',{data:{backup,expected_state_hash:current.sha256,actor:'本地测试工程师',role:'design_engineer'}})
 expect(restore.ok(),await restore.text()).toBe(true)
 }
})
