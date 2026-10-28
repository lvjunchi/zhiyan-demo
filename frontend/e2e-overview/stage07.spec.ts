import {expect,test} from '@playwright/test'
import {openWorkspaceTab} from '../e2e-support/navigation'
const evidence=process.env.ZHIYAN_EVIDENCE_DIR??'test-results/overview/screenshots'
test('comprehensive Word and PDF imports produce the same nineteen draft requirements',async({page,request})=>{
 const project=(await(await request.get('/api/projects')).json())[0]
 let expected:unknown[]=[]
 for(const ext of ['docx','pdf']){
  const checked=await(await request.post(`/api/projects/${project.id}/clear-preview`)).json()
  const cleared=await request.post(`/api/projects/${project.id}/clear`,{data:{expected_state_hash:checked.expected_state_hash,confirmation_code:project.display_code,actor:'本地测试工程师',role:'design_engineer'}})
  expect(cleared.ok(),await cleared.text()).toBe(true)
  await page.goto('/');await openWorkspaceTab(page,'协议解析与澄清')
  await page.getByLabel('选择协议文件').setInputFiles(`../演示导入文件/综合演示/01_综合技术协议_V1.${ext}`)
  await expect(page.getByRole('region',{name:'协议处理进度'})).toContainText('文本已就绪')
  await page.getByRole('button',{name:'导入并解析',exact:true}).click()
  await expect(page.getByRole('region',{name:'协议处理进度'})).toContainText('结果已保存')
  const rows=await(await request.get(`/api/projects/${project.id}/requirements`)).json() as {id:string;parser_key:string;value_text:string;unit:string;category:string;review_status:string}[]
  expect(rows).toHaveLength(19);expect(new Set(rows.map(row=>row.category)).size).toBe(9)
  expect(rows.every(row=>row.review_status==='draft')).toBe(true)
  const values=rows.map(row=>[row.parser_key,row.value_text.replace(/\s/g,''),row.unit.replace(/\s/g,'')]).sort((a,b)=>String(a).localeCompare(String(b)))
  if(ext==='docx')expected=values;else expect(values).toEqual(expected)
  await page.screenshot({path:`${evidence}/comprehensive-${ext}-import.png`,fullPage:true})
 }
})
