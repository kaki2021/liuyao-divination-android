'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../..'),checks=[],errors=[],requests=[];
let browser,server;
function check(name,value){assert.ok(value,name);checks.push(name);console.log('PASS',name);}
async function launchServer(){
  server=spawn(process.env.PYTHON||'python',[path.join(__dirname,'conversation_server.py')],{cwd:root,env:process.env,stdio:['ignore','pipe','pipe']});
  let stderr='';server.stderr.on('data',data=>stderr+=data);
  return await new Promise((resolve,reject)=>{
    let data='';const timeout=setTimeout(()=>reject(new Error('Test server timeout: '+stderr)),10000);
    server.stdout.on('data',part=>{data+=part;if(data.includes('\n')){clearTimeout(timeout);try{resolve(JSON.parse(data.split('\n')[0]));}catch(error){reject(error);}}});
    server.on('exit',code=>{clearTimeout(timeout);if(code)reject(new Error(stderr));});
  });
}
(async()=>{
  const config=await launchServer();
  browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined,headless:true,
    args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--no-zygote','--single-process']});
  const page=await browser.newPage({viewport:{width:390,height:844},locale:'zh-CN',timezoneId:'Asia/Shanghai'});
  page.on('pageerror',error=>errors.push(String(error)));
  page.on('request',request=>{if(request.method()==='POST')requests.push(request.url());});
  // Exercise the same Chrome 58 scripts included in the Android payload.
  await page.route('**/static/*.js',route=>{
    const file=path.join(root,'android/web',path.basename(new URL(route.request().url()).pathname));
    return fs.existsSync(file)?route.fulfill({contentType:'text/javascript',body:fs.readFileSync(file)}):route.continue();
  });
  await page.goto(config.url);
  await page.locator('.history-item').first().click();
  await page.waitForFunction(()=>document.querySelector('#question').value.includes('工作'));
  const original=await page.locator('#analysis-content').textContent();
  await page.locator('#context-text').fill('你刚才说的条件是什么意思？');
  await page.locator('#context-analyze').click();
  await page.waitForFunction(()=>document.querySelector('#conversation-status').textContent==='回复已保存。');
  check('追问调用独立接口，保留原报告',requests.some(url=>url.endsWith('/conversation'))&&!requests.some(url=>url.endsWith('/analyze'))&&(await page.locator('#analysis-content').textContent()).includes('需先确认待遇'));
  check('用户与助手分条显示，AI 内容作为文本',await page.locator('.conversation-user').count()===1&&await page.locator('.conversation-assistant').count()===1&&await page.locator('#conversation-list b').count()===0);
  await page.locator('#context-text').fill('待遇已确认，接下来呢？');await page.locator('#context-analyze').click();
  await page.waitForFunction(()=>document.querySelectorAll('.conversation-assistant').length===2&&document.querySelector('#conversation-status').textContent==='回复已保存。');
  check('第二轮带上前一轮问答',await page.locator('.conversation-assistant').last().textContent().then(text=>text.includes('3 条消息')));
  check('影响前提时显示重新解卦入口说明',await page.locator('.conversation-assistant').last().textContent().then(text=>text.includes('完整复评')));
  await page.reload();await page.locator('.history-item').first().click();
  await page.waitForFunction(()=>document.querySelectorAll('.conversation-assistant').length===2);
  check('重新打开案例后保留连续对话',await page.locator('.conversation-user').count()===2);
  await page.locator('#tab-input').click();await page.locator('#time-details').evaluate(el=>el.open=true);
  check('历史卦使用保存的经度与时间口径',await page.locator('#cast-longitude').inputValue()==='104.06'&&await page.evaluate(()=>window.LiuyaoSolarTime.read().time_basis)==='true_solar');
  await page.waitForFunction(()=>document.querySelector('#solar-time-preview').textContent.includes('当地真太阳时'));
  check('太阳时预览由本地历法生成',await page.locator('#solar-time-preview').textContent().then(text=>text.includes('当地真太阳时')));
  await page.evaluate(()=>{window.LiuyaoAndroid={saveDraft(){},analysisState(){},requestLocation(id){setTimeout(()=>window.LiuyaoLocation.receive(id,{error:'定位权限被拒绝'}),0);}};});
  await page.locator('#location-button').click();await page.waitForFunction(()=>document.querySelector('#location-status').textContent.includes('被拒绝'));
  check('拒绝定位后仍保留手动经度',await page.locator('#cast-longitude').inputValue()==='104.06');
  await page.evaluate(()=>{window.LiuyaoAndroid.requestLocation=id=>setTimeout(()=>window.LiuyaoLocation.receive(id,{longitude:120,latitude:30,source:'device',captured_at:'2026-10-24T04:00:00Z'}),0);});
  await page.locator('#location-button').click();await page.waitForFunction(()=>document.querySelector('#cast-longitude').value==='120');
  check('原生定位回调更新经度并保留真太阳时选项',await page.evaluate(()=>window.LiuyaoSolarTime.read().time_basis)==='true_solar');
  for(const width of [320,390,768]){
    await page.setViewportSize({width,height:844});
    check(width+' 像素输入页面无横向溢出',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await page.locator('#tab-results').click();
    check(width+' 像素对话页面无横向溢出',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await page.locator('#tab-input').click();
  }
  check('页面无脚本异常',errors.length===0);
  console.log(JSON.stringify({status:'passed',checks:checks.length,errors,live_model_calls:0}));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(server)server.kill('SIGTERM');});
