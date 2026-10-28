// Explicit synthetic values from 演示导入文件/综合演示/04 and 06. Never auto-submit.
export const DEMO_STATIC_TORSION={backupCoefficient:'2.6'}
export const DEMO_SCORES: Record<string, readonly [number,number,number]> = {
  'FMEA-01':[8,4,3], 'FMEA-02':[7,3,4], 'FMEA-03':[6,3,4],
  'FMEA-04':[6,3,4], 'FMEA-05':[6,3,4], 'FMEA-06':[6,3,4],
}
export const DEMO_COORDINATION = {
  // Independent synthetic cost inputs, not inferred from messages or progress.
  laborHours:'3',hourlyRate:'120',
  name:'合成设计冻结交付协同', participants:['A 主机方','B 研发方'],
  windowStart:'2026-10-20T00:00',windowEnd:'2026-10-24T00:00',reportedAt:'2026-10-23T16:00',
  acceptance:'合成排练中明确接受已登记进度差和交付版本风险，后续按计划复核；不代表产品不合格结论',
}

// Explicit values from 05_样件与实测样例.json; never inferred from an uploaded drawing.
export const DEMO_SAMPLE = {
  supplier:'合成样件提供方',partCode:'P-03',drawingCode:'DEMO-DRW-001',drawingRevision:'A',
  deliveredAt:'2026-10-23',quantity:'1',notes:'合成尺寸基准，不由系统读取CAD自动识别',
  parameters:'holePosition|孔位|120|0.5|mm|配套示意图尺寸1\nshaftDiameter|轴径|45|0.02|mm|配套示意图尺寸2',
  measurements:{holePosition:{value:120.2,failed:121,expected:120,tolerance:0.5,unit:'mm'},shaftDiameter:{value:45.01,failed:45.01,expected:45,tolerance:0.02,unit:'mm'}},
}
