import { DEMO_COORDINATION } from '../demoInputs'
import type { CoordinationTopic } from '../types'

export function isDemoTopic(topic:CoordinationTopic):boolean {
  return topic.name===DEMO_COORDINATION.name&&DEMO_COORDINATION.participants.every(name=>topic.expected_participants.includes(name))
}
function localTime(epoch:number):string {
  const date=new Date(epoch)
  return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}T${String(date.getHours()).padStart(2,'0')}:${String(date.getMinutes()).padStart(2,'0')}`
}
export function communicationPreset(topic:CoordinationTopic,reply:boolean,rootId?:string){
  const start=Date.parse(topic.window_start),end=Date.parse(topic.window_end)
  if(!Number.isFinite(start)||!Number.isFinite(end)||end-start<120000||topic.expected_participants.length<2)return null
  const roots=topic.records.filter(record=>record.record_type==='message'&&!record.reply_to_external_id)
  const root=rootId?roots.find(record=>record.external_id===rootId):roots.find(record=>!topic.records.some(other=>other.reply_to_external_id===record.external_id))
  if(reply&&!root)return null
  const used=new Set(topic.records.map(record=>record.external_id))
  let number=reply?2:1
  while(used.has(`DEMO-MSG-${String(number).padStart(2,'0')}`))number++
  const rootTime=root?Date.parse(root.sent_at):NaN
  const initial=start+Math.min(9*3600000,Math.floor((end-start)/3))
  const replyTime=reply&&Number.isFinite(rootTime)?Math.min(rootTime+2*3600000,end-60000):initial
  if(reply&&(replyTime<=rootTime||rootTime<start||rootTime>=end))return null
  return {
    externalId:`DEMO-MSG-${String(number).padStart(2,'0')}`,
    sender:reply?topic.expected_participants.find(name=>name!==root?.sender)??topic.expected_participants[1]:topic.expected_participants[0],
    summary:reply?'合成演示：回复资料核对状态':'合成演示：请确认交付资料',
    sentAt:localTime(reply?replyTime:initial),replyTo:reply?root!.external_id:'',
  }
}
