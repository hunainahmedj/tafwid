import { activeStates, labels, sortLabels, conversationName, modelName, backendName, roleName, groupWorkers, filterRuns, sortRuns, elapsed, messageBoundary } from "/view.mjs";
import { usageTotals, tokenText, costText, compactUsage, compactCost, usageDetails } from "/stats.mjs";
import { setupActivity } from "/activity-ui.mjs";
const params = new URLSearchParams(location.hash.slice(1));
const token = params.get("token");
const task = params.get("thread");
const $ = id => document.getElementById(id);
const filters = Object.fromEntries(["conversation","model","role","status","period","sort","q","message"].map(key=>[key,params.get(key)||""]));
if(!params.has("conversation"))filters.conversation=task||"";
if(!sortLabels[filters.sort])filters.sort="newest";
if(filters.role)filters.role=roleName(filters.role);
let runs = [];
let messageContext = {thread:null,messages:[]};
let selectedId = null;
let selected = null;
let selectedTab = "exchanges";
let selectedRunId = null;
let busy = false;
function el(tag, className, value) { const node=document.createElement(tag); if(className)node.className=className; if(value!==undefined)node.textContent=value; return node; }
function modelClass(run) { const name=modelName(run).toLowerCase(); return ["fable","opus","sonnet"].find(m=>name.includes(m)) || "other"; }
function duration(seconds) { const n=Math.max(0,Math.floor(seconds)); return n<60?`${n}s`:n<3600?`${Math.floor(n/60)}m ${n%60}s`:`${Math.floor(n/3600)}h ${Math.floor(n%3600/60)}m`; }
function age(timestamp) { const seconds=Math.max(0,Date.now()/1000-timestamp); return seconds<60?"Just now":seconds<3600?`${Math.floor(seconds/60)}m ago`:seconds<86400?`${Math.floor(seconds/3600)}h ago`:`${Math.floor(seconds/86400)}d ago`; }
async function api(path, options={}) { const response=await fetch(path,{...options,headers:{Authorization:`Bearer ${token}`, ...(options.body ? {"Content-Type":"application/json"} : {})}}); if(!response.ok)throw new Error(response.status===401?"This dashboard link has expired. Ask Codex to reopen the workers dashboard.":`Dashboard unavailable (${response.status}).`); return response.json(); }
function saveFilters() {
  for(const [key,value] of Object.entries(filters))params.set(key,value);
  history.replaceState(null,"",location.pathname+"#"+params.toString());
  $("settings-link").href="/settings"+location.hash;
}
function options(id, entries, allLabel) {
  const select=$(id);
  const current=filters[id];
  const items=[...entries];
  if(current&&!items.some(([value])=>value===current))items.push([current,current]);
  const signature=JSON.stringify(items);
  if(select.dataset.signature!==signature){
    select.replaceChildren(new Option(allLabel,""),...items.map(([value,label])=>new Option(label,value)));
    select.dataset.signature=signature;
  }
  select.value=current;
}
function populateFilters() {
  const conversations=new Map(runs.map(run=>[run.codex_thread_id||"unassigned",conversationName(run)]));
  if(task&&!conversations.has(task))conversations.set(task,conversationName({codex_thread_id:task}));
  const counts=new Map();for(const title of conversations.values())counts.set(title,(counts.get(title)||0)+1);
  const choices=[...conversations].map(([id,title])=>[id,counts.get(title)>1?`${title} · ${id.slice(-6)}`:title]).sort((a,b)=>a[1].localeCompare(b[1]));
  options("conversation",choices,"All conversations");
  options("model",[...new Map(runs.map(run=>[run.model_selection?.requested_model||"default",modelName(run)]))].sort((a,b)=>a[1].localeCompare(b[1])),"All models");
  options("role",[...new Set(runs.map(run=>roleName(run.model_selection?.role)))].sort().map(role=>[role,role]),"All roles");
  const title=conversations.get(task)||conversationName({codex_thread_id:task});
  $("scope-context").textContent=task?`Opened from: ${title}`:"Browsing all locally recorded conversations";
}
function changed() {saveFilters();render();refresh();}
function setScope(id) {if(filters.conversation!==id)filters.message="";filters.conversation=id;$("conversation").value=id;changed();}
function empty(list,active,filtered) { const box=el("div","empty"); box.append(el("span","empty-symbol",active?"◌":"↳")); const copy=el("div"); copy.append(el("strong",null,filtered?"No matching workers":active?"All quiet for now":"No completed workers yet")); copy.append(el("p",null,filtered?"Try adjusting the filters or choose All conversations.":active?"New Tafwid workers will appear here as soon as they launch.":"Completed runs and workers needing attention will be saved here.")); box.append(copy); list.append(box); }
function row(run) {
  const button=el("button","worker"); button.type="button"; button.dataset.runId=run.id;
  button.setAttribute("aria-label",`Open ${run.title}, ${run.runs.length} ${run.runs.length===1?"run":"runs"}, latest ${labels[run.status]||run.status}`);
  button.append(el("span",`avatar ${modelClass(run)}`,modelClass(run)==="fable"?"✳":modelClass(run)==="opus"?"◈":"✧"));
  const body=el("span","worker-body");body.append(el("span","worker-title",run.title));
  const sub=el("span","worker-subtitle");sub.append(el("span",null,backendName(run)),el("span","separator","·"),el("span",null,modelName(run)),el("span","separator","/"),el("span",null,(run.model_selection?.role||"worker").replaceAll("-"," ")));
  const conversation=el("span","worker-conversation",conversationName(run));
  conversation.title=conversationName(run)+(run.codex_thread_id?` · ${run.codex_thread_id}`:"");
  const history=el("span","worker-history",`${run.runs.length} ${run.runs.length===1?"run":"runs"} · ${run.runs.length>1?"same worker session":"single run"}${run.matching_runs<run.runs.length?` · ${run.matching_runs} match filters`:""}`);
  if(run.runs.length>1)history.title="Latest run: "+run.runs.at(-1).title;
  body.append(sub,conversation,history,el("span","worker-usage",compactUsage(run.runs)+" · all recorded runs"),el("span","worker-usage",compactCost(run.runs)));button.append(body);
  const end=el("span","worker-end");end.append(el("span",`status ${run.status}`,labels[run.status]||run.status));
  end.append(el("span","time",activeStates.has(run.status)?duration(elapsed(run)):age(run.ended_at||run.updated_at)));
  if(["longest","shortest"].includes(filters.sort)&&!activeStates.has(run.status))end.append(el("span","time",duration(elapsed(run))+" total"));
  button.append(end,el("span","chevron","›"));button.addEventListener("click",()=>openDetails(run.id));return button;
}
function renderTimeFilter() {
  const byMessage=["latest","message"].includes(filters.period);
  const single=Boolean(filters.conversation&&filters.conversation!=="unassigned");
  const loaded=messageContext.thread===filters.conversation;
  const messages=single&&loaded?messageContext.messages:[];
  $("message-filter").hidden=filters.period!=="message";
  $("message").disabled=!single||!loaded;
  const choices=messages.map(m=>[String(m.line),`${new Date(m.timestamp*1000).toLocaleString()} · ${m.preview}`]);
  options("message",choices,"Choose a message…");
  const boundary=messageBoundary(filters,messages);
  const note=$("time-context");note.hidden=!byMessage;
  if(byMessage)note.textContent=!single?"Choose one conversation to filter from its messages.":
    !loaded?"Loading this conversation’s messages…":
    messageContext.error?messageContext.error:
    !messages.length?"No user-message boundary is available in this task’s local log.":
    !boundary?"Choose a starting message. If a saved message is no longer available, choose another.":
    `Runs started since ${new Date(boundary.timestamp*1000).toLocaleString()} · “${boundary.preview}”${filters.period==="latest"?" · Follows new messages automatically.":" · This starting message stays selected as new messages arrive."}`;
  return boundary?.timestamp;
}
function render() {
  const since=renderTimeFilter();
  const filtered=sortRuns(groupWorkers(runs,{...filters,since}),filters.sort);
  renderStats(filterRuns(runs,{...filters,since}));
  const scoped=Boolean(filters.q||filters.model||filters.role||filters.status||filters.period);
  for(const [id,on] of [["this-task",Boolean(task)&&filters.conversation===task],["all-tasks",!filters.conversation]]){
    $(id).classList.toggle("selected",on);$(id).setAttribute("aria-pressed",String(on));
  }
  const matchingRuns=filtered.reduce((total,worker)=>total+worker.matching_runs,0);
  const count=`${filtered.length} of ${groupWorkers(runs).length} workers · ${matchingRuns} of ${runs.length} runs match`;
  renderOrchestrators();
  if($("result-count").textContent!==count)$("result-count").textContent=count;
  $("done-caption").textContent=sortLabels[filters.sort];
  for(const [kind,isActive] of [["active",true],["done",false]]){
    const list=$(kind+"-list");const records=filtered.filter(run=>activeStates.has(run.status)===isActive);
    $(kind+"-count").textContent=records.length;
    // Avoid replacing focused worker buttons every polling cycle.
    const signature=JSON.stringify(records.map(r=>[r.id,r.status,r.title,r.model_selection,r.conversation_title,r.ended_at,r.runs.map(item=>[item.id,item.status,item.title,item.model_selection,item.updated_at]),r.matching_runs,Math.floor(Date.now()/1000/2)]))+JSON.stringify(filters);
    if(list.dataset.signature===signature)continue;
    const focused=document.activeElement?.dataset.runId;
    list.replaceChildren(); if(!records.length)empty(list,isActive,scoped); else records.forEach(run=>list.append(row(run)));
    list.dataset.signature=signature;
    if(focused)list.querySelector(`[data-run-id="${focused}"]`)?.focus();
  }
}
function renderOrchestrators() {
  const workers=groupWorkers(runs, {conversation:filters.conversation});
  const controllers=new Map();
  for(const worker of workers){
    const key=worker.codex_thread_id||"unassigned";
    if(!controllers.has(key))controllers.set(key,{name:conversationName(worker),workers:0,runs:0});
    const entry=controllers.get(key);entry.workers++;entry.runs+=worker.runs.length;
  }
  const list=$("orchestrators");
  const signature=JSON.stringify([...controllers]);
  if(list.dataset.signature===signature)return;
  list.dataset.signature=signature;list.replaceChildren();
  if(!controllers.size)list.append(el("p",null,"No recorded workers for this conversation."));
  for(const [id,entry] of controllers){
    const item=el("div","orchestrator");
    item.append(el("strong",null,(id==="unassigned"?"Unknown coordinator":"Codex")+" · "+entry.name),el("span",null,`Recorded: ${entry.workers} workers · ${entry.runs} runs`));
    item.title=id==="unassigned"?"Conversation ID not recorded":`Codex conversation: ${id}`;
    if(id!=="unassigned"){
      const button=el("button","activity-button","View activity");button.type="button";
      button.setAttribute("aria-label",`View Codex activity for ${entry.name}`);
      button.addEventListener("click",()=>activityView.open(id,entry.name));item.append(button);
    }
    list.append(item);
  }
}
function renderExchanges(history) {
  const container=$("exchange-content");
  const signature=JSON.stringify(history.map(run=>[run.id,run.status,run.documents,run.model_selection,run.ended_at]));
  if(container.dataset.signature===signature)return;
  const expanded=new Map([...container.querySelectorAll("details")].map(node=>[node.dataset.exchange,node.open]));
  container.dataset.signature=signature;container.replaceChildren();
  container.append(el("p","exchange-note","Recorded handoffs, in order. Instructions include the launcher's wrapper when available. Replies are saved reports and may include launcher diagnostics, not a verbatim chat transcript. Use the coordinator’s activity view to inspect Codex actions outside these exchanges."));
  history.forEach((run,index)=>{
    const section=el("section","exchange-run");
    section.append(el("h3",null,`Run ${index+1} · ${run.title}`));
    section.append(el("p","exchange-meta",`${new Date(run.started_at*1000).toLocaleString()} · ${modelName(run)} / ${roleName(run.model_selection?.role)} · ${labels[run.status]||run.status}`));
    const request=run.documents?.input||run.documents?.brief;
    const report=run.documents?.report;
    const entries=[
      ["request",`Codex → ${backendName(run)} · ${index?"Follow-up instructions":"First recorded instructions"}`,request||"Instructions are unavailable for this recorded run."],
      ["reply",`${["error","timeout","interrupted"].includes(run.status)?"Launcher outcome for Codex":`${backendName(run)} → Codex · Reported outcome`}`,report||(activeStates.has(run.status)?"Awaiting the worker's report.":"No report was recorded.")]
    ];
    for(const [kind,title,body] of entries){
      const key=run.id+":"+kind;
      const card=el("details","exchange "+kind);card.dataset.exchange=key;
      card.open=expanded.has(key)?expanded.get(key):(index===history.length-1&&kind==="reply");
      card.append(el("summary",null,title),el("pre",null,body));section.append(card);
    }
    container.append(section);
  });
}
function renderStats(matching) {
  const stats=usageTotals(matching),container=$("usage-summary");container.replaceChildren();
  const items=[['Input tokens',tokenText(stats.input.value),`${stats.input.known}/${stats.runs} runs · uncached`],
    ['Output tokens',tokenText(stats.output.value),`${stats.output.known}/${stats.runs} runs`],
    ['Cache read',tokenText(stats.cache_read.value),`${stats.cache_read.known}/${stats.runs} runs`],
    ['Reported cost',costText(stats.reported.value),`${stats.reported.known} OpenCode runs`],
    ['API-equivalent estimate',costText(stats.api_equivalent.value),`${stats.api_equivalent.known} Claude runs · not a bill`],
    ['Effective output rate',stats.throughput===null?'—':stats.throughput.toFixed(1)+' tok/s',`${stats.timed} timed runs · includes tools`]];
  for(const [label,value,note] of items){const card=el('div','stat');card.append(el('span','stat-label',label),el('strong','stat-value',value),el('span','stat-note',note));container.append(card);}
}
function renderDetail() {
  if(!selected)return;
  const history=selected.runs?.length?selected.runs:[selected];
  const current=history.find(run=>run.id===selectedRunId)||history.at(-1);
  selectedRunId=current.id;
  $("detail-title").textContent=history[0].title;
  $("detail-role").textContent=`${backendName(current).toUpperCase()} WORKER · ${history.length} ${history.length===1?"RUN":"RUNS"}`;
  const meta=$("detail-meta");meta.replaceChildren(el("span",null,`${duration(history.reduce((sum,run)=>sum+elapsed(run),0))} across recorded runs`),el("span","detail-conversation",`Coordinator: Codex · ${conversationName(selected)}`));
  document.querySelectorAll("[data-tab]").forEach(button=>button.setAttribute("aria-selected",String(button.dataset.tab===selectedTab)));
  const exchanges=selectedTab==="exchanges";
  $("exchange-content").hidden=!exchanges;$("detail-content").hidden=exchanges;$("run-picker").hidden=exchanges;
  if(exchanges)renderExchanges(history);
  else {
    const selector=$("selected-run");
    const signature=JSON.stringify(history.map(run=>[run.id,run.title,run.status]));
    if(selector.dataset.signature!==signature){
      selector.replaceChildren(...history.map((run,i)=>new Option(`Run ${i+1} · ${run.title} · ${labels[run.status]||run.status}`,run.id)));
      selector.dataset.signature=signature;
    }
    selector.value=selectedRunId;
    $("detail-content").setAttribute("aria-labelledby","tab-"+selectedTab);
    let text;
    if(selectedTab==="info")text=[`Harness: ${backendName(current)}`,`Requested model: ${current.model_selection?.requested_model||"Claude default"}`,`Task type: ${current.model_selection?.task_type?.replaceAll("_"," ")||"Not recorded"}`,`Model routing: ${current.model_selection?.source?.replaceAll("_"," ")||"Not recorded"}`,`Role assigned by Codex: ${roleName(current.model_selection?.role)}`,"Role labels describe the assignment; they do not select a named harness plugin agent. Role-template provenance was not recorded.",`Permission policy: ${({scoped:"Scoped",full:"Full access",inherit:"Follow Codex"})[current.permissions?.policy]||"Not recorded"}`,`Effective permissions: ${({scoped:"Scoped",full:"Full access"})[current.permissions?.effective]||"Not recorded"}`,`Harness permission mode: ${current.permissions?.opencode_mode||current.permissions?.claude_mode||"Not recorded"}`,`Permission source: ${current.permissions?.source||"Not recorded"}`,`Permission decision: ${current.permissions?.reason||"Not recorded"}`,`Profile: ${current.model_selection?.profile||"Explicit or legacy"}`,`Effort: ${current.model_selection?.effort||"Claude default"}`,`Selection reason: ${current.model_selection?.reason||"Not recorded"}`,`Observed models: ${(current.models_used||[]).join(", ")||"Not reported yet"}`,current.backend==="opencode"?"Model evidence covers exported session history; helper calls may be absent.":"(Usage can include helper models.)",`Started: ${new Date(current.started_at*1000).toLocaleString()}`,`Worker session: ${current.session_id||"Not recorded"}`,`Run ID: ${current.id}`,`Coordinator: Codex · ${conversationName(current)}`,`Conversation ID: ${current.codex_thread_id||"Not recorded"}`,`Workspace: ${current.cwd}`,`Artifacts: ${current.output_dir}`,current.status_note||""].join("\n\n");
    else if(selectedTab==="usage")text=usageDetails(current);
    else text=current.documents?.[selectedTab] || (selectedTab==="report"&&activeStates.has(current.status)?"The worker is running. Its report will appear here when it finishes.":selectedTab==="stderr"?"No diagnostic output recorded. The full tool transcript is not streamed into this view.":"This artifact is not available.");
    if($("detail-content").textContent!==text)$("detail-content").textContent=text;
  }
  $("detail-footnote").textContent="One worker groups runs sharing a harness, worker session and Codex conversation. Only recorded runs are shown. A completed run does not prove Codex reviewed or accepted it.";
}
async function openDetails(id) {
  selectedId=id;selected=null;selectedRunId=null;selectedTab="exchanges";$("exchange-content").replaceChildren();delete $("exchange-content").dataset.signature;$("exchange-content").hidden=false;$("run-picker").hidden=true;$("detail-content").hidden=true;$("detail-title").textContent="Loading worker…";$("detail-content").textContent="";$("detail-meta").replaceChildren();$("details").showModal();
  try { const detail=await api("/api/runs/"+id);if(selectedId!==id)return;selected=detail;renderDetail(); } catch(error){$("exchange-content").textContent=error.message;}
}
async function refresh() {
  if(busy)return;busy=true;
  try {
    if(!token)throw new Error("Open this dashboard using the link provided by Codex. The link grants access to your local worker records.");
    const data=await api("/api/runs");runs=data.runs;populateFilters();
    if(["latest","message"].includes(filters.period)&&filters.conversation&&filters.conversation!=="unassigned"){
      const thread=filters.conversation;
      try {const context=await api("/api/messages?thread="+encodeURIComponent(thread));messageContext={thread,...context};}
      catch(error){messageContext={thread,messages:[],error:"Message filter unavailable: "+error.message};}
    }
    render();$("connection").className="connection online";$("connection-text").textContent="Live";$("notice").hidden=true;$("last-updated").textContent="Updated "+new Date().toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});
    if(selectedId&&$("details").open){const id=selectedId;const detail=await api("/api/runs/"+id);if(selectedId===id){selected=detail;renderDetail();}}
  } catch(error){$("connection").className="connection offline";$("connection-text").textContent="Disconnected";$("notice").textContent=error.message;$("notice").hidden=false;}
  finally{busy=false;}
}
$("this-task").disabled=!task;
$("this-task").addEventListener("click",()=>setScope(task||""));
$("all-tasks").addEventListener("click",()=>setScope(""));
for(const [value,label] of Object.entries(labels))$("status").append(new Option(label,value));
for(const key of ["conversation","model","role","status","period","sort","message"]){
  if(["status","period","sort"].includes(key)){
    $(key).value=filters[key];
    if($(key).selectedIndex<0){filters[key]=key==="sort"?"newest":"";$(key).value=filters[key];}
  }
  $(key).addEventListener("change",()=>{if(key==="conversation")filters.message="";filters[key]=$(key).value;changed();});
}
$("search").value=filters.q;
$("search").addEventListener("input",()=>{filters.q=$("search").value;changed();});
$("reset-filters").title="Restore the conversation from this link and clear other filters";
$("reset-filters").addEventListener("click",()=>{
  for(const key of Object.keys(filters))filters[key]="";
  filters.conversation=task||"";filters.sort="newest";
  for(const key of ["status","period","sort"])$(key).value=filters[key];
  $("search").value="";populateFilters();changed();
});
$("selected-run").addEventListener("change",()=>{selectedRunId=$("selected-run").value;renderDetail();});
$("close-details").addEventListener("click",()=>$("details").close());$("details").addEventListener("close",()=>{selectedId=null;selected=null;});
document.querySelectorAll("[data-tab]").forEach(button=>button.addEventListener("click",()=>{selectedTab=button.dataset.tab;renderDetail();}));
document.querySelector(".detail-tabs").addEventListener("keydown",event=>{if(!["ArrowLeft","ArrowRight","Home","End"].includes(event.key))return;event.preventDefault();const tabs=[...document.querySelectorAll("[data-tab]")];const current=tabs.indexOf(document.activeElement);const next=event.key==="Home"?0:event.key==="End"?tabs.length-1:(current+(event.key==="ArrowRight"?1:-1)+tabs.length)%tabs.length;tabs[next].focus();tabs[next].click();});
const activityView=setupActivity(api,el);
$("settings-link").href="/settings"+location.hash;
populateFilters();render();refresh();setInterval(refresh,2000);
