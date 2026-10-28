import { render,screen,within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach,expect,it,vi } from 'vitest'
import { api } from '../api'
import type { TestCase } from '../types'
import { TestCaseRevisionDialog } from './TestCaseRevisionDialog'
afterEach(()=>vi.restoreAllMocks())
const row:TestCase={id:'tc4',plan_id:'plan',display_code:'TC-004',case_key:'durability',case_kind:'manual',title:'耐久验证',purpose:'核对耐久',revision:1,review_status:'draft',validity:'current',conditions_text:'合成台架',load_conditions_text:'循环加载',acceptance_criteria:'',load_basis_requirement_id:null,minimum_coefficient:null,requirement_refs:[],fmea_refs:[],complete:false,coverage_valid:false,runs:[]}
it('saves a criteria revision independently of confirmation and preserves failed input',async()=>{
 const save=vi.spyOn(api,'updateTestCase').mockRejectedValueOnce(new Error('存储暂不可用')).mockResolvedValue({...row,revision:2,acceptance_criteria:'1000h无失效'})
 const confirm=vi.spyOn(api,'confirmTestCase')
 const onSaved=vi.fn(async()=>{}),close=vi.fn(),user=userEvent.setup()
 render(<TestCaseRevisionDialog testCase={row} returnFocus={null} onClose={close} onSaved={onSaved}/>)
 const dialog=screen.getByRole('dialog',{name:'修订试验用例'})
 await user.type(within(dialog).getByLabelText('用例通过判据'),'合成补充规程：1000h无失效')
 await user.type(within(dialog).getByLabelText('用例修订依据'),'CN-02合成澄清单')
 await user.click(within(dialog).getByRole('button',{name:'保存用例修订'}))
 expect(await within(dialog).findByRole('alert')).toHaveTextContent('存储暂不可用')
 expect(within(dialog).getByLabelText('用例通过判据')).toHaveValue('合成补充规程：1000h无失效')
 await user.click(within(dialog).getByRole('button',{name:'保存用例修订'}))
 expect(save).toHaveBeenLastCalledWith('tc4',expect.objectContaining({expected_revision:1,acceptance_criteria:'合成补充规程：1000h无失效',comment:'CN-02合成澄清单'}))
 expect(confirm).not.toHaveBeenCalled();expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({revision:2}));expect(close).toHaveBeenCalledOnce()
})
