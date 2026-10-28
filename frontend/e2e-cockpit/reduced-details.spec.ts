import { openWorkspaceTab } from '../e2e-support/navigation'
import { expect, test, type APIRequestContext } from '@playwright/test'

const evidence = process.env.ZHIYAN_EVIDENCE_DIR ?? 'test-results/screenshots'
async function restore(request: APIRequestContext, backup: unknown) {
  const current = await (await request.get('/api/system/backup')).json()
  const response = await request.post('/api/system/restore', { data: { backup, expected_state_hash: current.sha256, actor: '本地测试工程师', role: 'design_engineer' } })
  expect(response.ok(), await response.text()).toBe(true)
}

test('review workspace keeps summary and actions while the preview retains full dependencies', async ({ page, request }) => {
  const backup = await (await request.get('/api/system/backup')).json()
  try {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')
    await openWorkspaceTab(page, '设计成果')
    const workspace = page.getByRole('region', { name: '设计评审工作区', exact: true })
    const trigger = workspace.getByRole('button', { name: '预览设计评审', exact: true })
    await expect(trigger).toBeVisible()
    await expect(workspace.getByRole('table')).toHaveCount(0)
    await expect(workspace.getByLabel('评审条目索引').locator('[data-object-id]').first()).toBeVisible()
    await page.screenshot({ path: `${evidence}/review-summary-desktop.png`, fullPage: true })
    await trigger.click()
    const preview = page.getByRole('dialog', { name: '设计评审预览', exact: true })
    await expect(preview.getByRole('table', { name: '设计评审完整清单', exact: true })).toBeVisible()
    await expect(preview.getByRole('columnheader', { name: '依赖需求', exact: true })).toBeVisible()
    await expect(preview.getByRole('heading', { name: '审核记录', exact: true })).toBeVisible()
    await page.screenshot({ path: `${evidence}/review-detail-desktop.png` })
    await page.setViewportSize({ width: 390, height: 844 })
    expect(await preview.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
    await page.screenshot({ path: `${evidence}/review-detail-mobile.png` })
    await page.keyboard.press('Escape')
    await expect(trigger).toBeFocused()
  } finally { await restore(request, backup) }
})
