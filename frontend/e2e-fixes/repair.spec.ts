import { openWorkspaceTab } from '../e2e-support/navigation'
import { test, expect } from '@playwright/test'

test.describe.configure({ mode: 'serial' })
let backup: Record<string, unknown>
test.beforeEach(async ({ request }) => {
  const response = await request.get('/api/system/backup')
  expect(response.ok()).toBe(true)
  backup = await response.json()
})
test.afterEach(async ({ request }) => {
  const current = await (await request.get('/api/system/backup')).json()
  const restored = await request.post('/api/system/restore', { data: {
    backup, expected_state_hash: current.sha256, actor: '浏览器回归工程师', role: '演示角色',
  } })
  expect(restored.ok(), await restored.text()).toBe(true)
})

test('opening design reads existing artifacts and similarity runs only on a click', async ({ page }) => {
  const writes: string[] = []
  page.on('request', request => { if (request.method() === 'POST') writes.push(request.url()) })
  await page.goto('/')
  await openWorkspaceTab(page, '设计成果')
  await expect(page.getByRole('button', { name: '预览设计评审' })).toBeVisible()
  expect(writes).toEqual([])
  await page.getByRole('button', { name: '重新计算相似项目', exact: true }).click()
  await expect(page.getByRole('dialog', { name: '相似项目匹配结果' })).toBeVisible()
  await expect.poll(() => writes.filter(url => url.endsWith('/similar-projects')).length).toBe(1)
})

test('a new FMEA version makes its linked test stale and prevents a ready package', async ({ page, request }) => {
  const [project] = await (await request.get('/api/projects')).json()
  const plan = await (await request.get(`/api/projects/${project.id}/test-plan`)).json()
  const linked = plan.cases.find((row: { fmea_refs: unknown[] }) => row.fmea_refs.length > 0)
  const ref = linked.fmea_refs[0]
  const edit = await request.patch(`/api/fmea-items/${ref.fmea_item_id}`, { data: {
    expected_revision: ref.revision, actor: '浏览器回归工程师', role: '演示角色', action_text: '补充接口疲劳验证措施',
  } })
  expect(edit.ok(), await edit.text()).toBe(true)
  const updated = await (await request.get(`/api/projects/${project.id}/test-plan`)).json()
  const current = updated.cases.find((row: { id: string }) => row.id === linked.id)
  expect(current.validity).toBe('stale')
  expect(current.review_status).toBe('confirmed')
  expect(current.runs).toEqual(linked.runs)
  const pack = await (await request.post(`/api/projects/${project.id}/material-packages`, { data: {} })).json()
  expect(pack.status).toBe('draft')
  await page.goto('/')
  await openWorkspaceTab(page, '试验验证与追溯')
  await expect(page.locator(`[data-object-id="${linked.id}"]`).first()).toContainText('待复核')
  await expect(page.getByText(/方案引用的需求或 FMEA 已变化/)).toBeVisible()
})

test('sample evidence edits persist with history and reject an old observed version', async ({ page, request }) => {
  const [project] = await (await request.get('/api/projects')).json()
  const [delivery] = await (await request.get(`/api/projects/${project.id}/sample-deliveries`)).json()
  const endpoint = `/api/sample-deliveries/${delivery.id}/comparison`
  const before = await (await request.get(endpoint)).json()
  const payload = {
    expected_revision: before.comparison.revision, actor: '浏览器回归工程师', role: '演示角色',
    parameters: before.comparison.findings.filter((row: { parameter_key: string }) => row.parameter_key !== 'visualCheck')
      .map((row: { parameter_key: string; measured_value: number; unit: string }) => ({ parameter_key: row.parameter_key, measured_value: row.measured_value, unit: row.unit })),
    visual_check: before.comparison.visual_check, evidence: '补充测量原始记录 BROWSER-TR-02',
  }
  const response = await request.post(endpoint, { data: payload })
  expect(response.ok(), await response.text()).toBe(true)
  const after = await response.json()
  expect(after.comparison.revision).toBe(before.comparison.revision + 1)
  expect(after.versions.find((row: { revision: number }) => row.revision === before.comparison.revision).snapshot.evidence).toBe(before.comparison.evidence)
  expect((await request.post(endpoint, { data: { ...payload, evidence: '旧页面覆盖' } })).status()).toBe(409)
  await page.goto('/')
  await openWorkspaceTab(page, '样件检验')
  await page.getByRole('button', { name: '查看 / 比对', exact: true }).first().click()
  await expect(page.getByRole('dialog')).toContainText('BROWSER-TR-02')
})

test('new collaboration records require recalculation and a new risk acceptance', async ({ page, request }) => {
  const [project] = await (await request.get('/api/projects')).json()
  const overview = await (await request.get(`/api/projects/${project.id}/coordination-overview`)).json()
  const topic = overview.topics[0]
  const added = await request.post(`/api/coordination-topics/${topic.id}/records`, { data: {
    external_id: 'BROWSER-REOPEN-5', record_type: 'reopened', sender: 'S-02', sent_at: topic.window_end, content_summary: '已接受风险后再次重开',
  } })
  expect(added.ok(), await added.text()).toBe(true)
  expect((await added.json()).latest_metrics.validity).toBe('stale')
  const draft = await (await request.post(`/api/projects/${project.id}/material-packages`, { data: {} })).json()
  expect(draft.status).toBe('draft')
  expect(draft.gate.blockers.some((row: { code: string }) => row.code === 'COORDINATION_METRICS_STALE')).toBe(true)
  await page.goto('/')
  await openWorkspaceTab(page, '协同风险')
  await expect(page.getByText(/沟通记录已变化，指标待重算/)).toBeVisible()
  await expect(page.getByRole('button', { name: '接受风险', exact: true })).toHaveCount(0)
  await page.getByLabel(`工时 ${topic.display_code}`).fill('6')
  await page.getByLabel(`费率 ${topic.display_code}`).fill('200')
  await page.getByRole('button', { name: '重算指标', exact: true }).click()
  await expect(page.getByRole('button', { name: '接受风险', exact: true })).toBeVisible()
  await page.getByLabel(`风险接受理由 ${topic.display_code}`).fill('已核对新增重开，继续跟踪供应商交期')
  await page.getByRole('button', { name: '接受风险', exact: true }).click()
  await expect(page.getByRole('button', { name: '已接受风险', exact: true })).toBeDisabled()
  expect((await (await request.post(`/api/projects/${project.id}/material-packages`, { data: {} })).json()).status).toBe('ready_to_submit')
})
