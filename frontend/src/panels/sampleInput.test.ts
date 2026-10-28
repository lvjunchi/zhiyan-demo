import { expect,it } from 'vitest'
import { parseParameters,measurementValue } from './sampleInput'
it('rejects missing drawing values and tolerance instead of turning blanks into zero',()=>{
 for(const value of ['bore|内孔||0.05|mm','bore|内孔|120||mm','bore|内孔|NaN|0.05|mm','bore|内孔|120|-1|mm'])expect(()=>parseParameters(value)).toThrow()
 expect(parseParameters('bore|内孔|0|0|mm|合成基准')[0]).toMatchObject({expected_value:0,tolerance:0})
 expect(()=>parseParameters('b|内孔|120|0.05|mm\nb|内孔|120|0.05|mm')).toThrow()
})
it('does not coerce blank measurements to a valid zero',()=>{
 for(const value of [undefined,'',' ','NaN','Infinity'])expect(()=>measurementValue(value)).toThrow()
 expect(measurementValue('0')).toBe(0)
})
