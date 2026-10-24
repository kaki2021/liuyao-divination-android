'use strict';
// Executes the packaged scripts against the real isolated HTTP test server.
// jsdom verifies behavior, not browser layout or Android platform permissions.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const {JSDOM,ResourceLoader,VirtualConsole}=require('jsdom');
const root=path.resolve(__dirname,'../..'),checks=[],errors=[],posts=[];
let server,dom;
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function wait(test){for(let i=0;i<250;i++){if(test())return;await pause(40);}throw new Error('Timed out waiting for UI');}
function check(name,value){assert.ok(value,name);checks.push(name);console.log('PASS',name);}
async function launchServer(){
  server=spawn(process.env.PYTHON||'python',[path.join(__dirname,'conversation_server.py')],{cwd:root,env:process.env,stdio:['ignore','pipe','pipe']});
  return await new Promise((resolve,reject)=>{
    let data='',err='';server.stderr.on('data',part=>err+=part);
    const timeout=setTimeout(()=>reject(new Error('Fixture startup timeout: '+err)),10000);
    server.stdout.on('data',part=>{data+=part;if(data.includes('\n')){clearTimeout(timeout);resolve(JSON.parse(data.split('\n')[0]));}});
    server.on('exit',code=>{clearTimeout(timeout);if(code)reject(new Error(err));});
  });
}
(async()=>{
  const config=await launchServer();
  class Assets extends ResourceLoader{
    fetch(url,options){
      const name=path.basename(new URL(url).pathname),compiled=path.join(root,'android/web',name);
      if(url.includes('/static/')&&name.endsWith('.js')&&fs.existsSync(compiled))return Promise.resolve(fs.readFileSync(compiled));
      return super.fetch(url,options);
    }
  }
  const log=new VirtualConsole();log.on('jsdomError',error=>{if(error.type!=='css parsing')errors.push(error.message);});
  dom=await JSDOM.fromURL(config.url,{resources:new Assets(),runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:log,beforeParse(w){
    w.matchMedia=()=>({matches:false,addListener(){},removeListener(){},addEventListener(){},removeEventListener(){}});
    w.HTMLElement.prototype.scrollIntoView=function(){};w.confirm=()=>true;
    w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
    w.HTMLDialogElement.prototype.close=function(){this.open=false;};
    const open=w.XMLHttpRequest.prototype.open;
    w.XMLHttpRequest.prototype.open=function(method,url,...args){if(method==='POST')posts.push(url);return open.call(this,method,url,...args);};
  }});
  const w=dom.window,$=id=>w.document.getElementById(id),event=(el,name)=>el.dispatchEvent(new w.Event(name,{bubbles:true,cancelable:true}));
  await wait(()=>w.document.querySelector('.history-item'));
  check('应用标题为六爻占问',w.document.title==='六爻占问');
  check('新起卦默认真太阳时且没有时间制切换',!$('time-basis')&&w.LiuyaoSolarTime.read().time_basis==='true_solar'&&!$('solar-location-fields').hidden);
  w.document.querySelector('.history-item').click();
  await wait(()=>$('question').value.includes('工作'));
  $('context-text').value='你刚才说的条件是什么意思？';event($('context-form'),'submit');
  await wait(()=>$('conversation-status').textContent==='回复已保存。');
  check('追问使用独立任务且原报告保留',posts.some(url=>url.endsWith('/conversation'))&&!posts.some(url=>url.endsWith('/analyze'))&&$('analysis-content').textContent.includes('需先确认待遇'));
  check('问答分条保存且回复不执行 HTML',w.document.querySelectorAll('.conversation-user').length===1&&w.document.querySelectorAll('.conversation-assistant').length===1&&!$('conversation-list').querySelector('b'));
  $('context-text').value='待遇已确认，接下来呢？';event($('context-form'),'submit');
  await wait(()=>w.document.querySelectorAll('.conversation-assistant').length===2&&$('conversation-status').textContent==='回复已保存。');
  check('第二轮携带前一轮问答',Array.from(w.document.querySelectorAll('.conversation-assistant')).at(-1).textContent.includes('3 条消息'));
  check('前提改变时提示完整复评',$('conversation-list').textContent.includes('完整复评'));
  $('conversation-list').textContent='';w.document.querySelector('.history-item').click();await wait(()=>w.document.querySelectorAll('.conversation-user').length===2);
  check('重开案例保留问答',$('conversation-list').textContent.includes('待遇已确认'));
  check('历史记录保留经度与排盘口径',$('cast-longitude').value==='104.06'&&w.LiuyaoSolarTime.read().time_basis==='true_solar');
  await wait(()=>$('solar-time-preview').textContent.includes('当地真太阳时'));
  check('本地接口返回太阳时预览',$('solar-time-preview').textContent.includes('当地真太阳时'));
  w.LiuyaoAndroid={saveDraft(){},analysisState(){},requestLocation(id){setTimeout(()=>w.LiuyaoLocation.receive(id,{error:'定位权限被拒绝'}),0);}};
  $('location-button').click();await wait(()=>$('location-status').textContent.includes('被拒绝'));
  check('定位失败后保留手动入口与原经度',$('cast-longitude').value==='104.06'&&!$('location-button').disabled);
  w.LiuyaoAndroid.requestLocation=id=>setTimeout(()=>w.LiuyaoLocation.receive(id,{longitude:120,latitude:30,source:'device',captured_at:'2026-10-24T04:00:00Z'}),0);
  $('location-button').click();await wait(()=>$('cast-longitude').value==='120');
  check('原生定位结果写入真太阳时输入',w.LiuyaoSolarTime.read().cast_location.source==='device'&&w.LiuyaoSolarTime.read().time_basis==='true_solar');
  check('定位回调不会写入已切换案例',await(async()=>{
    let request;w.LiuyaoAndroid.requestLocation=id=>{request=id;};$('location-button').click();
    w.LiuyaoSolarTime.fill({time_basis:'true_solar',cast_location:{longitude:105,source:'manual'}});
    w.LiuyaoLocation.receive(request,{longitude:99,source:'device'});await pause(20);return $('cast-longitude').value==='105';
  })());
  w.LiuyaoSolarTime.fill({});
  check('历史卦不会静默改用新口径',!('time_basis' in w.LiuyaoSolarTime.read()));
  w.LiuyaoSolarTime.fill(null);$('cast-time').value='';
  check('未知时间可留空且保留太阳时默认',w.LiuyaoSolarTime.read().time_basis==='true_solar');
  $('cast-time').value='2026-10-24T12:00';
  let missing=false;try{w.LiuyaoSolarTime.read();}catch(error){missing=error.message.includes('经度');}
  check('已知起卦时间要求定位或手动经度',missing);
  let nowRequest;w.LiuyaoAndroid.requestLocation=id=>{nowRequest=id;};$('cast-now').click();
  check('现在起卦自动获取手机定位',Boolean(nowRequest));
  w.LiuyaoSolarTime.clearTime();$('cast-time').value='';
  await pause(350);check('页面脚本无异常',errors.length===0);
  console.log(JSON.stringify({status:'passed',checks:checks.length,errors,live_model_calls:0,layout_verified:false}));
})().catch(error=>{console.error(error,errors,{banner:dom?.window.document.getElementById('global-message')?.textContent,status:dom?.window.document.getElementById('conversation-status')?.textContent,posts});process.exitCode=1;}).finally(()=>{dom?.window.close();server?.kill('SIGTERM');});
