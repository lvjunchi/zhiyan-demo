import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import type { Requirement } from '../types'
import { RequirementReviewChart } from './RequirementReviewChart'

const row:Requirement={id:'r1',project_id:'p1',display_code:'REQ-1',category:'C',parameter_name:'档位数',data_type:'numeric',operator:'=',value_text:'12',value_num:12,value_num_high:null,unit:'档',raw_expression:'12档',source_document_id:null,source_location:'',source_excerpt:'12档',review_status:'confirmed',validity:'current',current_revision:1,created_at:'2026-10-25T00:00:00+00:00',updated_at:'2026-10-25T00:00:00+00:00'}

it('counts review states once and reports stale validity separately with working filters',async()=>{
 const onFilter=vi.fn(),user=userEvent.setup()
 render(<RequirementReviewChart rows={[row,{...row,id:'r2',validity:'stale'},{...row,id:'r3',review_status:'draft'},{...row,id:'r4',review_status:'pending_review'},{...row,id:'r5',review_status:'rejected'}]} onFilter={onFilter} unavailable={false}/>)
 expect(screen.getByRole('img',{name:'需求审核分布：待审核2条，已确认2条，已驳回1条'})).toBeVisible()
 expect(screen.getByText('已确认占比 40%')).toBeVisible()
 expect(screen.getByText('1 条待复核')).toBeVisible()
 for(const [label,key] of [['待审核','pending'],['已确认','confirmed'],['已驳回','rejected']]){
  await user.click(screen.getByRole('button',{name:`按${label}筛选`}))
  expect(onFilter).toHaveBeenLastCalledWith(key)
 }
 await user.click(screen.getByRole('button',{name:'查看全部需求'}))
 expect(onFilter).toHaveBeenLastCalledWith('all')
})

it('does not present empty or unavailable data as 100% confirmed',()=>{
 const {rerender}=render(<RequirementReviewChart rows={[]} onFilter={()=>{}} unavailable={false}/>)
 expect(screen.getByText('暂无需求')).toBeVisible()
 expect(screen.queryByText(/已确认占比/)).not.toBeInTheDocument()
 expect(screen.queryByRole('img')).not.toBeInTheDocument()
 rerender(<RequirementReviewChart rows={[row]} onFilter={()=>{}} unavailable/>)
 expect(screen.getByText('统计暂不可用，请先刷新需求列表。')).toBeVisible()
 expect(screen.getByRole('button',{name:'查看全部需求'})).toBeDisabled()
 expect(screen.queryByRole('img')).not.toBeInTheDocument()
 expect(screen.queryByText(/已确认占比/)).not.toBeInTheDocument()
})
