import { useState } from 'react'
import { Icon } from '../components/Icon'
import { DetailOverlay } from '../components/DetailOverlay'
import type { ProjectOverview } from '../types'
import { formatTime, riskLabels } from '../uiSupport'
import { ratioLabel } from '../businessPresentation'
import './overview-risk.css'

type Topic = NonNullable<ProjectOverview['cockpit']>['risk_topics'][number]
const shortName = (name: string) => name.replace(/^初始展示\s*·\s*/, '').replace(/[（(]合成[）)]$/, '').trim()
const names = (values: string[] | null | undefined) => values ? values.join('、') || '无' : '未记录'
const synthetic = (topic: Topic) => `${topic.name} ${topic.source_label ?? ''}`.includes('合成')
function Metric({label,value}:{label:string;value:string}) {return <div className="dash-fact"><span>{label}</span><strong>{value}</strong></div>}

export function OverviewRisk({data,onOpenWorkspace}:{data:ProjectOverview;onOpenWorkspace:()=>void}) {
  const [overlay,setOverlay] = useState<{kind:'details'|'metrics';trigger:HTMLElement}|null>(null)
  const topics = data.cockpit?.risk_topics ?? []
  const topic = topics.find(value=>value.risk_level==='high') ?? topics.find(value=>value.risk_level==='medium') ?? topics.find(value=>value.risk_level==='insufficient') ?? topics[0]
  const latencies = topic?.response_latencies_hours.slice(-6) ?? []
  const maxLatency = Math.max(48,...latencies)
  const headline = topic?.risk_level === 'insufficient' ? '暂无当前可用的计算依据' : topic?.headline ?? topic?.reasons[0] ?? (topic ? '当前未触发风险规则' : '暂无当前可用的计算依据')
  function open(kind:'details'|'metrics',trigger:HTMLElement) {setOverlay({kind,trigger})}
  return <section className="dash-card dash-risk dash-risk-compact" data-risk={data.coordination.highest_risk} aria-label="协同风险依据">
    <header className="dash-card-head"><div><h3>协同风险预警</h3><small>进度与沟通 · 基于登记记录</small></div><button type="button" className="dash-link" onClick={onOpenWorkspace}>查看风险<Icon name="arrow" size={13}/></button></header>
    <div className="dash-risk-content"><div className="dash-risk-plot"><div className="dash-risk-title"><span className={`dash-pill ${data.coordination.highest_risk}`}><Icon name={data.coordination.highest_risk==='insufficient'?'coordination':'alert'} size={14}/>{riskLabels[data.coordination.highest_risk]}</span><small>最近配对响应耗时</small></div>
      {latencies.length ? <div className="dash-bars" role="img" aria-label={`响应耗时：${latencies.join('、')} 小时`}><div className="dash-threshold" style={{bottom:`${48/maxLatency*70}%`}}>48h 规则阈值</div>{latencies.map((hours,index)=><div key={index}><strong>{hours}h</strong><i style={{height:`${hours/maxLatency*70}%`}}/><small>配对 {index+1}</small></div>)}</div> : <div className="dash-empty"><span>暂无可配对的响应记录</span><small className="dash-risk-empty-hint">响应图需要配对沟通记录，协议导入不包含这些记录。</small></div>}
      <div className="dash-risk-numbers" role="group" aria-label="协同指标摘要"><Metric label="平均响应" value={topic?.average_response_hours!=null?`${topic.average_response_hours}h`:'—'}/><Metric label="议题反复" value={topic?.iteration_count!=null?`${topic.iteration_count} 次`:'—'}/><Metric label="缺席率" value={topic?.absence_rate!=null?ratioLabel(topic.absence_rate):'—'}/></div>
    </div><div className="risk-brief">
      <ul aria-label="协同预警列表">{topic && <li data-risk={topic.risk_level}><header><strong title={topic.name}>{shortName(topic.name)}</strong><span className={`dash-pill ${topic.risk_level}`}>{riskLabels[topic.risk_level]}</span>{synthetic(topic)&&<span className="risk-source">合成样例</span>}</header><p className="risk-headline" title={headline}>{headline}</p><div className="risk-brief-facts"><span>平均响应 <strong>{topic.average_response_hours!=null?`${topic.average_response_hours}h`:'待计算'}</strong><small>阈值 48h</small></span><span>参与方缺席率 <strong>{topic.absence_rate!=null?ratioLabel(topic.absence_rate):'待计算'}</strong></span></div></li>}</ul>
      {!topic&&<p className="dash-empty">暂无当前可用的计算依据</p>}
      <footer><span>{data.coordination.topic_count} 个议题 · {data.coordination.record_count} 条记录</span><div><button type="button" className="dash-link" onClick={e=>open('metrics',e.currentTarget)}>指标说明</button><button type="button" className="risk-details-open" disabled={!topics.length} onClick={e=>open('details',e.currentTarget)}>预警详情<Icon name="arrow" size={12}/></button></div></footer>
    </div></div>
    {overlay&&<DetailOverlay title={overlay.kind==='details'?'协同预警详情':'协同指标说明'} subtitle="展示登记记录与规则计算结果；协同高风险不代表产品不合格。" eyebrow="协同风险 · 依据与来源" variant="wide" returnFocus={overlay.trigger} closeLabel="关闭预警详情" onClose={()=>setOverlay(null)} footer={<button type="button" onClick={()=>{setOverlay(null);onOpenWorkspace()}}>进入风险工作台 →</button>}>
      <div className="risk-evidence">{!topics.length&&<p>尚无协同议题。登记沟通和进度记录后，可在风险工作台计算指标。</p>}{topics.map(value=><article key={value.id} aria-label={`议题详情 ${value.name}`}><header><h3>{value.name}</h3><span className={`dash-pill ${value.risk_level}`}>{riskLabels[value.risk_level]}</span>{synthetic(value)&&<span className="risk-source">合成样例</span>}</header>
        <p className="risk-evidence-meta">来源：{value.source_label??'来源说明未记录'} · 规则：{value.rule_label??'暂无当前计算结果'}<br/>统计窗口：{formatTime(value.window_start)} — {formatTime(value.window_end)}<br/>应参与方：{value.expected_participants?.join('、')||'未记录'}</p>
        {overlay.kind==='metrics'?<><h4>统计口径与触发规则</h4><p>平均响应仅使用窗口内有效的请求—响应配对；当前 {value.metric_details?.response_sample_size??'未记录'} 个配对样本。未配对请求不按0小时计入。</p><p>缺席率按应参与方计算；实际参与方：{names(value.metric_details?.actual_participants)}；缺席方：{names(value.metric_details?.absent_participants)}。</p><p>议题反复为窗口内“重新打开”记录的计数，与消息数量分开。</p>{value.rule_conditions?.map(condition=><p key={condition.key}>{condition.label} · {condition.available?condition.hit?'已触发':'未触发':'数据不足'}</p>)}{value.progress&&<p>{value.progress.assessment.thresholds}</p>}{value.metric_details?.data_gaps?.map(gap=><p key={gap}>{gap}</p>)}</>:<>
          <h4>完整触发原因</h4>{value.reasons.length?<ul>{value.reasons.map(reason=><li key={reason}>{reason}</li>)}</ul>:<p>{value.risk_level==='insufficient'?'暂无当前可用的计算依据，请补充记录或重新计算。':'当前规则未列出触发原因。'}</p>}
          <h4>参与方计划与实际进度</h4>{value.progress?.rows.length?<div className="table-wrap"><table aria-label={`参与方进度 ${value.name}`}><thead><tr><th>参与方 / 里程碑</th><th>计划</th><th>实际</th><th>交付版本</th><th>记录与依据</th></tr></thead><tbody>{value.progress.rows.map(row=><tr key={row.id}><td>{row.participant} · {row.milestone}</td><td>{row.planned_percent}%</td><td>{row.actual_percent}%</td><td>{row.artifact_version} · 记录V{row.revision}</td><td>{formatTime(row.reported_at)}<br/>{row.evidence}</td></tr>)}</tbody></table></div>:<p>尚无进度登记记录。</p>}{value.progress?.assessment.data_gaps.map(gap=><p key={gap}>{gap}</p>)}
          <h4>原始沟通记录</h4>{value.records?.length?<div className="table-wrap"><table aria-label={`原始沟通记录 ${value.name}`}><thead><tr><th>编号 / 类型</th><th>参与方</th><th>时间</th><th>响应对象</th><th>摘要</th></tr></thead><tbody>{value.records.map(record=><tr key={record.id}><td>{record.external_id} · {record.record_type==='reopened'?'议题重开':'沟通'}</td><td>{record.sender}</td><td>{formatTime(record.sent_at)}</td><td>{record.reply_to_external_id??'—'}</td><td>{record.content_summary}</td></tr>)}</tbody></table></div>:<p>暂无可显示的沟通记录。</p>}
        </>}
      </article>)}</div>
    </DetailOverlay>}
  </section>
}
