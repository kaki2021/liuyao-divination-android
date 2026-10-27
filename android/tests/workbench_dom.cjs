'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const {JSDOM,ResourceLoader,VirtualConsole}=require('jsdom');
const root=path.resolve(__dirname,'../..'),checks=[],errors=[];
let server,dom;
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function wait(fn){for(let i=0;i<350;i++){if(fn())return;await pause(25);}throw new Error('Timed out');}
function check(name,value){assert.ok(value,name);checks.push(name);console.log('PASS',name);}
async function launch(){
  server=spawn(process.env.PYTHON||'python',[path.join(__dirname,'workbench_server.py')],{cwd:root,env:process.env,stdio:['ignore','pipe','pipe']});
  return await new Promise((resolve,reject)=>{let text='',err='';const timer=setTimeout(()=>reject(new Error(err||'startup timeout')),10000);
    server.stderr.on('data',x=>err+=x);server.stdout.on('data',x=>{text+=x;if(text.includes('\n')){clearTimeout(timer);resolve(JSON.parse(text.split('\n')[0]));}});server.on('exit',code=>{if(code)reject(new Error(err));});});
}
(async()=>{
 const config=await launch();
 class Assets extends ResourceLoader{fetch(url,options){const name=path.basename(new URL(url).pathname),compiled=path.join(root,'android/web',name);if(url.includes('/static/')&&name.endsWith('.js')&&fs.existsSync(compiled))return Promise.resolve(fs.readFileSync(compiled));return super.fetch(url,options);}}
 const log=new VirtualConsole();log.on('jsdomError',error=>{if(error.type!=='css parsing')errors.push(error.message);});
 dom=await JSDOM.fromURL(config.url,{resources:new Assets(),runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:log,beforeParse(w){
  w.matchMedia=()=>({matches:false,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}});w.scrollTo=()=>{};
  w.HTMLElement.prototype.scrollIntoView=function(){};w.confirm=()=>true;w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};
 }});
 const w=dom.window,$=id=>w.document.getElementById(id),submit=id=>$(id).dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
 await wait(()=>$('model-select').value==='test-model');
 check('应用名称保留六爻占问',w.document.title==='六爻占问');
 check('仅有两个专业技能和反馈入口',w.document.querySelectorAll('[data-skill-page]').length===3&&!$('time-basis'));
 w.document.querySelector('[data-skill-page=knowledge]').click();await wait(()=>!$('knowledge-workspace').hidden);
 check('切换到知识库而不清空六爻输入',w.document.body.dataset.workbenchPage==='knowledge');
 $('kb-document-title').value='五行 <script>测试</script>';$('kb-import-text').value='水对应系统的储备与起始点。木对应向目标探察与延展。';submit('kb-import-form');
 await wait(()=>$('kb-document-count').textContent==='1');
 check('粘贴原文保存到真实本地资料库',$('kb-documents').textContent.includes('五行 <script>测试</script>')&&!$('kb-documents').querySelector('script'));
 $('kb-question').value='水对应什么？';submit('kb-ask-form');await wait(()=>$('kb-status').textContent==='回答与出处已保存。');
 check('回答与出处一起显示',$('kb-turns').textContent.includes('1 条消息')&&$('kb-turns').querySelectorAll('.kb-citation').length===1);
 check('模型回复作为文本展示，不执行HTML',$('kb-turns').textContent.includes('<b>原文回答</b>')&&!$('kb-turns').querySelector('b'));
 $('kb-question').value='它和木有什么不同？';submit('kb-ask-form');await wait(()=>$('kb-turns').textContent.includes('3 条消息'));
 check('追问接续前一轮对话',$('kb-turns').querySelectorAll('.kb-turn').length===2);
 const chat=$('kb-chat-select').value;$('kb-new-chat').click();$('kb-chat-select').value=chat;$('kb-chat-select').dispatchEvent(new w.Event('change'));
 await wait(()=>$('kb-turns').querySelectorAll('.kb-turn').length===2);
 check('重开对话保留原文引用',$('kb-turns').querySelectorAll('.kb-citation').length===2&&!$('kb-export').hidden);
 w.document.querySelector('[data-skill-page=issues]').click();$('issue-skill').value='knowledge';$('issue-title').value='回答太长';$('issue-description').value='请简短回答，解释专业术语';$('issue-process').click();
 await wait(()=>$('skill-issue-list').textContent.includes('已更新本机技能'));
 check('反馈自动生成并应用技能偏好版本',$('skill-issue-list').textContent.includes('版本 2'));
 $('version-skill').value='knowledge';$('version-skill').dispatchEvent(new w.Event('change'));await wait(()=>$('skill-version-list').textContent.includes('版本 2 · 当前使用'));
 check('更新限定在选中的技能',$('skill-version-list').textContent.includes('简洁'));
 w.document.querySelector('[data-skill-page=knowledge]').click();$('kb-question').value='再解释一下储备';submit('kb-ask-form');await wait(()=>$('kb-turns').textContent.includes('已采用简洁偏好'));
 check('后续问答实际使用新版技能偏好',$('kb-turns').textContent.includes('已采用简洁偏好'));
 w.document.querySelector('[data-skill-page=issues]').click();await wait(()=>$('skill-version-list').querySelector('button'));
 $('skill-version-list').querySelector('button').click();await wait(()=>$('skill-version-list').textContent.includes('版本 3 · 当前使用'));
 check('回退生成新版本并保留历史',$('skill-version-list').textContent.includes('版本 2')&&$('skill-version-list').textContent.includes('版本 1'));
 $('issue-title').value='程序报错';$('issue-description').value='点击导入时程序报错';$('issue-process').click();await wait(()=>$('skill-issue-list').textContent.includes('待开发修复'));
 check('代码问题保留为待修复任务，不谎报已修复',$('skill-issue-list').querySelectorAll('.skill-issue').length===2&&$('skill-issue-list').textContent.includes('导出反馈 / 修复任务'));
 w.document.querySelector('[data-skill-page=knowledge]').click();$('kb-documents').querySelector('button').click();await wait(()=>$('kb-document-count').textContent==='0');
 $('kb-question').value='水对应什么？';submit('kb-ask-form');await wait(()=>$('kb-turns').textContent.includes('没有找到足够相关的原文'));
 check('移出资料后不从历史AI回答伪造新依据',$('kb-turns').lastElementChild.textContent.includes('资料不足')&&!$('kb-turns').lastElementChild.querySelector('.kb-citation'));
 check('历史引用仍然保留',$('kb-turns').querySelectorAll('.kb-citation').length===3);
 w.MobileUI.back();check('手机返回可回到六爻',w.document.body.dataset.workbenchPage==='liuyao');
 await pause(100);check('脚本无异常',errors.length===0);
 dom.window.close();let savedDraft=null;
 const nativeDraft={fields:{},workbench:{page:'knowledge',chatId:chat,question:'尚未发送的追问',issueSkill:'knowledge',issueTitle:'未提交标题',issueDescription:'未提交描述'}};
 dom=await JSDOM.fromURL(config.url,{resources:new Assets(),runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:log,beforeParse(w){
  w.matchMedia=()=>({matches:false,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}});w.scrollTo=()=>{};w.HTMLElement.prototype.scrollIntoView=function(){};
  w.confirm=()=>true;w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};
  w.LiuyaoAndroid={readDraft(){return JSON.stringify(nativeDraft);},saveDraft(value){savedDraft=JSON.parse(value);},analysisState(){},configureModel(){},exportFile(){}};
 }});
 await wait(()=>dom.window.document.getElementById('kb-question').value==='尚未发送的追问');
 check('原生重启恢复知识库追问草稿与当前页面',dom.window.document.body.dataset.workbenchPage==='knowledge');
 check('原生重启恢复尚未提交的技能反馈',dom.window.document.getElementById('issue-title').value==='未提交标题');
 await wait(()=>dom.window.document.getElementById('kb-export').hidden===false);
 dom.window.LiuyaoApp.persistDraft();check('保存六爻草稿同时保留知识库与反馈草稿',savedDraft.workbench.question==='尚未发送的追问'&&savedDraft.workbench.issueTitle==='未提交标题');
 console.log(JSON.stringify({status:'passed',checks:checks.length,errors,live_model_calls:0,layout_verified:false}));
})().catch(error=>{console.error(error,errors,{kb:dom?.window.document.getElementById('kb-status')?.textContent,issue:dom?.window.document.getElementById('skill-issue-status')?.textContent});process.exitCode=1;}).finally(()=>{dom?.window.close();server?.kill('SIGTERM');});
