import { openWorkspaceTab } from '../e2e-support/navigation'
import { expect, test } from '@playwright/test'

const evidence = process.env.ZHIYAN_EVIDENCE_DIR ?? 'test-results/screenshots'

test('sidebar is the only full module navigation and work contexts stay compact', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  const order = ['项目总览', '协议解析与澄清', '需求清单', '型谱选型与变型', '设计成果', '试验验证与追溯', '样件检验', '一致性检测', '协同风险', '评审材料', '系统设置']
  await expect(page.locator('[role=tab]')).toHaveText(order)
  for (const module of order.slice(1, -1)) {
    await openWorkspaceTab(page, module)
    const context = page.getByRole('region', { name: '当前模块工作提示' })
    await expect(context).toHaveCount(1)
    await expect(page.getByRole('navigation', { name: '项目阶段导航' })).toHaveCount(0)
    await expect(page.getByRole('region', { name: '模块工作路径' })).toHaveCount(0)
    await expect(context.getByText(/已登记/)).toBeVisible()
    const box = await context.boundingBox()
    expect(box!.height).toBeLessThan(190)
    if (module !== '需求清单') await expect(context.getByRole('button', { name: /变更影响/ })).toHaveCount(0)
  }
  await page.getByRole('button', { name: '回到项目总览', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1, name: '项目总览' })).toBeVisible()
})
test('saved change exposes revision impact, stale confirmation and working object navigation', async ({ page, request }) => {
  const project = (await (await request.get('/api/projects')).json() as { id: string; display_code: string }[]).find(p => p.display_code === 'P01')!
  const requirements = await (await request.get(`/api/projects/${project.id}/requirements`)).json() as { id: string; parser_key: string; value_text: string; current_revision: number }[]
  let engine = requirements.find(r => r.parser_key === 'engineMaxTorque')!
  if (engine.value_text !== '2600') {
    const response = await request.patch(`/api/requirements/${engine.id}`, { data: { expected_revision: engine.current_revision, value_text: '2600' } })
    expect(response.ok()).toBe(true)
    engine = await response.json()
  }
  const beforePlan = await (await request.get(`/api/projects/${project.id}/test-plan`)).json()
  await page.goto('/')
  await openWorkspaceTab(page, '需求清单')
  const journey = page.getByRole('region', { name: '当前模块工作提示' })
  await expect(journey.getByText(/核对来源与版本/)).toBeVisible()
  await expect(page.getByRole('navigation', { name: '项目阶段导航' })).toHaveCount(0)
  await page.getByLabel('选择要修订的需求').selectOption(engine.id)
  await page.getByLabel('修订后的数值').fill('2800')
  await page.getByRole('button', { name: '提交修订', exact: true }).click()
  await expect(page.getByText(/已更新为 V/)).toBeVisible()
  await journey.getByRole('button', { name: /变更影响/ }).click()
  await journey.getByLabel('选择变更需求').selectOption(engine.id)
  await expect(journey.getByText(/2600 N·m/, { exact: false })).toBeVisible()
  await expect(journey.getByText(/2800 N·m/, { exact: false })).toBeVisible()
  const caseRow = journey.getByRole('row').filter({ hasText: 'TC-007' })
  await expect(caseRow).toContainText('待复核')
  await expect(caseRow).toContainText('已确认')
  await page.screenshot({ path: `${evidence}/change-impact.png`, fullPage: true })
  await caseRow.getByRole('button', { name: '处理 TC-007' }).click()
  await expect(page.getByRole('heading', { level: 1, name: '试验验证与追溯' })).toBeVisible()
  await expect(page.locator('[data-focus-target="true"]')).toBeVisible()
  await expect(page.getByText(/来自需求变更/)).toBeVisible()
  await page.getByRole('button', { name: '返回变更工作区' }).click()
  await expect(page.getByRole('heading', { level: 1, name: '需求清单' })).toBeVisible()
  const afterPlan = await (await request.get(`/api/projects/${project.id}/test-plan`)).json()
  expect(afterPlan.cases.map((c: { runs: unknown[] }) => c.runs)).toEqual(beforePlan.cases.map((c: { runs: unknown[] }) => c.runs))
})

test('result previews remain readable, keyboard accessible and fit desktop and mobile', async ({ page }) => {
  await page.goto('/')
  for (const size of [{ width: 1440, height: 900 }, { width: 1366, height: 768 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(size)
    await openWorkspaceTab(page, '设计成果')
    await page.getByRole('button', { name: '预览设计评审', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '设计评审预览' })
    await expect(dialog.getByRole('heading', { name: '审核记录' })).toBeVisible()
    expect(await dialog.evaluate(e => e.scrollWidth <= e.clientWidth)).toBe(true)
    const box = await dialog.boundingBox()
    expect(box!.width).toBeLessThanOrEqual(size.width)
    await page.screenshot({ path: `${evidence}/review-preview-${size.width}.png` })
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
    await expect(page.getByRole('button', { name: '预览设计评审', exact: true })).toBeFocused()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  }
  await page.setViewportSize({ width: 1440, height: 900 })
  for (const [tab, trigger, title] of [['设计成果', '预览DFMEA', 'DFMEA预览'], ['试验验证与追溯', '预览试验方案', '试验方案预览']]) {
    await openWorkspaceTab(page, tab)
    await page.getByRole('button', { name: trigger, exact: true }).click()
    await expect(page.getByRole('dialog', { name: title })).toBeVisible()
    await page.screenshot({ path: `${evidence}/${tab}-preview.png` })
    await page.getByRole('button', { name: '关闭预览' }).click()
  }
  await openWorkspaceTab(page, '评审材料')
  await page.getByRole('table', { name: '材料包列表', exact: true }).getByRole('button', { name: '查看', exact: true }).click()
  await expect(page.getByRole('dialog', { name: /材料包详情/ })).toBeVisible()
  await page.getByRole('button', { name: '关闭材料详情', exact: true }).click()
})

test('workspace failure offers retry without fabricating completed progress', async ({ page }) => {
  await page.route('**/workspace', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: { code: 'PERSISTENCE_UNAVAILABLE', message: '临时不可用' } }) }))
  await page.goto('/')
  await openWorkspaceTab(page, '需求清单')
  await expect(page.getByText(/操作进度暂不可用/)).toBeVisible()
  await expect(page.getByRole('navigation', { name: '项目阶段导航' })).toHaveCount(0)
  await page.unroute('**/workspace')
  await page.getByRole('button', { name: '重试进度' }).click()
  await expect(page.getByRole('region', { name: '当前模块工作提示' }).getByText(/核对来源与版本/)).toBeVisible()
})

test('consistency summary renders backend counts and nested distributions without raw objects', async ({ page, request }) => {
  const browserErrors: string[] = []
  page.on('pageerror', error => browserErrors.push(error.message))
  await page.goto('/')
  await openWorkspaceTab(page, '一致性检测')
  const stats = page.getByRole('region', { name: '一致性检查统计', exact: true })
  await expect(stats).toBeVisible()
  const project = (await (await request.get('/api/projects')).json() as { id: string; display_code: string }[]).find(p => p.display_code === 'P01')!
  const metrics = ['total', 'blocking_open', 'open', 'review_pending', 'closed', 'accepted_risk']
  async function assertSummary() {
    const response = await request.get(`/api/projects/${project.id}/consistency-checks/latest`)
    expect(response.ok()).toBe(true)
    const { check } = await response.json() as { check: { summary: Record<string, number | Record<string, number>> } }
    for (const key of metrics) await expect(stats.locator(`[data-metric="${key}"] dd`)).toHaveText(String(check.summary[key]))
    for (const [field, label] of [['by_severity', '本次检出严重度分布'], ['by_type', '本次检出类型分布']]) {
      await expect(stats.getByRole('region', { name: label }).locator('dd')).toHaveText(Object.values(check.summary[field] as Record<string, number>).map(String))
    }
    await expect(stats).not.toContainText('[object Object]')
    await expect(stats).not.toContainText(/by_severity|by_type|total|confirmed/)
  }
  await assertSummary()
  await page.getByRole('button', { name: '运行一致性检查', exact: true }).click()
  await expect(page.getByText(/一致性检查 CR-.*完成/)).toBeVisible()
  await assertSummary()
  for (const size of [{ width: 1920, height: 1080 }, { width: 1440, height: 900 }, { width: 1366, height: 768 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(size)
    await expect(stats).toBeVisible()
    expect(await stats.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    await stats.screenshot({ path: `${evidence}/consistency-${size.width}.png` })
  }
  expect(browserErrors).toEqual([])
})
