import { render,screen,within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach,expect,it,vi } from 'vitest'
import { api } from '../api'
import { WorkflowOverview } from './WorkflowOverview'
import { CoordinationProgress } from './CoordinationProgress'
afterEach(()=>vi.restoreAllMocks())
it('shows backend case review, current execution and sample steps without counting historical passes',async()=>{
 vi.spyOn(api,'getWorkflowSummary').mockResolvedValue({testing:{total:2,review:{draft:1,pending_review:0,confirmed:1,rejected:0},stale:1,valid_coverage_cases:1,execution:{not_run:1,pass:0,fail:1,incomplete:0,invalid:0},cases:[],plan_status:'confirmed'},samples:{total:1,compared:1,confirmed:0,rows:[{id:'s1',display_code:'SD-01',steps:[{label:'样件登记',done:true},{label:'审核确认',done:false}],current_step:1,result:'fail',review_status:'draft',open_issues:1}]},consistency:{scope:['需求参数'],changes:[{id:'r1',label:'REQ-1',kind:'需求修订',parameter:'发动机扭矩',before:'2600',after:'2800',unit:'N·m',versions:'V1 → V2',state:'changed',evidence:'合成变更单'}]}})
 const {rerender}=render(<WorkflowOverview projectId="p1" section="testing" refreshKey="v1"/>)
 expect(await screen.findByRole('region',{name:'试验状态与进度'})).toHaveTextContent('待复核1')
 expect(screen.getByLabelText('当前通过')).toHaveTextContent('0')
 rerender(<WorkflowOverview projectId="p1" section="samples" refreshKey="v1"/>)
 expect(await screen.findByRole('region',{name:'样件检验流程'})).toHaveTextContent('审核确认')
 rerender(<WorkflowOverview projectId="p1" section="consistency" refreshKey="v1"/>)
 expect(await screen.findByRole('region',{name:'参数与版本变化'})).toHaveTextContent('2600')
 expect(screen.getByRole('region',{name:'参数与版本变化'})).toHaveTextContent('2800')
 const user=userEvent.setup()
 await user.type(screen.getByLabelText('搜索参数版本变化'),'不存在的参数')
 expect(screen.getByText('没有匹配的变化记录')).toBeVisible()
 await user.clear(screen.getByLabelText('搜索参数版本变化'))
 await user.click(screen.getByRole('button',{name:'查看 REQ-1 变化依据'}))
 expect(screen.getByRole('dialog',{name:'变化依据 · REQ-1'})).toHaveTextContent('合成变更单')
})
it('records participant progress with the loaded revision and shows distinct alert reasons',async()=>{
 const data={topic_id:'t1',rows:[],assessment:{rule_label:'PROGRESS-DEMO-V1',risk_level:'insufficient',alerts:[],data_gaps:[],thresholds:'20/40个百分点'}}
 vi.spyOn(api,'getCoordinationProgress').mockResolvedValue(data)
 const save=vi.spyOn(api,'saveCoordinationProgress').mockResolvedValue({...data,assessment:{...data.assessment,risk_level:'high',alerts:[{kind:'progress_gap',level:'high',milestone:'设计冻结',participants:['A','B'],reason:'A 90% / B 30%，进度相差60个百分点',evidence:['周报A','周报B'],reported_at:['2026-10-23T08:00:00+00:00','2026-10-23T08:00:00+00:00']}]}})
 const user=userEvent.setup();render(<CoordinationProgress topicId="t1" participants={['A','B']} onChanged={()=>{}}/>)
 await user.click(await screen.findByRole('button',{name:'登记参与方进度'}))
 const dialog=screen.getByRole('dialog',{name:'参与方进度登记'})
 await user.type(within(dialog).getByLabelText('进度里程碑'),'设计冻结')
 await user.type(within(dialog).getByLabelText('计划进度百分比'),'80')
 await user.type(within(dialog).getByLabelText('实际进度百分比'),'90')
 await user.type(within(dialog).getByLabelText('交付版本'),'V2')
 await user.type(within(dialog).getByLabelText('进度记录时间'),'2026-10-23T16:00')
 await user.type(within(dialog).getByLabelText('进度依据'),'合成周报A')
 await user.click(within(dialog).getByRole('button',{name:'保存参与方进度'}))
 expect(save).toHaveBeenCalledWith('t1',expect.objectContaining({participant:'A',expected_revision:0,planned_percent:80,actual_percent:90}))
 expect(await screen.findByText('A 90% / B 30%，进度相差60个百分点')).toBeVisible()
})
