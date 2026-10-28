import type { WorkflowSummary, ProgressPayload } from '../types'
export const emptyWorkflow:WorkflowSummary={testing:{total:0,review:{draft:0,pending_review:0,confirmed:0,rejected:0},stale:0,valid_coverage_cases:0,execution:{not_run:0,pass:0,fail:0,incomplete:0,invalid:0},cases:[],plan_status:'not_started'},samples:{total:0,compared:0,confirmed:0,rows:[]},consistency:{scope:[],changes:[]}}
export function emptyProgress(topicId:string):ProgressPayload{return {topic_id:topicId,rows:[],assessment:{rule_label:'PROGRESS-DEMO-V1',risk_level:'insufficient',alerts:[],data_gaps:[],thresholds:'合成规则'}}}
