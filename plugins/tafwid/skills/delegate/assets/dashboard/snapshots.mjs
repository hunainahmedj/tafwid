import {filterRuns, workerKey} from './view.mjs';

const periods={'15m':900,'30m':1800,'1h':3600,'3h':10800,'6h':21600,'12h':43200,'24h':86400,'7d':604800,'30d':2592000};
const known=value=>typeof value==='number'&&Number.isFinite(value)&&value>=0;
export function snapshotRange(filters={},now=Date.now()/1000) {
  if(['latest','message'].includes(filters.period))return {
    valid:Boolean(filters.conversation&&filters.conversation!=='unassigned'&&known(filters.since)),
    start:known(filters.since)?filters.since:null,end:now};
  return {valid:true,start:periods[filters.period]?now-periods[filters.period]:null,end:now};
}

export function usageSnapshot(runs,filters={},now=Date.now()/1000) {
  const range=snapshotRange(filters,now);
  const result={...range,samples:0,workers:[],first_at:null,latest_at:null,coverage:'unavailable',missing_runs:0,partial_runs:0};
  const fields=['input','output','cache_read','cache_write'];
  for(const field of fields)result[field]={value:null,known:0};
  if(!range.valid)return result;
  // Identity follows the existing filters; time is applied to observations below.
  const candidates=filterRuns(runs,{...filters,period:'',since:undefined},now);
  const groups=new Map(),seenRuns=new Set();
  for(const run of candidates){
    if(seenRuns.has(run.id))continue;
    seenRuns.add(run.id);
    const samples=(run.telemetry?.samples||[]).filter(s=>known(s.at)&&s.at<=range.end&&(range.start===null||s.at>=range.start));
    const overlaps=(!known(run.started_at)||run.started_at<=range.end)&&
      (range.start===null||!known(run.ended_at)||run.ended_at>=range.start);
    if(!samples.length){if(overlaps)result.missing_runs++;continue;}
    if(run.telemetry?.coverage!=='complete'||run.telemetry?.truncated)result.partial_runs++;
    const key=workerKey(run);
    if(!groups.has(key))groups.set(key,{key,title:run.title,session_id:run.session_id,backend:run.backend||'claude',codex_thread_id:run.codex_thread_id,conversation_title:run.conversation_title,samples:new Map()});
    const group=groups.get(key);
    for(const sample of samples){
      const id=sample.id||JSON.stringify([sample.at,...fields.map(f=>sample[f]),sample.context_tokens,sample.context_limit,sample.model]);
      if(!group.samples.has(id))group.samples.set(id,sample);
    }
  }
  const all=[];
  for(const group of groups.values()){
    const samples=[...group.samples.values()].sort((a,b)=>a.at-b.at);
    all.push(...samples);
    const context=samples.filter(s=>known(s.context_percent)||known(s.context_tokens));
    const percentages=context.filter(s=>known(s.context_percent));
    const peakField=percentages.length?'context_percent':'context_tokens';
    const peakSamples=percentages.length?percentages:context.filter(s=>known(s.context_tokens));
    result.workers.push({...group,samples:samples.length,first:context[0]||null,latest:context.at(-1)||null,
      peak:peakSamples.reduce((peak,s)=>!peak||s[peakField]>peak[peakField]?s:peak,null)});
  }
  all.sort((a,b)=>a.at-b.at);
  result.samples=all.length;
  result.first_at=all[0]?.at??null;result.latest_at=all.at(-1)?.at??null;
  for(const field of fields){
    const values=all.map(s=>s[field]).filter(known);
    result[field]={value:values.length?values.reduce((sum,n)=>sum+n,0):null,known:values.length};
  }
  if(all.length)result.coverage=result.missing_runs||result.partial_runs||fields.some(f=>result[f].known<all.length)?'partial':'complete';
  return result;
}

export function accountDeltas(account,filters={},now=Date.now()/1000) {
  const range=snapshotRange(filters,now);
  const history=(account.history||[]).filter(s=>known(s.at)&&s.at<=now&&account.account_id&&s.account_id===account.account_id).sort((a,b)=>a.at-b.at);
  const baseline=range.start===null?history[0]:history.filter(s=>s.at<=range.start).at(-1);
  const latest=history.at(-1);
  const windows=account.windows?.length?account.windows:latest?.windows||[];
  return windows.map(window=>{
    const item={key:window.key,label:window.label,delta:null,comparable:false,baseline_at:baseline?.at??null,latest_at:latest?.at??null,approximate:range.start!==null&&baseline?.at!==range.start,reason:'No comparable observations'};
    if(!range.valid)return {...item,reason:'Choose a valid message boundary'};
    if(!baseline||range.start!==null&&range.start-baseline.at>120)return {...item,reason:'No account observation near the starting boundary'};
    if(!latest||latest.at<=baseline.at||range.start!==null&&latest.at<range.start)return {...item,reason:'Waiting for a later account observation'};
    const points=history.filter(s=>s.at>=baseline.at&&s.at<=latest.at).map(s=>s.windows?.find(w=>w.key===window.key));
    if(points.some(w=>!w||!known(w.used_percent)||!known(w.resets_at)))return {...item,reason:'Window usage or reset time is unknown'};
    if(points.some(w=>Math.abs(w.resets_at-points[0].resets_at)>1)||points.some((w,i)=>i&&w.used_percent<points[i-1].used_percent))return {...item,reason:'Limit reset or usage decreased; not comparable'};
    if(now>=points[0].resets_at)return {...item,reason:'Limit reset time passed; waiting for a fresh observation'};
    return {...item,comparable:true,reason:null,delta:points.at(-1).used_percent-points[0].used_percent};
  });
}

export function accountStatus(account,now=Date.now()/1000) {
  const status=account.status||'unavailable';
  if(status!=='unavailable'&&(account.windows||[]).some(window=>known(window.resets_at)&&window.resets_at<=now))return 'stale';
  return status;
}
