import test from 'node:test';
import assert from 'node:assert/strict';
import * as view from '../assets/dashboard/view.mjs';
import { usageTotals } from '../assets/dashboard/stats.mjs';
const {filterRuns, sortRuns, conversationName}=view;

test('usage sums runs once and keeps subscription equivalent separate from reported cost',()=>{
 const runs=[{id:'one',started_at:0,ended_at:10,usage:{input:100,output:20,cache_read:500,cost_usd:.2,cost_kind:'api_equivalent'}},
 {id:'two',started_at:20,ended_at:40,usage:{input:50,output:40,cost_usd:0,cost_kind:'reported'}},
 {id:'unknown',started_at:50,ended_at:60}];
 const stats=usageTotals([...runs,runs[0]]);
 assert.equal(stats.runs,3);
 assert.equal(stats.input.value,150);
 assert.equal(stats.input.known,2);
 assert.equal(stats.output.value,60);
 assert.equal(stats.cache_read.value,500);
 assert.equal(stats.api_equivalent.value,.2);
 assert.equal(stats.reported.value,0);
 assert.equal(stats.throughput,2);
 assert.equal(stats.timed,2);
});
test('unknown tokens and unfinished time do not become zero or false throughput',()=>{
 const stats=usageTotals([{id:'one',status:'running',started_at:0,usage:{output:10}},
   {id:'two',started_at:0,ended_at:0,usage:{input:NaN,output:-1,cost_usd:null}}]);
 assert.equal(stats.input.value,null);
 assert.equal(stats.reported.value,null);
 assert.equal(stats.throughput,null);
});
test('filtered usage excludes nonmatching resumes even when worker card retains full history',()=>{
 const runs=[{id:'old',session_id:'same',started_at:1,usage:{input:100}},
   {id:'new',session_id:'same',started_at:199900,usage:{input:20}}];
 const matching=view.filterRuns(runs,{period:'15m'},200000);
 assert.equal(usageTotals(matching).input.value,20);
 assert.equal(usageTotals(view.groupWorkers(runs)[0].runs).input.value,120);
});
const now=200000;
const rows=[
 {id:'a', title:'Review PDF', codex_thread_id:'one', conversation_title:'Learning Hub', status:'needs_review', started_at:190000, ended_at:190100, model_selection:{requested_model:'fable',role:'reviewer'}},
 {id:'b', title:'Build PDF', codex_thread_id:'one', conversation_title:'Learning Hub', status:'completed', started_at:180000, ended_at:180500, model_selection:{requested_model:'opus',role:'implementer'}},
 {id:'c', title:'Earlier review', codex_thread_id:'two', conversation_title:'Other project', status:'completed', started_at:100, ended_at:110, model_selection:{requested_model:'fable',role:'reviewer'}},
 {id:'d', title:'Active review', codex_thread_id:'one', conversation_title:'Learning Hub', status:'running', started_at:199900, ended_at:null, model_selection:{requested_model:'fable',role:'reviewer'}}
];
test('combined filters match only the requested conversation, role, model and outcome',()=>{
 assert.deepEqual(filterRuns(rows,{conversation:'one',model:'fable',role:'reviewer',status:'needs_review'},now).map(r=>r.id),['a']);
 assert.deepEqual(filterRuns(rows,{conversation:'one',status:'attention'},now).map(r=>r.id),['a']);
});
test('search finds conversation names and status labels; dates use start time',()=>{
 assert.equal(filterRuns(rows,{q:'learning hub'},now).length,3);
 assert.deepEqual(filterRuns(rows,{q:'needs review'},now).map(r=>r.id),['a']);
 assert.deepEqual(filterRuns(rows,{period:'24h',model:'fable'},now).map(r=>r.id),['a','d']);
 assert.deepEqual(filterRuns(rows,{q:'no match'},now),[]);
});
test('sorting is numeric, supports running duration and does not mutate input',()=>{
 assert.deepEqual(sortRuns(rows,'oldest',now).map(r=>r.id),['c','b','a','d']);
 assert.deepEqual(sortRuns(rows,'longest',now).map(r=>r.id),['b','d','a','c']);
 assert.deepEqual(sortRuns(rows,'title',now).map(r=>r.id),['d','b','c','a']);
 assert.deepEqual(rows.map(r=>r.id),['a','b','c','d']);
});
test('duplicate conversation names remain separate by ID and unknown titles fall back',()=>{
 const renamed=rows.map(r=>({...r,conversation_title:'Same title'}));
 assert.equal(filterRuns(renamed,{conversation:'two'},now).length,1);
 assert.equal(conversationName({codex_thread_id:'abcdef123456'}),'Conversation 123456');
 assert.equal(conversationName({}),'Unassigned conversation');
});

test('role spelling variants share a human-readable filter',()=>{
 const variants=[{...rows[0],model_selection:{role:'verification-worker'}},{...rows[1],model_selection:{role:'verification worker'}}];
 assert.equal(filterRuns(variants,{role:'verification worker'},now).length,2);
});

test('resumes group by conversation and Claude session, retaining history across filters',()=>{
 const history=[{...rows[0],session_id:'same',status:'error'},
   {...rows[1],session_id:'same',started_at:195000,ended_at:195300},
   {...rows[2],session_id:'same'}, rows[3]];
 assert.equal(typeof view.groupWorkers,'function');
 const groups=view.groupWorkers(history);
 assert.equal(groups.length,3);
 const group=groups.find(g=>g.codex_thread_id==='one'&&g.session_id==='same');
 assert.equal(group.runs.length,2);
 assert.equal(group.status,'completed');
 assert.equal(group.title,'Review PDF');
 assert.equal(view.elapsed(group,now),400);
 const filtered=view.groupWorkers(history,{status:'error'});
 assert.equal(filtered.length,1);
 assert.equal(filtered[0].runs.length,2);
 assert.equal(filtered[0].matching_runs,1);
 assert.equal(filtered[0].status,'completed');
});

test('missing session IDs never merge and an active run keeps its worker active',()=>{
 assert.equal(typeof view.groupWorkers,'function');
 assert.equal(view.groupWorkers(rows).length,4);
 const grouped=view.groupWorkers([{...rows[0],session_id:'same',status:'running'},
   {...rows[1],session_id:'same',started_at:199999}]);
 assert.equal(grouped.length,1);
 assert.equal(grouped[0].status,'running');
});

test('worker identity includes harness and preserves legacy Claude groups',()=>{
 const history=[{...rows[0],session_id:'same'},
   {...rows[1],session_id:'same',backend:'claude'},
   {...rows[2],codex_thread_id:'one',session_id:'same',backend:'opencode'}];
 const groups=view.groupWorkers(history);
 assert.equal(groups.length,2);
 assert.equal(groups.find(g=>(g.backend||'claude')==='claude').runs.length,2);
 assert.equal(view.backendName({backend:'opencode'}),'OpenCode');
 assert.equal(view.backendName({}),'Claude Code');
});

test('short time windows include the exact start boundary',()=>{
 for(const [period,seconds] of Object.entries({'15m':900,'30m':1800,'1h':3600,'3h':10800,'6h':21600,'12h':43200})){
  const r=[{...rows[0],id:'before',started_at:now-seconds-1},{...rows[0],id:'at',started_at:now-seconds}];
  assert.deepEqual(filterRuns(r,{period},now).map(r=>r.id),['at']);
 }
});
test('message filters fail closed without a single conversation and a known boundary',()=>{
 assert.deepEqual(filterRuns(rows,{period:'latest',conversation:'one'},now),[]);
 assert.deepEqual(filterRuns(rows,{period:'message',since:190000},now),[]);
 assert.deepEqual(filterRuns(rows,{period:'message',conversation:'one',since:190000},now).map(r=>r.id),['a','d']);
 const resumed=[{...rows[1],session_id:'same'},{...rows[3],session_id:'same'}];
 const groups=view.groupWorkers(resumed,{period:'latest',conversation:'one',since:190000},now);
 assert.equal(groups.length,1);assert.equal(groups[0].runs.length,2);assert.equal(groups[0].matching_runs,1);
});
test('latest boundary follows new messages while a chosen message stays pinned',()=>{
 assert.equal(typeof view.messageBoundary,'function');
 const messages=[{line:20,timestamp:199000},{line:10,timestamp:190000}];
 assert.equal(view.messageBoundary({period:'latest'},messages).timestamp,199000);
 assert.equal(view.messageBoundary({period:'message',message:'10'},messages).timestamp,190000);
 assert.equal(view.messageBoundary({period:'message',message:'missing'},messages),null);
});

// Snapshot totals must follow the time of each observation, including active workers
// whose run started before the selected message. Run summaries cannot answer this.
const snapshots=await import('../assets/dashboard/snapshots.mjs');
const sample=(id,at,extra={})=>({id,at,input:10,output:2,cache_read:0,cache_write:null,context_tokens:400,context_limit:1000,context_percent:40,model:'sonnet',...extra});
const sampledRun=(id,samples,extra={})=>({id,title:'Sampled worker',codex_thread_id:'one',backend:'claude',session_id:'session',status:'completed',started_at:10,ended_at:200,model_selection:{requested_model:'sonnet',role:'implementer'},telemetry:{samples,coverage:'complete',source:'test',truncated:false},...extra});
test('sample snapshot counts an already active worker from the inclusive message boundary',()=>{
 assert.equal(typeof snapshots.usageSnapshot,'function');
 const result=snapshots.usageSnapshot([sampledRun('old',[sample('before',99),sample('boundary',100),sample('after',150),sample('future',250)])],{period:'message',conversation:'one',since:100},200);
 assert.equal(result.samples,2);
 assert.equal(result.input.value,20);
 assert.equal(result.first_at,100);
 assert.equal(result.latest_at,150);
});
test('snapshot fails closed for unresolved message scope and preserves identity filters',()=>{
 const runs=[sampledRun('one',[sample('a',100)]),sampledRun('two',[sample('b',100)],{codex_thread_id:'two'})];
 assert.equal(snapshots.usageSnapshot(runs,{period:'latest',conversation:'one'},200).samples,0);
 assert.equal(snapshots.usageSnapshot(runs,{period:'message',since:100},200).samples,0);
 assert.equal(snapshots.usageSnapshot(runs,{conversation:'two',model:'sonnet'},200).samples,1);
 assert.equal(snapshots.usageSnapshot(runs,{model:'opus'},200).samples,0);
 assert.equal(snapshots.usageSnapshot(runs,{},200).samples,2);
});
test('snapshot deduplicates resumed samples only within the same worker identity',()=>{
 const a=sample('shared',100),b=sample('new',110);
 const result=snapshots.usageSnapshot([sampledRun('first',[a]),sampledRun('resume',[a,b]),sampledRun('other',[a],{backend:'opencode'})],{},200);
 assert.equal(result.samples,3);
 assert.equal(result.input.value,30);
 assert.equal(result.workers.length,2);
});
test('zero remains known while missing samples and partial telemetry remain explicit',()=>{
 const result=snapshots.usageSnapshot([sampledRun('one',[sample('a',100,{input:0,output:null}),sample('b',110,{input:null,output:null})]),{id:'missing',started_at:50}],{},200);
 assert.equal(result.input.value,0);
 assert.equal(result.input.known,1);
 assert.equal(result.output.value,null);
 assert.equal(result.coverage,'partial');
 assert.equal(result.missing_runs,1);
 const empty=snapshots.usageSnapshot([],{},200);
 assert.equal(empty.input.value,null);
 assert.equal(empty.coverage,'unavailable');
});
test('context tracks first peak and latest observations across compaction without summing workers',()=>{
 const result=snapshots.usageSnapshot([sampledRun('one',[sample('c',120,{context_percent:15,context_tokens:150}),sample('a',100),sample('b',110,{context_percent:90,context_tokens:900})]),sampledRun('other',[sample('d',130)],{session_id:'another'})],{},200);
 const worker=result.workers.find(w=>w.session_id==='session');
 assert.equal(worker.first.context_percent,40);
 assert.equal(worker.peak.context_percent,90);
 assert.equal(worker.latest.context_percent,15);
 assert.equal(worker.latest.at,120);
 assert.equal(worker.latest.context_tokens,150);
 assert.equal(result.context_percent,undefined);
});
const accountSample=(at,used=20,reset=500,account='a')=>({at,account_id:account,windows:[{key:'five_hour',label:'Five-hour',used_percent:used,resets_at:reset}]});
const accountData=history=>({account_id:'a',history,windows:history.at(-1)?.windows||[]});
test('account delta uses known bracketing samples and ignores worker and model filters',()=>{
 const result=snapshots.accountDeltas(accountData([accountSample(80,10),accountSample(120,20),accountSample(180,25)]),{period:'message',conversation:'one',since:100,model:'sonnet',role:'reviewer'},200);
 assert.equal(result[0].delta,15);
 assert.equal(result[0].baseline_at,80);
 assert.equal(result[0].latest_at,180);
 assert.equal(result[0].comparable,true);
});
test('account resets decreases and unavailable start baselines are never negative consumption',()=>{
 for(const history of [[accountSample(80,90),accountSample(180,10,900)],[accountSample(80,30),accountSample(180,10)],[accountSample(120,10),accountSample(180,20)],[accountSample(80,10,null),accountSample(180,20,null)],[accountSample(80,10),accountSample(180,20,500,'other')]]){
  const result=snapshots.accountDeltas(accountData(history),{period:'message',conversation:'one',since:100},200);
  assert.equal(result[0].comparable,false);
  assert.equal(result[0].delta,null);
 }
});
test('account delta detects an intermediate reset even when endpoint usage is higher',()=>{
 const result=snapshots.accountDeltas(accountData([accountSample(80,10),accountSample(120,5,900),accountSample(180,20)]),{period:'message',conversation:'one',since:100},200);
 assert.equal(result[0].comparable,false);
 assert.equal(result[0].delta,null);
});
test('account boundary must be observed recently and fractional reset rounding is tolerated',()=>{
 const stale=snapshots.accountDeltas(accountData([accountSample(10,10),accountSample(190,20)]),{period:'message',conversation:'one',since:150},200);
 assert.equal(stale[0].comparable,false);
 const near=snapshots.accountDeltas(accountData([accountSample(80,10,500),accountSample(180,20,501)]),{period:'message',conversation:'one',since:100},200);
 assert.equal(near[0].delta,10);
 assert.equal(near[0].approximate,true);
});

test('relative sample windows include the boundary and unknown context never becomes zero',()=>{
 const result=snapshots.usageSnapshot([sampledRun('old',[sample('before',99),sample('at',100,{context_percent:null,context_tokens:null,context_limit:null}),sample('after',200,{context_percent:null,context_tokens:200,context_limit:null})])],{period:'15m'},1000);
 assert.equal(result.samples,2);
 assert.equal(result.workers[0].first.context_tokens,200);
 assert.equal(result.workers[0].peak.context_tokens,200);
 assert.equal(result.workers[0].peak.context_percent,null);
 assert.equal(result.workers[0].latest.context_percent,null);
});
test('expired account windows cannot imply current consumption from old observations',()=>{
 const result=snapshots.accountDeltas(accountData([accountSample(80,10,190),accountSample(180,20,190)]),{period:'message',conversation:'one',since:100},200);
 assert.equal(result[0].comparable,false);
 assert.equal(result[0].delta,null);
});

test('peak uses highest recorded tokens when all capacities are unknown',()=>{
 const result=snapshots.usageSnapshot([sampledRun('one',[sample('a',100,{context_tokens:900,context_limit:null,context_percent:null}),sample('b',120,{context_tokens:150,context_limit:null,context_percent:null})])],{},200);
 assert.equal(result.workers[0].peak.context_tokens,900);
 assert.equal(result.workers[0].peak.context_percent,null);
 assert.equal(result.workers[0].peak.at,100);
});
test('peak percentage uses only known capacity observations when capacities are mixed',()=>{
 const result=snapshots.usageSnapshot([sampledRun('one',[sample('a',100,{context_tokens:9000,context_limit:null,context_percent:null}),sample('b',120,{context_tokens:150,context_limit:1000,context_percent:15})])],{},200);
 assert.equal(result.workers[0].peak.context_percent,15);
 assert.equal(result.workers[0].peak.at,120);
});
test('account status becomes stale at reset without requiring another poll',()=>{
 assert.equal(typeof snapshots.accountStatus,'function');
 const observation={status:'available',windows:[{resets_at:200}]};
 assert.equal(snapshots.accountStatus(observation,199),'available');
 assert.equal(snapshots.accountStatus(observation,200),'stale');
 assert.equal(snapshots.accountStatus(observation,201),'stale');
 assert.equal(snapshots.accountStatus({...observation,windows:[{resets_at:500}]},201),'available');
 assert.equal(snapshots.accountStatus({status:'stale',windows:[{resets_at:500}]},201),'stale');
 assert.equal(snapshots.accountStatus({status:'refreshing',windows:[]},201),'refreshing');
});
