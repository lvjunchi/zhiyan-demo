import { openWorkspaceTab } from '../e2e-support/navigation'
import { expect, test } from '@playwright/test'

const evidence = process.env.ZHIYAN_EVIDENCE_DIR ?? 'test-results/screenshots'

test('requirement queue persists review, reason and revisions without deleting processed records', async ({ page, request }) => {
  const backupResponse = await request.get('/api/system/backup')
  expect(backupResponse.ok()).toBe(true)
  const backup = await backupResponse.json()
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  try {
    const projects = await (await request.get('/api/projects')).json() as { id: string; display_code: string }[]
    const project = projects.find(item => item.display_code === 'P01')!
    const created: { id: string; display_code: string }[] = []
    for (const suffix of ['A', 'B']) {
      const response = await request.post(`/api/projects/${project.id}/requirements`, { data: {
        display_code: `REQ-UIX-${suffix}`, category: 'I', parameter_name: `审核交互合成参数${suffix}`,
        data_type: 'numeric', operator: '<=', value_text: '100', unit: 'mm',
        source_location: 'UI-X 合成验收', source_excerpt: '合成输入：长度不超过100 mm',
      } })
      expect(response.ok()).toBe(true)
      created.push(await response.json())
    }
    const [confirmed, rejected] = created
    const before = await (await request.get(`/api/projects/${project.id}/requirements`)).json() as { id: string; review_status: string }[]
    const initialPending = before.filter(item => ['draft', 'pending_review'].includes(item.review_status)).length
    let failOnce = true
    await page.route(`**/api/requirements/${confirmed.id}/confirmations`, async route => {
      if (route.request().method() === 'POST' && failOnce) {
        failOnce = false
        await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'TEST_UNAVAILABLE', message: '审核服务暂不可用（隔离测试）' } }) })
      } else await route.continue()
    })
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')
    await openWorkspaceTab(page, '需求清单')
    await expect(page.getByRole('button', { name: `待审核 ${initialPending} 条`, exact: true })).toHaveAttribute('aria-pressed', 'true')
    const confirmButton = page.getByRole('button', { name: `确认 ${confirmed.display_code}`, exact: true })
    await confirmButton.click()
    await expect(page.getByRole('alert')).toContainText('审核服务暂不可用')
    await expect(confirmButton).toBeEnabled()
    await confirmButton.click()
    await expect(page.getByRole('status').filter({ hasText: `已确认 ${confirmed.display_code}` })).toContainText('已移至已确认列表')
    await expect(page.getByRole('row').filter({ hasText: confirmed.display_code })).toHaveCount(0)
    await expect(page.getByRole('button', { name: `待审核 ${initialPending - 1} 条`, exact: true })).toHaveAttribute('aria-pressed', 'true')
    const rejectButton = page.getByRole('button', { name: `驳回 ${rejected.display_code}`, exact: true })
    await rejectButton.click()
    const rejectDrawer = page.getByRole('dialog', { name: '驳回需求', exact: true })
    await expect(rejectDrawer.getByLabel('驳回原因')).toBeFocused()
    await expect(rejectDrawer.getByLabel('驳回原因')).not.toHaveAttribute('required')
    await expect(rejectDrawer.getByRole('button', { name: '提交驳回', exact: true })).toBeEnabled()
    const reason = '原文参数需要澄清，核对后提交修订（合成验收）'
    await rejectDrawer.getByLabel('驳回原因').fill(reason)
    await page.keyboard.press('Escape')
    await expect(rejectButton).toBeFocused()
    await rejectButton.click()
    await expect(rejectDrawer.getByLabel('驳回原因')).toHaveValue(reason)
    await rejectDrawer.getByRole('button', { name: '提交驳回', exact: true }).click()
    await expect(rejectDrawer).toHaveCount(0)
    await expect(page.getByRole('status').filter({ hasText: `已驳回 ${rejected.display_code}` })).toContainText('待修订')
    await page.getByRole('button', { name: /^已驳回 \d+ 条$/ }).click()
    const rejectedRow = page.getByRole('row').filter({ hasText: rejected.display_code })
    await expect(rejectedRow).toBeVisible()
    await expect(rejectedRow.getByRole('button', { name: /^确认 / })).toHaveCount(0)
    await page.screenshot({ path: `${evidence}/rejected-queue-desktop.png`, fullPage: true })
    await rejectedRow.getByRole('button', { name: `修订 ${rejected.display_code}`, exact: true }).click()
    await expect(page.getByLabel('修订后的数值')).toBeFocused()
    await page.getByRole('button', { name: '提交修订', exact: true }).click()
    await expect(page.getByRole('status').filter({ hasText: /未发生实质变化/ })).toContainText('已驳回')
    await page.getByLabel('修订后的数值').fill('101')
    await page.getByLabel('修订来源说明').fill('澄清后长度101 mm，合成补充依据')
    await page.getByRole('button', { name: '提交修订', exact: true }).click()
    await expect(page.getByRole('status').filter({ hasText: /已更新为 V2/ })).toContainText('待审核')
    const revisedRow = page.getByRole('row').filter({ hasText: rejected.display_code })
    await expect(revisedRow).toContainText('V2')
    await revisedRow.getByRole('button', { name: `确认 ${rejected.display_code}`, exact: true }).click()
    await expect(revisedRow).toHaveCount(0)
    await page.reload()
    await openWorkspaceTab(page, '需求清单')
    await page.getByRole('button', { name: /^已确认 \d+ 条$/ }).click()
    const row = page.getByRole('row').filter({ hasText: rejected.display_code })
    await expect(row).toContainText('V2')
    const historyButton = row.getByRole('button', { name: `查看 ${rejected.display_code} 审核记录`, exact: true })
    await historyButton.click()
    const history = page.getByRole('dialog', { name: '需求审核记录', exact: true })
    await expect(history.getByText(reason, { exact: true })).toBeVisible()
    await expect(history.getByText('V1 · 历史版本', { exact: true })).toBeVisible()
    await expect(history.getByText('V2 · 当前版本', { exact: true })).toBeVisible()
    await page.screenshot({ path: `${evidence}/review-history-desktop.png` })
    await page.keyboard.press('Escape')
    await expect(historyButton).toBeFocused()
    await page.setViewportSize({ width: 390, height: 844 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await historyButton.click()
    expect(await history.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
    await page.screenshot({ path: `${evidence}/review-history-mobile.png` })
    await page.keyboard.press('Escape')
    await page.getByRole('button', { name: /^待审核 \d+ 条$/ }).click()
    await page.screenshot({ path: `${evidence}/pending-queue-mobile.png`, fullPage: true })
    const after = await (await request.get(`/api/projects/${project.id}/requirements`)).json() as { id: string; review_status: string; current_revision: number }[]
    expect(after).toHaveLength(before.length)
    expect(after.find(item => item.id === rejected.id)).toMatchObject({ review_status: 'confirmed', current_revision: 2 })
    const records = await (await request.get(`/api/requirements/${rejected.id}/confirmations`)).json() as { object_revision: number; decision: string; comment: string }[]
    expect(records).toHaveLength(2)
    expect(records[0]).toMatchObject({ object_revision: 1, decision: 'rejected', comment: reason })
    expect(records[1]).toMatchObject({ object_revision: 2, decision: 'confirmed' })
    expect(errors).toEqual([])
  } finally {
    const current = await (await request.get('/api/system/backup')).json()
    const restored = await request.post('/api/system/restore', { data: { backup, expected_state_hash: current.sha256, actor: '本地测试工程师', role: 'design_engineer' } })
    expect(restored.ok(), await restored.text()).toBe(true)
  }
})
