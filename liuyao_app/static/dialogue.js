(() => {
  'use strict';
  if (new URLSearchParams(location.search).get('legacy') === '1') {document.body.classList.remove('chat-first');return;}
  const $ = id => document.getElementById(id), app = window.LiuyaoApp;
  const state = {id:null,detail:null,mount:null,switching:false,sending:false,pending:null,creation:null,
    jobs:new Map(),binds:new Map(),collapsed:new Set(),applied:null,restored:null,ready:false,draftQueue:Promise.resolve(),reloadQueue:Promise.resolve()};
  const names = {cast:'六爻占问',case:'六爻占问',followup:'六爻占问',knowledge:'知识库问答',feedback:'技能反馈'};
  const make = (tag,cls,text) => {const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=String(text);return n;};
  const key = () => window.LiuyaoCompat.requestId();
  const clear = n => {while(n.firstChild)n.removeChild(n.firstChild);};
  const request = (path,data,idem) => new Promise((resolve,reject)=>{
    const xhr=new XMLHttpRequest();xhr.open(data===undefined?'GET':'POST',path);xhr.timeout=15000;
    xhr.setRequestHeader('X-App-Request','1');xhr.setRequestHeader('Accept','application/json');
    if(data!==undefined){xhr.setRequestHeader('Content-Type','application/json');xhr.setRequestHeader('X-Idempotency-Key',idem||key());}
    xhr.onload=()=>{try{const result=JSON.parse(xhr.responseText);if(xhr.status>=200&&xhr.status<300)resolve(result);else reject(new Error(result.error?.message||'操作未完成。'));}catch(_){reject(new Error('本地服务暂时未能返回结果。'));}};
    xhr.onerror=()=>reject(new Error('本地连接中断，输入仍然保留。'));xhr.ontimeout=()=>reject(new Error('本地连接未及时响应，输入仍然保留。'));
    xhr.send(data===undefined?null:JSON.stringify(data));
  });
  const api = (path,data,idem) => request('/api/workbench/'+path,data,idem);
  function note(text,error=false){if(typeof document==='undefined')return;const n=$('dialogue-status');if(!n)return;n.textContent=text;n.classList.toggle('is-error',error);}
  function persist(){if(!state.ready)return;app.persistDraft();if(!window.LiuyaoAndroid){try{localStorage.setItem('liuyao-dialogue-session',JSON.stringify(draft()));}catch(_){}}}
  function draft(){let card=null;if(state.mount&&!state.switching)card={turn_id:state.mount.turnId,case_id:state.mount.caseId,...app.captureCard()};return {id:state.id,text:$('dialogue-input').value,mode:$('dialogue-mode').value,pending:state.pending,creation:state.creation,collapsed:Array.from(state.collapsed).slice(-20),card};}
  function restoreDraft(value){state.restored=value;}
  function busy(){return state.sending||Array.from(state.jobs.values()).some(j=>j.dialogueId===state.id);}
  function refreshBusy(){$('dialogue-send').disabled=!state.ready||busy();$('dialogue-send').textContent=busy()?'处理中…':'发送 ↗';window.LiuyaoAndroid?.analysisState(Boolean(state.jobs.size||app.isAnalyzing()||window.SkillWorkbench?.isBusy()));}

  // Reuse the checked specialist controls; keep their DOM and event handlers alive.
  const specialist=make('div');specialist.id='dialogue-specialist';
  const specialistTools=make('div','dialogue-case-tools');
  for(const [view,label]of [['input','核对输入'],['results','查看卦盘与解读'],['feedback','记录实际结果']]){
    const b=make('button','text-button',label);b.type='button';b.onclick=()=>{if(view!=='input'&&!app.context().caseId)return;app.showView(view);};specialistTools.append(b);
  }
  specialist.append(specialistTools);
  for(const id of ['input-section','results-section','feedback-section'])specialist.append($(id));
  $('dialogue-parking').append(specialist);
  const contextDetails=make('details','dialogue-case-context'),contextSummary=make('summary','','核对所问与本次人物信息');contextDetails.append(contextSummary);
  const questionStep=$('case-form').querySelector('.mobile-question-step');
  if(questionStep){questionStep.before(contextDetails);contextDetails.append(questionStep);}
  const buzhai=$('buzhai-details');buzhai.hidden=true;contextDetails.after(buzhai);
  const direct=document.querySelector('input[name="casting-method"][value="direct"]');if(direct)direct.parentElement.querySelector('span').textContent='逐爻录入';
  $('time-details').querySelector('summary').textContent='起卦时间与地点 · 默认当前定位和真太阳时';
  const defaults=make('p','dialogue-defaults');defaults.id='dialogue-defaults';$('time-details').before(defaults);
  const addBuzhai=make('button','text-button','补充卜宅选项');addBuzhai.type='button';addBuzhai.id='dialogue-add-buzhai';
  addBuzhai.onclick=()=>{buzhai.hidden=false;$('buzhai-enabled').checked=true;buzhai.open=true;$('buzhai-enabled').dispatchEvent(new Event('change',{bubbles:true}));};$('time-details').after(addBuzhai);
  const welcome=$('dialogue-feed').firstElementChild;
  $('dialogue-documents-dialog').append($('kb-status'),$('kb-library'));
  $('dialogue-feedback-dialog').append($('issues-workspace'));
  $('dialogue-rules-dialog').append($('rules-page'));
  $('dialogue-feed').before($('global-message'));
  function updateDefaults(){
    if(!state.mount)return;
    const location=$('location-status').textContent,solar=$('solar-time-preview').textContent;
    const recorded=state.mount.caseId?'沿用这卦保存的时间和地点。':state.applied?.time_policy==='current'?'默认当前起卦时刻与手机定位；按当地真太阳时排盘。':'补录旧卦：请核对当时的时间和地点。';
    defaults.textContent=[recorded,solar||location].filter(Boolean).join('\n');
    if(!state.mount.caseId&&/未能|被拒绝|无法定位|定位未完成|权限/.test(location)&&!$('cast-longitude').value)$('time-details').open=true;
  }
  new MutationObserver(updateDefaults).observe($('location-status'),{childList:true,subtree:true,characterData:true});
  new MutationObserver(updateDefaults).observe($('solar-time-preview'),{childList:true,subtree:true,characterData:true});

  async function stashCard(){
    if(!state.id||!state.mount||state.switching)return;
    const id=state.id,cardId=state.mount.turnId;
    const turn=state.detail?.turns.find(t=>t.turn_id===cardId);
    if(turn?.result?.action!=='cast')return;
    const capture=app.captureCard(),body={card_id:cardId,...capture};
    state.detail.context.drafts=state.detail.context.drafts||{};state.detail.context.drafts[cardId]=capture;
    state.draftQueue=state.draftQueue.catch(()=>{}).then(()=>api('dialogues/'+id+'/draft',body));
    try{await state.draftQueue;}catch(error){note('草稿尚未同步到本机服务：'+error.message,true);}
  }
  function inferredDefaults(turn){const pending=state.detail?.context.pending_cast;return pending?.turn_id===turn.turn_id?pending.prefill:turn.result.prefill;}
  function applyUpdates(prefill){
    const before=state.applied||{};
    if(prefill.buzhai){
      const current=window.Buzhai.read(false)||{};const next={...current};
      for(const [field,value]of Object.entries(prefill.buzhai)){
        if(!current[field]||current[field]===before.buzhai?.[field]||(!before.buzhai&&['stage','site_kind','role','residence'].includes(field)))next[field]=value;
      }
      window.Buzhai.fill(next);buzhai.hidden=false;buzhai.open=true;
    }else if(before.buzhai){window.Buzhai.fill(null);buzhai.hidden=true;}
    for(const [field,id]of [['subject','person-subject'],['querent_age','querent-age'],['subject_age','subject-age'],['background','person-background']]){
      const value=prefill.person?.[field];if(value===undefined)continue;
      if(!$(id).value||$(id).value==='unspecified'||String($(id).value)===String(before.person?.[field]??'')){$(id).value=String(value);$(id).dispatchEvent(new Event('change',{bubbles:true}));}
    }
    state.applied=JSON.parse(JSON.stringify(prefill));updateDefaults();
  }
  async function mountCard(turn,host,force=false){
    if(state.switching)return;
    state.collapsed.delete(turn.turn_id);
    const result=turn.result,caseId=result.case_id||null;
    if(state.mount?.turnId===turn.turn_id&&state.mount.dialogueId===state.id&&!force){
      host.append(specialist);if(!caseId)applyUpdates(inferredDefaults(turn));updateDefaults();const toggle=$('dialogue-toggle-'+turn.turn_id);if(toggle)toggle.textContent='收起操作卡片';return;
    }
    if(app.context().busy){note('当前卦例正在分析。可以继续查看或讨论资料，完成后再切换卦例。');return;}
    await stashCard();state.switching=true;
    try{
      $('dialogue-parking').append(specialist);state.mount={turnId:turn.turn_id,caseId,dialogueId:state.id};host.append(specialist);specialist.hidden=true;host.setAttribute('aria-busy','true');
      const stored=state.restored?.id===state.id&&state.restored.card?.turn_id===turn.turn_id?state.restored.card:state.detail.context.drafts?.[turn.turn_id];
      if(caseId){await app.loadCase(caseId,{quiet:true});if(stored)app.restoreCard(stored);buzhai.hidden=!window.Buzhai.read(false);}
      else{
        const prefill=inferredDefaults(turn);state.applied=JSON.parse(JSON.stringify(prefill));
        await app.prepareDialogue(prefill,state.detail.context.profile_id,stored);buzhai.hidden=!prefill.buzhai;
        if(prefill.buzhai)buzhai.open=true;
        const selected=$('profile-select').value;
        if(selected&&!state.detail.context.profile_id){state.detail.context.profile_id=selected;$('dialogue-profile').value=selected;await api('dialogues/'+state.id+'/profile',{profile_id:selected});}
      }
      contextDetails.open=false;updateDefaults();
    }catch(error){note(error.message,true);}finally{state.switching=false;specialist.hidden=false;host.setAttribute('aria-busy','false');const toggle=$('dialogue-toggle-'+turn.turn_id);if(toggle)toggle.textContent='收起操作卡片';persist();}
  }
  function cardFor(turn,container){
    const result=turn.result,card=make('section','dialogue-card');card.dataset.turnId=turn.turn_id;
    card.append(make('h3','',result.case_id?'保存的卦例':result.prefill?.buzhai?'卜宅 · 记录本次起卦':'记录本次起卦'));
    const p=make('p','dialogue-case-question',result.prefill?.question||result.answer||'');card.append(p);
    if(!result.case_id)card.append(make('p','dialogue-card-caption','会话中能确定的选项已预填，你可以核对或更改。'));
    const host=make('div','dialogue-mount');host.id='dialogue-mount-'+turn.turn_id;
    const open=make('button','secondary-button dialogue-card-toggle',result.case_id?'展开卦盘 / 继续这次占问':'展开起卦卡片');open.id='dialogue-toggle-'+turn.turn_id;open.type='button';open.onclick=async()=>{
      if(state.mount?.turnId===turn.turn_id&&host.contains(specialist)){await stashCard();$('dialogue-parking').append(specialist);state.collapsed.add(turn.turn_id);state.mount=null;open.textContent=result.case_id?'展开卦盘 / 继续这次占问':'展开起卦卡片';persist();}
      else await mountCard(turn,host);
    };
    card.append(open,host);container.append(card);
  }
  function feedbackCard(turn,container){
    const result=turn.result,card=make('section','dialogue-card');card.append(make('h3','','给当前技能提反馈'));
    const skill=make('select');skill.setAttribute('aria-label','反馈对应技能');for(const [id,name]of [['liuyao','六爻占问'],['knowledge','知识库问答']]){const option=make('option','',name);option.value=id;skill.append(option);}skill.value=result.skill_id;
    const title=make('input','dialogue-feedback-title');title.value=result.title;title.maxLength=200;title.setAttribute('aria-label','反馈标题');
    const description=make('textarea','dialogue-feedback-description');description.value=result.description;description.maxLength=8000;description.setAttribute('aria-label','反馈详情');
    const button=make('button','primary-button','保存并由 AI 处理');button.type='button';const message=make('p','small-note');let issueId=result.issue_id||null,saveKey='dialogue-feedback-'+turn.turn_id,processKey=key();
    button.onclick=async()=>{button.disabled=true;try{if(!issueId){issueId=(await api('issues',{skill_id:skill.value,title:title.value,description:description.value},saveKey)).issue_id;await api('dialogues/'+state.id+'/feedback',{turn_id:turn.turn_id,issue_id:issueId});result.issue_id=issueId;}
      title.disabled=description.disabled=skill.disabled=true;
      const job=await api('issues/'+issueId+'/process',model(),processKey);message.textContent='反馈已保存，AI 正在处理。';watchIssue(job.job_id,message,button);
    }catch(error){message.textContent=error.message;button.disabled=false;}};
    card.append(skill,title,description,button,message);container.append(card);
    if(issueId){title.disabled=description.disabled=skill.disabled=true;button.disabled=true;api('issues/'+issueId).then(issue=>{message.textContent=issue.result?.summary||issue.result?.error?.message||'反馈已保存。';const running=issue.attempts?.find(a=>['queued','running'].includes(a.status));
      if(running){watchIssue(running.job_id,message,button);return;}
      button.disabled=false;if(['applied','reviewed','needs_development','needs_sources'].includes(issue.status)){button.textContent='查看反馈与处理记录';button.onclick=openFeedback;}else button.textContent='交给 AI 继续处理';
    }).catch(error=>{message.textContent=error.message;button.disabled=false;});}
  }
  function citation(source,container){const details=make('details','dialogue-citation');details.append(make('summary','',`${source.title} · 第 ${source.sequence} 段`),make('blockquote','',source.text));container.append(details);}
  async function render(scroll=false){
    const mounted=state.mount;
    $('dialogue-parking').append(specialist);clear($('dialogue-feed'));
    if(!state.detail?.turns.length){$('dialogue-feed').append(welcome);return;}
    for(const turn of state.detail.turns){
      const article=make('article','dialogue-turn');article.dataset.messageId=turn.turn_id;
      article.append(make('div','dialogue-user',turn.user_text));const answer=make('div','dialogue-assistant'),result=turn.result||{};
      if(names[result.action])answer.append(make('span','dialogue-skill-tag',names[result.action]));
      answer.append(make('p','dialogue-answer',result.answer||result.error?.message||(turn.status==='failed'?'这条消息未完成，内容已保存。':'正在处理你的消息…')));
      if(result.requires_reanalysis)answer.append(make('p','small-note','这条补充可能影响原判断，可以展开卦盘后进行完整复评。'));
      if(result.demo)answer.append(make('p','small-note','离线检索演示 · 未调用模型'));
      for(const source of result.citations||[])citation(source,answer);
      if(result.action==='cast'&&!result.update_target||result.action==='case')cardFor(turn,answer);
      if(result.action==='cast'&&result.update_target){const button=make('button','text-button','查看已更新的起卦卡片');button.type='button';button.onclick=()=>{const target=state.detail.turns.find(t=>t.turn_id===result.update_target);const host=$('dialogue-mount-'+result.update_target);if(target&&host)mountCard(target,host);};answer.append(button);}
      if(result.action==='feedback')feedbackCard(turn,answer);
      if(result.action==='documents'){const b=make('button','secondary-button','导入或管理资料');b.type='button';b.onclick=openDocuments;answer.append(b);}
      if(result.action==='profiles'){const b=make('button','secondary-button','打开人物档案');b.type='button';b.onclick=openPeople;answer.append(b);}
      if(result.choices?.length){const choices=make('div','dialogue-message-tools');for(const choice of result.choices){const b=make('button','dialogue-choice',choice.label);b.type='button';b.onclick=()=>send(turn.user_text,choice.mode);choices.append(b);}answer.append(choices);}
      if(turn.status==='failed'){const retry=make('button','text-button','重新处理这条消息');retry.type='button';retry.onclick=()=>send(turn.user_text,turn.mode);answer.append(retry);}
      article.append(answer);$('dialogue-feed').append(article);
    }
    const pending=state.detail.context.pending_cast,targetId=pending?.turn_id||((mounted?.dialogueId===state.id)?mounted.turnId:null);
    if(targetId&&!state.collapsed.has(targetId)){const turn=state.detail.turns.find(t=>t.turn_id===targetId);const host=$('dialogue-mount-'+targetId);if(turn&&host)await mountCard(turn,host);}
    $('dialogue-context-label').textContent=pending?'补充会话会预填到当前起卦卡片。':state.detail.context.last_skill==='knowledge'?'继续围绕资料提问，也可以说“回到刚才的卦”。':state.detail.context.active_case?'继续追问会沿用当前卦盘；新问题可以另起一卦。':'我会根据你的问题展开需要的操作。';
    if(scroll)$('dialogue-feed').lastElementChild?.scrollIntoView({block:'start',behavior:'smooth'});
  }
  function reload(scroll=false){
    if(!state.id)return Promise.resolve();const id=state.id;
    const operation=state.reloadQueue.catch(()=>{}).then(async()=>{
      if(id!==state.id)return;const result=await api('dialogues/'+id);if(id!==state.id)return;
      state.detail=result;$('dialogue-title').textContent=result.title;$('dialogue-export').hidden=false;$('dialogue-export').href='/api/workbench/dialogues/'+id+'/export';
      await render(scroll);for(const jobId of result.active_jobs)watch(jobId,id);await loadHistory();
    });state.reloadQueue=operation;return operation;
  }
  function model(){return {provider:$('provider-select').value,model:$('model-select').value};}
  async function ensureDialogue(title){if(state.id)return;if(!state.creation)state.creation={title:title.slice(0,60),key:key()};persist();const result=await api('dialogues',{title:state.creation.title},state.creation.key);state.id=result.dialogue_id;state.creation=null;state.detail={turns:[],context:{}};persist();}
  async function send(text,mode){
    if(busy())return;text=(text??$('dialogue-input').value).trim();mode=mode||$('dialogue-mode').value;if(!text){$('dialogue-input').focus();return;}
    state.sending=true;refreshBusy();note('');
    try{
      await stashCard();await ensureDialogue(text);const body={text,mode,...model()},signature=JSON.stringify([state.id,body]);
      if(state.pending?.signature!==signature)state.pending={signature,key:key(),text,mode,dialogueId:state.id};persist();
      const accepted=await api('dialogues/'+state.id+'/messages',body,state.pending.key);state.pending.jobId=accepted.job_id;
      $('dialogue-input').value='';$('dialogue-mode').value='auto';persist();await reload(true);watch(accepted.job_id,state.id);
    }catch(error){note(error.message,true);}finally{state.sending=false;refreshBusy();}
  }
  function watch(jobId,dialogueId){
    if(state.jobs.has(jobId))return;const tracked={dialogueId};state.jobs.set(jobId,tracked);refreshBusy();
    async function tick(){
      try{
        const job=await api('jobs/'+jobId);
        if(!['queued','running'].includes(job.status)){
          state.jobs.delete(jobId);refreshBusy();
          if(state.id===dialogueId){await reload(true);note(job.result?.error?.message||'',job.status==='failed');}
          if(state.pending?.jobId===jobId)state.pending=null;
          persist();return;
        }
      }catch(error){if(state.id===dialogueId)note(error.message,true);}
      tracked.timer=setTimeout(tick,1000);
    }tick();
  }
  async function watchIssue(jobId,message,button){
    if(!state.jobs.has(jobId)){state.jobs.set(jobId,{dialogueId:state.id,kind:'issue'});refreshBusy();}
    try{const job=await api('jobs/'+jobId);if(['queued','running'].includes(job.status)){setTimeout(()=>watchIssue(jobId,message,button),1200);return;}
      state.jobs.delete(jobId);refreshBusy();
      message.textContent=job.result?.applied_skill?'本机技能偏好已更新，可以在反馈与技能版本中回退。':job.result?.summary||job.result?.error?.message||'处理记录已保存。';button.textContent='查看反馈与版本';button.disabled=false;button.onclick=openFeedback;
    }catch(error){state.jobs.delete(jobId);refreshBusy();message.textContent=error.message;button.disabled=false;}
  }
  async function loadHistory(){
    const [dialogues,cases]=await Promise.all([api('dialogues'),request('/api/cases')]);
    for(const id of ['dialogue-history-list','dialogue-recent']){clear($(id));for(const item of dialogues.dialogues.slice(0,id==='dialogue-recent'?6:100)){
      const b=make('button','dialogue-history-item',item.title);b.type='button';b.setAttribute('aria-current',String(item.dialogue_id===state.id));b.append(make('small','',`${item.turns} 条消息`));b.onclick=()=>openDialogue(item.dialogue_id);$(id).append(b);
    }if(!$(id).childElementCount)$(id).append(make('p','small-note','对话会自动保存在这里。'));}
    clear($('dialogue-legacy-cases'));for(const item of cases.cases.slice(0,100)){const b=make('button','dialogue-history-item',item.question);b.type='button';b.onclick=()=>openLegacy(item.case_id,item.question);$('dialogue-legacy-cases').append(b);}
  }
  async function openDialogue(id){
    if(state.switching)return;if(app.context().busy){note('当前卦例仍在分析，完成后再切换对话。');return;}
    await stashCard();$('dialogue-parking').append(specialist);state.id=id;state.mount=null;state.pending=null;state.applied=null;$('dialogue-input').value='';$('global-message').hidden=true;$('global-message').textContent='';$('dialogue-history-dialog').close();await reload();await loadProfiles();persist();
  }
  async function newDialogue(){if(app.context().busy){note('当前卦例仍在分析，完成后再新建对话。');return false;}await stashCard();$('dialogue-parking').append(specialist);state.id=null;state.detail=null;state.mount=null;state.pending=null;state.creation=null;state.applied=null;$('dialogue-input').value='';$('dialogue-mode').value='auto';$('dialogue-title').textContent='今天想聊什么？';$('dialogue-export').hidden=true;$('global-message').hidden=true;$('global-message').textContent='';clear($('dialogue-feed'));$('dialogue-feed').append(welcome);note('');persist();$('dialogue-input').focus();return true;}
  async function openLegacy(caseId,title){try{if(!await newDialogue())return;await ensureDialogue(title);await api('dialogues/'+state.id+'/case',{case_id:caseId});$('dialogue-history-dialog').close();await reload();const turn=state.detail.turns.at(-1);await mountCard(turn,$('dialogue-mount-'+turn.turn_id));}catch(error){note(error.message,true);}}
  async function loadProfiles(){
    const result=await request('/api/profiles'),select=$('dialogue-profile'),previous=state.detail?.context.profile_id||select.value;clear(select);const blank=make('option','','暂不关联人物');blank.value='';select.append(blank);
    for(const person of result.profiles){const option=make('option','',person.profile.name+(person.is_self?'（本人）':''));option.value=person.person_id;select.append(option);}select.value=previous||'';
    $('dialogue-profile-note').textContent='关联用于本次占问；修改档案不会改写已经保存的卦例。';
  }
  function openDocuments(){$('dialogue-documents-dialog').showModal();}
  async function openPeople(){await loadProfiles();if(matchMedia('(max-width:999px)').matches){$('dialogue-people-dialog').append($('dialogue-people-panel'));$('dialogue-people-dialog').showModal();}else $('dialogue-people-panel').scrollIntoView({block:'center',behavior:'smooth'});}
  function openFeedback(){$('dialogue-more-dialog').close();window.SkillWorkbench.page('issues',false);$('dialogue-feedback-dialog').showModal();}
  $('dialogue-profile').onchange=async()=>{try{await ensureDialogue('人物与占问');await api('dialogues/'+state.id+'/profile',{profile_id:$('dialogue-profile').value||null});if(!state.detail)state.detail={turns:[],context:{}};state.detail.context.profile_id=$('dialogue-profile').value||null;if(state.mount&&!state.mount.caseId){window.LiuyaoV5.setProfile($('dialogue-profile').value);$('profile-select').dispatchEvent(new Event('change',{bubbles:true}));await stashCard();}persist();}catch(error){note(error.message,true);}};
  $('dialogue-profile-manage').onclick=()=>{$('dialogue-people-dialog').close();window.LiuyaoV5.openProfiles();};
  const oldRules=window.MobileUI.openRules;window.MobileUI.openRules=()=>{$('rules-page').hidden=false;$('dialogue-rules-dialog').showModal();};
  const oldBack=window.MobileUI.back;window.MobileUI.back=()=>{const modal=document.querySelector('dialog[open]');if(modal){modal.close();return true;}if(state.mount&&app.context().view!=='input'){app.showView('input');return true;}return false;};
  $('dialogue-new').onclick=()=>newDialogue().catch(e=>note(e.message,true));$('dialogue-history-open').onclick=()=>{loadHistory().catch(e=>note(e.message,true));$('dialogue-history-dialog').showModal();};
  $('dialogue-documents-open').onclick=openDocuments;$('dialogue-people-open').onclick=()=>openPeople().catch(e=>note(e.message,true));$('dialogue-more-open').onclick=()=>$('dialogue-more-dialog').showModal();
  $('dialogue-feedback-open').onclick=openFeedback;$('dialogue-rules-open').onclick=()=>{$('dialogue-more-dialog').close();$('rules-open').click();};$('dialogue-settings-open').onclick=()=>{$('dialogue-more-dialog').close();$('settings-dialog').showModal();};
  $('dialogue-form').addEventListener('submit',event=>{event.preventDefault();send();});
  document.querySelectorAll('[data-dialogue-prompt]').forEach(button=>button.onclick=()=>{$('dialogue-input').value=button.dataset.dialoguePrompt;$('dialogue-input').focus();});
  $('dialogue-input').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing&&event.keyCode!==229&&!matchMedia('(pointer:coarse)').matches){event.preventDefault();send();}});
  document.querySelector('.brand').addEventListener('click',event=>{event.preventDefault();$('dialogue-input').focus();},true);
  let draftTimer;document.addEventListener('input',event=>{if(event.target.closest('#case-form')){clearTimeout(draftTimer);draftTimer=setTimeout(()=>{stashCard();persist();},600);}else if(event.target.id==='dialogue-input')persist();});
  document.addEventListener('change',event=>{if(event.target.closest('#case-form')){clearTimeout(draftTimer);draftTimer=setTimeout(()=>{stashCard();persist();},250);}});
  document.addEventListener('liuyao:busy',refreshBusy);
  document.addEventListener('profiles:changed',()=>loadProfiles().catch(error=>note(error.message,true)));
  document.addEventListener('liuyao:case-loaded',async()=>{
    if(state.switching||!state.mount||state.mount.dialogueId!==state.id)return;const context=app.context();if(!context.caseId)return;
    if(state.mount.caseId&&state.mount.caseId!==context.caseId){
      state.switching=true;
      try{await api('dialogues/'+state.id+'/case',{case_id:context.caseId,analysis_run_id:context.runId||null});state.mount=null;}
      catch(error){note('尚未关联所选卦例：'+error.message,true);}
      finally{state.switching=false;}
      await reload();const selected=state.detail?.turns.at(-1),host=selected&&$('dialogue-mount-'+selected.turn_id);if(host)await mountCard(selected,host);return;
    }
    const turn=state.detail?.turns.find(t=>t.turn_id===state.mount.turnId);if(!turn||!['cast','case'].includes(turn.result?.action))return;
    const signature=JSON.stringify([state.id,state.mount.turnId,context.caseId,context.runId]);
    if(state.binds.has(signature))return;state.binds.set(signature,key());
    try{await api('dialogues/'+state.id+'/case',{turn_id:state.mount.turnId,case_id:context.caseId,analysis_run_id:context.runId||null},state.binds.get(signature));state.mount.caseId=context.caseId;turn.result.case_id=context.caseId;
      state.detail.context.active_case=context.caseId;state.detail.context.active_run=context.runId;state.detail.context.last_skill='liuyao';delete state.detail.context.pending_cast;updateDefaults();persist();
    }catch(error){state.binds.delete(signature);note('卦例已保存，尚未关联到对话：'+error.message,true);}
  });
  window.DialogueUI={draft,restoreDraft,isBusy:()=>state.jobs.size>0,send,newDialogue,reload};
  const peoplePanel=$('dialogue-people-panel'),peopleHome=peoplePanel.parentElement;
  matchMedia('(max-width:999px)').addListener(event=>{if(!event.matches&&peoplePanel.parentElement!==peopleHome){$('dialogue-people-dialog').close();peopleHome.append(peoplePanel);}});
  refreshBusy();app.ready.then(async()=>{
    if(!state.restored&&!window.LiuyaoAndroid){try{state.restored=JSON.parse(localStorage.getItem('liuyao-dialogue-session')||'null');}catch(_){}}
    if(state.restored){state.id=state.restored.id||null;state.pending=state.restored.pending||null;state.creation=state.restored.creation||null;state.collapsed=new Set(state.restored.collapsed||[]);$('dialogue-input').value=state.restored.text||'';$('dialogue-mode').value=state.restored.mode||'auto';}
    state.ready=true;
    try{await Promise.all([loadHistory(),loadProfiles()]);if(state.id)await reload();
      const active=await api('active');for(const job of active.jobs)if(job.kind==='assistant')watch(job.job_id,job.dialogue_id);
    }catch(error){note(error.message,true);}refreshBusy();
  });
})();
