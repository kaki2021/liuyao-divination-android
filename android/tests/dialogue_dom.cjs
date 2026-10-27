'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');const {JSDOM,ResourceLoader,VirtualConsole}=require('jsdom');
const root=path.resolve(__dirname,'../..'),checks=[],errors=[];let server,dom,geoCalls=0,nativeDraft=null;
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function wait(fn){for(let i=0;i<500;i++){if(fn())return;await pause(25);}throw new Error('Timed out');}
async function until(fn){for(let i=0;i<200;i++){if(await fn())return;await pause(30);}throw new Error('Async timeout');}
function check(name,value){assert.ok(value,name);checks.push(name);console.log('PASS',name);}
async function launch(){server=spawn(process.env.PYTHON||'python',[path.join(__dirname,'dialogue_server.py')],{cwd:root,env:process.env,stdio:['ignore','pipe','pipe']});return await new Promise((resolve,reject)=>{let text='',err='';const timer=setTimeout(()=>reject(new Error(err||'startup timeout')),10000);server.stderr.on('data',x=>err+=x);server.stdout.on('data',x=>{text+=x;if(text.includes('\n')){clearTimeout(timer);resolve(JSON.parse(text.split('\n')[0]));}});server.on('exit',code=>{if(code)reject(new Error(err));});});}
(async()=>{
 const config=await launch();
 class Assets extends ResourceLoader{fetch(url,options){const name=path.basename(new URL(url).pathname),compiled=path.join(root,'android/web',name);if(url.includes('/static/')&&name.endsWith('.js')&&fs.existsSync(compiled))return Promise.resolve(fs.readFileSync(compiled));return super.fetch(url,options);}}
 const log=new VirtualConsole();log.on('jsdomError',error=>{if(error.type!=='css parsing')errors.push(error.message);});
 function beforeParse(w){
  w.matchMedia=q=>({matches:/max-width/.test(q),addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}});
  w.scrollTo=()=>{};w.HTMLElement.prototype.scrollIntoView=function(){};w.confirm=()=>true;
  const prototype=w.HTMLDialogElement.prototype;
  prototype.showModal=function(){this.open=true;};prototype.close=function(){this.open=false;};
  w.fetch=(url,options={})=>new Promise((resolve,reject)=>{const xhr=new w.XMLHttpRequest();xhr.open(options.method||'GET',url);for(const [name,value]of Object.entries(options.headers||{}))xhr.setRequestHeader(name,value);xhr.onload=()=>resolve({ok:xhr.status>=200&&xhr.status<300,status:xhr.status,json:async()=>JSON.parse(xhr.responseText)});xhr.onerror=reject;xhr.send(options.body||null);});
  w.LiuyaoAndroid={readDraft(){return nativeDraft||'null';},saveDraft(value){nativeDraft=value;},readPreference(){return '';},analysisState(){},configureModel(){},exportFile(){},requestLocation(id){geoCalls++;setTimeout(()=>w.LiuyaoLocation.receive(id,{longitude:120,latitude:30,source:'device',captured_at:new Date().toISOString(),accuracy_m:30}),1);}};
 }
 dom=await JSDOM.fromURL(config.url,{resources:new Assets(),runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:log,beforeParse});
 let w=dom.window;const $=id=>w.document.getElementById(id),event=(el,name)=>el.dispatchEvent(new w.Event(name,{bubbles:true,cancelable:true}));
 const fetchJson=(url,body)=>new Promise((resolve,reject)=>{const x=new w.XMLHttpRequest();x.open(body===undefined?'GET':'POST',url);if(body!==undefined){x.setRequestHeader('Content-Type','application/json');x.setRequestHeader('X-App-Request','1');x.setRequestHeader('X-Idempotency-Key','fixture-'+Date.now()+'-'+Math.random());}x.onload=()=>{const result=JSON.parse(x.responseText);if(x.status<200||x.status>=300)reject(new Error(JSON.stringify(result)));else resolve(result);};x.onerror=reject;x.send(body===undefined?null:JSON.stringify(body));});
 async function send(text){await wait(()=>!$('dialogue-send').disabled);$('dialogue-input').value=text;event($('dialogue-form'),'submit');await wait(()=>!$('dialogue-send').disabled&&$('dialogue-input').value==='');}
 await wait(()=>$('model-select').value==='test-model'&&w.DialogueUI);
 check('默认只有统一对话入口，旧技能导航隐藏',w.document.body.classList.contains('chat-first')&&w.getComputedStyle(w.document.querySelector('.skill-nav')).display==='none');
 check('未开始起卦不会索取定位',geoCalls===0&&!$('dialogue-feed').querySelector('#case-form'));
 await send('我想起一卦，选A房，给我们一家三口长期自住，尚未入住，我本人起卦。');
 await wait(()=>$('dialogue-feed').querySelector('#case-form')&&$('cast-longitude').value==='120');
 check('对话内展开起卦卡片并默认获取手机定位',geoCalls===1&&$('cast-time').value.length>10&&!$('time-basis'));
 check('卜宅选项来自会话且可编辑',$('buzhai-stage').value==='site_choice'&&$('buzhai-site').value==='A房'&&$('buzhai-role').value==='host'&&$('buzhai-residence').value==='not_occupied'&&!$('buzhai-site').disabled);
 check('所问房屋与起卦定位分开保存',$('buzhai-site').value==='A房'&&w.LiuyaoSolarTime.read().cast_location.longitude===120);
 check('自占可复用已保存的本人档案',$('profile-select').value===config.profile_id);
 $('buzhai-residence').value='occupied';event($('buzhai-residence'),'change');
 await send('不是本人，是朋友代起卦，地点选B房。');
 await wait(()=>$('buzhai-role').value==='other');
 check('后续补充预填角色与房屋',$('buzhai-site').value==='B房');
 check('会话预填不会覆盖手动改过的选项',$('buzhai-residence').value==='occupied');
 check('补充同一张卡片不会重新定位或重置时间',geoCalls===1);
 const direct=w.document.querySelector('input[name="casting-method"][value="direct"]');direct.checked=true;event(direct,'change');
 for(let i=1;i<=6;i++){const radio=w.document.querySelector(`input[name="line-${i}"][value="young_yang"]`);radio.checked=true;event(radio,'change');}
 $('save-case').click();await wait(()=>w.LiuyaoApp.context().caseId&&!w.LiuyaoApp.context().busy);
 const caseId=w.LiuyaoApp.context().caseId,dialogueId=w.DialogueUI.draft().id;
 await until(async()=>(await fetchJson('/api/workbench/dialogues/'+dialogueId)).context.active_case===caseId);
 let saved=(await fetchJson('/api/cases/'+caseId)).case;
 check('保存卦例关联当前会话，保留太阳时和已核对选项',saved.revisions.at(-1).input.time_basis==='true_solar'&&saved.revisions.at(-1).input.buzhai.site==='B房'&&saved.revisions.at(-1).input.buzhai.residence==='occupied');
 const castTime=saved.revisions.at(-1).input.actual_cast_time;
 $('analyze-current-case').click();await wait(()=>w.LiuyaoApp.context().runId&&!w.LiuyaoApp.context().busy);
 await until(async()=>Boolean((await fetchJson('/api/workbench/dialogues/'+dialogueId)).context.active_run));
 await send('它对家人会有什么影响？');await wait(()=>$('dialogue-feed').textContent.includes('继续沿用当前卦盘'));
 check('从主对话框追问沿用原卦且不重跑分析',(await fetchJson('/api/cases/'+caseId)).case.analysis_runs.length===1);
 $('dialogue-feed').querySelector('.dialogue-card-toggle').click();await wait(()=>!$('dialogue-feed').querySelector('#case-form'));
 check('卦盘和录入卡片可以收起，回到轻量对话',$('dialogue-parking').contains($('case-form')));
 $('dialogue-documents-open').click();$('kb-document-title').value='五行原文';$('kb-import-text').value='水表示系统的储备与起始点。木表示对目标的探察与延展。';event($('kb-import-form'),'submit');await wait(()=>$('kb-document-count').textContent==='1');$('dialogue-documents-dialog').close();
 await send('根据知识库资料，解释一下水。');await wait(()=>$('dialogue-feed').querySelector('.dialogue-citation'));
 check('同一会话可切到带出处的知识库问答',$('dialogue-feed').textContent.includes('根据原文回答'));
 await send('它与木有什么区别？');await wait(()=>$('dialogue-feed').textContent.includes('已接续 3 条消息'));
 check('知识库追问保存自己的对话上下文',$('dialogue-feed').querySelectorAll('.dialogue-citation').length===2);
 await send('回到刚才的卦，继续讨论');
 check('切回原卦仍然只有一次原始分析',(await fetchJson('/api/cases/'+caseId)).case.analysis_runs.length===1);
 $('dialogue-people-open').click();await wait(()=>$('dialogue-people-dialog').open);$('dialogue-profile-manage').click();await wait(()=>$('profiles-dialog').open);
 $('profile-occupation').value='测试职业';event($('profile-form'),'submit');await wait(()=>$('profile-message').textContent.includes('人物档案已保存'));
 check('人物档案独立保存并保持已保存卦例不变',(await fetchJson('/api/cases/'+caseId)).case.revisions.length===1);$('profiles-dialog').close();
 await send('回答太长，希望先给结论');await wait(()=>$('dialogue-feed').querySelector('.dialogue-feedback-title'));
 const feedback=$('dialogue-feed').querySelector('.dialogue-feedback-title').closest('.dialogue-card');feedback.querySelector('button').click();await wait(()=>feedback.textContent.includes('本机技能偏好已更新'));
 check('主对话中可以提交反馈并应用偏好',feedback.textContent.includes('回退'));
 const child=(await fetchJson('/api/cases',{input:{question:'子卦：另一份工作的情况',lines:['young_yang','young_yin','young_yang','young_yin','young_yang','young_yin'],time_basis:'true_solar'},parent_case_id:caseId,parent_revision_seq:1,parent_analysis_run_id:w.LiuyaoApp.context().runId})).case_id;
 $('dialogue-feed').querySelector('.dialogue-card-toggle').click();await wait(()=>$('series-tree').querySelector(`[data-case-id="${child}"]`));$('series-tree').querySelector(`[data-case-id="${child}"]`).click();
 await until(async()=>(await fetchJson('/api/workbench/dialogues/'+dialogueId)).context.active_case===child);
 check('选择系列中的另一卦会更新会话关联而不改写原卡片',(await fetchJson('/api/workbench/dialogues/'+dialogueId)).turns.some(t=>t.result?.case_id===caseId));
 await w.DialogueUI.newDialogue();await send('补录昨天起的卦，问工作。');
 await wait(()=>$('dialogue-feed').querySelector('#case-form'));
 check('补录旧卦不会套用现在的时间和定位',$('cast-time').value===''&&$('cast-longitude').value===''&&geoCalls===1);
 await w.DialogueUI.newDialogue();await send('我想起一卦问明年工作');await wait(()=>$('cast-longitude').value==='120');
 $('question').value='我的手动修改问题';event($('question'),'input');$('dialogue-input').value='还没有发送的补充';event($('dialogue-input'),'input');
 w.LiuyaoApp.persistDraft();const restoredId=w.DialogueUI.draft().id;await pause(700);dom.window.close();
 dom=await JSDOM.fromURL(config.url,{resources:new Assets(),runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:log,beforeParse});w=dom.window;
 await wait(()=>w.DialogueUI?.draft().id===restoredId&&$('dialogue-feed').querySelector('#case-form')&&!$('dialogue-specialist').hidden&&$('question').value==='我的手动修改问题');
 check('原生重启恢复统一会话与未发送内容',$('dialogue-input').value==='还没有发送的补充');
 check('原生重启恢复手工修改过的起卦草稿',$('question').value==='我的手动修改问题');
 const old=(await fetchJson('/api/cases/'+caseId)).case;
 check('历史卦例时间没有因对话切换而变化',old.revisions.at(-1).input.actual_cast_time===castTime);
 await pause(100);check('脚本无异常',errors.length===0);
 console.log(JSON.stringify({status:'passed',checks:checks.length,errors,live_model_calls:0,physical_device_tested:false,layout_verified:false}));
})().catch(error=>{console.error(error,errors,{status:dom?.window.document.getElementById('dialogue-status')?.textContent,banner:dom?.window.document.getElementById('global-message')?.textContent,feed:dom?.window.document.getElementById('dialogue-feed')?.textContent.slice(-1200)});process.exitCode=1;}).finally(()=>{dom?.window.close();server?.kill('SIGTERM');});
