import {escapeHTML as e,scoreLabel,testLabel,statusClass,diffClass,parseSSE} from './utils.mjs';
const $=id=>document.getElementById(id);
const state={token:sessionStorage.getItem('patchpilot-token')||'',tasks:[],jobs:[],job:null,candidate:null,tab:'diff',events:[],watch:null,config:null};
let toastTimer;
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,7000);}
async function api(path,options={}){
  const headers={'Authorization':`Bearer ${state.token}`,...(options.body?{'Content-Type':'application/json'}:{}),...options.headers};
  const response=await fetch('/api'+path,{...options,headers});
  if(!response.ok){let detail;try{detail=(await response.json()).detail;}catch{detail=`HTTP ${response.status}`;}throw new Error(typeof detail==='string'?detail:JSON.stringify(detail));}
  return response;
}
async function connect(){
  if($('token').value.trim()) state.token=$('token').value.trim();
  try{
    state.config=await (await api('/config')).json();
    state.tasks=await (await api('/tasks')).json();
    sessionStorage.setItem('patchpilot-token',state.token);
    $('login').hidden=true;$('workspace').hidden=false;
    $('task').innerHTML=state.tasks.map(t=>`<option value="${e(t.id)}">${e(t.title)}</option>`).join('');
    $('provider').querySelector('[value="openai"]').disabled=!state.config.live_provider_enabled;
    $('mode-label').textContent=state.config.runner==='docker'?'Docker runner':'Local fixture runner';
    taskChanged();await refreshHistory();
    if(state.jobs.length)await selectJob(state.jobs[0].id);
  }catch(err){toast(err.message);$('login').hidden=false;$('workspace').hidden=true;}
}
function taskChanged(){const task=state.tasks.find(t=>t.id===$('task').value);$('issue-text').textContent=task?.issue||'';if(task?.kind==='local_snapshot')$('provider').value='openai';else $('provider').value='demo';providerChanged();}
function providerChanged(){$('consent-label').hidden=$('provider').value!=='openai';$('run').disabled=$('provider').value==='openai'&&!state.config?.live_provider_enabled;}
async function refreshHistory(){state.jobs=await (await api('/jobs')).json();renderHistory();}
function renderHistory(){
  $('history').innerHTML=state.jobs.slice(0,12).map(j=>`<button data-job="${e(j.id)}" class="${state.job?.id===j.id?'selected':''}">${e(state.tasks.find(t=>t.id===j.task_id)?.title||j.task_id)}<small>${e(j.status.replaceAll('_',' '))} · ${e(new Date(j.created*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}))}</small></button>`).join('')||'<div class="small muted">No investigations yet.</div>';
  $('history').querySelectorAll('[data-job]').forEach(b=>b.onclick=()=>selectJob(b.dataset.job).catch(x=>toast(x.message)));
}
async function start(){
  $('run').disabled=true;
  try{
    const job=await (await api('/jobs',{method:'POST',body:JSON.stringify({task_id:$('task').value,provider:$('provider').value,consent_external:$('consent').checked})})).json();
    await refreshHistory();await selectJob(job.id);
  }catch(err){toast(err.message);}finally{providerChanged();}
}
async function selectJob(id){
  state.watch?.abort();state.watch=null;
  state.job=await (await api(`/jobs/${id}`)).json();
  state.events=await (await api(`/jobs/${id}/events`)).json();
  state.candidate=state.job.result.candidates?.[0]?.id||null;render();renderHistory();
  if(['queued','running'].includes(state.job.status))watchJob(id);
}
async function watchJob(id){
  const control=new AbortController();state.watch=control;
  let buffer='';
  try{
    const last=state.events.at(-1)?.id||0;
    const response=await api(`/jobs/${id}/stream?after=${last}`,{signal:control.signal});
    const reader=response.body.getReader();const decoder=new TextDecoder();
    while(true){
      const {done,value}=await reader.read();if(done)break;
      buffer+=decoder.decode(value,{stream:true});
      let boundary;
      while((boundary=buffer.indexOf('\n\n'))>=0){
        const segment=buffer.slice(0,boundary+2);buffer=buffer.slice(boundary+2);
        for(const ev of parseSSE(segment)){
          if(ev.event==='activity'){state.events.push(ev.data);renderActivity();}
          if(ev.event==='complete'){
            state.job=await (await api(`/jobs/${id}`)).json();state.candidate=state.job.result.candidates?.[0]?.id||null;render();await refreshHistory();return;
          }
        }
      }
    }
    if(!control.signal.aborted&&state.job?.id===id){state.job=await (await api(`/jobs/${id}`)).json();render();}
  }catch(err){if(err.name!=='AbortError')toast('Event connection ended. Refresh to inspect the job.');}
}
function render(){
  const job=state.job;if(!job)return;
  $('stat-status').textContent=job.status==='awaiting_review'?'Ready for review':job.status.charAt(0).toUpperCase()+job.status.slice(1);
  $('stat-id').textContent=job.id;
  const base=job.result.baseline;
  $('stat-baseline').textContent=base?`${base.passed} / ${base.tests}`:'Running…';
  const cs=job.result.candidates||[];
  $('stat-candidates').textContent=cs.length?`${cs.filter(c=>c.eligible).length} / ${cs.length}`:'—';
  $('stat-time').textContent=job.result.elapsed_s!=null?`${job.result.elapsed_s.toFixed(2)}s`:'—';
  $('candidate-count').textContent=String(cs.length);
  $('candidates').classList.toggle('empty',!cs.length);
  $('candidates').innerHTML=cs.length?cs.map((c,i)=>`<button class="candidate ${state.candidate===c.id?'selected':''}" data-candidate="${e(c.id)}"><div class="candidate-title"><span><span class="rank">${i+1}</span>${e(c.title)}</span><span class="badge ${c.eligible?'good':'bad'}">${c.eligible?'PASS':c.status==='rejected'?'BLOCKED':'FAIL'}</span></div><div class="candidate-meta"><span>${e(testLabel(c.test_result))}</span><span>score <strong>${scoreLabel(c.score)}</strong></span></div></button>`).join(''):e(job.error||'Investigation in progress. Test results will appear here.');
  $('candidates').querySelectorAll('[data-candidate]').forEach(b=>b.onclick=()=>{state.candidate=b.dataset.candidate;render();});
  renderPatch();renderActivity();
}
function renderActivity(){
  const visible=state.events.filter(ev=>!['model_turn'].includes(ev.kind));
  $('activity').classList.toggle('empty',!visible.length);
  $('activity').innerHTML=visible.length?visible.map(ev=>`<div class="activity-row"><span class="activity-dot"></span><div>${e(ev.payload.message||`${ev.kind.replaceAll('_',' ')}${ev.payload.eligible?' · public tests passed':''}`)}<time>${e(new Date(ev.created*1000).toLocaleTimeString())}</time></div></div>`).join(''):'Actions and evidence appear here.';
  $('activity').scrollTop=$('activity').scrollHeight;
}
function renderPatch(){
  const c=state.job?.result.candidates?.find(x=>x.id===state.candidate);const content=$('patch-content');
  if(!c){$('review-controls').hidden=true;content.classList.add('empty');content.textContent='Select a candidate to inspect its diff and evidence.';return;}
  content.classList.remove('empty');$('patch-title').textContent=c.title;$('patch-subtitle').textContent=c.id+' · original tests unchanged';
  $('patch-status').textContent=c.eligible?'PUBLIC TESTS PASS':c.policy_error?'POLICY BLOCKED':'TESTS FAILED';$('patch-status').className='badge '+(c.eligible?'good':'bad');
  document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===state.tab));
  if(state.tab==='diff')content.innerHTML=c.diff?c.diff.split('\n').map(line=>`<div class="diff-line ${diffClass(line)}">${e(line)||' '}</div>`).join(''):`<div class="test-output">${e(c.policy_error||'No changes')}</div>`;
  else if(state.tab==='tests')content.innerHTML=`<div class="test-output">${e(c.test_result?.output||c.policy_error||'No test output')}\n\nRunner: ${e(c.test_result?.runner||'not executed')}\n${e(c.rationale)}</div>`;
  else content.innerHTML=c.features?`<table class="feature-table"><tbody>${Object.entries(c.features).map(([key,value])=>`<tr><td>${e(key)}</td><td>${Number(value).toFixed(4)}</td></tr>`).join('')}</tbody></table>`:'<div class="test-output">No features computed for a policy-blocked proposal.</div>';
  const pending=state.job.status==='awaiting_review';const approved=state.job.status==='approved'&&state.job.reviews.at(-1)?.candidate_id===c.id;
  $('review-controls').hidden=!pending&&!approved;
  $('approve').hidden=!pending;$('reject').hidden=!pending;$('review-note').hidden=!pending;document.querySelector('label[for="review-note"]').hidden=!pending;
  $('approve').disabled=!c.eligible;$('download').hidden=!approved;
}
async function review(decision){
  if(!$('review-note').value.trim()||$('review-note').value.trim().length<3){toast('Add a review note before submitting.');return;}
  try{
    state.job=await (await api(`/jobs/${state.job.id}/review`,{method:'POST',body:JSON.stringify({candidate_id:state.candidate,decision,note:$('review-note').value.trim(),version:state.job.version})})).json();
    state.events=await (await api(`/jobs/${state.job.id}/events`)).json();render();await refreshHistory();toast(decision==='approve'?'Review recorded. The diff can now be exported; original code is unchanged.':'Review recorded. No code was applied.');
  }catch(err){toast(err.message);}
}
async function download(){try{const response=await api(`/jobs/${state.job.id}/patch`);const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download=`patchpilot-${state.job.id}.diff`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(err){toast(err.message);}}
async function metrics(){
  if(!state.token){toast('Connect with your local API token first.');return;}
  try{
    const r=await (await api('/metrics')).json();$('workspace').hidden=true;$('metrics').hidden=false;$('breadcrumb').textContent='Model evaluation';$('nav-work').classList.remove('active');$('nav-metrics').classList.add('active');
    const rows=Object.entries(r.evaluations.test).map(([name,m])=>`<tr><td>${e(name.replaceAll('_',' '))}</td><td>${m.top1_correct} / ${m.tasks}</td><td>${m.mean_reciprocal_rank.toFixed(3)}</td><td>${m.candidate_auc?.toFixed(3)||'—'}</td></tr>`).join('');
    $('metrics-content').innerHTML=`<h2>Held-out bug families</h2><p>24 authored tasks · 144 candidate patches · 15 train / 3 validation / 6 test tasks</p><table><thead><tr><th>Method</th><th>Top-ranked repairs correct</th><th>Reciprocal rank</th><th>Candidate AUC</th></tr></thead><tbody>${rows}</tbody></table><p>The neural model does not outperform the logistic baseline on top-1 accuracy here. This small result supports pipeline correctness—not production repair accuracy.</p><p>${r.limitations.map(e).join('<br>')}</p>`;
  }catch(err){toast(err.message);}
}
$('connect').onclick=connect;$('token').onkeydown=ev=>{if(ev.key==='Enter')connect();};$('task').onchange=taskChanged;$('provider').onchange=providerChanged;$('run').onclick=start;
$('refresh').onclick=async()=>{try{await refreshHistory();if(state.job)await selectJob(state.job.id);}catch(err){toast(err.message);}};
$('approve').onclick=()=>review('approve');$('reject').onclick=()=>review('reject');$('download').onclick=download;
$('nav-metrics').onclick=metrics;$('nav-work').onclick=()=>{if(!state.token)return;$('metrics').hidden=true;$('workspace').hidden=false;$('breadcrumb').textContent='Software repair';$('nav-work').classList.add('active');$('nav-metrics').classList.remove('active');};
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{state.tab=b.dataset.tab;renderPatch();});
$('logout').onclick=()=>{state.watch?.abort();state.token='';sessionStorage.removeItem('patchpilot-token');location.reload();};
if(state.token)connect();
