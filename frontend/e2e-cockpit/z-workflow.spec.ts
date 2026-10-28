import { openWorkspaceTab } from '../e2e-support/navigation'
import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'

const base = '/api'
const evidence = process.env.ZHIYAN_EVIDENCE_DIR ?? 'test-results/screenshots'

test('archives original bytes and retains engineering versions and actionable material blockers', async ({ page, request }) => {
  const backup = await (await request.get(`${base}/system/backup`)).json()
  try {
    const projects = await (await request.get(`${base}/projects`)).json() as { id: string; display_code: string }[]
    const project = projects.find(item => item.display_code === 'P01')!
    await page.goto('/')
    await openWorkspaceTab(page, '协议解析与澄清')
    const bytes = Buffer.from('研发备注：本地合成归档验收。', 'utf8')
    await page.getByLabel('选择协议文件').setInputFiles({ name: 'archive-proof.txt', mimeType: 'text/plain', buffer: bytes })
    await expect(page.getByText(/文件文本已提取/)).toBeVisible()
    await page.getByLabel('来源文档编号').fill('ARCHIVE-E2E')
    await page.getByRole('button', { name: '导入并解析', exact: true }).click()
    const download = page.getByRole('link', { name: '下载原件', exact: true })
    await expect(download).toBeVisible()
    const saved = page.waitForEvent('download')
    await download.click()
    const file = await saved
    await file.saveAs(`${evidence}/archive-proof.txt`)
    expect(await readFile(`${evidence}/archive-proof.txt`)).toEqual(bytes)
    await page.screenshot({ path: `${evidence}/archive-original.png`, fullPage: true })
    await openWorkspaceTab(page, '需求清单')
    await page.getByRole('button', { name: /^全部需求 \d+ 条$/ }).click()
    await page.getByLabel('搜索需求').fill('发动机最大扭矩')
    await page.getByRole('button', { name: '查看 REQ-P01-B-003 来源与版本', exact: true }).click()
    await expect(page.getByRole('dialog', { name: '需求来源与版本对比' })).toBeVisible()
    await expect(page.getByText('仅留存正文，未归档原件')).toBeVisible()
    await page.screenshot({ path: `${evidence}/requirement-source-versions.png`, fullPage: true })
    await page.getByRole('button', { name: '关闭详情', exact: true }).click()
    await openWorkspaceTab(page, '型谱选型与变型')
    await page.getByLabel('变型分析基型编号').fill('JX-12A')
    await page.getByRole('button', { name: '运行变型分析', exact: true }).click()
    await expect(page.getByRole('status').filter({ hasText: /变型点/ })).toBeVisible()
    await page.getByRole('button', { name: '关闭变型结果', exact: true }).click()
    const records = await (await request.get(`${base}/projects/${project.id}/engineering-records`)).json() as { id: string; kind: string; display_code?: string; revision: number }[]
    const variant = records.find(item => item.kind === 'variant' && item.display_code === 'V-01')!
    await page.getByRole('button', { name: '查看 V-01 版本', exact: true }).click()
    await expect(page.getByText(`V${variant.revision} · 当前版本`, { exact: true })).toBeVisible()
    await page.getByLabel('工程决策审核意见').fill('已核对当前取力器依据')
    await page.getByRole('button', { name: '确认当前版本', exact: true }).click()
    await expect(page.getByText('当前版本审核已保存；历史审核保留。')).toBeVisible()
    const detail = await (await request.get(`${base}/engineering-records/variant/${variant.id}`)).json()
    expect(detail.confirmations.some((item: { object_revision: number }) => item.object_revision === variant.revision)).toBe(true)
    await page.screenshot({ path: `${evidence}/engineering-history-review.png`, fullPage: true })
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await openWorkspaceTab(page, '评审材料')
    await page.getByRole('button', { name: '生成材料包', exact: true }).click()
    await expect(page.getByRole('heading', { name: '材料准备待办', exact: true })).toBeVisible()
    const handle = page.getByRole('button', { name: /处理：复用决策/ }).first()
    await handle.click()
    await expect(page.getByRole('heading', { level: 1, name: '型谱选型与变型' })).toBeVisible()
    await expect(page.getByText(/已高亮关联记录/)).toBeVisible()
    await expect(page.locator('[data-focus-target="true"]')).toBeVisible()
    await page.screenshot({ path: `${evidence}/blocker-focus.png`, fullPage: true })
    await page.getByRole('button', { name: '返回评审材料', exact: true }).click()
    await expect(page.getByRole('heading', { name: '材料准备待办', exact: true })).toBeVisible()
  } finally {
    const current = await (await request.get(`${base}/system/backup`)).json()
    const restored = await request.post(`${base}/system/restore`, { data: { backup, expected_state_hash: current.sha256, actor: '本地测试工程师', role: 'design_engineer' } })
    expect(restored.ok(), await restored.text()).toBe(true)
  }
})
