import { openWorkspaceTab } from '../e2e-support/navigation'
import { expect, test } from '@playwright/test'

test('an engine torque revision updates the derived requirement and blocks stale delivery', async ({ page, request }) => {
  const base = '/api'
  const projects = await (await request.get(`${base}/projects`)).json() as { id: string; display_code: string }[]
  const project = projects.find((item) => item.display_code === 'P01')!
  const requirements = await (await request.get(`${base}/projects/${project.id}/requirements`)).json() as { id: string; parser_key: string; display_code: string; value_text: string }[]
  const engine = requirements.find((item) => item.parser_key === 'engineMaxTorque')!
  expect(engine.value_text).toBe('2600')
  const beforePlan = await (await request.get(`${base}/projects/${project.id}/test-plan`)).json()
  const caseBefore = beforePlan.cases.find((item: { display_code: string }) => item.display_code === 'TC-007')
  const runsBefore = caseBefore.runs
  expect(runsBefore.length).toBeGreaterThan(0)
  await page.goto('/')
  await openWorkspaceTab(page, '需求清单')
  await page.getByRole('button', { name: /^全部需求 \d+ 条$/ }).click()
  await page.getByRole('button', {name: `修订 ${engine.display_code}`, exact:true}).click()
  await page.getByLabel('选择要修订的需求').selectOption(engine.id)
  await page.getByLabel('修订后的数值').fill('2800')
  await page.getByLabel('修订来源说明').fill('发动机最大扭矩 2800 N·m（合成变更 CN-UI）')
  await page.getByRole('button', { name: '提交修订', exact: true }).click()
  const derived = page.getByRole('row').filter({ has: page.getByRole('cell', { name: 'REQ-P01-C-002', exact: true }) })
  await expect(derived).toContainText('2800')
  await expect(derived).toContainText('草案')
  await expect(derived).toContainText('2')
  await openWorkspaceTab(page, '设计成果')
  await expect(page.getByText('评审输入或内容已变化，请重新生成并复核确认。')).toBeVisible()
  await expect(page.getByText('DFMEA 输入或内容已变化，请重新生成并复核确认。')).toBeVisible()
  await openWorkspaceTab(page, '项目总览')
  await expect(page.getByRole('region', { name: '项目实时指标' }).getByLabel('有效用例覆盖率')).toContainText('80%')
  await openWorkspaceTab(page, '评审材料')
  await page.getByRole('button', { name: '生成材料包', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: '已生成草稿' })).toBeVisible()
  await expect(page.getByRole('region', { name: '当前材料准备' })).toContainText(/阻断\s*[1-9]/)
  await expect(page.getByRole('button', { name: '核对哈希后批准', exact: true })).toHaveCount(0)
  const packages = await (await request.get(`${base}/projects/${project.id}/material-packages`)).json()
  const latest = await (await request.get(`${base}/material-packages/${packages[0].id}`)).json()
  expect(latest.status).toBe('draft')
  expect(latest.gate.blockers.some((item: { code: string }) => item.code === 'COVERAGE_INCOMPLETE')).toBe(true)
  const afterPlan = await (await request.get(`${base}/projects/${project.id}/test-plan`)).json()
  const caseAfter = afterPlan.cases.find((item: { id: string }) => item.id === caseBefore.id)
  expect(caseAfter.validity).toBe('stale')
  expect(caseAfter.runs).toEqual(runsBefore)
  await page.screenshot({ path: `${process.env.ZHIYAN_EVIDENCE_DIR ?? 'test-results/screenshots'}/change-blocked-package.png`, fullPage: true })
})
