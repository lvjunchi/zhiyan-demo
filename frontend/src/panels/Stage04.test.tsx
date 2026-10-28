import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { api } from '../api'
import type { Project, Requirement } from '../types'
import { RequirementsPanel } from './RequirementsPanel'

const project: Project = {id:'p1',display_code:'P01',name:'定制项目',customer:'客户',product:'设备',stage:'requirement_parsing',created_at:'2026-10-23T00:00:00+00:00',updated_at:'2026-10-23T00:00:00+00:00'}
const first: Requirement = {id:'r1',project_id:'p1',display_code:'REQ-2',category:'B',parameter_name:'发动机扭矩',data_type:'numeric',operator:'=',value_text:'2600',value_num:2600,value_num_high:null,unit:'N·m',raw_expression:'发动机扭矩2600N·m',source_document_id:'s1',source_location:'3.1',source_excerpt:'发动机扭矩2600N·m',review_status:'draft',validity:'current',current_revision:1,created_at:project.created_at,updated_at:project.updated_at}
const second: Requirement = {...first,id:'r2',display_code:'REQ-1',category:'C',parameter_name:'档位数',unit:'档',value_text:'12',value_num:12}
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

it('sorts, filters by category and locates a stable requirement outside the current review queue', async () => {
  vi.spyOn(api,'listRequirements').mockResolvedValue([first,second,{...first,id:'r3',display_code:'REQ-3',review_status:'confirmed'}])
  const user = userEvent.setup()
  render(<RequirementsPanel project={project} />)
  await screen.findByText('REQ-2',{selector:'td'})
  await user.selectOptions(screen.getByLabelText('需求类别筛选'),'C')
  expect(screen.queryByText('REQ-2',{selector:'td'})).not.toBeInTheDocument()
  await user.selectOptions(screen.getByLabelText('需求类别筛选'),'all')
  await user.selectOptions(screen.getByLabelText('需求排序字段'),'code')
  expect(screen.getAllByRole('row')[1]).toHaveTextContent('REQ-1')
  await user.type(screen.getByLabelText('定位需求编号'),'REQ-3')
  await user.click(screen.getByRole('button',{name:'定位需求'}))
  expect(screen.getByRole('row',{name:/REQ-3/})).toHaveFocus()
  expect(screen.getByRole('button',{name:'全部需求 3 条'})).toHaveAttribute('aria-pressed','true')
})

it('previews exact bulk scope, requires acknowledgement and preserves rejected requirements', async () => {
  let rows: Requirement[] = [first,second,{...first,id:'r3',display_code:'REQ-3',review_status:'rejected'}]
  const bodies: unknown[] = []
  vi.stubGlobal('fetch',vi.fn(async (url:RequestInfo|URL,init?:RequestInit) => {
    if (String(url).endsWith('/batch-preview')) { const body=JSON.parse(String(init?.body)); bodies.push(body); return new Response(JSON.stringify({project_id:'p1',selected_count:2,preview_hash:'a'.repeat(64),can_submit:true,rows:rows.filter(row=>row.id!=='r3').map(row=>({requirement:row,eligible:true,reasons:[]}))})) }
    if (String(url).endsWith('/batch-confirm')) { rows=rows.map(row=>row.id==='r3'?row:{...row,review_status:'confirmed'}); return new Response(JSON.stringify({project_id:'p1',confirmed_count:2,events:[{id:'a1',object_id:'r1',object_revision:1,decision:'confirmed'},{id:'a2',object_id:'r2',object_revision:1,decision:'confirmed'}]})) }
    return new Response(JSON.stringify(rows))
  }))
  const user=userEvent.setup()
  render(<RequirementsPanel project={project} />)
  await screen.findByText('REQ-2',{selector:'td'})
  await user.click(screen.getByRole('button',{name:'预览一键确认范围'}))
  const dialog=await screen.findByRole('dialog',{name:'批量确认需求'})
  expect(await within(dialog).findByText('REQ-1')).toBeVisible()
  expect(within(dialog).queryByText('REQ-3')).not.toBeInTheDocument()
  const submit=within(dialog).getByRole('button',{name:'确认本批次需求'})
  const cancel=within(dialog).getByRole('button',{name:'取消批量确认'})
  expect(submit.compareDocumentPosition(cancel)&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(submit).toBeDisabled()
  await user.click(within(dialog).getByLabelText('我已逐条核对本批次需求'))
  await user.click(submit)
  expect(await screen.findByText(/已批量确认 2 条需求/)).toBeVisible()
  expect(bodies[0]).toEqual({items:[{requirement_id:'r1',expected_revision:1},{requirement_id:'r2',expected_revision:1}]})
  expect(screen.getByRole('button',{name:'已驳回 1 条'})).toBeVisible()
})

it('revises inside a modal, keeps failed input, then shows a new pending revision', async () => {
  let row:Requirement={...first,review_status:'rejected'}
  let writes=0
  vi.spyOn(api,'listRequirements').mockImplementation(async()=>[row])
  vi.spyOn(api,'updateRequirement').mockImplementation(async(_id,payload)=>{if(++writes===1)throw new Error('暂未保存');row={...row,value_text:String(payload.value_text),current_revision:2,review_status:'draft'};return row})
  const user=userEvent.setup()
  render(<RequirementsPanel project={project} />)
  await user.click(await screen.findByRole('button',{name:'已驳回 1 条'}))
  await user.click(screen.getByRole('button',{name:'修订 REQ-2'}))
  const dialog=await screen.findByRole('dialog',{name:'修订需求'})
  await user.clear(within(dialog).getByLabelText('修订后的数值'))
  await user.type(within(dialog).getByLabelText('修订后的数值'),'2800')
  await user.click(within(dialog).getByRole('button',{name:'提交修订'}))
  expect(await within(dialog).findByRole('alert')).toHaveTextContent('暂未保存')
  expect(within(dialog).getByLabelText('修订后的数值')).toHaveValue('2800')
  await user.click(within(dialog).getByRole('button',{name:'提交修订'}))
  expect(await screen.findByText(/已更新为 V2/)).toBeVisible()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getByRole('button',{name:'待审核 1 条'})).toHaveAttribute('aria-pressed','true')
})

it('uses the bottom review chart to filter the queue without changing requirements', async () => {
  vi.spyOn(api,'listRequirements').mockResolvedValue([first,{...second,review_status:'confirmed'}])
  const user=userEvent.setup()
  render(<RequirementsPanel project={project} />)
  const chart=await screen.findByRole('region',{name:'需求审核状态统计'})
  await user.click(within(chart).getByRole('button',{name:'按已确认筛选'}))
  expect(screen.getByText('REQ-1',{selector:'td'})).toBeVisible()
  expect(screen.queryByText('REQ-2',{selector:'td'})).not.toBeInTheDocument()
})
