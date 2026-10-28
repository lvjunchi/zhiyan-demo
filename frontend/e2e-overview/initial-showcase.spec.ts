import { expect, test } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { readFile } from 'node:fs/promises'
import { openWorkspaceTab } from '../e2e-support/navigation'
const evidence = process.env.ZHIYAN_EVIDENCE_DIR ?? 'test-results/overview/screenshots'

test('opens a full initial scene then clears it and imports a new protocol without old results', async ({ page, request }, info) => {
  const output = info.outputPath('prepared-scene')
  execFileSync('python',['../scripts/prepare_initial_showcase.py','--output-dir',output],{env:{...process.env,PYTHONIOENCODING:'utf-8'}})
  const preset = JSON.parse(await readFile(`${output}/initial-backup.json`,'utf-8'))
  const before = await (await request.get('/api/system/backup')).json()
  async function restore(backup: unknown) {
    const preview = await request.post('/api/system/restore-preview',{data:{backup}})
    expect(preview.status()).toBe(200)
    const checked = await preview.json()
    const response = await request.post('/api/system/restore',{data:{backup,expected_state_hash:checked.expected_state_hash,actor:'隔离测试',role:'演示场景验证'}})
    expect(response.status()).toBe(200)
  }
  try {
    await restore(preset)
    await page.setViewportSize({width:1440,height:900})
    await page.goto('/')
    await expect(page.getByLabel('需求总量')).toContainText('13')
    await expect(page.getByRole('img',{name:'响应耗时：48、52、56 小时'})).toBeVisible()
    const risk = page.getByRole('region',{name:'协同风险依据'})
    await expect(risk).toContainText('接口交付协同')
    await expect(risk).toContainText('52h')
    await expect(risk).toContainText('最大进度落后 50 个百分点')
    await risk.getByRole('button',{name:'预警详情'}).click()
    const details = page.getByRole('dialog',{name:'协同预警详情'})
    await expect(details).toContainText('进度相差60个百分点')
    await expect(details.getByRole('table',{name:/参与方进度/})).toBeVisible()
    await details.getByRole('button',{name:'关闭预警详情'}).click()
    await page.screenshot({path:`${evidence}/initial-full-scene.png`,fullPage:true})
    await openWorkspaceTab(page,'系统设置')
    await page.getByRole('button',{name:'清空当前项目业务数据',exact:true}).click()
    const dialog = page.getByRole('dialog',{name:'清空当前项目业务数据'})
    await dialog.getByLabel('输入项目编号确认').fill('P01')
    await dialog.getByRole('button',{name:'备份并清空当前项目'}).click()
    await expect(page.getByText('当前项目已清空，清空前备份已保存')).toBeVisible()
    await page.getByRole('button',{name:'重新载入空白项目'}).click()
    await expect(page.getByRole('region',{name:'项目启动介绍'})).toBeVisible()
    await page.getByRole('button',{name:'开始导入技术协议'}).click()
    await page.getByLabel('选择协议文件').setInputFiles('../演示导入文件/综合演示/01_综合技术协议_V1.docx')
    await expect(page.getByText(/文件文本已提取/)).toBeVisible()
    await page.getByRole('button',{name:'导入并解析',exact:true}).click()
    await expect(page.getByRole('link',{name:'下载原件',exact:true})).toBeVisible()
    await openWorkspaceTab(page,'项目总览')
    await expect(page.getByLabel('需求总量')).toContainText('19')
    await expect(page.getByText('响应图需要配对沟通记录，协议导入不包含这些记录。')).toBeVisible()
    const project = (await (await request.get('/api/projects')).json())[0]
    const current = await (await request.get(`/api/projects/${project.id}/overview`)).json()
    expect(current.requirements).toMatchObject({total:19,confirmed:0,draft:19})
    expect(current.coordination).toMatchObject({topic_count:0,record_count:0})
    expect(current.design_review).toBeNull()
    expect(current.traceability).toBeNull()
    await page.reload()
    await expect(page.getByLabel('需求总量')).toContainText('19')
    await page.screenshot({path:`${evidence}/new-protocol-after-clear.png`,fullPage:true})
  } finally {
    await restore(before)
  }
})
