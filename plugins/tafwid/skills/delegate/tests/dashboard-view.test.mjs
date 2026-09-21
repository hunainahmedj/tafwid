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
