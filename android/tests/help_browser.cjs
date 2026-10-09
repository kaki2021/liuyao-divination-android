'use strict';
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
let server,browser;
(async()=>{
  server=spawn(process.env.PYTHON||'python3',[path.join(__dirname,'buttons_server.py')],{stdio:['ignore','pipe','inherit']});
  const url=await new Promise((resolve,reject)=>{server.stdout.once('data',b=>resolve(b.toString().trim()));server.once('error',reject);server.once('exit',c=>reject(Error('server '+c)));});
  browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.addInitScript(()=>{window.exports=[];window.LiuyaoAndroid={readPreference:()=>null,savePreference:()=>{},readDraft:()=>null,saveDraft:()=>{},configureModel:()=>{},exportFile:(url,name)=>window.exports.push({url,name}),analysisState:()=>{}};});
  await page.route(url+'/',r=>r.continue({headers:{...r.request().headers(),'X-Liuyao-Bootstrap':'button-test'}}));
  await page.goto(url);await page.waitForFunction(()=>Boolean(window.LiuyaoApp));
  for(const width of [320,390,760]){
    await page.setViewportSize({width,height:844});
    await page.locator('#user-help-open').click();
    await page.locator('#user-help-dialog .user-help-content').waitFor();
    assert.ok((await page.locator('#user-help-body').textContent()).includes('新人使用说明'));
    const fits=await page.evaluate(()=>{const d=document.querySelector('#user-help-dialog');return d.scrollWidth<=d.clientWidth+1;});
    assert.ok(fits,'help fits '+width+'px');
    await page.locator('#user-help-dialog a[download]').click();
    assert.ok((await page.evaluate(()=>window.exports.at(-1))).name.endsWith('.html'));
    if(width===390){fs.mkdirSync('test-results',{recursive:true});await page.screenshot({path:'test-results/help-phone.png'});}
    await page.locator('#user-help-dialog .dialog-close').click();
    assert.equal(await page.locator('#user-help-dialog').isVisible(),false);
  }
  await page.evaluate(()=>{
    document.querySelector('#analysis-content').replaceChildren();
    window.ReportViews.render({plain_language:{source:'local',answer:'有机会；须先确认条件。',watch_for:['一','二','三','四'],next_steps:[]},sections:[]},document.querySelector('#analysis-content'));
  });
  assert.equal(await page.locator('#analysis-content .answer-note li').count(),4);
  await page.setViewportSize({width:390,height:844});
  await page.locator('#question').fill('筹策逐爻录入与保存检查');
  await page.locator('#mobile-next').click();
  await page.locator('input[name="casting-method"][value="direct"]').check();
  assert.ok((await page.locator('#casting-instruction').textContent()).includes('蓍草'));
  for(const width of [320,390]){
    await page.setViewportSize({width,height:844});
    await page.locator('#guide-open').click();
    await page.locator('#direct-record-guide h4').first().waitFor();
    const guide=await page.locator('#direct-record-guide').textContent();
    assert.ok(guide.includes('一元')&&guide.includes('45 或 41')&&guide.includes('十八变'));
    assert.ok(await page.evaluate(()=>{const d=document.querySelector('#guide-dialog');return d.scrollWidth<=d.clientWidth+1;}));
    if(width===390)await page.screenshot({path:'test-results/casting-guide-phone.png'});
    await page.locator('#guide-dialog .dialog-close').click();
  }
  // The source's six-line example remains a normal manual entry and round-trips.
  const lines=['young_yang','young_yin','young_yin','young_yin','young_yang','old_yin'];
  for(let i=0;i<lines.length;i++)await page.locator(`input[name="line-${i+1}"][value="${lines[i]}"]`).check();
  await page.screenshot({path:'test-results/casting-entry-phone.png'});
  await page.locator('#save-case').click();
  await page.waitForFunction(()=>document.body.dataset.view==='results');
  const saved=await (await page.request.get(url+await page.locator('#export-case').getAttribute('href'))).json();
  assert.deepEqual(saved.revisions.at(-1).input.lines,lines);
  assert.deepEqual(errors,[]);
  console.log('PASS: help opens and exports, local report retains conditions, manual coin/yarrow guidance fits phones, and six lines save unchanged.');
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(server)server.kill();});
