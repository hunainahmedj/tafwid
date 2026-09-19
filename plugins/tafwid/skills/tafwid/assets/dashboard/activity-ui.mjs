export function setupActivity(api,el) {
  const $=id=>document.getElementById(id);
  const dialog=$('activity-dialog');
  let thread=null,before=null,next=null,generation=0,busy=false,signature='';
  async function refresh(force=false){
    if(!dialog.open||!thread||(busy&&!force))return;
    const version=++generation;busy=true;
    const query=new URLSearchParams({thread,q:$('activity-search').value,kind:$('activity-kind').value});
    if(before!==null)query.set('before',before);
    try{
      const data=await api('/api/activity?'+query);
      if(version!==generation)return;
      const last=data.last_activity?new Date(data.last_activity).toLocaleString():'Not recorded';
      $('activity-meta').textContent=`Model: ${data.model||'not recorded'}${data.effort?' · '+data.effort+' effort':''} · Last recorded turn: ${data.turn_status} · Last activity: ${last}`;
      next=data.next_before;
      $('activity-older').disabled=!data.has_more;$('activity-newest').disabled=before===null;
      $('activity-status').textContent=data.availability!=='available'?'This conversation’s local activity log is unavailable.':`${data.events.length} shown · ${data.total} matching events${data.history_truncated?' · only the most recent 5,000 events are retained':''}${before!==null?' · viewing older history':''}`;
      const updated=JSON.stringify(data.events);
      if(updated===signature)return;signature=updated;
      const expanded=new Set([...$('activity-events').querySelectorAll('details[open]')].map(n=>n.dataset.line));
      const nodes=data.events.map(event=>{
        const node=el('details','exchange activity-event');node.dataset.line=String(event.line);node.open=expanded.has(String(event.line));
        const kind=event.kind==='tool'?`Tool · ${event.name} · ${event.state==='returned'?'result recorded':'requested; no result recorded'}`:event.kind==='message'?`Codex ${event.name==='final'?'response':'update'}`:`Turn · ${event.text}`;
        node.append(el('summary',null,`${new Date(event.timestamp).toLocaleString()} — ${kind}`),el('pre',null,event.text));
        node.append(el('p','activity-source',`${data.source_path}:${event.line}`));return node;
      });
      $('activity-events').replaceChildren(...nodes);
    }catch(error){if(version===generation)$('activity-status').textContent=error.message;}
    finally{if(version===generation)busy=false;}
  }
  function changed(){before=null;signature='';refresh(true);}
  $('activity-search').addEventListener('input',changed);
  $('activity-kind').addEventListener('change',changed);
  $('activity-older').addEventListener('click',()=>{before=next;signature='';refresh(true);});
  $('activity-newest').addEventListener('click',changed);
  $('close-activity').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('close',()=>{thread=null;generation++;busy=false;});
  setInterval(()=>{if(before===null)refresh();},2000);
  return {open(id,title){thread=id;before=null;next=null;signature='';$('activity-title').textContent=title;$('activity-meta').textContent='Loading recorded activity…';$('activity-status').textContent='';$('activity-events').replaceChildren();$('activity-search').value='';$('activity-kind').value='';$('activity-older').disabled=true;$('activity-newest').disabled=true;dialog.showModal();refresh(true);}};
}
