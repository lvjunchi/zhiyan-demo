import { expect,it } from 'vitest'
import { executionLoadPreset } from './executionPreset'
const testCase={load_basis_requirement_id:'engine-id',requirement_refs:[{requirement_id:'engine-id',revision:2,current_revision:2}]}
const source={id:'engine-id',project_id:'p1',current_revision:2,review_status:'confirmed' as const,validity:'current' as const,unit:'N·m',value_num:2800}
it('uses the exact current referenced source rather than a hardcoded demo baseline',()=>{
 expect(executionLoadPreset(testCase,[source],'p1')).toBe('2800')
 expect(executionLoadPreset({...testCase,requirement_refs:[]},[source],'p1')).toBe('')
 for(const changed of [{current_revision:1},{project_id:'p2'},{review_status:'draft' as const},{validity:'stale' as const},{unit:'kN·m'},{value_num:NaN},{value_num:null},{value_num:0}]){
  expect(executionLoadPreset(testCase,[{...source,...changed}],'p1')).toBe('')
 }
})
