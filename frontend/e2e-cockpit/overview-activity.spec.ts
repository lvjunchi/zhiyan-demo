import { expect, test } from '@playwright/test'
const evidence = process.env.ZHIYAN_EVIDENCE_DIR ?? 'test-results/screenshots'

test('audit list scrolls manually and stays at the inspected record without writing business data', async ({ page, request }) => {
  const before = await (await request.get('/api/system/backup')).json()
  const writes: string[] = []
  page.on('request', req => { if (req.url().includes('/api/') && !['GET', 'HEAD', 'OPTIONS'].includes(req.method())) writes.push(req.url()) })
  await page.goto('/')
  const list = page.getByRole('region', { name: '项目动态记录' })
  await expect(list).toBeVisible()
  const count = await list.getByRole('listitem').count()
  expect(count).toBeGreaterThan(6)
  expect(count).toBeLessThanOrEqual(30)
  expect(await list.evaluate(el => el.scrollHeight > el.clientHeight)).toBe(true)
  await list.hover()
  await page.mouse.wheel(0, 160)
  await expect.poll(() => list.evaluate(el => el.scrollTop)).toBeGreaterThan(0)
  const position = await list.evaluate(el => el.scrollTop)
  await list.focus()
  await page.screenshot({ path: `${evidence}/activity-paused.png`, fullPage: true })
  expect(await list.evaluate(el => el.scrollTop)).toBe(position)
  await page.keyboard.press('End')
  await expect.poll(() => list.evaluate(el => el.scrollTop)).toBeGreaterThan(position)
  const risk = page.getByRole('list', { name: '协同预警列表' })
  await expect(risk.getByText('高风险', { exact: true })).toBeVisible()
  await expect(risk).toContainText('平均响应时延 > 48 小时')
  expect(writes).toEqual([])
  expect((await (await request.get('/api/system/backup')).json()).sha256).toBe(before.sha256)
})
