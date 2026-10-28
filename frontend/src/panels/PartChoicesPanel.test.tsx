import { render,screen,within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach,expect,it,vi } from 'vitest'
import { api } from '../api'
import { PartChoicesPanel } from './PartChoicesPanel'
import type { PartChoices } from '../types'
afterEach(()=>vi.restoreAllMocks())
const record={kind:'part' as const,id:'p1',project_id:'project',revision:1,review_status:'draft',status:'current',is_applicable:1,part_name:'主箱壳体',part_display_code:'P-03',part_number:'original',base_display_code:'JX-12A',dependency_versions:[]}
const candidate={id:'c1',model_code:'DEMO-P01-3',part_name:'主箱壳体',rated_torque_nm:3000,max_gears:16,material:'合金钢',image_key:'housing',source:'合成候选库V1',fit:'pass' as const,checks:[],limitations:'几何接口需核对'}
const fixture:PartChoices={parts:[{record,candidates:[candidate,{...candidate,id:'c2',model_code:'DEMO-LOW',fit:'fail'}],selected_candidate_id:null,selection_state:'unselected'}],counts:{unselected:1,pending_review:0,confirmed:0,rejected:0,recheck:0},mode:'rule',catalog_source:'合成候选'}
it('shows a candidate comparison, saves the choice and confirms independently',async()=>{
 let current=structuredClone(fixture)
 vi.spyOn(api,'listPartChoices').mockImplementation(async()=>current)
 vi.spyOn(api,'selectPartCandidate').mockImplementation(async()=>{current={...current,parts:[{...current.parts[0],record:{...record,part_number:candidate.model_code,revision:2},selected_candidate_id:'c1',selection_state:'pending_review'}],counts:{...current.counts,unselected:0,pending_review:1}};return current.parts[0].record})
 const review=vi.spyOn(api,'confirmEngineering').mockImplementation(async()=>{current={...current,parts:[{...current.parts[0],record:{...current.parts[0].record,review_status:'confirmed'},selection_state:'confirmed'}],counts:{...current.counts,pending_review:0,confirmed:1}};return {}})
 const user=userEvent.setup();render(<PartChoicesPanel projectId="project" refreshKey={0} onChanged={()=>{}}/>)
 await user.click(await screen.findByRole('button',{name:'选择型号 P-03'}))
 const dialog=screen.getByRole('dialog',{name:'零件候选比选'})
 expect(within(dialog).getByRole('button',{name:'选用 DEMO-LOW'})).toBeDisabled()
 await user.click(within(dialog).getByRole('button',{name:'选用 DEMO-P01-3'}))
 expect(review).not.toHaveBeenCalled()
 await user.click(within(dialog).getByRole('button',{name:'确认选定型号'}))
 expect(review).toHaveBeenCalledWith('part','p1',expect.objectContaining({expected_revision:2,decision:'confirmed'}))
 expect(await screen.findByText('选型审核已保存')).toBeVisible()
 expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
 expect(screen.getByText('✓ 已确认')).toBeVisible()
})
it('explains upstream blockers but allows rejection with a reason',async()=>{
 const current:PartChoices={...fixture,parts:[{...fixture.parts[0],record:{...record,part_number:candidate.model_code},selected_candidate_id:'c1',selection_state:'pending_review',confirmation_blockers:['V-03 取力器接口 V1：上游未确认']} ]}
 vi.spyOn(api,'listPartChoices').mockResolvedValue(current)
 const review=vi.spyOn(api,'confirmEngineering').mockResolvedValue({})
 const user=userEvent.setup();render(<PartChoicesPanel projectId="project" refreshKey={0} onChanged={()=>{}}/>)
 await user.click(await screen.findByRole('button',{name:'选择型号 P-03'}))
 expect(screen.getByText(/V-03 取力器接口 V1/)).toBeVisible()
 expect(screen.getByRole('button',{name:'确认选定型号'})).toBeDisabled()
 expect(screen.getByRole('button',{name:'驳回选定型号'})).toBeDisabled()
 await user.type(screen.getByLabelText('零件选型审核意见'),'安装接口需要修改')
 await user.click(screen.getByRole('button',{name:'驳回选定型号'}))
 expect(review).toHaveBeenCalledWith('part','p1',expect.objectContaining({decision:'rejected',comment:'安装接口需要修改'}))
 expect(await screen.findByText('选型已驳回，修改型号后重新审核')).toBeVisible()
})
it('keeps a failed candidate save in the comparison and allows retry',async()=>{
 vi.spyOn(api,'listPartChoices').mockResolvedValue(fixture)
 const save=vi.spyOn(api,'selectPartCandidate').mockRejectedValue(new Error('版本变化，请重新读取'))
 const user=userEvent.setup();render(<PartChoicesPanel projectId="project" refreshKey={0} onChanged={()=>{}}/>)
 await user.click(await screen.findByRole('button',{name:'选择型号 P-03'}))
 await user.click(screen.getByRole('button',{name:'选用 DEMO-P01-3'}))
 expect(await within(screen.getByRole('dialog')).findByRole('alert')).toHaveTextContent('版本变化')
 expect(save).toHaveBeenCalledTimes(1)
})

it('withdraws a confirmed selection with an optional reason, keeps failed input and closes on success',async()=>{
 let current:PartChoices={...fixture,parts:[{...fixture.parts[0],record:{...record,review_status:'confirmed',part_number:candidate.model_code},selected_candidate_id:'c1',selection_state:'confirmed'}]}
 vi.spyOn(api,'listPartChoices').mockImplementation(async()=>current)
 const review=vi.spyOn(api,'confirmEngineering').mockRejectedValueOnce(new Error('保存失败'))
 const user=userEvent.setup();render(<PartChoicesPanel projectId="project" refreshKey={0} onChanged={()=>{}}/>)
 await user.click(await screen.findByRole('button',{name:'选择型号 P-03'}))
 const button=screen.getByRole('button',{name:'撤回确认并驳回'})
 expect(button).toBeEnabled()
 expect(screen.getByText('撤回原因（选填）')).toBeVisible()
 await user.type(screen.getByLabelText('零件选型审核意见'),'接口需要重新核对')
 await user.click(button)
 expect(await screen.findByRole('alert')).toHaveTextContent('保存失败')
 expect(screen.getByLabelText('零件选型审核意见')).toHaveValue('接口需要重新核对')
 review.mockReset().mockImplementation(async()=>{current={...current,parts:[{...current.parts[0],record:{...current.parts[0].record,review_status:'rejected'},selection_state:'rejected'}]};return {}})
 await user.clear(screen.getByLabelText('零件选型审核意见'))
 await user.click(button)
 expect(review).toHaveBeenCalledWith('part','p1',expect.objectContaining({decision:'rejected',expected_revision:1,comment:''}))
 expect(await screen.findByText('已撤回确认并驳回，相关成果需复核')).toBeVisible()
 expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
 expect(screen.getByText('已驳回',{selector:'.choice-state'})).toBeVisible()
})
