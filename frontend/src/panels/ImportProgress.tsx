import type {ImportPhase,ProgressSnapshot} from './importProgressState'
const steps = ['文件检查', '文本提取', '核对正文', '需求解析', '保存结果']
const phaseIndex: Record<ImportPhase, number> = { idle: -1, checking: 0, extracting: 1, reviewing: 2, archiving: 3, parsing: 3, saved: 4 }
export function ImportProgress({ phase, failed, filename, textOnly=false, statusText }: ProgressSnapshot) {
  const index = phaseIndex[phase]
  return <section className="import-progress" role="region" aria-label="协议处理进度">
    <div className="import-progress-caption"><strong>协议处理流程</strong><span>{filename || '选择文件或粘贴正文开始'}</span></div>
    <ol>{steps.map((label, i) => {const skipped=textOnly&&i<2;return <li key={label} className={`${!skipped&&(i < index || phase === 'saved') ? 'is-done' : ''} ${!skipped&&i === index ? failed ? 'is-failed' : 'is-current' : ''}`} aria-current={!skipped&&i === index ? 'step' : undefined}><span>{skipped?'—':i + 1}</span><strong>{label}{skipped?'（不适用）':''}</strong></li>})}</ol>
    <p aria-live="polite">{failed ? `${phase === 'archiving' ? '正文归档' : steps[Math.max(index, 0)]}失败：${failed}` : statusText ? statusText : phase === 'saved' ? '结果已保存，需求仍需人工审核' : phase === 'reviewing' ? '文本已就绪，请核对正文与来源位置，再提交解析。' : phase === 'archiving' ? '正在归档原文件及核对正文…' : phase === 'parsing' ? '正在请求规则解析；需求与问题由后端在同一事务保存，返回后标记完成。' : phase === 'extracting' ? '正在读取文件文本与来源位置…' : '仅显示实际处理阶段，不使用模拟百分比。'}</p>
  </section>
}
