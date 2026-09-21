const valid = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
export function usageTotals(runs) {
  const rows=[...new Map(runs.map(run=>[run.id,run])).values()];
  const fields=['input','output','cache_read','cache_write','reasoning','reported','api_equivalent'];
  const result=Object.fromEntries(fields.map(key=>[key,{value:null,known:0}]));
  let seconds=0,output=0,timed=0;
  for(const run of rows){
    const usage=run.usage||{};
    for(const key of fields){
      const cost=['reported','api_equivalent'].includes(key);
      const value=cost?(usage.cost_kind===key?usage.cost_usd:null):usage[key];
      if(valid(value)){result[key].value=(result[key].value??0)+value;result[key].known++;}
    }
    const duration=valid(usage.duration_seconds)?usage.duration_seconds:
      valid(run.ended_at)&&valid(run.started_at)?run.ended_at-run.started_at:null;
    if(valid(usage.output)&&valid(duration)&&duration>0&&!['running','starting'].includes(run.status)){
      seconds+=duration;output+=usage.output;timed++;
    }
  }
  return {...result,runs:rows.length,timed,throughput:seconds>0?output/seconds:null};
}
export function tokenText(value) {
  return value===null?'—':new Intl.NumberFormat(undefined,{notation:'compact',maximumFractionDigits:1}).format(value);
}
export function costText(value) {
  return value===null?'—':value===0?'$0.00':value<.0001?'< $0.0001':`$${value.toFixed(4)}`;
}
export function compactUsage(runs) {
  const stats=usageTotals(runs);
  const coverage=stats.input.known<stats.runs||stats.output.known<stats.runs||runs.some(r=>r.usage?.partial)?' · partial':'';
  return `${tokenText(stats.input.value)} in · ${tokenText(stats.output.value)} out${coverage}`;
}
export function compactCost(runs) {
  const stats=usageTotals(runs),parts=[];
  if(stats.reported.known)parts.push(`${costText(stats.reported.value)} reported (${stats.reported.known}/${stats.runs} runs)`);
  if(stats.api_equivalent.known)parts.push(`${costText(stats.api_equivalent.value)} API equiv. (${stats.api_equivalent.known}/${stats.runs} runs)`);
  if(stats.throughput!==null)parts.push(`${stats.throughput.toFixed(1)} out tok/s incl. tools`);
  return parts.join(' · ')||'Cost and throughput not recorded';
}
export function usageDetails(run) {
  const usage=run.usage||{},stats=usageTotals([run]);
  const exact=value=>valid(value)?value.toLocaleString():'Not recorded';
  return [
    `Input tokens (uncached): ${exact(usage.input)}`,
    `Output tokens: ${exact(usage.output)}`,
    `Cache read tokens: ${exact(usage.cache_read)}`,
    `Cache write tokens: ${exact(usage.cache_write)}`,
    `Reasoning tokens: ${exact(usage.reasoning)} (provider-defined; may overlap output)`,
    `${usage.cost_kind==='api_equivalent'?'API-equivalent estimate':'Harness-reported cost'}: ${costText(usage.cost_usd??null)}`,
    `Effective output throughput: ${stats.throughput===null?'Not available':stats.throughput.toFixed(2)+' tokens/s'}`,
    'Throughput = reported output / elapsed run time, including tools, waits and retries. This is not decode speed.',
    `Source: ${usage.source||'No usage record available'}`,
    `Coverage: ${usage.scope||'Unknown'}`,
    `Partial stream: ${usage.partial?'Yes; totals may exclude unfinished steps':'Not flagged; completeness is not guaranteed'}`,
    'Claude API-equivalent estimates are not Max subscription charges. Harness-reported costs are not verified invoices. Missing values remain unknown; helper calls and interrupted streams may be incomplete. Input excludes separately reported cache tokens. Reasoning is not added to output totals.'
  ].join('\n\n');
}
