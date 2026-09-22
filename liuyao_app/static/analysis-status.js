/* Stage progress is based on saved events, never a simulated completion rate. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id),box=$('analysis-progress');
  const el=(tag,id,text,cls='')=>{const n=document.createElement(tag);n.id=id;n.textContent=text;n.className=cls;return n;};
  const stages=[['intent','理解问题'],['selection','确定取用'],['interpretation','综合解卦'],['report','整理报告']];
  box.replaceChildren();box.classList.add('analysis-monitor');box.setAttribute('aria-label','本次分析进度');
  const title=el('h3','analysis-progress-text','准备分析'),meta=el('p','analysis-job-model','','small-note');
  const stepText=el('p','analysis-step-count','','small-note'),bar=el('progress','analysis-stage-progress','');bar.max=4;bar.value=0;bar.setAttribute('aria-label','已完成的分析步骤');
  const list=el('ol','analysis-stage-list','');
  for(const [key,label] of stages){const item=el('li','analysis-stage-'+key,label);list.append(item);}
  const time=el('p','analysis-elapsed','','small-note'),connection=el('p','analysis-connection','','small-note');
  const hint=el('p','analysis-wait-hint','','small-note'),error=el('p','analysis-job-error','','error-text');error.hidden=true;error.setAttribute('role','status');
  const actions=el('div','analysis-monitor-actions','');
  const replies=el('button','analysis-view-replies','查看 AI 回复与报错','secondary-button'),refresh=el('button','analysis-refresh','刷新状态','text-button');
  const answer=el('button','analysis-view-answer','先看解卦结论','secondary-button');answer.type='button';answer.hidden=true;
  replies.type=refresh.type='button';actions.append(answer,replies,refresh);
  const note=el('p','analysis-lock-note','','small-note');
  box.append(title,meta,stepText,bar,list,time,connection,hint,error,actions,note);
  const floating=el('button','analysis-floating','正在解卦 · 查看进度');floating.type='button';floating.hidden=true;document.body.append(floating);
  const shortcut=el('button','analysis-records-open','AI 回复与报错','text-button');shortcut.type='button';document.querySelector('.analysis-actions').append(shortcut);
  let job=null,receivedAt=0,disconnected='',callbacks={};
  const running=()=>job&&['queued','running'].includes(job.status);
  const duration=s=>{s=Math.max(0,Math.floor(s||0));return s<60?`${s} 秒`:`${Math.floor(s/60)} 分 ${s%60} 秒`;};
  function tick(){
    if(!job)return;
    const age=Math.floor((Date.now()-receivedAt)/1000),extra=running()?age:0;
    time.textContent=`本次已用 ${duration((job.elapsed_seconds||0)+extra)}`+(running()&&job.request_started_at?` · 本次请求已等 ${duration((job.request_elapsed_seconds||0)+extra)}`:'');
    connection.textContent=disconnected?`状态连接中断：${disconnected} 正在自动重连，最后确认在 ${new Date(receivedAt).toLocaleTimeString('zh-CN',{hour12:false})}。`:
      `本地状态已连接 · ${age<3?'刚刚更新':duration(age)+'前更新'}`;
  }
  function update(value){
    job=value;receivedAt=Date.now();disconnected='';box.hidden=false;
    const active=running(),done=job.completed_stages||[],stage=job.stage==='finished'||job.stage==='interrupted'||job.stage==='failed'?job.last_stage:job.stage;
    const runningValue=String(Boolean(active));
    if(box.dataset.running!==runningValue)box.dataset.running=runningValue;
    floating.hidden=!active;
    const i=stages.findIndex(x=>x[0]===stage),name=i>=0?stages[i][1]:'准备任务';
    const failed=job.status==='failed',issue=job.error||job.result?.error;
    const fallback=job.result?.report_status?.mode==='fallback',preview=Boolean(job.preview_report);answer.hidden=!preview;
    title.textContent=active?(job.status==='queued'?'任务已提交，等待开始':`${i>=0?'第 '+(i+1)+' / 4 步 · ':''}${name}${job.attempt===2?' · 自动修复':''}`):failed?`分析未完成${i>=0?' · 停在'+name:''}`:job.result?.is_demo?'离线演示已完成':job.status==='completed'?'分析已完成':'本次分析已结束';
    meta.textContent=[job.model,job.analysis_run_id?'本次记录 '+job.analysis_run_id.slice(-8):'正在建立分析记录'].filter(Boolean).join(' · ');
    bar.value=done.length;stepText.textContent=`已完成 ${done.length} / 4 步${job.result?.is_demo?' · 演示未调用 AI':''}`;
    for(const [key]of stages){const item=$('analysis-stage-'+key);item.dataset.state=done.includes(key)?'done':key===stage?(failed?'error':'current'):'pending';item.setAttribute('aria-label',item.textContent+'：'+(done.includes(key)?'已完成':key===stage?(failed?'未完成':'当前步骤'):'尚未开始'));}
    hint.textContent=active?(job.phase==='validating'?'本阶段已收到回复，正在校验。':job.phase==='repairing'||job.attempt===2?'上一份回复格式未通过校验，正在自动修复；可展开查看草稿和原因。':job.phase==='stage_done'?'本阶段已保存，正在进入下一步。':'尚未收到本阶段的完整回复。max 模式可能等待较久；每一步返回后即可查看正文。'):'已返回的回复和报错保存在本次分析记录中。';
    if(preview)hint.textContent=`解卦结论已生成，可先看答案。报告整理最多等待 ${job.report_timeout_seconds||90} 秒（含格式修复），超时会保留现有结论。`;
    if(fallback){title.textContent='解卦已完成 · 已保留结论';hint.textContent=job.result.report_status.message;stepText.textContent=`已完成 ${done.length} / 4 步 · 报告使用程序排版`;}
    error.hidden=!issue;error.textContent=issue?`${issue.code||'分析错误'}：${issue.message||'请查看本次回复与报错。'}`:'';
    note.textContent=active?'分析期间暂不重复发起请求；刷新状态不会重新解卦或再次调用 AI。':'现在可以重新解卦；新分析将另建记录。';
    box.dataset.status=failed?'error':active?'running':'finished';tick();
  }
  floating.onclick=()=>{if($('mobile-work'))$('mobile-work').click();$('tab-results').click();box.scrollIntoView({block:'start',behavior:'smooth'});};
  replies.onclick=shortcut.onclick=()=>callbacks.replies?.();
  answer.onclick=()=>callbacks.answer?.();
  refresh.onclick=async()=>{refresh.disabled=true;try{await callbacks.refresh?.();}finally{refresh.disabled=false;}};
  setInterval(tick,1000);
  window.AnalysisStatus={bind(value){callbacks=value;},start(id,caseId){update({job_id:id,case_id:caseId,status:'queued',stage:'queued',elapsed_seconds:0,completed_stages:[]});},update,
    offline(message){disconnected=message;box.dataset.status='disconnected';tick();},clear(){job=null;box.hidden=true;box.dataset.running='false';floating.hidden=true;},
    focus(){box.scrollIntoView({block:'start',behavior:'smooth'});}};
})();
