export const activeStates = new Set(["running", "starting"]);
export const labels = {running:"Running", starting:"Starting", completed:"Completed", error:"Failed", interrupted:"Interrupted", timeout:"Timed out", blocked:"Blocked", needs_review:"Needs review", native_required:"Needs Codex"};
export const sortLabels = {newest:"Newest started", oldest:"Oldest started", updated:"Recently updated", longest:"Longest duration", shortest:"Shortest duration", title:"Title A–Z"};
export function conversationName(run) {
  return run.conversation_title || (run.codex_thread_id ? `Conversation ${run.codex_thread_id.slice(-6)}` : "Unassigned conversation");
}
export function modelName(run) {
  const model=run.model_selection?.requested_model;
  return model ? model.charAt(0).toUpperCase()+model.slice(1) : "Claude default";
}
export function roleName(role) {
  return String(role||"worker").replaceAll("-"," ").trim().replace(/\s+/g," ").toLowerCase();
}
export function elapsed(run, now=Date.now()/1000) {
  if(run.runs)return run.runs.reduce((total,item)=>total+elapsed(item,now),0);
  return Math.max(0,(run.ended_at ?? (activeStates.has(run.status)?now:run.updated_at) ?? now)-(run.started_at ?? now));
}
export function workerKey(run) {
  return JSON.stringify([run.codex_thread_id||null,run.session_id||`run:${run.id}`]);
}
export function groupWorkers(runs, filters={}, now=Date.now()/1000) {
  const matching=new Set(filterRuns(runs,filters,now).map(run=>run.id));
  const groups=new Map();
  for(const run of runs){
    const key=workerKey(run);
    if(!groups.has(key))groups.set(key,[]);
    groups.get(key).push(run);
  }
  return [...groups.values()].flatMap(history=>{
    history.sort((a,b)=>(a.started_at||0)-(b.started_at||0)||a.id.localeCompare(b.id));
    const matching_runs=history.filter(run=>matching.has(run.id)).length;
    if(!matching_runs)return [];
    const latest=history.at(-1);
    const active=history.filter(run=>activeStates.has(run.status)).at(-1);
    return [{...latest,id:history[0].id,title:history[0].title,
      latest_run_id:latest.id,status:active?.status||latest.status,
      updated_at:Math.max(...history.map(run=>run.updated_at||run.started_at||0)),
      runs:history,matching_runs}];
  });
}
export function filterRuns(runs, filters={}, now=Date.now()/1000) {
  const q=(filters.q||"").trim().toLowerCase();
  const period={"15m":900,"30m":1800,"1h":3600,"3h":10800,"6h":21600,"12h":43200,"24h":86400,"7d":604800,"30d":2592000}[filters.period];
  const byMessage=["latest","message"].includes(filters.period);
  if(byMessage&&(!filters.conversation||filters.conversation==="unassigned"||!Number.isFinite(filters.since)))return [];
  const attention=new Set(["error","interrupted","timeout","blocked","needs_review","native_required"]);
  return runs.filter(run=>
    (!filters.conversation || (run.codex_thread_id||"unassigned")===filters.conversation) &&
    (!filters.model || (run.model_selection?.requested_model||"default")===filters.model) &&
    (!filters.role || roleName(run.model_selection?.role)===roleName(filters.role)) &&
    (!filters.status || (filters.status==="attention"?attention.has(run.status):run.status===filters.status)) &&
    (!period || run.started_at>=now-period) &&
    (!byMessage || run.started_at>=filters.since) &&
    (!q || [run.title,conversationName(run),run.codex_thread_id,modelName(run),roleName(run.model_selection?.role),labels[run.status]||run.status].join(" ").toLowerCase().includes(q)));
}
export function sortRuns(runs, sort="newest", now=Date.now()/1000) {
  const newest=(a,b)=>(b.started_at||0)-(a.started_at||0)||a.id.localeCompare(b.id);
  const comparators={newest, oldest:(a,b)=>(a.started_at||0)-(b.started_at||0),
    updated:(a,b)=>(b.updated_at||0)-(a.updated_at||0),
    longest:(a,b)=>elapsed(b,now)-elapsed(a,now), shortest:(a,b)=>elapsed(a,now)-elapsed(b,now),
    title:(a,b)=>(a.title||"").localeCompare(b.title||"")};
  return [...runs].sort((a,b)=>(comparators[sort]||newest)(a,b)||newest(a,b));
}

export function messageBoundary(filters, messages=[]) {
  return (filters.period==="latest"?messages[0]:filters.period==="message"?messages.find(m=>String(m.line)===filters.message):null)||null;
}
