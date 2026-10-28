import { openWorkspaceTab } from '../e2e-support/navigation'
import { expect, test } from '@playwright/test'

const evidence = process.env.ZHIYAN_EVIDENCE_DIR ?? 'test-results/screenshots'

test('desktop navigation fits and keeps readable type across overview and modules', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '法士特—陕汽定制项目试点' })).toBeVisible()
  for (const [width, height] of [[1920, 1080], [1440, 900], [1366, 768], [1280, 720]]) {
    await page.setViewportSize({ width, height })
    for (const name of ['项目总览', '需求清单']) {
      await openWorkspaceTab(page, name)
      const nav = await page.locator('.side-nav').evaluate(element => ({ height: element.clientHeight, scroll: element.scrollHeight }))
      expect(nav.scroll, `${name}: menu overflow at ${width}`).toBeLessThanOrEqual(nav.height + 1)
      const labels = await page.locator('.side-nav-item:visible span').evaluateAll(elements => elements.map(element => ({
        size: parseFloat(getComputedStyle(element).fontSize),
        top: element.getBoundingClientRect().top,
        bottom: element.getBoundingClientRect().bottom,
        clipped: element.scrollWidth > element.clientWidth,
      })))
      expect(labels).toHaveLength(6)
      for (const label of labels) {
        expect(label.size).toBeGreaterThanOrEqual(14)
        expect(label.top).toBeGreaterThanOrEqual(0)
        expect(label.bottom).toBeLessThanOrEqual(height)
        expect(label.clipped).toBe(false)
      }
      if (name === '需求清单') {
        await page.getByRole('button', { name: /^全部需求 \d+ 条$/ }).click()
        await expect(page.locator('.module-surface tbody tr').first()).toBeVisible()
        const cellSize = await page.locator('.module-surface td').first().evaluate(element => parseFloat(getComputedStyle(element).fontSize))
        expect(cellSize).toBeGreaterThanOrEqual(13)
        await page.getByRole('button', {name:'修订 REQ-P01-B-003', exact:true}).click()
        const inputSize = await page.getByLabel('修订后的数值').evaluate(element => parseFloat(getComputedStyle(element).fontSize))
        await page.getByRole('button', {name:'关闭详情'}).click()
        expect(inputSize).toBeGreaterThanOrEqual(14)
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      await page.screenshot({ path: `${evidence}/${name}-${width}.png`, fullPage: true })
    }
  }
  await openWorkspaceTab(page, '系统设置')
  await page.getByLabel('信息密度').selectOption('comfortable')
  await page.getByRole('button', { name: '保存显示设置' }).click()
  const nav = await page.locator('.side-nav').evaluate(element => ({ height: element.clientHeight, scroll: element.scrollHeight }))
  expect(nav.scroll).toBeLessThanOrEqual(nav.height + 1)
})

test('mobile keeps readable module text and reachable navigation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await openWorkspaceTab(page, '需求清单')
  await page.getByRole('button', { name: /^全部需求 \d+ 条$/ }).click()
  await expect(page.locator('.module-surface tbody tr').first()).toBeVisible()
  expect(await page.locator('.module-surface td').first().evaluate(element => parseFloat(getComputedStyle(element).fontSize))).toBeGreaterThanOrEqual(13)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await openWorkspaceTab(page, '系统设置')
  await expect(page.getByRole('heading', { name: '系统设置', exact: true })).toBeVisible()
  await page.screenshot({ path: `${evidence}/mobile-settings.png`, fullPage: true })
})
