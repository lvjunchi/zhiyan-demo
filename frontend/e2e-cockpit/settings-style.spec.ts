import { expect, test } from '@playwright/test'
import { openWorkspaceTab } from '../e2e-support/navigation'
const evidence = process.env.ZHIYAN_EVIDENCE_DIR ?? 'test-results/screenshots'

test('top-level navigation aligns labels and settings actions stay readable on desktop and mobile', async ({ page, request }) => {
  const before = await (await request.get('/api/system/backup')).json()
  await page.goto('/')
  for (const [width,height] of [[1920,1080],[1440,900],[1366,768],[1280,720]]) {
    await page.setViewportSize({width,height})
    const positions = await page.locator('.side-nav .overview-item, .side-nav .nav-group-toggle, .side-nav .nav-standalone .side-nav-item, .side-nav .settings-nav').evaluateAll(elements => elements.map(el => {
      const label = el.querySelector('span')!, style = getComputedStyle(label), box = label.getBoundingClientRect()
      return { size:style.fontSize, weight:style.fontWeight, x:box.x }
    }))
    expect(new Set(positions.map(item => item.size)).size).toBe(1)
    expect(new Set(positions.map(item => item.weight)).size).toBe(1)
    expect(Math.max(...positions.map(item => item.x)) - Math.min(...positions.map(item => item.x))).toBeLessThanOrEqual(1)
    expect(await page.locator('.side-nav').evaluate(el => el.scrollHeight <= el.clientHeight + 1)).toBe(true)
  }
  for (const [width,height] of [[1920,1080],[1440,900],[390,844]]) {
    await page.setViewportSize({width,height})
    await openWorkspaceTab(page,'系统设置')
    for (const label of await page.locator('.side-nav .nav-group-toggle > span').all()) expect(await label.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
    await expect(page.getByRole('heading',{name:'显示与交互',exact:true})).toBeVisible()
    const clear = page.getByRole('button',{name:'清空当前项目业务数据',exact:true})
    await clear.scrollIntoViewIfNeeded()
    await expect(clear).toBeVisible()
    expect((await clear.boundingBox())!.height).toBeGreaterThanOrEqual(40)
    expect(await clear.evaluate(el => getComputedStyle(el).backgroundColor)).not.toBe('rgba(0, 0, 0, 0)')
    const restart = page.locator('.project-clear-card')
    const assuranceBox = await restart.locator('.project-clear-assurances').boundingBox()
    const clearBox = await clear.boundingBox()
    expect(Math.abs(clearBox!.x-assuranceBox!.x)).toBeLessThanOrEqual(1)
    expect(clearBox!.y-(assuranceBox!.y+assuranceBox!.height)).toBeGreaterThanOrEqual(8)
    expect(clearBox!.y-(assuranceBox!.y+assuranceBox!.height)).toBeLessThanOrEqual(20)
    const runtime = page.locator('.settings-runtime')
    expect(await restart.evaluate(el => getComputedStyle(el).backgroundColor)).toBe(await runtime.evaluate(el => getComputedStyle(el).backgroundColor))
    const restartHeading = restart.getByRole('heading', {name:'重新开始项目',exact:true})
    expect(await restartHeading.evaluate(el => getComputedStyle(el).color)).toBe(await runtime.locator('h2').evaluate(el => getComputedStyle(el).color))
    expect(await restartHeading.evaluate(el => getComputedStyle(el).fontSize)).toBe(await runtime.locator('h2').evaluate(el => getComputedStyle(el).fontSize))
    const warningIcon = restart.locator('.project-clear-icon')
    await expect(warningIcon).toBeVisible()
    const color = await warningIcon.evaluate(el => getComputedStyle(el).color.match(/\d+/g)!.map(Number))
    expect(color[0]).toBeGreaterThan(color[1] * 1.4)
    expect(color[0]).toBeGreaterThan(color[2] * 1.4)
    await clear.click()
    const dialog = page.getByRole('dialog',{name:'清空当前项目业务数据'})
    await expect(dialog.getByLabel('输入项目编号确认')).toBeVisible()
    await expect(dialog.getByRole('button',{name:'备份并清空当前项目'})).toBeDisabled()
    await dialog.getByRole('button',{name:'取消清空'}).click()
    await expect(clear).toBeFocused()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({path:`${evidence}/settings-refined-${width}.png`,fullPage:true})
  }
  expect((await (await request.get('/api/system/backup')).json()).sha256).toBe(before.sha256)
})
