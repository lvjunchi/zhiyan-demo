import { expect, it } from 'vitest'
import { samplePreset } from './samplePresets'
import type { DrawingParameter } from '../types'
const hole:DrawingParameter={id:'hole-id',parameter_key:'holePosition',parameter_name:'孔位',expected_value:120,tolerance:0.5,unit:'mm',source_note:'合成基准'}
it('uses independent synthetic pass/fail values and explicit evidence only for an exact baseline match',()=>{
  expect(samplePreset([hole])).toEqual({measurements:{holePosition:'120.2'},evidence:'合成尺寸记录DEMO-MEASURE-001',count:1})
  expect(samplePreset([hole],true)).toEqual({measurements:{holePosition:'121'},evidence:'合成超差记录DEMO-MEASURE-002',count:1})
})
it('leaves unknown, changed baseline, tolerance and unit parameters for manual entry',()=>{
  for(const changed of [{parameter_key:'unknown'},{expected_value:121},{tolerance:0.05},{unit:'cm'}]){
    expect(samplePreset([{...hole,...changed}])).toEqual({measurements:{},evidence:'',count:0})
  }
  expect(samplePreset([hole,{...hole,id:'unknown-id',parameter_key:'unknown'}]).measurements).toEqual({holePosition:'120.2'})
})
