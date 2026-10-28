import {expect,test} from '@playwright/test'
const evidence=process.env.ZHIYAN_EVIDENCE_DIR??'test-results/screenshots'

test('package action stays inside its padding across the height breakpoint and density settings',async({page,request})=>{
  const before=await(await request.get('/api/system/backup')).json()
  await page.goto('/')
  const card=page.getByRole('region',{name:'评审材料摘要'})
  await expect(card).toBeVisible()
  for(const density of ['compact','comfortable']){
    await page.evaluate(value=>{document.documentElement.dataset.density=value},density)
    for(const [width,height] of [[2560,1440],[1920,908],[1920,909],[1920,910],[1920,953],[1920,954],[1920,955],[1920,983],[1920,984],[1920,985],[1920,1000],[1920,1001],[1920,1024],[1920,1040],[1920,1050],[1920,1076],[1920,1077],[1920,1078],[1920,1080],[1440,1001],[1366,768],[1199,1001],[390,844]]){
      await page.setViewportSize({width,height})
      const layout=await card.evaluate(el=>{
        const frame=el.getBoundingClientRect(),button=el.querySelector('button')!.getBoundingClientRect(),style=getComputedStyle(el)
        const checks=el.querySelector('.package-checks')!
        const summary=checks.getBoundingClientRect(),summaryStyle=getComputedStyle(checks)
        return{bottom:frame.bottom-button.bottom,required:parseFloat(style.paddingBottom)+parseFloat(style.borderBottomWidth),scroll:el.scrollHeight,visible:el.clientHeight,checksScroll:checks.scrollHeight,checksVisible:checks.clientHeight,checksWidth:summary.width,checksHeight:summary.height,buttonWidth:button.width,summaryLeft:summary.left,buttonLeft:button.left,background:summaryStyle.backgroundColor,border:parseFloat(summaryStyle.borderTopWidth),horizontalScroll:checks.scrollWidth,horizontalVisible:checks.clientWidth}
      })
      expect(layout.bottom,`${density} ${width}x${height}: action preserves card padding`).toBeGreaterThanOrEqual(layout.required-.5)
      expect(layout.scroll).toBeLessThanOrEqual(layout.visible+1)
      expect(layout.checksScroll).toBeLessThanOrEqual(layout.checksVisible+1)
      expect(layout.background,'snapshot retains its pale blue frame').toBe('rgb(243, 247, 252)')
      expect(layout.border).toBe(1)
      expect(Math.abs(layout.checksWidth-layout.buttonWidth),'statistics align with the full card content').toBeLessThanOrEqual(1)
      expect(Math.abs(layout.summaryLeft-layout.buttonLeft)).toBeLessThanOrEqual(1)
      expect(layout.horizontalScroll).toBeLessThanOrEqual(layout.horizontalVisible+1)
      expect(layout.checksHeight,`${density} ${width}x${height}: snapshot summary does not stretch vertically`).toBeLessThanOrEqual(60)
      if(density==='compact'&&[1001,1024,1080,768,844].includes(height))await card.screenshot({path:`${evidence}/package-${width}x${height}.png`})
    }
  }
  expect((await(await request.get('/api/system/backup')).json()).sha256).toBe(before.sha256)
})
