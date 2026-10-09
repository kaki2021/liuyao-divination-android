'use strict';
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
let server,browser;
(async()=>{
  server=spawn(process.env.PYTHON||'python3',[path.join(__dirname,'buttons_server.py')],{stdio:['ignore','pipe','inherit']});
  const url=await new Promise((resolve,reject)=>{server.stdout.once('data',b=>resolve(b.toString().trim()));server.once('error',reject);server.once('exit',c=>reject(Error('server '+c)));});
  browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const errors=[];page.on('pageerror',e=>{errors.push(String(e));console.error('PAGE ERROR:',String(e));});
  await page.addInitScript(()=>{window.exports=[];window.LiuyaoAndroid={readPreference:()=>null,savePreference:()=>{},readDraft:()=>null,saveDraft:()=>{},configureModel:()=>{},exportFile:(url,name)=>window.exports.push({url,name}),analysisState:()=>{}};});
  await page.route(url+'/',r=>r.continue({headers:{...r.request().headers(),'X-Liuyao-Bootstrap':'button-test'}}));
  await page.goto(url);await page.waitForFunction(()=>Boolean(window.LiuyaoApp));
  fs.mkdirSync('test-results',{recursive:true});
  assert.equal(await page.title(),'六爻占问');
  assert.equal(await page.locator('.brand').getAttribute('aria-label'),'六爻占问首页');
  await page.screenshot({path:'test-results/question-phone.png'});
  for(const width of [320,390,760,1024]){
    await page.setViewportSize({width,height:844});await page.locator('#user-help-open').click();
    await page.locator('#help-panel-start').waitFor();
    for(const section of ['start','casting','results','faq']){
      await page.locator('[data-help-tab="'+section+'"]').click();
      assert.equal(await page.locator('[data-help-panel]:visible').count(),1);
      if(section==='casting')for(const method of ['meibu','taiji','yarrow','direct','random_coin']){
        await page.locator('#help-method').selectOption(method);
        assert.equal(await page.locator('[data-help-method]:visible').count(),1);
        assert.ok(await page.locator('[data-help-method]:visible svg[role=img]').count()>=1);
        assert.ok(await page.evaluate(()=>{const d=document.querySelector('#user-help-body');return d.scrollWidth<=d.clientWidth+1;}),'guide '+method+' fits '+width);
      }
      assert.ok(await page.evaluate(()=>{const d=document.querySelector('#user-help-body');return d.scrollWidth<=d.clientWidth+1;}),'help '+section+' fits '+width);
    }
    await page.locator('#help-tab-start').focus();await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator('#help-tab-casting').getAttribute('aria-selected'),'true');
    assert.equal(await page.locator('.help-tabs [tabindex="0"]').count(),1);
    await page.locator('#user-help-dialog a[download]').click();
    assert.equal((await page.evaluate(()=>window.exports.at(-1))).name,'六爻占问_使用说明.html');
    await page.locator('#help-tab-start').click();
    if(width===390)await page.screenshot({path:'test-results/help-phone.png'});
    await page.locator('#user-help-dialog .dialog-close').click();
    assert.equal(await page.locator('#user-help-dialog').isVisible(),false);
  }
  const standalone=await browser.newPage({viewport:{width:390,height:844}});
  standalone.on('pageerror',e=>errors.push(String(e)));
  const offlineRequests=[];standalone.on('request',r=>{if(/^https?:/.test(r.url()))offlineRequests.push(r.url());});
  await standalone.goto('file://'+path.resolve(__dirname,'../../liuyao_app/static/user-guide.html'));
  await standalone.locator('#help-tab-casting').click();await standalone.locator('#help-method').selectOption('yarrow');
  assert.equal(await standalone.locator('[data-help-method]:visible').getAttribute('id'),'yarrow-guide');
  assert.equal(await standalone.locator('[data-help-panel]:visible').count(),1);
  assert.deepEqual(offlineRequests,[]);await standalone.close();
  await page.setViewportSize({width:390,height:844});
  await page.locator('#question').fill('考虑接受新项目，未来三个月能否按计划完成？');
  await page.locator('#mobile-next').click();
  const names=['枚卜丸','太极丸','蓍草/筹策','逐爻录入','随机模拟掷币'];
  assert.deepEqual(await page.locator('#casting-method option').allTextContents(),names);
  // Reproduce opening from a scrolled form, small screens, landscape, and
  // enlarged guide text. Exercise native touch scrolling, not just widths.
  const touch=await page.context().newCDPSession(page);
  async function swipe(up){
    const box=await page.locator('#user-help-body').boundingBox();
    const x=box.x+box.width*.7,from=box.y+box.height*(up?.82:.28),to=box.y+box.height*(up?.28:.82);
    await touch.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y:from}]});
    for(let i=1;i<=8;i++){await touch.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x,y:from+(to-from)*i/8}]});await page.waitForTimeout(25);}
    await touch.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForTimeout(350);
  }
  for(const viewport of [{width:320,height:480},{width:390,height:520},{width:844,height:390}]){
    await page.setViewportSize(viewport);await page.locator('#casting-method').selectOption('direct');
    await page.locator('#guide-open').click();await page.locator('[data-help-method="direct"]:visible').waitFor();
    assert.deepEqual(await page.locator('#help-method option').allTextContents(),names);
    await page.locator('#user-help-body .help-document').evaluate(el=>{el.style.fontSize='21px';});
    await page.locator('[data-help-method="direct"] details').evaluateAll(nodes=>nodes.forEach(el=>{el.open=true;}));
    const bounds=await page.locator('#user-help-dialog').boundingBox();
    assert.ok(bounds.y>=0&&bounds.y+bounds.height<=viewport.height+1,'entire dialog fits visible height');
    await page.locator('#user-help-body').evaluate(el=>{el.scrollTop=0;});await swipe(true);
    assert.ok(await page.locator('#user-help-body').evaluate(el=>el.scrollTop)>30,'touch scroll advances guide');
    await page.locator('#user-help-body').evaluate(el=>{el.scrollTop=el.scrollHeight;});
    assert.ok(await page.evaluate(()=>{
      const body=document.querySelector('#user-help-body'),last=document.querySelector('[data-help-method="direct"] details:last-child');
      return last.getBoundingClientRect().bottom<=body.getBoundingClientRect().bottom&&body.scrollHeight-body.clientHeight-body.scrollTop<=2;
    }),'final manual-entry explanation is reachable');
    if(viewport.width===390)await page.screenshot({path:'test-results/help-scroll-phone.png'});
    const before=await page.locator('#user-help-body').evaluate(el=>el.scrollTop);await swipe(false);
    assert.ok(await page.locator('#user-help-body').evaluate(el=>el.scrollTop)<before,'can scroll back up');
    await page.locator('#user-help-dialog .dialog-close').click();
    await page.waitForFunction(()=>!document.documentElement.classList.contains('help-is-open'));
  }
  await touch.detach();await page.setViewportSize({width:390,height:844});
  await page.locator('#user-help-body .help-document').evaluate(el=>{el.style.fontSize='';});
  for(const method of ['meibu','taiji','yarrow','direct','random_coin']){
    await page.locator('#casting-method').selectOption(method);await page.locator('#guide-open').click();
    await page.locator('[data-help-method="'+method+'"]:visible').waitFor();
    assert.equal(await page.locator('#help-method').inputValue(),method);
    if(method==='meibu')await page.screenshot({path:'test-results/casting-guide-phone.png'});
    await page.keyboard.press('Escape');assert.equal(await page.locator('#user-help-dialog').isVisible(),false);
  }
  await page.locator('#casting-method').selectOption('meibu');await page.locator('input[name="meibu-1"][value="1"]').check();
  await page.locator('.casting-selector').scrollIntoViewIfNeeded();await page.screenshot({path:'test-results/meibu-phone.png'});
  await page.locator('#casting-method').selectOption('taiji');await page.locator('#casting-method').selectOption('meibu');
  assert.equal(await page.locator('input[name="meibu-1"][value="1"]').isChecked(),true);
  await page.locator('#casting-method').selectOption('direct');
  assert.ok((await page.locator('#casting-instruction').textContent()).includes('蓍草'));
  const lines=['young_yang','young_yin','young_yin','young_yin','young_yang','old_yin'];
  for(let i=0;i<lines.length;i++)await page.locator(`input[name="line-${i+1}"][value="${lines[i]}"]`).check();
  await page.locator('.casting-selector').scrollIntoViewIfNeeded();await page.screenshot({path:'test-results/casting-entry-phone.png'});
  await page.locator('#save-case').click();await page.waitForFunction(()=>document.body.dataset.view==='results');
  const saved=await(await page.request.get(url+await page.locator('#export-case').getAttribute('href'))).json();assert.deepEqual(saved.revisions.at(-1).input.lines,lines);
  await page.locator('#result-export-menu summary').click();assert.equal(await page.locator('#export-case').isVisible(),true);
  await page.locator('#export-case').click();assert.equal((await page.evaluate(()=>window.exports.at(-1))).name,'六爻案例.json');
  assert.equal(await page.locator('#result-export-menu').getAttribute('open'),null);
  // Clearly labelled fixture for layout review; no paid model calls.
  await page.evaluate(()=>{
    document.querySelector('#analysis-content').replaceChildren();
    window.ReportViews.render({plain_language:{source:'local',answer:'【界面示例】有推进的机会，先确认交付范围、资源与时间安排。',watch_for:['明确交付标准。','确认关键人员投入。','保留沟通记录。','重新评估时间安排。'],next_steps:['补充已知条件后再判断。']},sections:[]},document.querySelector('#analysis-content'));
    window.ReportViews.show('answer');
  });
  assert.ok((await page.locator('#analysis-content').textContent()).includes('重新评估时间安排。'));
  for(const width of [320,390,760,1024]){
    await page.setViewportSize({width,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'results fits '+width);
    if(width===390){await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:'test-results/results-phone.png'});}
  }
  await page.setViewportSize({width:390,height:844});await page.locator('#mobile-history').click();
  assert.ok(await page.evaluate(()=>document.querySelector('.history-item').getBoundingClientRect().width>=document.querySelector('#history-list').clientWidth*.95),'phone history uses the available width');
  await page.screenshot({path:'test-results/history-phone.png'});
  await page.locator('.history-item').first().click();await page.waitForFunction(()=>document.body.dataset.mobilePage==='work');
  assert.deepEqual(errors,[]);
  console.log('PASS: renamed app, compact method selector, retained input, four help tabs and five illustrated methods at 320/390/760/1024px, keyboard navigation, offline guide, native exports, result menu, chart save and history.');
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(server)server.kill();});
