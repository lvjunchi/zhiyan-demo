import { openWorkspaceTab } from '../e2e-support/navigation'
import { expect, test } from '@playwright/test'

const evidenceDir = process.env.ZHIYAN_EVIDENCE_DIR ?? 'test-results/screenshots'

test('walks the populated P0 demo across all nine tabs', async ({ page }) => {
  test.setTimeout(120_000)

  await page.goto('/')
  await expect(
    page.getByRole('heading', { name: '项目总览' }),
  ).toBeVisible()
  await expect(page.locator('.demo-role, .actor-badge')).toHaveCount(0)

  await expect(page.getByRole('combobox', { name: '选择项目' })).toHaveCount(0)
  await expect(
    page.getByRole('heading', { name: '法士特—陕汽定制项目试点' }),
  ).toBeVisible()
  await expect(page.getByRole('heading', { name: '三智能体协同工作' })).toBeVisible()
  for (const group of [
    '需求解析智能体',
    '变型设计智能体',
    '试验验证智能体',
    '贯穿引擎',
  ]) {
    await expect(page.getByRole('tablist', { name: '工作台模块' }).getByText(group, { exact: true })).toBeVisible()
  }
  await page.screenshot({
    path: `${evidenceDir}/demo-00-overview.png`,
    fullPage: true,
  })

  await openWorkspaceTab(page, '需求清单')
  await page.getByRole('button', { name: /^全部需求 \d+ 条$/ }).click()

  await expect(
    page.getByRole('cell', { name: 'REQ-P01-B-003', exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('cell', { name: '发动机最大扭矩', exact: true }),
  ).toBeVisible()
  await expect(page.getByText('13 条', { exact: true })).toBeVisible()
  await page.screenshot({
    path: `${evidenceDir}/demo-01-requirements.png`,
    fullPage: true,
  })

  await openWorkspaceTab(page, '协议解析与澄清')
  await expect(
    page.getByRole('heading', {
      name: '来源文档导入与规则解析',
    }),
  ).toBeVisible()
  await expect(
    page.getByRole('heading', { name: '问题闭环' }),
  ).toBeVisible()
  await expect(page.getByText('已关闭')).toBeVisible()
  await expect(page.getByText('开放', { exact: true })).toBeVisible()
  await page.screenshot({
    path: `${evidenceDir}/demo-02-parsing-issues.png`,
    fullPage: true,
  })

  await openWorkspaceTab(page, '型谱选型与变型')
  await page.getByRole('button', { name: '计算 Top-3' }).click()
  await expect(
    page.getByText('JX-12A', { exact: true }).first(),
  ).toBeVisible()
  await expect(
    page.getByText('JX-12B', { exact: true }).first(),
  ).toBeVisible()
  await page.getByRole('button', { name: '选用 JX-12A', exact: true }).click()
  await page.getByLabel('变型分析基型编号').fill('JX-12A')
  await page.getByRole('button', { name: '运行变型分析' }).click()
  await expect(
    page.getByRole('cell', { name: 'V-01', exact: true }).first(),
  ).toBeVisible()
  await expect(
    page.getByText('取力器接口', { exact: true }).first(),
  ).toBeVisible()
  await expect(
    page.getByRole('cell', { name: 'P-03', exact: true }).first(),
  ).toBeVisible()
  await page.screenshot({
    path: `${evidenceDir}/demo-03-spectrum-variant.png`,
    fullPage: true,
  })
  await page.getByRole('button', { name: '关闭变型结果', exact: true }).click()

  await openWorkspaceTab(page, '设计成果')
  await expect(
    page.getByRole('heading', { name: '相似项目' }),
  ).toBeVisible()
  await expect(page.getByText('DR-P01')).toBeVisible()
  await expect(page.getByText('DFMEA-P01')).toBeVisible()
  await page.getByRole('button', { name: '重新计算相似项目', exact: true }).click()
  await expect(page.getByText('HX-2023-01')).toBeVisible()
  await page.getByRole('button', { name: '关闭相似项目', exact: true }).click()
  await page.screenshot({
    path: `${evidenceDir}/demo-04-design-risk.png`,
    fullPage: true,
  })

  await openWorkspaceTab(page, '试验验证与追溯')
  await expect(
    page.getByRole('heading', { name: '试验方案与用例' }),
  ).toBeVisible()
  await expect(page.getByText('TP-P01')).toBeVisible()
  await expect(page.getByText('TC-007')).toBeVisible()
  await expect(page.getByText(/5\/5 · 覆盖率 100%/)).toBeVisible()
  await page.screenshot({
    path: `${evidenceDir}/demo-05-testing-traceability.png`,
    fullPage: true,
  })

  await openWorkspaceTab(page, '样件检验')
  await expect(
    page.getByRole('heading', { name: '样件交付与比对' }),
  ).toBeVisible()
  await expect(
    page.getByRole('cell', { name: 'SD-01', exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: '查看 / 比对' }).click()
  await expect(page.getByText(/CMP-SD-01/).first()).toBeVisible()
  await expect(page.getByText('外观检查（模拟生成）', { exact: false })).toBeVisible()
  await page.screenshot({
    path: `${evidenceDir}/demo-06-sample-comparison.png`,
    fullPage: true,
  })

  await page.getByRole('button', { name: '关闭样件详情', exact: true }).click()
  await openWorkspaceTab(page, '一致性检测')
  await expect(
    page.getByRole('heading', { name: '一致性检查（引擎 1）' }),
  ).toBeVisible()
  await expect(page.getByText('CR-P01-001')).toBeVisible()
  await expect(page.getByText('暂无冲突记录。')).toBeVisible()
  await page.screenshot({
    path: `${evidenceDir}/demo-07-consistency.png`,
    fullPage: true,
  })

  await openWorkspaceTab(page, '协同风险')
  await expect(
    page.getByRole('heading', { name: '协同看板（引擎 2）' }),
  ).toBeVisible()
  await expect(page.getByText('CT-01').first()).toBeVisible()
  await expect(
    page.getByText('样件接口与响应协同').first(),
  ).toBeVisible()
  await expect(page.getByText('高风险').first()).toBeVisible()
  await page.screenshot({
    path: `${evidenceDir}/demo-08-coordination.png`,
    fullPage: true,
  })

  await openWorkspaceTab(page, '评审材料')
  await expect(
    page.getByRole('heading', { name: '评审材料包' }),
  ).toBeVisible()
  await expect(page.getByText('MP-P01-001').first()).toBeVisible()
  await expect(page.getByText('旧版门禁 · 请重新生成').first()).toBeVisible()
  await expect(page.getByRole('button', { name: '核对哈希后批准' })).toHaveCount(0)
  await expect(page.getByText('尚未冻结')).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
  await page.screenshot({
    path: `${evidenceDir}/demo-09-material-package.png`,
    fullPage: true,
  })
})
