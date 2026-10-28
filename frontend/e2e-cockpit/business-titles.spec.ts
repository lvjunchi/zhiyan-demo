import { openWorkspaceTab } from '../e2e-support/navigation'
import { expect, test } from '@playwright/test'

test('module headings use business names without internal output codes', async ({ page }) => {
  await page.goto('/')
  const modules = [
    ['协议解析与澄清', '来源文档导入与规则解析'],
    ['型谱选型与变型', '型谱 Top-3'],
    ['设计成果', '相似项目'],
    ['试验验证与追溯', '试验方案与用例'],
    ['样件检验', '样件交付与比对'],
  ]
  for (const [tab, heading] of modules) {
    await openWorkspaceTab(page, tab)
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible()
    await expect(page.getByRole('heading').filter({ hasText: /[（(]\s*O\d/ })).toHaveCount(0)
    await page.screenshot({
      path: `${process.env.ZHIYAN_EVIDENCE_DIR ?? 'test-results/screenshots'}/${tab}.png`,
      fullPage: true,
    })
  }
})
