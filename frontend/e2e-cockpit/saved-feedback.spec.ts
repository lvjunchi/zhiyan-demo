import { openWorkspaceTab } from '../e2e-support/navigation'
import { expect, test } from '@playwright/test'

const evidence = process.env.ZHIYAN_EVIDENCE_DIR ?? 'test-results/screenshots'

test('saved review survives readback failure and saving a score preserves other drafts', async ({ page, request }) => {
  const backupResponse = await request.get('/api/system/backup')
  expect(backupResponse.ok()).toBe(true)
  const backup = await backupResponse.json()
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  try {
    const projects = await (await request.get('/api/projects')).json() as { id: string; display_code: string }[]
    const project = projects.find(item => item.display_code === 'P01')!
    const created = await request.post(`/api/projects/${project.id}/design-review`, { data: { base_display_code: 'JX-12A' } })
    expect(created.ok(), await created.text()).toBe(true)
    const review = await created.json() as { review: { id: string } }
    const dfmea = await request.post(`/api/projects/${project.id}/dfmea`, { data: { base_display_code: 'JX-12A' } })
    expect(dfmea.ok(), await dfmea.text()).toBe(true)
    const items = (await dfmea.json()).items as { id: string; display_code: string }[]
    expect(items.length).toBeGreaterThanOrEqual(2)
    let committed = false, failedRead = false, confirmations = 0
    await page.route(`**/api/design-reviews/${review.review.id}/confirmations`, async route => {
      if (route.request().method() === 'POST') {
        confirmations++
        const response = await route.fetch()
        expect(response.ok()).toBe(true)
        committed = true
        await route.fulfill({ response })
      } else await route.continue()
    })
    await page.route(`**/api/projects/${project.id}/design-review`, async route => {
      if (route.request().method() === 'GET' && committed && !failedRead) {
        failedRead = true
        await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'TEST_READBACK', message: '已保存后的读取故障（隔离验收）' } }) })
      } else await route.continue()
    })
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')
    await openWorkspaceTab(page, '设计成果')
    await page.getByRole('button', { name: '确认设计评审', exact: true }).click()
    const warning = page.getByRole('alert').filter({ hasText: '设计评审审核已保存，但页面刷新失败' })
    await expect(warning).toBeVisible()
    await expect(page.getByRole('button', { name: '确认设计评审', exact: true })).toBeDisabled()
    await page.screenshot({ path: `${evidence}/saved-review-readback-failure.png`, fullPage: true })
    await warning.getByRole('button', { name: '重新读取已保存结果', exact: true }).click()
    await expect(warning).toHaveCount(0)
    await expect(page.getByRole('button', { name: '确认设计评审', exact: true })).toHaveCount(0)
    expect(confirmations).toBe(1)
    const persisted = await (await request.get(`/api/projects/${project.id}/design-review`)).json()
    expect(persisted.review.status).toBe('confirmed')
    const [first, second] = items
    for (const [item, severity] of [[first, '8'], [second, '9']] as const) {
      await page.getByLabel(`${item.display_code} severity`, { exact: true }).fill(severity)
      await page.getByLabel(`${item.display_code} occurrence`, { exact: true }).fill('4')
      await page.getByLabel(`${item.display_code} detection`, { exact: true }).fill('3')
    }
    const firstRow = page.getByRole('row').filter({ has: page.getByRole('cell', { name: first.display_code, exact: true }) })
    await expect(firstRow.getByRole('button', { name: '确认评分', exact: true })).toBeDisabled()
    await expect(page.getByRole('button', { name: '确认 DFMEA', exact: true })).toBeDisabled()
    await firstRow.getByRole('button', { name: '保存评分', exact: true }).click()
    await expect(page.getByRole('status').filter({ hasText: `${first.display_code} 评分已保存` })).toBeVisible()
    await expect(page.getByLabel(`${second.display_code} severity`, { exact: true })).toHaveValue('9')
    const secondRow = page.getByRole('row').filter({ has: page.getByRole('cell', { name: second.display_code, exact: true }) })
    await expect(secondRow.getByRole('button', { name: '确认评分', exact: true })).toBeDisabled()
    await expect(secondRow.getByText('评分有未保存修改，请先保存评分。', { exact: true })).toBeVisible()
    await page.screenshot({ path: `${evidence}/fmea-unsaved-score-desktop.png`, fullPage: true })
    await page.setViewportSize({ width: 390, height: 844 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: `${evidence}/fmea-unsaved-score-mobile.png`, fullPage: true })
    for (const base of ['JX-12A', 'JX-12B']) {
      const analyzed = await request.post(`/api/projects/${project.id}/variant-analysis`, { data: { base_display_code: base } })
      expect(analyzed.ok(), await analyzed.text()).toBe(true)
    }
    await page.setViewportSize({ width: 1440, height: 900 })
    await openWorkspaceTab(page, '型谱选型与变型')
    const engineering = page.locator('.engineering-records')
    await engineering.getByLabel('工程决策基型筛选').selectOption('JX-12A')
    await expect(engineering.getByRole('cell', { name: 'JX-12B', exact: true })).toHaveCount(0)
    await expect(engineering.getByRole('cell', { name: 'JX-12A', exact: true }).first()).toBeVisible()
    await page.screenshot({ path: `${evidence}/engineering-base-filter.png`, fullPage: true })
    const trigger = engineering.getByRole('button', { name: '查看 V-01 版本', exact: true })
    await trigger.click()
    const detail = page.getByRole('dialog', { name: 'V-01 版本与审核', exact: true })
    await detail.getByLabel('工程决策审核意见').fill('已核对JX-12A当前依据，合成验收')
    await detail.getByRole('button', { name: '确认当前版本', exact: true }).click()
    await expect(detail).toHaveCount(0)
    await expect(trigger).toBeEnabled()
    await trigger.click()
    await expect(detail.getByText('该版本已完成审核，调整内容后请重新生成并审核新版本。', { exact: true })).toBeVisible()
    await expect(detail.getByRole('button', { name: '驳回当前版本', exact: true })).toHaveCount(0)
    await page.screenshot({ path: `${evidence}/engineering-reviewed-readonly.png` })
    await page.keyboard.press('Escape')
    await expect(trigger).toBeFocused()
    expect(errors).toEqual([])
  } finally {
    const current = await (await request.get('/api/system/backup')).json()
    const restored = await request.post('/api/system/restore', { data: { backup, expected_state_hash: current.sha256, actor: '本地测试工程师', role: 'design_engineer' } })
    expect(restored.ok(), await restored.text()).toBe(true)
  }
})
