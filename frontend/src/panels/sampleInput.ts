export function measurementValue(value:string|undefined):number {
 if(value===undefined||!value.trim()||!Number.isFinite(Number(value)))throw new Error('请填写完整、有效的数值；空白不按0处理')
 return Number(value)
}
export function parseParameters(text:string):Record<string,unknown>[] {
 const keys=new Set<string>()
 return text.split('\n').map(line=>line.trim()).filter(Boolean).map((line,index)=>{
  const fields=line.split('|').map(value=>value.trim())
  if(fields.length<5||!fields[0]||!fields[1]||keys.has(fields[0]))throw new Error(`第${index+1}行参数格式不完整或编号重复`)
  const expected=measurementValue(fields[2]),tolerance=measurementValue(fields[3])
  if(tolerance<0)throw new Error(`第${index+1}行公差不能为负数`)
  keys.add(fields[0])
  return {parameter_key:fields[0],parameter_name:fields[1],expected_value:expected,tolerance,unit:fields[4],source_note:fields[5]??''}
 })
}
