export type Status = 'working' | 'review' | 'ready' | 'attention';
export interface Agent {id:string; name:string; role:string; backend:'claude'|'gpt'; status:Status; task:string; elapsedSeconds:number; nextStep:string; color:string}
export interface Scenario {id:'active'|'empty'|'unavailable'; agents:Agent[]; completedRuns:number; fresh:boolean}
export type Filter = 'all'|'working'|'attention';
export interface DashboardState {scenario:Scenario; filter:Filter; selectedId:string|null}
export type Action = {type:'select';id:string;source:'scene'|'roster'} | {type:'filter';filter:Filter} | {type:'scenario';scenario:Scenario};
export function visibleAgents(s:DashboardState):Agent[] {return s.scenario.agents.filter(a=>s.filter==='all'||(s.filter==='working'?a.status==='working':a.status==='review'||a.status==='attention'));}
export function createState(scenario:Scenario):DashboardState {return {scenario,filter:'all',selectedId:scenario.agents[0]?.id??null};}
export function transition(state:DashboardState,action:Action):DashboardState {
 if(action.type==='scenario') return createState(action.scenario);
 if(action.type==='select') {
  if(!state.scenario.agents.some(a=>a.id===action.id))return state;
  if(action.source==='roster'&&!visibleAgents(state).some(a=>a.id===action.id))return state;
  return {...state,selectedId:action.id,filter:action.source==='scene'&&!visibleAgents(state).some(a=>a.id===action.id)?'all':state.filter};
 }
 const next={...state,filter:action.filter}; const agents=visibleAgents(next);
 return {...next,selectedId:agents.some(a=>a.id===state.selectedId)?state.selectedId:agents[0]?.id??null};
}
export function metrics(s:Scenario) {return {working:s.fresh?s.agents.filter(a=>a.status==='working').length:null,review:s.fresh?s.agents.filter(a=>a.status==='review').length:null,completed:s.completedRuns};}
export const statusLabels:Record<Status,string>={working:'Working',review:'Awaiting review',ready:'Ready',attention:'Needs attention'};
