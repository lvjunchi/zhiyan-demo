import { openWorkspaceTab } from '../e2e-support/navigation'
import { expect, test } from '@playwright/test'

const base = '/api'
const evidence = process.env.ZHIYAN_EVIDENCE_DIR ?? 'test-results/screenshots'

test('backup download, validation and restore use real retained database copies', async ({ page, request }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '法士特—陕汽定制项目试点' })).toBeVisible()
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '备份 JSON', exact: true }).click()
  const download = await downloadPromise
  const path = `${evidence}/browser-backup.json`
  await download.saveAs(path)
  const original = await (await request.get(`${base}/projects`)).json() as { id: string; display_code: string }[]
  const addition = await request.post(`${base}/projects`, { data: { display_code: 'BACKUPCHECK', name: '备份恢复测试项目', customer: '合成客户', product: '合成设备' } })
  expect(addition.status()).toBe(201)
  await page.getByRole('button', { name: '恢复备份', exact: true }).click()
  await page.getByLabel('选择备份文件').setInputFiles(path)
  await expect(page.getByText('校验通过，尚未恢复')).toBeVisible()
  expect((await (await request.get(`${base}/projects`)).json()).length).toBe(original.length + 1)
  await expect(page.getByRole('button', { name: '确认恢复并切换数据' })).toBeDisabled()
  await page.getByLabel('我已核对备份，确认切换当前工作数据；原库保留。').check()
  await page.getByRole('button', { name: '确认恢复并切换数据' }).click()
  await expect(page.getByRole('status').filter({ hasText: '恢复成功' })).toBeVisible()
  expect((await (await request.get(`${base}/projects`)).json()).map((item: { id: string }) => item.id)).toEqual(original.map(item => item.id))
  await page.screenshot({ path: `${evidence}/restore-success.png`, fullPage: true })
  await page.getByRole('button', { name: '重新载入工作台' }).click()
  await expect(page.getByRole('heading', { name: '法士特—陕汽定制项目试点' })).toBeVisible()
  await expect(page.getByText('离线浏览器存储')).toHaveCount(0)
})

test('network and persistence faults are visible and never turn into saved changes', async ({ page, request }) => {
  await page.route('**/api/projects/*/overview', route => route.abort('connectionfailed'))
  await page.goto('/')
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page.getByRole('region', { name: '项目实时指标' })).toHaveCount(0)
  await page.unroute('**/api/projects/*/overview')
  await page.getByRole('button', { name: '重新加载' }).click()
  await expect(page.getByRole('heading', { name: '法士特—陕汽定制项目试点' })).toBeVisible()
  const projects = await (await request.get(`${base}/projects`)).json() as { id: string; display_code: string }[]
  const project = projects.find(item => item.display_code === 'P01')!
  const requirements = await (await request.get(`${base}/projects/${project.id}/requirements`)).json() as { id: string; parser_key: string; display_code: string; value_text: string }[]
  const engine = requirements.find(item => item.parser_key === 'engineMaxTorque')!
  const before = await (await request.get(`${base}/system/backup`)).json()
  await openWorkspaceTab(page, '需求清单')
  await page.getByRole('button', { name: /^全部需求 \d+ 条$/ }).click()
  await page.getByRole('button', {name: `修订 ${engine.display_code}`, exact:true}).click()
  await page.getByLabel('选择要修订的需求').selectOption(engine.id)
  await page.getByLabel('修订后的数值').fill('2800')
  await page.route(`**/api/requirements/${engine.id}`, async route => {
    if (route.request().method() === 'PATCH') await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'PERSISTENCE_UNAVAILABLE', message: '故障注入：存储不可用，未保存' } }) })
    else await route.continue()
  })
  await page.getByRole('button', { name: '提交修订', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('存储不可用，未保存')
  await expect(page.getByRole('row').filter({ has: page.getByRole('cell', { name: 'REQ-P01-B-003', exact: true }) })).toContainText(engine.value_text)
  const after = await (await request.get(`${base}/system/backup`)).json()
  expect(after.sha256).toBe(before.sha256)
  await page.screenshot({ path: `${evidence}/fault-save-visible.png`, fullPage: true })
})
