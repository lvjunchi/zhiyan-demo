import { openWorkspaceTab } from '../e2e-support/navigation'
import { expect, test } from '@playwright/test'

const evidence = '../docs/test-evidence/2026-10-21/UI-N'

test('business evidence retains real versions and Chinese results across modules', async ({ page, request }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/')
  await openWorkspaceTab(page, '型谱选型与变型')
  const result = page.waitForResponse(response => response.url().endsWith('/recommend-bases') && response.request().method() === 'POST')
  await page.getByRole('button', { name: '计算 Top-3', exact: true }).click()
  const data = await (await result).json() as { requirement_versions: { display_code: string; revision: number }[] }
  const versions = page.getByRole('group', { name: '选型输入依据', exact: true })
  await versions.locator('summary').click()
  await expect(versions.getByRole('row')).toHaveCount(data.requirement_versions.length + 1)
  for (const row of data.requirement_versions) {
    await expect(versions.getByRole('row').filter({ has: page.getByText(row.display_code, { exact: true }) })).toContainText(`V${row.revision}`)
  }
  await expect(versions).not.toContainText('"requirement_id"')
  await page.screenshot({ path: `${evidence}/business-versions.png`, fullPage: true })
  await page.getByRole('button', { name: '关闭推荐结果', exact: true }).click()
  await openWorkspaceTab(page, '设计成果')
  await page.getByRole('button', { name: '预览设计评审', exact: true }).click()
  await expect(page.getByRole('dialog').getByText(/规则计算/)).toBeVisible()
  await page.getByRole('button', { name: '关闭预览', exact: true }).click()
  await openWorkspaceTab(page, '试验验证与追溯')
  const execution = page.getByRole('region', { name: '执行结果汇总' })
  await expect(execution).toBeVisible()
  await expect(execution).not.toContainText(/not_run|pass|fail|incomplete|invalid/)

  const project = (await (await request.get('/api/projects')).json() as { id: string; display_code: string }[]).find(p => p.display_code === 'P01')!
  const requirements = await (await request.get(`/api/projects/${project.id}/requirements`)).json() as { id: string; parser_key: string; current_revision: number; value_text: string }[]
  const engine = requirements.find(r => r.parser_key === 'engineMaxTorque')!
  expect((await request.patch(`/api/requirements/${engine.id}`, { data: { expected_revision: engine.current_revision, value_text: engine.value_text === '2800' ? '2600' : '2800' } })).ok()).toBe(true)
  await openWorkspaceTab(page, '一致性检测')
  await page.getByRole('button', { name: '运行一致性检查', exact: true }).click()
  await expect(page.getByText(/一致性检查 CR-.*完成/)).toBeVisible()
  const proof = page.getByRole('group', { name: '检查依据', exact: true }).first()
  await proof.locator('summary').click()
  await expect(proof.locator('dl')).toBeVisible()
  await expect(proof).not.toContainText('[object Object]')
  await expect(proof).not.toContainText('{"')
  for (const size of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(size)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: `${evidence}/business-conflicts-${size.width}.png`, fullPage: true })
  }
  expect(errors).toEqual([])
})

test('an unavailable backend offers startup guidance and recovers with retry', async ({ page }) => {
  await page.route('**/api/projects', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'PERSISTENCE_UNAVAILABLE', message: '本地服务暂不可用' } }) }))
  await page.goto('/')
  await expect(page.getByText(/Start-Demo.cmd/)).toBeVisible()
  await expect(page.getByRole('tab')).toHaveCount(0)
  await page.screenshot({ path: `${evidence}/startup-unavailable.png`, fullPage: true })
  await page.unroute('**/api/projects')
  await page.getByRole('button', { name: '重试连接', exact: true }).click()
  await expect(page.getByRole('heading', { name: '项目总览', exact: true })).toBeVisible()
  await expect(page.getByRole('tab', { name: '需求清单', exact: true })).toBeVisible()
})
