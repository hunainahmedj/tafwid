import { test, expect } from '@playwright/test';
import {createState, transition, metrics, visibleAgents} from '../src/model';
import {scenarios} from '../src/fixtures';
test('counts work and reviews separately from completed history',()=>{
 expect(metrics(scenarios.active)).toEqual({working:2,review:1,completed:7});
 expect(metrics(scenarios.empty)).toEqual({working:0,review:0,completed:0});
 expect(metrics(scenarios.unavailable)).toEqual({working:null,review:null,completed:4});
});
test('filter reconciles selection, scene selection reveals a hidden agent',()=>{
 let s=transition(createState(scenarios.active),{type:'filter',filter:'attention'});
 expect(visibleAgents(s).map(a=>a.id)).toEqual(['cleo']); expect(s.selectedId).toBe('cleo');
 s=transition(s,{type:'select',id:'milo',source:'scene'});
 expect(s.filter).toBe('all');expect(s.selectedId).toBe('milo');
 expect(transition(s,{type:'select',id:'missing',source:'scene'})).toEqual(s);
});
test('empty filters and scenario changes remove stale selection',()=>{
 let s=transition(createState(scenarios.active),{type:'scenario',scenario:scenarios.empty});
 expect(s.selectedId).toBeNull();expect(visibleAgents(s)).toEqual([]);
 s=transition(s,{type:'filter',filter:'working'}); expect(s.selectedId).toBeNull();
 s=transition(s,{type:'scenario',scenario:scenarios.active});expect(s.filter).toBe('all');expect(s.selectedId).toBe('milo');
});
