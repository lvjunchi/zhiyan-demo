import { openWorkspaceTab } from '../e2e-support/navigation'
import { expect, test } from '@playwright/test'
const evidence = process.env.ZHIYAN_EVIDENCE_DIR ?? 'test-results/screenshots'

test('shows the complete project dashboard in one desktop viewport', async ({ page, request }) => {
  const errors: string[] = [], external: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('request', req => { if (!['127.0.0.1','localhost'].includes(new URL(req.url()).hostname)) external.push(req.url()) })
  const projectsBefore = await (await request.get('/api/projects')).json()
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '法士特—陕汽定制项目试点' })).toBeVisible()
  await expect(page.getByRole('combobox', { name: '选择项目' })).toHaveCount(0)
  await expect(page.locator('.demo-role, .actor-badge')).toHaveCount(0)
  await expect(page.locator('html')).toHaveAttribute('data-density','compact')
  for (const [width,height] of [[2560,1440],[1920,1080],[1440,900],[1366,768]]) {
    await page.setViewportSize({ width,height })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    expect(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight), `one screen at ${width}x${height}`).toBe(true)
    for (const title of ['需求解析智能体','变型设计智能体','试验验证智能体','一致性检测','协同风险预警','工程知识底座','最近任务与动态','评审材料']) {
      const heading = page.getByRole('heading', { name: title, exact: true })
      await expect(heading).toBeVisible()
      const box = await heading.boundingBox()
      expect(box!.y + box!.height).toBeLessThanOrEqual(height)
    }
    await expect(page.getByRole('region', { name:'当前验证追溯' }).getByRole('row')).toHaveCount(6)
    const clarity = page.getByRole('group',{name:'需求审核状态'})
    const statusRows = await clarity.locator(':scope > span').evaluateAll(elements => elements.map(el => ({top:el.getBoundingClientRect().top,clipped:el.scrollWidth>el.clientWidth})))
    expect(statusRows).toHaveLength(5)
    expect(Math.max(...statusRows.map(row=>row.top))-Math.min(...statusRows.map(row=>row.top))).toBeLessThanOrEqual(1)
    expect(statusRows.every(row=>!row.clipped)).toBe(true)
    const knowledge = page.locator('.dash-knowledge')
    const knowledgeSizes = await knowledge.locator('button').evaluateAll(elements => elements.map(el => ({icon:el.querySelector('svg')!.getBoundingClientRect().width,label:parseFloat(getComputedStyle(el.querySelector('strong')!).fontSize),clipped:el.scrollHeight>el.clientHeight+1})))
    for (const item of knowledgeSizes) {expect(item.icon).toBeGreaterThanOrEqual(28);expect(item.label).toBeGreaterThanOrEqual(12);expect(item.clipped).toBe(false)}
    for (const count of (await knowledge.locator('button small').all()).slice(0,3)) {
      const style = await count.evaluate(el => {const value=getComputedStyle(el);return {size:parseFloat(value.fontSize),weight:parseInt(value.fontWeight),width:el.getBoundingClientRect().width,clipped:el.scrollWidth>el.clientWidth+1}})
      expect(style.size,'resource counts stay secondary to library names').toBeLessThanOrEqual(13)
      expect(style.weight).toBeLessThanOrEqual(500)
      expect(style.width,'count labels fit their content').toBeLessThanOrEqual(80)
      expect(style.clipped).toBe(false)
    }
    const contrast = await page.getByRole('navigation',{name:'研发流程'}).locator("button[aria-current='step']").evaluate(el=>{
      function luminance(color:string) {const rgb=color.match(/[\d.]+/g)!.slice(0,3).map(value=>{const c=Number(value)/255;return c<=.04045?c/12.92:((c+.055)/1.055)**2.4});return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722}
      const background=luminance(getComputedStyle(el).backgroundColor),text=luminance(getComputedStyle(el.querySelector('strong')!).color)
      return (Math.max(background,text)+.05)/(Math.min(background,text)+.05)
    })
    expect(contrast,`active stage text contrast at ${width}`).toBeGreaterThanOrEqual(4.5)
    const packageCard = page.getByRole('region',{name:'评审材料摘要'})
    await expect(packageCard.getByRole('group',{name:'材料包快照检查摘要'})).toBeVisible()
    const packageLayout = await packageCard.evaluate(el=>{
      const card=el.getBoundingClientRect(),button=el.querySelector('button')!.getBoundingClientRect()
      return {width:button.width,innerWidth:card.width-parseFloat(getComputedStyle(el).paddingLeft)-parseFloat(getComputedStyle(el).paddingRight)-2,bottom:card.bottom-button.bottom}
    })
    expect(packageLayout.width/packageLayout.innerWidth).toBeGreaterThanOrEqual(.95)
    expect(packageLayout.bottom).toBeGreaterThanOrEqual(0)
    expect(packageLayout.bottom).toBeLessThanOrEqual(18)
    for (const selector of ['.dash-table-scroll', '.dash-middle', '.dash-bottom', '.dash-agent-grid article', '.dash-package', '.package-checks']) {
      for (const element of await page.locator(selector).all()) {
        const layout = await element.evaluate(element => ({ scroll: element.scrollHeight, visible: element.clientHeight }))
        expect(layout.scroll, `${selector} fits without internal clipping at ${width}`).toBeLessThanOrEqual(layout.visible + 1)
      }
    }
    for (const card of await page.locator('.dash-agent-grid article').all()) {
      const layout = await card.evaluate(element => {
        const facts = element.querySelector('.dash-agent-facts')!.lastElementChild!.getBoundingClientRect()
        const subtitle = element.querySelector(':scope > p')!.getBoundingClientRect()
        const firstFact = element.querySelector('.dash-agent-facts')!.firstElementChild!.getBoundingClientRect()
        const buttons = Array.from(element.querySelectorAll('.dash-agent-bottom > button')).map(button => {
          const box = button.getBoundingClientRect()
          return {width:box.width,height:box.height,top:box.top}
        })
        return {gap:buttons[0].top-facts.bottom,subtitleGap:firstFact.top-subtitle.bottom,bottomGap:element.getBoundingClientRect().bottom-buttons[0].top-buttons[0].height,buttons}
      })
      expect(layout.subtitleGap, `agent subtitle-to-metrics gap at ${width}`).toBeLessThanOrEqual(12)
      expect(layout.gap, `agent content-to-action gap at ${width}`).toBeLessThanOrEqual(16)
      expect(layout.gap).toBeGreaterThanOrEqual(0)
      expect(layout.bottomGap, `agent actions-to-card-bottom gap at ${width}`).toBeLessThanOrEqual(18)
      expect(layout.buttons).toHaveLength(2)
      expect(Math.abs(layout.buttons[0].width-layout.buttons[1].width)).toBeLessThanOrEqual(1)
      expect(Math.abs(layout.buttons[0].height-layout.buttons[1].height)).toBeLessThanOrEqual(1)
      expect(Math.abs(layout.buttons[0].top-layout.buttons[1].top)).toBeLessThanOrEqual(1)
      expect(layout.buttons[0].height).toBeGreaterThanOrEqual(28)
    }
    const parametersFit = await page.locator('.dash-product-body').evaluate(element => {
      const body = element.getBoundingClientRect(), parameters = element.querySelector('dl')!.getBoundingClientRect()
      return parameters.top >= body.top - 1 && parameters.bottom <= body.bottom + 1
    })
    expect(parametersFit, `all product parameters fit at ${width}`).toBe(true)
    await expect(page.getByRole('img', { name:/响应耗时/ })).toBeVisible()
    await page.screenshot({ path: `${evidence}/dashboard-${width}.png`,fullPage:true })
  }
  await page.setViewportSize({width:390,height:844})
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({path:`${evidence}/dashboard-mobile.png`,fullPage:true})
  await page.setViewportSize({width:1440,height:900})
  for (const [button, heading] of [['查看设计成果','设计评审清单'],['查看试验与追溯','追溯矩阵']]) {
    await page.getByRole('button',{name:button,exact:true}).click()
    await expect(page.getByRole('heading',{name:heading,exact:true})).toBeVisible()
    await openWorkspaceTab(page, '项目总览')
  }
  expect(await (await request.get('/api/projects')).json()).toEqual(projectsBefore)
  expect(errors).toEqual([]); expect(external).toEqual([])
})

test('settings persist and business modules share the workspace design', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/')
  await openWorkspaceTab(page, '系统设置')
  await expect(page.getByText('数据库已连接')).toBeVisible()
  await expect(page.getByLabel('信息密度')).toHaveValue('compact')
  await page.getByLabel('减少界面动效', { exact: true }).check()
  await page.getByRole('button', { name: '保存显示设置' }).click()
  await expect(page.getByRole('status')).toContainText('显示设置已保存')
  await page.reload()
  await openWorkspaceTab(page, '系统设置')
  await expect(page.getByLabel('信息密度')).toHaveValue('compact')
  await expect(page.getByLabel('减少界面动效', { exact: true })).toBeChecked()
  await page.screenshot({ path: `${evidence}/settings.png`, fullPage: true })
  await page.getByLabel('信息密度').selectOption('comfortable')
  await page.getByRole('button', { name: '保存显示设置' }).click()
  for (const tab of ['需求清单', '设计成果', '试验验证与追溯']) {
    await openWorkspaceTab(page, tab)
    await expect(page.getByRole('heading', { level: 1, name: tab })).toBeVisible()
    await expect(page.locator('.state').filter({ hasText: /加载/ })).toHaveCount(0)
    await page.screenshot({ path: `${evidence}/module-${tab}.png`, fullPage: true })
  }
  await openWorkspaceTab(page, '协议解析与澄清')
  await page.getByLabel('选择协议文件').setInputFiles({ name: 'local-protocol.txt', mimeType: 'text/plain', buffer: Buffer.from('3.1 发动机最大扭矩 2800 N·m。', 'utf8') })
  await expect(page.getByRole('status')).toContainText('文件文本已提取')
  await expect(page.getByLabel('来源文档正文')).toHaveValue(/【TXT 行 1】/)
  await page.screenshot({ path: `${evidence}/file-preview.png`, fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await openWorkspaceTab(page, '系统设置')
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
})
