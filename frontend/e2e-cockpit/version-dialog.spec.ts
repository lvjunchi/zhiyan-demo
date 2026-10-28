import { openWorkspaceTab } from '../e2e-support/navigation'
import { expect, test } from '@playwright/test'

const evidence = process.env.ZHIYAN_EVIDENCE_DIR ?? 'test-results/screenshots'

test('version review uses a native modal, restores focus and fits desktop and mobile', async ({ page, request }) => {
  const backup = await (await request.get('/api/system/backup')).json()
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  try {
    const projects = await (await request.get('/api/projects')).json() as { id: string; display_code: string }[]
    const project = projects.find(item => item.display_code === 'P01')!
    for (let index = 0; index < 2; index++) {
      const analysis = await request.post(`/api/projects/${project.id}/variant-analysis`, { data: { base_display_code: 'JX-12A' } })
      expect(analysis.ok(), await analysis.text()).toBe(true)
    }
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')
    await openWorkspaceTab(page, '型谱选型与变型')
    const trigger = page.getByRole('button', { name: '查看 V-01 版本', exact: true })
    await trigger.scrollIntoViewIfNeeded()
    const scroll = await page.evaluate(() => scrollY)
    await trigger.click()
    const dialog = page.getByRole('dialog', { name: 'V-01 版本与审核', exact: true })
    await expect(dialog).toBeVisible()
    await expect(dialog.getByText(/历史版本/).first()).toBeVisible()
    await expect(dialog.getByText(/当前版本/, { exact: false }).first()).toBeVisible()
    expect(await dialog.evaluate(element => element.matches(':modal'))).toBe(true)
    expect(await page.locator('.engineering-records .result-box').count()).toBe(0)
    await expect(dialog.getByRole('button', { name: '关闭版本详情' })).toBeFocused()
    await page.keyboard.press('Shift+Tab')
    expect(await dialog.evaluate(element => element.contains(document.activeElement))).toBe(true)
    await page.screenshot({ path: `${evidence}/version-dialog-desktop.png` })
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
    await expect(trigger).toBeFocused()
    expect(await page.evaluate(() => scrollY)).toBe(scroll)

    await page.setViewportSize({ width: 390, height: 844 })
    await trigger.click()
    await expect(dialog).toBeVisible()
    const bounds = await dialog.boundingBox()
    expect(bounds!.x).toBeGreaterThanOrEqual(0)
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(390)
    expect(bounds!.y).toBeGreaterThanOrEqual(0)
    expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(844)
    expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
    await dialog.getByLabel('工程决策审核意见').fill('关闭测试，不提交审核')
    await page.screenshot({ path: `${evidence}/version-dialog-mobile.png` })
    await dialog.getByRole('button', { name: '关闭版本详情' }).click()
    await expect(dialog).toHaveCount(0)
    await expect(trigger).toBeFocused()
    expect(errors).toEqual([])
  } finally {
    const current = await (await request.get('/api/system/backup')).json()
    const restored = await request.post('/api/system/restore', { data: { backup, expected_state_hash: current.sha256, actor: '本地测试工程师', role: 'design_engineer' } })
    expect(restored.ok(), await restored.text()).toBe(true)
  }
})
