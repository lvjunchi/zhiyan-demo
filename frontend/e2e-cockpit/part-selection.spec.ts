import { expect,test } from '@playwright/test'
import { openWorkspaceTab } from '../e2e-support/navigation'
const evidence=process.env.ZHIYAN_EVIDENCE_DIR??'test-results/screenshots'
test('compares part candidates, saves and confirms a choice that appears in engineering versions',async({page,request})=>{
 const backup=await(await request.get('/api/system/backup')).json()
 try{
 const project=(await(await request.get('/api/projects')).json())[0]
 const analysis=await request.post(`/api/projects/${project.id}/variant-analysis`,{data:{base_display_code:'JX-12A'}})
 expect(analysis.ok(),await analysis.text()).toBe(true)
 const records=await(await request.get(`/api/projects/${project.id}/engineering-records`)).json() as {id:string;kind:string;review_status:string;revision:number}[]
 for(const row of records.filter(row=>row.kind==='variant'&&row.review_status!=='confirmed')){
  const confirm=await request.post(`/api/engineering-records/variant/${row.id}/confirmations`,{data:{expected_revision:row.revision,actor:'本地测试工程师',role:'design_engineer',decision:'confirmed',comment:'选型验收先核对变型输入'}})
  expect(confirm.ok(),await confirm.text()).toBe(true)
 }
 await page.goto('/');await openWorkspaceTab(page,'型谱选型与变型')
 const section=page.getByRole('region',{name:'零件型号选择'})
 await expect(section.getByRole('group',{name:'零件选择状态统计'})).toBeVisible()
 await section.getByRole('button',{name:'选择型号 P-03',exact:true}).click()
 const dialog=page.getByRole('dialog',{name:'零件候选比选'})
 await expect(dialog.getByRole('button',{name:'选用 DEMO-P01-1',exact:true})).toBeDisabled()
 await dialog.getByRole('button',{name:'选用 DEMO-P01-3',exact:true}).click()
 await expect(dialog.getByText('型号已保存，需独立审核当前版本',{exact:true})).toBeVisible()
 await dialog.getByLabel('零件选型审核意见').fill('合成验收：登记包络与接口要求已核对')
 await dialog.getByRole('button',{name:'确认选定型号',exact:true}).click()
 await expect(dialog).toHaveCount(0)
 await expect(page.getByText('选型审核已保存',{exact:true})).toBeVisible()
 await page.screenshot({path:`${evidence}/part-candidate-compare.png`,fullPage:true})
 await page.keyboard.press('Escape')
 await page.reload();await openWorkspaceTab(page,'型谱选型与变型')
 await expect(section).toContainText('DEMO-P01-3')
 await page.getByRole('button',{name:'查看 P-03 版本',exact:true}).click()
 const versions=page.getByRole('dialog',{name:'P-03 版本与审核'})
 await expect(versions).toContainText('DEMO-P01-3')
 await expect(versions).toContainText('合成验收：登记包络与接口要求已核对')
 await page.keyboard.press('Escape')
 await page.setViewportSize({width:390,height:844})
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
 await section.getByRole('button',{name:'选择型号 P-03',exact:true}).click()
 expect(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth)).toBe(true)
 await page.screenshot({path:`${evidence}/part-candidates-mobile.png`,fullPage:true})
 }finally{
 const current=await(await request.get('/api/system/backup')).json()
 const restore=await request.post('/api/system/restore',{data:{backup,expected_state_hash:current.sha256,actor:'本地测试工程师',role:'design_engineer'}})
 expect(restore.ok(),await restore.text()).toBe(true)
 }
})
