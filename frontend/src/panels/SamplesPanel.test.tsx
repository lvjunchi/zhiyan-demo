import { api, ApiError } from '../api'
import { emptyWorkflow,emptyProgress } from '../test/workflowFixture'
import { waitFor, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import type {
  SampleComparison,
  SampleDelivery,
} from '../types'
import { SamplesPanel } from './SamplesPanel'
import { DEMO_SAMPLE } from '../demoInputs'

const delivery: SampleDelivery = {
  id: 'sd1',
  project_id: 'p1',
  display_code: 'SD-P01-001',
  supplier: '陕汽样件厂',
  part_display_code: 'P-100',
  drawing_display_code: 'DWG-100',
  drawing_revision: 'A',
  delivered_at: '2026-10-18',
  quantity: 2,
  notes: '合成样件',
  mode: 'manual',
  source_label: '样件交付登记',
  drawing_parameters: [
    {
      id: 'dp1',
      parameter_key: 'bore',
      parameter_name: '内孔直径',
      expected_value: 120,
      tolerance: 0.05,
      unit: 'mm',
      source_note: '图纸尺寸 120±0.05',
    },
  ],
  file_uploaded: false,
  file: null,
  created_at: '2026-10-19T00:00:00+00:00',
  updated_at: '2026-10-19T00:00:00+00:00',
}

const comparison: SampleComparison = {
  comparison: {
    id: 'sc1',
    project_id: 'p1',
    sample_id: 'sd1',
    display_code: 'SC-P01-001',
    revision: 1,
    status: 'draft',
    mode: 'manual',
    overall_result: 'pass',
    findings: [
      {
        parameter_key: 'bore',
        parameter_name: '内孔直径',
        expected_value: 120,
        tolerance: 0.05,
        measured_value: 120.02,
        unit: 'mm',
        result: 'pass',
        reason: '|120.02 - 120| = 0.02 ≤ 0.05',
      },
    ],
    visual_check: {
      mode: 'manual',
      result: 'pass',
      note: '合成样件外观检查',
    },
    evidence: '三坐标测量报告 T-01',
    created_at: '2026-10-19T00:00:00+00:00',
    updated_at: '2026-10-19T00:00:00+00:00',
  },
  issues: [],
  confirmations: [],
  mode: 'manual',
  source_label: '样件比对',
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response
}

beforeEach(()=>{vi.spyOn(api,'getWorkflowSummary').mockResolvedValue(emptyWorkflow);vi.spyOn(api,'getCoordinationProgress').mockImplementation(async(topicId)=>emptyProgress(topicId))})
afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('SamplesPanel', () => {
  it('prefills only matching synthetic measurements and evidence, preserves edits during upload and collapses the uploaded original',async()=>{
    const sample={...delivery,drawing_parameters:Object.entries(DEMO_SAMPLE.measurements).map(([key,p])=>({id:key,parameter_key:key,parameter_name:key==='holePosition'?'孔位':'轴径',expected_value:p.expected,tolerance:p.tolerance,unit:p.unit,source_note:'05合成样例'}))}
    const uploaded={...sample,file_uploaded:true,file:{file_name:'07_样件尺寸示意.svg',content_hash:'a'.repeat(64),content_type:'image/svg+xml',size_bytes:794,uploaded_by:'test',uploaded_at:delivery.created_at}}
    vi.spyOn(api,'listSampleDeliveries').mockResolvedValueOnce([sample]).mockResolvedValue([uploaded])
    vi.spyOn(api,'getSampleComparison').mockRejectedValue(new ApiError(404,'not_found','未比对'))
    vi.spyOn(api,'uploadSampleFile').mockResolvedValue(uploaded)
    const save=vi.spyOn(api,'createSampleComparison')
    const user=userEvent.setup();render(<SamplesPanel projectId="p1"/>);
    await user.click(await screen.findByRole('button',{name:'查看 / 比对'}))
    expect(await screen.findByLabelText('实测 孔位')).toHaveValue(120.2)
    expect(screen.getByLabelText('实测 轴径')).toHaveValue(45.01)
    expect(screen.getByLabelText('比对证据')).toHaveValue('合成尺寸记录DEMO-MEASURE-001')
    await user.clear(screen.getByLabelText('实测 孔位'));await user.type(screen.getByLabelText('实测 孔位'),'120.3')
    await user.clear(screen.getByLabelText('比对证据'));await user.type(screen.getByLabelText('比对证据'),'人工改写证据')
    await user.upload(screen.getByLabelText('选择样件文件'),new File(['synthetic'],'07_样件尺寸示意.svg',{type:'image/svg+xml'}))
    await user.click(screen.getByRole('button',{name:'上传样件文件'}))
    expect(await screen.findByRole('link',{name:'下载样件原件'})).toHaveAttribute('href','/api/sample-deliveries/sd1/file')
    expect(screen.queryByLabelText('选择样件文件')).not.toBeInTheDocument()
    expect(screen.queryByRole('button',{name:'上传样件文件'})).not.toBeInTheDocument()
    expect(screen.getByLabelText('实测 孔位')).toHaveValue(120.3)
    expect(screen.getByLabelText('比对证据')).toHaveValue('人工改写证据')
    expect(save).not.toHaveBeenCalled()
  })
  it('selects a real local demo original or dropped file without registering or uploading automatically',async()=>{
    vi.spyOn(api,'listSampleDeliveries').mockResolvedValue([])
    const create=vi.spyOn(api,'createSampleDelivery')
    const upload=vi.spyOn(api,'uploadSampleFile')
    const fetchMock=vi.fn().mockResolvedValue({ok:true,headers:new Headers({'Content-Type':'image/svg+xml'}),arrayBuffer:async()=>new TextEncoder().encode('<svg/>').buffer})
    vi.stubGlobal('fetch',fetchMock)
    const user=userEvent.setup();render(<SamplesPanel projectId="p1"/>);
    await user.click(screen.getByRole('button',{name:'使用演示图纸'}))
    expect(await screen.findByText('已选择：07_样件尺寸示意.svg')).toBeVisible()
    expect(fetchMock).toHaveBeenCalledWith('/demo/sample-dimensions.svg')
    const zone=screen.getByRole('group',{name:'登记原件拖放区'})
    fireEvent.drop(zone,{dataTransfer:{files:[new File(['drop'],'拖入图纸.pdf',{type:'application/pdf'})]}})
    expect(screen.getByText('已选择：拖入图纸.pdf')).toBeVisible()
    fireEvent.drop(zone,{dataTransfer:{files:[new File(['a'],'a.pdf'),new File(['b'],'b.pdf')]}})
    expect(screen.getByRole('alert')).toHaveTextContent('每次请选择一个文件')
    expect(screen.getByText('已选择：拖入图纸.pdf')).toBeVisible()
    expect(create).not.toHaveBeenCalled();expect(upload).not.toHaveBeenCalled()
  })
  it('keeps a registered delivery after upload failure and clears the registration draft before retrying only the upload',async()=>{
    let created=false
    vi.spyOn(api,'listSampleDeliveries').mockImplementation(async()=>created?[delivery]:[])
    const create=vi.spyOn(api,'createSampleDelivery').mockImplementation(async()=>{created=true;return delivery})
    vi.spyOn(api,'getSampleComparison').mockResolvedValue(comparison)
    const upload=vi.spyOn(api,'uploadSampleFile').mockRejectedValueOnce(new Error('上传暂时失败')).mockResolvedValue(delivery)
    const user=userEvent.setup();render(<SamplesPanel projectId="p1"/>)
    await screen.findByText('暂无样件交付记录。')
    await user.click(screen.getByRole('button',{name:'填入样件合成样例'}))
    const input=screen.getByLabelText('登记时选择样件文件') as HTMLInputElement
    await user.upload(input,new File(['synthetic'],'sample.svg',{type:'image/svg+xml'}))
    await user.click(screen.getByRole('button',{name:'登记并上传文件'}))
    const dialog=await screen.findByRole('dialog')
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('交付已登记')
    expect(input.files).toHaveLength(0)
    expect(screen.getByLabelText('样件供应商')).toHaveValue('')
    await user.click(within(dialog).getByRole('button',{name:'上传样件文件'}))
    await within(dialog).findByText('样件文件已上传并记录 SHA-256')
    expect(create).toHaveBeenCalledTimes(1);expect(upload).toHaveBeenCalledTimes(2)
  })
  it('shows upload before registration and fills labelled sample data without submitting',async()=>{
    vi.spyOn(api,'listSampleDeliveries').mockResolvedValue([])
    const save=vi.spyOn(api,'createSampleDelivery')
    const user=userEvent.setup();render(<SamplesPanel projectId="p1"/>)
    await user.click(screen.getByRole('button',{name:'填入样件合成样例'}))
    expect(screen.getByLabelText('样件供应商')).toHaveValue('合成样件提供方')
    expect((screen.getByLabelText('图纸参数') as HTMLTextAreaElement).value).toContain('holePosition|孔位|120|0.5|mm')
    expect(screen.getByLabelText('登记时选择样件文件')).toBeVisible()
    expect(screen.getByRole('button',{name:'登记并上传文件'})).toBeVisible()
    expect(save).not.toHaveBeenCalled()
  })
  it('submits the existing comparison revision for a new measurement report',async()=>{
    vi.spyOn(api,'listSampleDeliveries').mockResolvedValue([delivery])
    vi.spyOn(api,'getSampleComparison').mockResolvedValue(comparison)
    const save=vi.spyOn(api,'createSampleComparison').mockResolvedValue({...comparison,comparison:{...comparison.comparison,revision:2}})
    const user=userEvent.setup();render(<SamplesPanel projectId="p1"/>)
    await user.click(await screen.findByRole('button',{name:'查看 / 比对'}))
    await screen.findByRole('table',{name:'样件比对结果'})
    await user.click(screen.getByRole('button',{name:'记录复检'}))
    await user.type(screen.getByRole('spinbutton',{name:'实测 内孔直径'}),'120.02')
    await user.type(screen.getByLabelText('比对证据'),'合成复检记录')
    await user.click(screen.getByRole('button',{name:'提交比对'}))
    await waitFor(()=>expect(save).toHaveBeenCalledWith('sd1',expect.objectContaining({expected_revision:1})))
  })

  it('keeps the saved comparison review distinct from a failed readback', async () => {
    let reads = 0, writes = 0
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') { writes++; return jsonResponse({ id: 'saved-comparison-review' }) }
      if (String(input).endsWith('/sample-deliveries')) return jsonResponse([delivery])
      if (++reads === 2) throw new Error('比对暂不可读')
      return jsonResponse(reads > 2 ? { ...comparison, comparison: { ...comparison.comparison, status: 'confirmed' } } : comparison)
    }))
    const user = userEvent.setup()
    render(<SamplesPanel projectId="p1" />)
    await user.click(await screen.findByRole('button', { name: '查看 / 比对' }))
    const dialog = screen.getByRole('dialog')
    await user.click(await within(dialog).findByRole('button', { name: '确认比对' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('样件比对审核已保存，但页面刷新失败')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '重新读取已保存结果' }))
    await user.click(screen.getByRole('button',{name:'查看 / 比对'}))
    expect(screen.queryByRole('button', { name: '确认比对' })).not.toBeInTheDocument()
    expect(writes).toBe(1)
  })
  it('closes a successfully confirmed comparison and returns focus, but keeps a failed confirmation open',async()=>{
    vi.spyOn(api,'listSampleDeliveries').mockResolvedValue([delivery])
    vi.spyOn(api,'getSampleComparison').mockResolvedValue(comparison)
    const confirm=vi.spyOn(api,'confirmSampleComparison').mockRejectedValueOnce(new Error('确认未保存')).mockResolvedValue({id:'confirmation',actor:'演示工程师',role:'engineer',decision:'confirmed',comment:'合成核对',created_at:delivery.created_at})
    const user=userEvent.setup();render(<SamplesPanel projectId="p1"/>);
    const trigger=await screen.findByRole('button',{name:'查看 / 比对'})
    await user.click(trigger);await user.click(await screen.findByRole('button',{name:'确认比对'}))
    expect(await screen.findByRole('alert')).toHaveTextContent('确认未保存')
    expect(screen.getByRole('dialog')).toBeVisible()
    await user.click(screen.getByRole('button',{name:'确认比对'}))
    await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(trigger).toHaveFocus();expect(confirm).toHaveBeenCalledTimes(2)
  })
  it('uses one saved comparison table and never replaces its baseline with current drawing values', async () => {
    const changedDrawing = { ...delivery, drawing_revision: 'B', drawing_parameters: [{ ...delivery.drawing_parameters[0], expected_value: 999, tolerance: 9, unit: 'cm', source_note: '修订后的登记来源' }] }
    vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL) => jsonResponse(String(url).endsWith('/comparison') ? comparison : [changedDrawing])))
    const user = userEvent.setup()
    render(<SamplesPanel projectId="p1" />)
    await user.click(await screen.findByRole('button', { name: '查看 / 比对' }))
    const dialog = await screen.findByRole('dialog', { name: '样件明细：SD-P01-001' })
    const table = await within(dialog).findByRole('table', { name: '样件比对结果' })
    expect(within(dialog).getAllByRole('table')).toHaveLength(1)
    expect(within(table).getByRole('cell', { name: '120' })).toBeInTheDocument()
    expect(within(table).getByRole('cell', { name: 'mm' })).toBeInTheDocument()
    expect(within(table).queryByRole('cell', { name: '999' })).not.toBeInTheDocument()
    const sources = within(dialog).getByRole('group', { name: '登记图纸来源' })
    await user.click(within(sources).getByText(/查看登记图纸来源/))
    expect(within(sources).getByText(/修订后的登记来源/)).toBeVisible()
    expect(within(dialog).queryByLabelText('实测 内孔直径')).not.toBeInTheDocument()
  })
  it('collects new measurements beside the expected value, tolerance, unit and source in one table', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: RequestInfo | URL) => String(url).endsWith('/comparison') ? jsonResponse({}, 404) : jsonResponse([delivery])))
    const user = userEvent.setup()
    render(<SamplesPanel projectId="p1" />)
    await user.click(await screen.findByRole('button', { name: '查看 / 比对' }))
    const dialog = screen.getByRole('dialog', { name: '样件明细：SD-P01-001' })
    const table = await within(dialog).findByRole('table', { name: '样件参数与实测' })
    expect(within(dialog).getAllByRole('table')).toHaveLength(1)
    expect(table).toHaveTextContent('120')
    expect(table).toHaveTextContent('±0.05')
    expect(table).toHaveTextContent('图纸尺寸 120±0.05')
    await user.type(within(table).getByLabelText('实测 内孔直径'), '120.02')
    expect(within(table).getByLabelText('实测 内孔直径')).toHaveValue(120.02)
  })
  it('shows visual inspection as nonnumeric rather than missing measurements', async () => {
    const visual = { ...comparison, comparison: { ...comparison.comparison, findings: [{ parameter_key: 'visualCheck', parameter_name: '目视检查', expected_value: null, tolerance: null, measured_value: null, unit: '', result: 'pass', reason: '人工目视结论：表面完好' }] } }
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => jsonResponse(String(input).endsWith('/comparison') ? visual : [delivery])))
    const user = userEvent.setup()
    render(<SamplesPanel projectId="p1" />)
    await user.click(await screen.findByRole('button', { name: '查看 / 比对' }))
    const table = await screen.findByRole('table', { name: '样件比对结果' })
    expect(within(table).getAllByRole('cell', { name: '不适用' })).toHaveLength(3)
    expect(within(table).queryByText('缺失')).not.toBeInTheDocument()
    expect(screen.getByText(/外观检查（人工判定）：通过/)).toBeInTheDocument()
  })
  it('opens a wide comparison dialog with units and returns focus without submitting', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => jsonResponse(String(input).endsWith('/comparison') ? comparison : [delivery]))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    const { container } = render(<SamplesPanel projectId="p1" />)
    const trigger = await screen.findByRole('button', { name: '查看 / 比对' })
    await user.click(trigger)
    const dialog = await screen.findByRole('dialog', { name: '样件明细：SD-P01-001' })
    expect(dialog).toHaveClass('detail-overlay--wide')
    const table = await within(dialog).findByRole('table', { name: '样件比对结果' })
    expect(table).toHaveTextContent('120.02')
    expect(table).toHaveTextContent('mm')
    expect(table).toHaveTextContent('通过')
    expect(container.querySelector('.result-box')).toBeNull()
    await user.click(within(dialog).getByRole('button', { name: '关闭样件详情' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
    expect(fetchMock.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true)
  })
  it('keeps failed comparison values and evidence in the dialog and on reopening the same sample', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') return jsonResponse({ error: { message: '比对保存失败' } }, 503)
      return String(input).endsWith('/comparison') ? jsonResponse({}, 404) : jsonResponse([delivery])
    }))
    const user = userEvent.setup()
    render(<SamplesPanel projectId="p1" />)
    const trigger = await screen.findByRole('button', { name: '查看 / 比对' })
    await user.click(trigger)
    const dialog = await screen.findByRole('dialog', { name: '样件明细：SD-P01-001' })
    const measured = await within(dialog).findByLabelText('实测 内孔直径')
    await user.type(measured, '120.02')
    await user.type(within(dialog).getByLabelText('比对证据'), '测量报告-重试')
    await user.click(within(dialog).getByRole('button', { name: '提交比对' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('比对保存失败')
    expect(measured).toHaveValue(120.02)
    await user.click(within(dialog).getByRole('button', { name: '关闭样件详情' }))
    await user.click(trigger)
    expect(screen.getByLabelText('实测 内孔直径')).toHaveValue(120.02)
    expect(screen.getByLabelText('比对证据')).toHaveValue('测量报告-重试')
  })
  it('does not offer a new comparison when loading failed and retries the existing result', async () => {
    let reads = 0
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith('/comparison')) return ++reads === 1 ? jsonResponse({ error: { message: '比对档案读取失败' } }, 503) : jsonResponse(comparison)
      return jsonResponse([delivery])
    }))
    const user = userEvent.setup()
    render(<SamplesPanel projectId="p1" />)
    await user.click(await screen.findByRole('button', { name: '查看 / 比对' }))
    const dialog = await screen.findByRole('dialog', { name: '样件明细：SD-P01-001' })
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('比对档案读取失败')
    expect(within(dialog).queryByRole('button', { name: '提交比对' })).not.toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: '重试加载比对' }))
    expect(await within(dialog).findByRole('table', { name: '样件比对结果' })).toHaveTextContent('120.02')
  })
  it('clears the native file selector when switching to a different sample', async () => {
    const second = { ...delivery, id: 'sd2', display_code: 'SD-P01-002' }
    vi.stubGlobal('fetch', vi.fn(async (url: string) => jsonResponse(url.endsWith('/comparison') ? {} : [delivery, second], url.endsWith('/comparison') ? 404 : 200)))
    const user = userEvent.setup()
    render(<SamplesPanel projectId="p1" />)
    await screen.findByText('SD-P01-002')
    await user.click(screen.getAllByRole('button', { name: '查看 / 比对' })[0])
    await user.upload(screen.getByLabelText('选择样件文件'), new File(['sample-one'], 'sample-one.txt'))
    expect((screen.getByLabelText('选择样件文件') as HTMLInputElement).files).toHaveLength(1)
    await user.click(screen.getByRole('button', { name: '关闭样件详情' }))
    await user.click(screen.getAllByRole('button', { name: '查看 / 比对' })[1])
    await screen.findByRole('heading', { name: '样件明细：SD-P01-002' })
    expect((screen.getByLabelText('选择样件文件') as HTMLInputElement).files).toHaveLength(0)
  })
  it('does not expose the previous project sample while the next project is loading', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url.includes('/p2/')) return new Promise<Response>(() => {})
      return jsonResponse(url.endsWith('/comparison') ? comparison : [delivery])
    }))
    const user = userEvent.setup()
    const { rerender } = render(<SamplesPanel projectId="p1" />)
    await user.click(await screen.findByRole('button', { name: '查看 / 比对' }))
    await screen.findByRole('heading', { name: '样件明细：SD-P01-001' })
    rerender(<SamplesPanel projectId="p2" />)
    expect(screen.queryByRole('heading', { name: '样件明细：SD-P01-001' })).not.toBeInTheDocument()
  })
  it('registers a sample delivery with parsed drawing parameters', async () => {
    let registered = false
    let createBody: unknown

    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url === '/api/projects/p1/sample-deliveries' && !init?.method) {
          return jsonResponse(registered ? [delivery] : [])
        }
        if (
          url === '/api/projects/p1/sample-deliveries' &&
          init?.method === 'POST'
        ) {
          createBody = JSON.parse(String(init.body))
          registered = true
          return jsonResponse(delivery, 201)
        }
        if (
          url === '/api/sample-deliveries/sd1/comparison' &&
          !init?.method
        ) {
          return jsonResponse({ error: { message: '尚未比对' } }, 404)
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<SamplesPanel projectId="p1" />)

    await screen.findByText('暂无样件交付记录。')
    await user.type(
      screen.getByRole('textbox', { name: '样件供应商' }),
      '陕汽样件厂',
    )
    await user.type(
      screen.getByRole('textbox', { name: '样件零件编号' }),
      'P-100',
    )
    await user.type(
      screen.getByRole('textbox', { name: '样件图纸编号' }),
      'DWG-100',
    )
    fireEvent.change(screen.getByLabelText('样件交付日期'), {
      target: { value: '2026-10-18' },
    })
    fireEvent.change(screen.getByLabelText('样件数量'), {
      target: { value: '2' },
    })
    await user.type(
      screen.getByRole('textbox', { name: '图纸参数' }),
      'bore|内孔直径|120|0.05|mm|图纸尺寸 120±0.05',
    )
    await user.click(
      screen.getByRole('button', { name: '登记交付' }),
    )

    expect(
      await screen.findByText('样件交付 SD-P01-001 已登记'),
    ).toBeInTheDocument()
    expect(createBody).toMatchObject({
      supplier: '陕汽样件厂',
      part_display_code: 'P-100',
      drawing_display_code: 'DWG-100',
      drawing_revision: 'A',
      delivered_at: '2026-10-18',
      quantity: 2,
      drawing_parameters: [
        {
          parameter_key: 'bore',
          parameter_name: '内孔直径',
          expected_value: 120,
          tolerance: 0.05,
          unit: 'mm',
          source_note: '图纸尺寸 120±0.05',
        },
      ],
    })
  })

  it('uploads a sample file and confirms the comparison', async () => {
    const uploaded: SampleDelivery = {
      ...delivery,
      file_uploaded: true,
      file: {
        file_name: 'sample.pdf',
        content_type: 'application/pdf',
        content_hash: 'c'.repeat(64),
        size_bytes: 12,
        uploaded_by: '演示工程师',
        uploaded_at: '2026-10-19T01:00:00+00:00',
      },
    }
    let fileUploaded = false
    let comparisonExists = false
    let confirmed = false
    let uploadInit: RequestInit | undefined
    let confirmBody: unknown

    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url === '/api/projects/p1/sample-deliveries' && !init?.method) {
          return jsonResponse([fileUploaded ? uploaded : delivery])
        }
        if (url.startsWith('/api/sample-deliveries/sd1/file?') && init?.method === 'PUT') {
          uploadInit = init
          fileUploaded = true
          return jsonResponse(uploaded)
        }
        if (
          url === '/api/sample-deliveries/sd1/comparison' &&
          !init?.method
        ) {
          return comparisonExists
            ? jsonResponse({
                ...comparison,
                comparison: {
                  ...comparison.comparison,
                  status: confirmed ? 'confirmed' : 'draft',
                },
              })
            : jsonResponse({ error: { message: '尚未比对' } }, 404)
        }
        if (
          url === '/api/sample-deliveries/sd1/comparison' &&
          init?.method === 'POST'
        ) {
          comparisonExists = true
          return jsonResponse(comparison, 201)
        }
        if (
          url === '/api/sample-comparisons/sc1/confirmations' &&
          init?.method === 'POST'
        ) {
          confirmBody = JSON.parse(String(init.body))
          confirmed = true
          return jsonResponse({ id: 'c-compare' }, 201)
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<SamplesPanel projectId="p1" />)

    await screen.findByText('SD-P01-001')
    await user.click(
      screen.getByRole('button', { name: '查看 / 比对' }),
    )
    await screen.findByText('新建比对')

    await user.upload(
      screen.getByLabelText('选择样件文件'),
      new File(['drawing'], 'sample.pdf', {
        type: 'application/pdf',
      }),
    )
    await user.click(
      screen.getByRole('button', { name: '上传样件文件' }),
    )
    expect(
      await screen.findByText('样件文件已上传并记录 SHA-256'),
    ).toBeInTheDocument()
    expect(uploadInit?.method).toBe('PUT')
    expect(uploadInit?.body).toBeInstanceOf(File)
    expect(uploadInit?.headers).toMatchObject({
      'Content-Type': 'application/pdf',
    })
    expect(fetchMock.mock.calls.some(([url]) =>
      String(url).includes(
        'file?file_name=sample.pdf&actor=%E6%BC%94%E7%A4%BA%E5%B7%A5%E7%A8%8B%E5%B8%88',
      ),
    )).toBe(true)

    await user.type(
      screen.getByRole('spinbutton', { name: '实测 内孔直径' }),
      '120.02',
    )
    await user.type(
      screen.getByRole('textbox', { name: '比对证据' }),
      '三坐标测量报告 T-01',
    )
    await user.click(screen.getByRole('button', { name: '提交比对' }))
    await screen.findByText('样件比对 SC-P01-001：通过')

    await user.click(screen.getByRole('button', { name: '确认比对' }))
    expect(
      await screen.findByText('样件比对已确认'),
    ).toBeInTheDocument()
    expect(confirmBody).toMatchObject({
      expected_revision: 1,
      decision: 'confirmed',
    })
  })

  it('loads a delivery, treats a missing comparison as empty, and submits measurements with evidence', async () => {
    let comparisonExists = false
    let comparisonBody: unknown

    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url === '/api/projects/p1/sample-deliveries' && !init?.method) {
          return jsonResponse([delivery])
        }
        if (
          url === '/api/sample-deliveries/sd1/comparison' &&
          !init?.method
        ) {
          return comparisonExists
            ? jsonResponse(comparison)
            : jsonResponse({ error: { message: '尚未比对' } }, 404)
        }
        if (
          url === '/api/sample-deliveries/sd1/comparison' &&
          init?.method === 'POST'
        ) {
          comparisonBody = JSON.parse(String(init.body))
          comparisonExists = true
          return jsonResponse(comparison, 201)
        }
        return jsonResponse({}, 404)
      },
    )
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<SamplesPanel projectId="p1" />)

    await screen.findByText('SD-P01-001')
    await user.click(
      screen.getByRole('button', { name: '查看 / 比对' }),
    )
    expect(await screen.findByText('新建比对')).toBeInTheDocument()
    expect(screen.getByText('内孔直径')).toBeInTheDocument()
    expect(screen.getByText('图纸尺寸 120±0.05')).toBeInTheDocument()

    await user.type(
      screen.getByRole('spinbutton', { name: '实测 内孔直径' }),
      '120.02',
    )
    await user.type(
      screen.getByRole('textbox', { name: '比对证据' }),
      '三坐标测量报告 T-01',
    )
    await user.click(screen.getByRole('button', { name: '提交比对' }))

    expect(
      await screen.findByText('样件比对 SC-P01-001：通过'),
    ).toBeInTheDocument()
    expect(comparisonBody).toMatchObject({
      actor: '演示工程师',
      role: 'design_engineer',
      parameters: [
        { parameter_key: 'bore', measured_value: 120.02, unit: 'mm' },
      ],
      visual_check: {
        mode: 'manual',
        result: 'pass',
        note: '合成样件外观检查',
      },
      evidence: '三坐标测量报告 T-01',
    })
    expect(screen.getByRole('cell', { name: '通过' })).toBeInTheDocument()
  })
})

it('exposes file upload directly from the sample list',async()=>{
 vi.spyOn(api,'listSampleDeliveries').mockResolvedValue([delivery])
 vi.spyOn(api,'getSampleComparison').mockResolvedValue(comparison)
 const user=userEvent.setup();render(<SamplesPanel projectId="p1"/>)
 await user.click(await screen.findByRole('button',{name:`上传文件 ${delivery.display_code}`}))
 expect(await screen.findByLabelText('选择样件文件')).toBeVisible()
})
