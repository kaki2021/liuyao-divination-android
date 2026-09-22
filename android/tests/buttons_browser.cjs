'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process'),{chromium}=require('playwright');
const output=path.resolve(process.env.LIUYAO_TEST_OUTPUT||'test-results');fs.mkdirSync(output,{recursive:true});
const checks=[],errors=[];let server,browser;
const check=(name,value)=>{assert.ok(value,name);checks.push(name);console.log('PASS',name)};
(async()=>{
 server=spawn(process.env.PYTHON||'python3',[path.join(__dirname,'buttons_server.py')],{stdio:['ignore','pipe','inherit']});
 const url=await new Promise((resolve,reject)=>{server.stdout.once('data',x=>resolve(x.toString().trim()));server.once('error',reject);server.once('exit',c=>reject(Error('server '+c)));});
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 const page=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1,locale:'zh-CN',isMobile:true,hasTouch:true});page.on('pageerror',e=>errors.push(String(e)));

 await page.addInitScript(()=>{
   if(!location.href.startsWith('http'))return;
   // Missing APIs in older WebViews are exercised against the actual packaged payload.
   for(const p of [Element.prototype,Document.prototype,DocumentFragment.prototype])delete p.replaceChildren;
   delete Crypto.prototype.randomUUID;delete Array.prototype.at;delete Object.hasOwn;delete Object.fromEntries;
   delete Promise.allSettled;delete Blob.prototype.arrayBuffer;
   window.nativeCalls=[];
   window.LiuyaoAndroid={readPreference:()=>localStorage.getItem('native-model')||'null',savePreference:v=>localStorage.setItem('native-model',v),readDraft:()=>localStorage.getItem('native-draft')||'null',saveDraft:v=>localStorage.setItem('native-draft',v),configureModel:v=>window.nativeCalls.push(['configure',v]),exportFile:(u,f)=>window.nativeCalls.push(['export',u,f]),analysisState:v=>window.nativeCalls.push(['analysis',v])};
 });
 await page.route(url+'/',r=>r.continue({headers:{...r.request().headers(),'X-Liuyao-Bootstrap':'button-test'}}));
 await page.goto(url);await page.waitForFunction(()=>document.querySelector('#model-current').textContent.includes('质量 max'));

 check('手机底部仅问卦档案规则三个入口',await page.locator('.mobile-nav button').count()===3&&!await page.locator('#mobile-settings').count());

 check('初始只呈现问题输入',await page.locator('.mobile-question-step').isVisible()&&!await page.locator('.mobile-casting-step').isVisible());
 await page.screenshot({path:path.join(output,'phone-home.png'),fullPage:false});
 await page.locator('#mobile-next').click();check('空问题不能进入起卦',await page.locator('#case-form').getAttribute('data-mobile-step')==='1');
 await page.locator('#question').fill('下个月能顺利签下这个合作合同吗？');await page.locator('#mobile-next').click();
 check('第二步只呈现起卦',!await page.locator('.mobile-question-step').isVisible()&&await page.locator('.mobile-casting-step').isVisible());
 await page.locator('input[name="meibu-1"][value="1"]').check();await page.locator('.mobile-draw-next').click();await page.locator('input[name="meibu-2"][value="5"]').check();await page.locator('.mobile-draw-next').click();await page.locator('input[name="meibu-3"][value="5"]').check();
 await page.screenshot({path:path.join(output,'phone-casting.png'),fullPage:false});
 await page.locator('#save-case').click();await page.waitForFunction(()=>document.body.dataset.view==='results');

 check('完整排盘可保存',await page.locator('#chart-lines tr').count()===6);
 // Reproduce the screenshot's rendering environment: flex gaps have no effect.
 await page.evaluate(()=>{for(const e of document.querySelectorAll('*'))if(getComputedStyle(e).display==='flex'||getComputedStyle(e).display==='inline-flex')e.style.gap='0px';});
 check('手机使用六张爻位卡片',await page.locator('.phone-line-card').count()===6&&await page.locator('#phone-chart').isVisible());
 check('手机宽卦盘表不再占用横向空间',!await page.locator('.desktop-chart-table').isVisible());
 check('六根卦线保持独立间距',await page.evaluate(()=>[...document.querySelectorAll('.chart-mini')].every(x=>{const a=[...x.children].map(e=>e.getBoundingClientRect());return a.length===6&&a.every((r,i)=>!i||r.top-a[i-1].bottom>=6);}))); 
 check('阴爻中间断口清楚',await page.evaluate(()=>[...document.querySelectorAll('.chart-mini .yao')].filter(x=>x.children.length===2).every(x=>x.children[1].getBoundingClientRect().left-x.children[0].getBoundingClientRect().right>=7)));
 await page.locator('.phone-chart-tabs button').nth(1).click();check('切换变卦可查看六个位置',await page.locator('.phone-line-card').count()===6&&(await page.locator('.phone-line-note').allTextContents()).some(t=>t.includes('本卦')));
 await page.screenshot({path:path.join(output,'changed-cards.png'),fullPage:false});await page.locator('.phone-chart-tabs button').first().click();
 await page.locator('.computed-v5 > summary').click();check('综合强度改成六张卡片',await page.locator('.phone-strength-card').count()===6&&await page.locator('.phone-strength').isVisible());await page.locator('.computed-v5 > summary').click();

 check('默认排盘分页独立',await page.locator('#result-chart').isVisible()&&!await page.locator('#result-answer').isVisible());
 await page.screenshot({path:path.join(output,'phone-chart.png'),fullPage:false});
 await page.locator('#mobile-history').click();check('案例档案独立一页',await page.locator('.history-panel').isVisible()&&!await page.locator('.main-column').isVisible());
 await page.screenshot({path:path.join(output,'phone-history.png'),fullPage:false});
 await page.locator('.history-item').first().click();await page.waitForFunction(()=>document.body.dataset.mobilePage==='work');
 await page.locator('#settings-open').click();check('手机设置打开',await page.locator('#settings-dialog').isVisible());
 check('Pro max 保留',await page.locator('#model-select').inputValue()==='deepseek-v4-pro'&&(await page.locator('#model-quality').textContent()).includes('max'));

 await page.locator('#mobile-key').click();check('配置密钥按钮连接原生接口',await page.evaluate(()=>nativeCalls.some(c=>c[0]==='configure'&&c[1]==='deepseek')));
 await page.locator('#provider-select').selectOption('demo');await page.locator('#settings-done').click();await page.locator('#analyze-current-case').click();
 await page.waitForFunction(()=>document.querySelector('#analysis-content').textContent.includes('离线演示'),{timeout:30000});
 check('离线演示完整流程',await page.locator('#result-answer').isVisible());
 await page.locator('#mobile-rules').click();await page.waitForFunction(()=>document.querySelector('#rule-list').children.length>0);

 check('规则为正常页面',await page.locator('#rules-page').isVisible()&&await page.locator('dialog[open]').count()===0&&await page.locator('#rules-page').evaluate(e=>e.tagName==='SECTION'));
 check('规则页底栏高亮正确',await page.locator('#mobile-rules').getAttribute('aria-current')==='page');


 await page.locator('#rule-next').click();check('规则下一页可用',(await page.locator('#rule-page').textContent()).startsWith('2 /'));
 await page.locator('#rule-prev').click();await page.locator('#rule-search').fill('BASE_SCORE');check('规则搜索可用',await page.locator('#rule-list .rule-item').count()===1);
 await page.locator('#rule-list .rule-item').click();await page.locator('#trial-value').fill('6');await page.locator('.rule-trial button').click();
 await page.waitForFunction(()=>document.querySelectorAll('#rule-trial-result tr').length===7);check('修改参数值后可试算',await page.locator('#rule-trial-result tr').count()===7);
 await page.locator('#rules-page a[download]').click();check('规则导出连接原生接口',await page.evaluate(()=>nativeCalls.some(c=>c[0]==='export'&&c[1].endsWith('/api/rules/export'))));
 const xlsx=await (await page.request.get(url+'/api/rules/export')).body();check('导出的规则表是有效文件',xlsx.subarray(0,2).toString()==='PK');
 await page.locator('#rules-file').locator('..').locator('summary').click();
 await page.locator('#rules-file').setInputFiles({name:'rules.xlsx',mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer:xlsx});await page.locator('#rules-import').click();
 await page.waitForFunction(()=>document.querySelector('#rules-message').textContent.includes('校验通过'));check('导出的规则可再次导入',true);
 await page.getByRole('button',{name:'卜宅原理 · 10 条',exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll('.principle-entry').length===10);check('10条卜宅原理保留',await page.locator('.principle-entry').count()===10);
 await page.screenshot({path:path.join(output,'phone-rules.png'),fullPage:false});
 await page.locator('#rules-back').click();
 await page.locator('#mobile-history').click();await page.locator('#profiles-open').click();await page.locator('#profile-name').fill('本人');await page.locator('#profile-birth_date').fill('1994-06-12');await page.waitForFunction(()=>document.querySelector('#birth-pillars').textContent.includes('甲戌'));
 check('出生日期自动排八字', (await page.locator('#birth-pillars').textContent()).includes('甲戌'));

 await page.locator('#profile-is-self').check();await page.locator('#profile-save').click();await page.waitForFunction(()=>document.querySelector('#profile-message').textContent.includes('已保存'));
 check('人物档案与八字可保存',true);await page.locator('#profiles-dialog .dialog-close').click();
 await page.locator('#profiles-open').click();check('保存的出生日期重新打开仍存在',await page.locator('#profile-birth_date').inputValue()==='1994-06-12');await page.locator('#profiles-dialog .dialog-close').click();

 await page.locator('#mobile-work').click();

 await page.locator('#open-feedback').click();await page.locator('#feedback-text').fill('测试记录：已经签约。');await page.locator('#feedback-form button[type=submit]').click();
 await page.waitForFunction(()=>document.querySelector('#feedback-list').textContent.includes('已经签约'));check('后续反馈能保存',true);
 await page.locator('#context-text').fill('测试补充：对方已确认条款。');await page.locator('#context-save-only').click();
 await page.waitForFunction(()=>document.querySelector('#context-list').textContent.includes('对方已确认条款'));check('补充说明能单独保存',true);
 await page.locator('#feedback-return').click();await page.locator('#edit-case-input').click();await page.locator('.mobile-step-back').click();await page.locator('#question').fill('修改后的问题：合同本月能签成吗？');await page.locator('#mobile-next').click();await page.locator('#save-case').click();
 await page.waitForFunction(()=>document.querySelector('#global-message').textContent.includes('修改原因'));check('缺少修改原因时提示并保留输入',await page.locator('#question').inputValue()==='修改后的问题：合同本月能签成吗？');
 await page.locator('#revision-reason').fill('实际情况变化');await page.locator('#save-case').click();await page.waitForFunction(()=>document.body.dataset.view==='results');check('修改原案例可保存',true);
 await page.locator('#mobile-history').click();await page.locator('#new-case').click();await page.locator('#question').fill('新的分析按钮测试');await page.locator('#mobile-next').click();await page.locator('input[name="casting-method"][value="direct"]').check();
 for(let i=1;i<=6;i++)await page.locator(`input[name="line-${i}"][value="young_yang"]`).check();
 await page.locator('#analyze-case').click();await page.waitForFunction(()=>document.querySelector('#analysis-content').textContent.includes('离线演示'));check('保存并分析按钮从新案例完成全流程',true);
 check('分析进度通知原生接口',await page.evaluate(()=>nativeCalls.some(c=>c[0]==='analysis'&&c[1]===true)));
 await page.waitForFunction(()=>document.querySelector('#case-form').getAttribute('aria-busy')==='false');
 // A presentation-only report verifies long real-world text layout without inventing an AI run.
 await page.evaluate(()=>{document.querySelector('#analysis-content').replaceChildren();window.ReportViews.render({plain_language:{answer:'偏向能签成，但条款和时间还要谈稳。',reason:'目前有推动合作的有利条件。对方提出的要求、合同细节和资源安排，会影响最后能否落定。',watch_for:['别因为赶时间而忽略付款与交付条款。','给审批与协调留一些余地。'],next_steps:['先确认双方最在意的条款。','把签约所需资料提前备齐。'],timing:'暂不能确定具体日期，结合实际进展继续核对。'},conclusion:{answer:'专业判断示例'},sections:[{heading:'从日月来看',content:'这里保留专业分析的原文与依据。'.repeat(55)},{heading:'从动变来看',content:'动变分析。'}]},document.querySelector('#analysis-content'));window.ReportViews.show('answer');});
 await page.screenshot({path:path.join(output,'phone-answer-layout.png'),fullPage:false});
 await page.locator('#result-tab-professional').click();check('专业分析逐主题分页',await page.locator('.professional-pager').isVisible());await page.locator('.professional-pager button').last().click();check('专业下一页可用',(await page.locator('.professional-body').textContent()).includes('动变分析'));
 for(const width of [320,360,390,412]){await page.setViewportSize({width,height:844});check('页面宽度无溢出 '+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.locator('#mobile-rules').click();check('规则页无溢出 '+width,await page.evaluate(()=>document.querySelector('#rules-page').scrollWidth<=document.querySelector('#rules-page').clientWidth+1));await page.locator('#rules-back').click();}

 await page.locator('#result-tab-chart').click();
 for(const width of [320,360,390,412]){
  await page.setViewportSize({width,height:844});
  check('卦盘页所有卡片均无需左右拖动 '+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth&&[...document.querySelectorAll('.phone-line-card,.chart-summary,.four-pillars,.phone-strength-card')].filter(e=>e.getBoundingClientRect().width).every(e=>e.scrollWidth<=e.clientWidth+1)));
 }
 await page.setViewportSize({width:360,height:844});await page.locator('#chart-summary').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,'phone-chart-final.png'),fullPage:false});
 await page.locator('#mobile-rules').click();check('安卓返回操作从规则页回到问卦',await page.evaluate(()=>window.MobileUI.back()&&document.body.dataset.mobilePage==='work')); 
 await page.setViewportSize({width:1280,height:900});
check('桌面布局继续可用',!await page.locator('.mobile-nav').isVisible()&&await page.locator('.history-panel').isVisible());
 check('桌面保留完整对照表',await page.locator('.desktop-chart-table').isVisible());check('前端无异常',errors.length===0);
 const result={status:'passed',checks,errors,live_api_calls:0};fs.writeFileSync(path.join(output,'browser_results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{await browser?.close();server?.kill();});
