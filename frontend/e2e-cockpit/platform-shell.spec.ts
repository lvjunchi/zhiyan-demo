import { expect, test } from '@playwright/test'
import { openWorkspaceTab } from '../e2e-support/navigation'

const evidence = process.env.ZHIYAN_EVIDENCE_DIR ?? 'test-results/screenshots'
const platformName = '复杂高端装备智能定制与自主验证平台'

test('platform identity and compact grouped navigation fit desktop screens without changing records', async ({ page, request }) => {
  const before = await (await request.get('/api/system/backup')).json()
  const writes: string[] = [], errors: string[] = []
  page.on('request', req => { if (req.url().includes('/api/') && !['GET', 'HEAD', 'OPTIONS'].includes(req.method())) writes.push(req.url()) })
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '法士特—陕汽定制项目试点' })).toBeVisible()
  for (const [width, height] of [[1920, 1080], [1440, 900], [1366, 768], [1280, 720]]) {
    await page.setViewportSize({ width, height })
    const masthead = page.getByRole('banner', { name: '平台品牌栏', exact: true })
    const title = masthead.getByText(platformName, { exact: true })
    await expect(title).toBeVisible()
    expect(await title.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
    const titleBox = await title.boundingBox(), brandBox = await masthead.locator('.brand').boundingBox()
    expect(titleBox!.x).toBeGreaterThan(brandBox!.x + brandBox!.width)
    expect(Math.abs(titleBox!.y + titleBox!.height / 2 - brandBox!.y - brandBox!.height / 2)).toBeLessThan(4)
    await expect(page.locator('.page-header').getByText(platformName, { exact: true })).toHaveCount(0)
    const truck = page.getByRole('img', { name: '重型商用车示意' })
    await expect(truck).toBeVisible()
    expect(await truck.evaluate((el: HTMLImageElement) => el.naturalWidth)).toBeGreaterThan(0)
    const box = await truck.boundingBox()
    expect(box!.y + box!.height).toBeLessThanOrEqual(height)
    expect(await page.locator('.side-nav').evaluate(el => el.scrollHeight <= el.clientHeight + 1)).toBe(true)
    const progress = page.getByRole('region', { name: '当前项目进度', exact: true })
    await expect(progress).toHaveCount(0)
    await expect(page.getByRole('navigation', { name: '研发流程' }).locator('[aria-current=step]')).toHaveCount(1)
    const active = page.locator('.dash-flow [aria-current=step]')
    const inactive = page.locator('.dash-flow button:not([aria-current])').first()
    expect(await active.evaluate(el => getComputedStyle(el).backgroundColor)).not.toBe(await inactive.evaluate(el => getComputedStyle(el).backgroundColor))
    for (const detail of await page.locator('.dash-flow small').all()) expect(await detail.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
    const numericColors = await page.locator('.dash-metrics strong').evaluateAll(elements => elements.map(el => getComputedStyle(el).color))
    expect(new Set(numericColors).size).toBeGreaterThanOrEqual(3)
    for (const color of numericColors) {
      const components = color.match(/\d+/g)!.map(Number).slice(0, 3).map(value => {
        const s = value / 255
        return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
      })
      const luminance = components[0] * .2126 + components[1] * .7152 + components[2] * .0722
      expect(1.05 / (luminance + .05), `numeric contrast: ${color}`).toBeGreaterThanOrEqual(4.5)
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: `${evidence}/platform-${width}.png`, fullPage: true })
  }
  expect(writes).toEqual([])
  expect(errors).toEqual([])
  expect((await (await request.get('/api/system/backup')).json()).sha256).toBe(before.sha256)
})

test('truck decoration has a transparent background without a rectangular color panel', async ({ page }) => {
  await page.goto('/')
  const truck = page.getByRole('img', { name: '重型商用车示意' })
  await expect(truck).toBeVisible()
  await expect(truck).toHaveJSProperty('complete', true)
  const pixels = await truck.evaluate((el: HTMLImageElement) => {
    const canvas = document.createElement('canvas')
    canvas.width = el.naturalWidth; canvas.height = el.naturalHeight
    const context = canvas.getContext('2d')!
    context.drawImage(el, 0, 0)
    const { data } = context.getImageData(0, 0, canvas.width, canvas.height)
    let transparent = 0, visible = 0, borderMaxAlpha = 0
    for (let y = 0; y < canvas.height; y++) for (let x = 0; x < canvas.width; x++) {
      const alpha = data[(y * canvas.width + x) * 4 + 3]
      if (alpha === 0) transparent++
      if (alpha > 32) visible++
      if (x < 3 || y < 3 || x >= canvas.width - 3 || y >= canvas.height - 3) borderMaxAlpha = Math.max(borderMaxAlpha, alpha)
    }
    return { transparent: transparent / (canvas.width * canvas.height), visible, visibleFraction: visible / (canvas.width * canvas.height), borderMaxAlpha }
  })
  expect(pixels.transparent, 'background and spaces between linework remain transparent').toBeGreaterThan(.5)
  expect(pixels.visible, 'truck linework exists').toBeGreaterThan(100)
  expect(pixels.visibleFraction, 'linework stays sparse without a filled silhouette or glow').toBeLessThan(.2)
  expect(pixels.borderMaxAlpha, 'border has at most one alpha level of rounding noise').toBeLessThanOrEqual(1)
})

test('groups respond to keyboard and next-step navigation reveals the destination group', async ({ page, request }) => {
  const before = await (await request.get('/api/system/backup')).json()
  await page.goto('/')
  const requirement = page.getByRole('button', { name: '需求解析智能体', exact: true })
  const design = page.getByRole('button', { name: '变型设计智能体', exact: true })
  await expect(requirement).toHaveAttribute('aria-expanded', 'true')
  await expect(design).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByRole('tab', { name: '设计成果', exact: true })).toHaveCount(0)
  await design.focus()
  await page.keyboard.press('Enter')
  await expect(design).toHaveAttribute('aria-expanded', 'true')
  await expect(requirement).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByRole('tab', { name: '设计成果', exact: true })).toBeVisible()
  await page.keyboard.press('Space')
  await expect(design).toHaveAttribute('aria-expanded', 'false')
  await openWorkspaceTab(page, '型谱选型与变型')
  const next = page.getByRole('region', { name: '下一步操作', exact: true })
  await expect(next.getByText('设计成果', { exact: true })).toBeVisible()
  await expect(page.getByRole('region', { name: '当前模块工作提示' })).not.toHaveAttribute('aria-busy', 'true')
  const metrics = await page.locator('.work-context-metrics').innerText()
  expect(metrics).toContain('待办检查')
  await requirement.click()
  await expect(requirement).toHaveAttribute('aria-expanded', 'false')
  await next.getByRole('button', { name: '下一步：设计成果', exact: true }).click()
  await expect(design).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByRole('tab', { name: '设计成果', exact: true })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByRole('heading', { level: 1, name: '设计成果', exact: true })).toBeVisible()
  await expect(page.locator('.module-surface').getByText(/正在加载/)).toHaveCount(0)
  await page.screenshot({ path: `${evidence}/platform-design-guidance.png`, fullPage: true })
  expect((await (await request.get('/api/system/backup')).json()).sha256).toBe(before.sha256)
})

test('platform title, group controls and next-step action remain usable on narrow screens', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await openWorkspaceTab(page, '试验验证与追溯')
  await expect(page.locator('.module-surface').getByText(/正在加载/)).toHaveCount(0)
  await expect(page.getByText(platformName, { exact: true })).toBeVisible()
  const next = page.getByRole('region', { name: '下一步操作', exact: true })
  await expect(next.getByRole('button', { name: '下一步：样件检验' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: `${evidence}/platform-mobile.png`, fullPage: true })
  await next.getByRole('button', { name: '下一步：样件检验' }).click()
  await expect(page.getByRole('heading', { name: '样件检验', level: 1, exact: true })).toBeVisible()
  await expect(page.getByRole('tab', { name: '样件检验', exact: true })).toHaveAttribute('aria-selected', 'true')
})
