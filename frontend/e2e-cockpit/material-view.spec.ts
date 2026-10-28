import { openWorkspaceTab } from '../e2e-support/navigation'
import { expect, test } from '@playwright/test'
import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'

const evidence = process.env.ZHIYAN_EVIDENCE_DIR ?? 'test-results/screenshots'

test('package view opens immediately, keeps current gate separate and retains downloadable history', async ({ page, request }) => {
  const backup = await (await request.get('/api/system/backup')).json()
  try {
    const projects: { id: string; display_code: string }[] = await (await request.get('/api/projects')).json()
    const project = projects.find(item => item.display_code === 'P01')!
    for (let count = 0; count < 2; count++) {
      const created = await request.post(`/api/projects/${project.id}/material-packages`, { data: { include_originals: false, actor: '本地测试工程师' } })
      expect(created.ok(), await created.text()).toBe(true)
    }
    const packages: { id: string; display_code: string; zip_sha256: string }[] = await (await request.get(`/api/projects/${project.id}/material-packages`)).json()
    const latest = packages[0], old = packages.at(-1)!
    const writes: string[] = []
    page.on('request', request => { if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) writes.push(request.url()) })
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')
    await openWorkspaceTab(page, '评审材料')
    const list = page.getByRole('table', { name: '材料包列表', exact: true })
    await expect(list.locator('tbody > tr')).toHaveCount(1)
    await expect(list).toContainText(latest.display_code)
    const latestWork = page.getByRole('region', { name: '当前材料准备', exact: true })
    await expect(latestWork).toBeVisible()
    await expect(latestWork).toContainText(latest.display_code)
    await expect(latestWork.getByRole('table')).toHaveCount(0)
    await expect(latestWork.getByText(/快照哈希|ZIP SHA-256/)).toHaveCount(0)
    await expect(page.getByRole('button', { name: '预览材料快照', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '下载 ZIP', exact: true })).toHaveCount(1)
    await page.screenshot({ path: `${evidence}/material-workspace-desktop.png`, fullPage: true })
    const currentTrigger = list.getByRole('button', { name: '查看', exact: true })
    await currentTrigger.click()
    const current = page.getByRole('dialog', { name: `材料包详情 · ${latest.display_code}`, exact: true })
    await expect(current.getByRole('heading', { name: '生成时快照', exact: true })).toBeVisible()
    expect(await current.evaluate(element => element.matches(':modal'))).toBe(true)
    await page.screenshot({ path: `${evidence}/package-detail-desktop.png` })
    await page.keyboard.press('Escape')
    await expect(currentTrigger).toBeFocused()
    await page.getByRole('button', { name: `展开历史材料包（${packages.length - 1}）`, exact: true }).click()
    await expect(list.locator('tbody > tr')).toHaveCount(packages.length)
    const oldRow = list.locator(`[data-object-id="${old.id}"]`)
    const oldTrigger = oldRow.getByRole('button', { name: '查看', exact: true })
    await page.route(`**/api/material-packages/${old.id}`, route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { message: '模拟详情读取失败' } }) }), { times: 1 })
    await oldTrigger.click()
    const history = page.getByRole('dialog', { name: `材料包详情 · ${old.display_code}`, exact: true })
    await expect(history.getByRole('alert')).toContainText('模拟详情读取失败')
    await expect(history.getByRole('heading', { name: '生成时快照', exact: true })).toHaveCount(0)
    await history.getByRole('button', { name: '重试加载材料', exact: true }).click()
    await expect(history.getByRole('heading', { name: '生成时快照', exact: true })).toBeVisible()
    await expect(history.getByText(/此包为旧版门禁快照/)).toBeVisible()
    await page.setViewportSize({ width: 390, height: 844 })
    expect(await history.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
    await page.screenshot({ path: `${evidence}/package-detail-mobile.png` })
    await history.getByRole('button', { name: '关闭材料详情', exact: true }).click()
    await expect(oldTrigger).toBeFocused()
    await expect(latestWork).toBeVisible()
    await expect(latestWork).toContainText(latest.display_code)
    const download = page.waitForEvent('download')
    await oldRow.getByRole('button', { name: '下载 ZIP', exact: true }).click()
    const archive = await download
    const file = `${evidence}/historical-package.zip`
    await archive.saveAs(file)
    expect(createHash('sha256').update(await readFile(file)).digest('hex')).toBe(old.zip_sha256)
    await page.getByRole('button', { name: `收起历史材料包（${packages.length - 1}）`, exact: true }).click()
    await expect(list.locator('tbody > tr')).toHaveCount(1)
    await page.screenshot({ path: `${evidence}/material-workspace-mobile.png`, fullPage: true })
    expect((await (await request.get(`/api/projects/${project.id}/material-packages`)).json()).length).toBe(packages.length)
    expect(writes).toEqual([])
  } finally {
    const current = await (await request.get('/api/system/backup')).json()
    const restored = await request.post('/api/system/restore', { data: { backup, expected_state_hash: current.sha256, actor: '本地测试工程师', role: 'design_engineer' } })
    expect(restored.ok(), await restored.text()).toBe(true)
  }
})
