import { openWorkspaceTab } from '../e2e-support/navigation'
import { expect, test } from '@playwright/test'

const apiBase = process.env.ZHIYAN_E2E_API_BASE ?? 'http://127.0.0.1:8000'

test('loads requirements, confirms one, and surfaces a revision conflict', async ({
  page,
  request,
}) => {
  const projectResponse = await request.post(`${apiBase}/api/projects`, {
    data: {
      display_code: 'P01',
      name: '法士特—陕汽定制项目试点',
      customer: '陕汽集团',
      product: '重型商用车变速器',
    },
  })
  expect(projectResponse.status()).toBe(201)
  const project = await projectResponse.json()

  const sourceResponse = await request.post(
    `${apiBase}/api/projects/${project.id}/source-documents`,
    {
      data: {
        display_code: 'DOC-P01-001',
        doc_type: 'protocol',
        version: 'V1',
        content: '3.1 发动机最大扭矩 2600 N·m。4.2 12 档 AMT。',
        mode: 'manual',
      },
    },
  )
  expect(sourceResponse.status()).toBe(201)
  const source = await sourceResponse.json()

  const firstRequirementResponse = await request.post(
    `${apiBase}/api/projects/${project.id}/requirements`,
    {
      data: {
        display_code: 'REQ-P01-B-003',
        category: 'B',
        parameter_name: '发动机最大扭矩',
        data_type: 'numeric',
        operator: '=',
        value_text: '2600',
        unit: 'N·m',
        raw_expression: '发动机最大扭矩 2600 N·m',
        source_document_id: source.id,
        source_location: '§3.1',
        source_excerpt: '发动机最大扭矩 2600 N·m',
      },
    },
  )
  expect(firstRequirementResponse.status()).toBe(201)

  const secondRequirementResponse = await request.post(
    `${apiBase}/api/projects/${project.id}/requirements`,
    {
      data: {
        display_code: 'REQ-P01-C-001',
        category: 'C',
        parameter_name: '档位数',
        data_type: 'numeric',
        operator: '=',
        value_text: '12',
        unit: '档',
        raw_expression: '12 档 AMT',
        source_document_id: source.id,
        source_location: '§4.2',
        source_excerpt: '12 档 AMT',
      },
    },
  )
  expect(secondRequirementResponse.status()).toBe(201)
  const secondRequirement = await secondRequirementResponse.json()

  await page.goto('/')

  await expect(
    page.getByRole('heading', { name: '项目总览' }),
  ).toBeVisible()
  await expect(page.getByText('法士特—陕汽定制项目试点')).toBeVisible()
  await expect(page.getByRole('region', { name: '项目实时指标' }).getByLabel('需求总量')).toBeVisible()

  await openWorkspaceTab(page, '需求清单')

  const firstRow = page.getByRole('row', { name: /REQ-P01-B-003/ })
  await expect(firstRow.getByText('草案')).toBeVisible()
  await firstRow
    .getByRole('button', { name: '确认 REQ-P01-B-003' })
    .click()
  await expect(firstRow.getByText('已确认')).toBeVisible()

  const staleUpdate = await request.patch(
    `${apiBase}/api/requirements/${secondRequirement.id}`,
    {
      data: {
        expected_revision: 1,
        value_text: '2800',
      },
    },
  )
  expect(staleUpdate.status()).toBe(200)

  const secondRow = page.getByRole('row', { name: /REQ-P01-C-001/ })
  await expect(secondRow.getByText('草案')).toBeVisible()
  await secondRow
    .getByRole('button', { name: '确认 REQ-P01-C-001' })
    .click()
  await expect(page.getByText(/版本冲突/)).toBeVisible()
  await expect(secondRow.getByText('草案')).toBeVisible()

  await page.screenshot({
    path: '../docs/test-evidence/2026-10-19/UI-D/e2e-workbench.png',
    fullPage: true,
  })
})

test('opens the material package tab and shows draft gate blockers', async ({
  page,
  request,
}) => {
  const projectResponse = await request.get(`${apiBase}/api/projects`)
  expect(projectResponse.ok()).toBe(true)
  const projects = await projectResponse.json() as { id: string; display_code: string }[]
  const project = projects.find((item) => item.display_code === 'P01')!
  expect(project).toBeDefined()


  await page.goto('/')
  await expect(page.getByRole('combobox', { name: '选择项目' })).toHaveCount(0)
  await page
    .getByRole('tab', { name: '评审材料', exact: true })
    .click()

  await expect(
    page.getByRole('heading', { name: '评审材料包' }),
  ).toBeVisible()
  await expect(page.getByText('尚无材料包。')).toBeVisible()

  await page.getByRole('button', { name: '生成材料包' }).click()

  await expect(
    page.getByText(/已生成草稿：仍有阻断项/),
  ).toBeVisible()
  await expect(
    page.getByRole('heading', { name: '当前材料准备' }),
  ).toBeVisible()
  await expect(
    page.getByText('当前为草稿，可下载供核对。处理待办后请重新生成材料包，再检查提交条件。'),
  ).toBeVisible()
  await expect(page.getByRole('heading', { name: '材料准备待办', exact: true })).toBeVisible()

  await page.screenshot({
    path: '../docs/test-evidence/2026-10-19/UI-D/e2e-package-draft.png',
    fullPage: true,
  })
})

test('opens all nine workspace tabs against real backend state', async ({
  page,
  request,
}) => {
  const projectResponse = await request.get(`${apiBase}/api/projects`)
  expect(projectResponse.ok()).toBe(true)
  const projects = await projectResponse.json() as { id: string; display_code: string }[]
  const project = projects.find((item) => item.display_code === 'P01')!
  expect(project).toBeDefined()


  const sourceResponse = await request.post(
    `${apiBase}/api/projects/${project.id}/source-documents`,
    {
      data: {
        display_code: 'DOC-SMOKE-001',
        doc_type: 'protocol',
        version: 'V1',
        content: '4.1 换挡方式为 AMT。',
        mode: 'manual',
      },
    },
  )
  expect(sourceResponse.status()).toBe(201)
  const source = await sourceResponse.json()

  const requirementResponse = await request.post(
    `${apiBase}/api/projects/${project.id}/requirements`,
    {
      data: {
        display_code: 'REQ-P01-A-001',
        category: 'A',
        parameter_name: '换挡方式',
        data_type: 'text',
        operator: '=',
        value_text: 'AMT',
        unit: '',
        raw_expression: '换挡方式为 AMT',
        source_document_id: source.id,
        source_location: '§4.1',
        source_excerpt: '换挡方式为 AMT',
      },
    },
  )
  expect(requirementResponse.status()).toBe(201)

  await page.goto('/')
  await expect(page.getByRole('combobox', { name: '选择项目' })).toHaveCount(0)
  await expect(
    page.getByRole('heading', { name: '法士特—陕汽定制项目试点' }),
  ).toBeVisible()

  const tabs: { tab: string; heading: string; loaded: string }[] = [
    {
      tab: '需求清单',
      heading: '结构化需求',
      loaded: 'REQ-P01-A-001',
    },
    {
      tab: '协议解析与澄清',
      heading: '来源文档导入与规则解析',
      loaded: '暂无问题记录。',
    },
    {
      tab: '型谱选型与变型',
      heading: '型谱 Top-3',
      loaded: '评分由已确认需求与受控型谱候选计算',
    },
    {
      tab: '设计成果',
      heading: '相似项目',
      loaded: '尚未生成设计评审清单。',
    },
    {
      tab: '试验验证与追溯',
      heading: '试验方案与用例',
      loaded: '尚未生成试验方案。',
    },
    {
      tab: '样件检验',
      heading: '样件交付与比对',
      loaded: '暂无样件交付记录。',
    },
    {
      tab: '一致性检测',
      heading: '一致性检查（引擎 1）',
      loaded: '项目尚无一致性检查报告。',
    },
    {
      tab: '协同风险',
      heading: '协同看板（引擎 2）',
      loaded: '最高风险',
    },
    {
      tab: '评审材料',
      heading: '评审材料包',
      loaded: '当前材料准备',
    },
  ]

  for (const item of tabs) {
    await page.getByRole('tab', { name: item.tab }).click()
    await expect(
      page.getByRole('heading', { name: item.heading }),
    ).toBeVisible()
    await expect(
      page.getByText(item.loaded, { exact: false }).first(),
    ).toBeVisible()
    if (item.tab === '评审材料') {
      await expect(page.getByRole('heading', { name: '材料准备待办', exact: true })).toBeVisible()
      await expect(page.getByRole('region', { name: '当前材料准备' })).toContainText('阻断')
      await expect(page.getByText('当前为草稿，可下载供核对。处理待办后请重新生成材料包，再检查提交条件。')).toBeVisible()
    } else {
      await expect(page.getByRole('alert')).toHaveCount(0)
    }
  }

  await page.screenshot({
    path: '../docs/test-evidence/2026-10-19/UI-D/e2e-all-tabs.png',
    fullPage: true,
  })
})
