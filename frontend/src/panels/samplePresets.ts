import { DEMO_SAMPLE } from '../demoInputs'
import type { DrawingParameter } from '../types'

// Presets describe independent synthetic measurements, never an SVG extraction.
export function samplePreset(parameters:DrawingParameter[],failed=false){
  const known:Record<string,{value:number;failed:number;expected:number;tolerance:number;unit:string}>=DEMO_SAMPLE.measurements
  const matched=parameters.filter(parameter=>{
    const sample=known[parameter.parameter_key]
    return sample&&sample.expected===parameter.expected_value&&sample.tolerance===parameter.tolerance&&sample.unit===parameter.unit
  })
  return {
    measurements:Object.fromEntries(matched.map(parameter=>[parameter.parameter_key,String(known[parameter.parameter_key][failed?'failed':'value'])])),
    evidence:matched.length?(failed?'合成超差记录DEMO-MEASURE-002':'合成尺寸记录DEMO-MEASURE-001'):'',
    count:matched.length,
  }
}
