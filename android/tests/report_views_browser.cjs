'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../..');
const output=path.resolve(process.env.LIUYAO_TEST_OUTPUT||'test-results');
const checks=[],errors=[];
let browser;
const check=(name,value)=>{assert.ok(value,name);checks.push(name);console.log('PASS',name);};
(async()=>{
  fs.mkdirSync(output,{recursive:true});
  browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
  const page=await browser.newPage({viewport:{width:390,height:844},locale:'zh-CN'});
  page.on('pageerror',error=>errors.push(String(error)));
  // Use the real page structure and packaged scripts, without backend rules or live AI.
  const html=fs.readFileSync(path.join(root,'liuyao_app/static/index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,'').replace(/<link\b[^>]*>/g,'');
  await page.setContent(html);
  await page.evaluate(()=>{
    for(const prototype of [Element.prototype,Document.prototype,DocumentFragment.prototype])delete prototype.replaceChildren;
    delete Array.prototype.flatMap;
  });
  for(const name of ['styles.css','mobile.css'])await page.addStyleTag({path:path.join(root,'liuyao_app/static',name)});
  if(process.env.CJK_FONT_PATH){
    const font=fs.readFileSync(process.env.CJK_FONT_PATH).toString('base64');
    await page.addStyleTag({content:`@font-face{font-family:TestCJK;src:url(data:font/otf;base64,${font})}body,button,input,textarea,select,h1,h2,h3,h4,.brand,.brand small{font-family:TestCJK,sans-serif}`});
    await page.evaluate(()=>document.fonts.ready);
  }
  for(const name of ['compat.js','report-views.js','analysis-status.js'])await page.addScriptTag({path:path.join(root,'android/web',name)});
  await page.evaluate(()=>{document.body.dataset.view='results';document.body.dataset.mobilePage='work';document.querySelector('#input-section').hidden=true;document.querySelector('#results-section').hidden=false;});

  const intent={candidate_id:'I1',primary_question:'合同能签成吗？',actor:'求测者',object:'合作合同',action:'签约',desired_outcome:'签成',time_scope:'下个月',facets:['签约结果','履约代价'],evidence_quotes:[{quote:'合同能签成吗？'}]};
  const use={candidate_id:'U1',purpose:'primary',object_role:'合同',function:'文书承诺',relation:'generates_me',six_relative:'parents',assumptions:['对方有签约权限。'],evidence_quotes:[{quote:'合作合同'}]};
  const report={plain_language:{answer:'偏向能签成。'},conclusion:{answer:'有条件地偏顺。',direction:'favorable',key_conditions:['条款谈稳。'],limits:['不能保证签约日期。']},sections:[{heading:'日月',content:'第一主题。'},{heading:'动变',content:'第二主题。'}]};
  const result={stage_outputs:{intent:{status:'ready',selected_candidate_id:'I1',candidates:[intent]},selection:{status:'ready',selected_primary_id:'U1',candidates:[use,{...use,candidate_id:'U2',purpose:'cost',object_role:'履约资源',six_relative:'wealth'}],unresolved:['旧缺口已解决。'],clarifying_questions:[]},interpretation:{conclusion:report.conclusion,uncertainties:[{gap_id:'G1',impact:'审批时间待确认。'}]}},unresolved:['审批时间待确认。'],clarifying_questions:['谁负责审批？'],selection_note_reviews:[{original_text:'旧缺口已解决。',current_status:'resolved',current_text:''}]};
  const render=async(data,context,options={})=>page.evaluate(({data,context,options})=>{
    document.querySelector('#analysis-content').replaceChildren();
    window.ReportViews.render(data,document.querySelector('#analysis-content'),{result:context,...options});
  },{data,context,options});
  await render(report,result);
  await page.locator('#result-tab-professional').click();
  const professional=page.locator('#professional-content');
  check('专业页使用表格展示意念与原文依据',await page.locator('table.professional-intent').count()===1&&(await professional.textContent()).includes('行动 / 目标')&&(await professional.textContent()).includes('原文依据'));
  check('全部取象候选与用途可核对',await page.locator('.professional-use').count()===2&&(await professional.textContent()).includes('代价'));
  check('其他候选与原文默认折叠',!await page.locator('.professional-alternatives .professional-use').isVisible()&&!await page.locator('.professional-evidence p').first().isVisible());
  await page.locator('.professional-alternatives>summary').click();
  check('其他取象可按需展开',await page.locator('.professional-alternatives .professional-use').isVisible());
  await page.locator('.professional-alternatives>summary').click();
  await page.locator('.professional-evidence>summary').first().click();
  check('原文依据可按需展开',await page.locator('.professional-evidence p').first().isVisible());
  await page.locator('.professional-evidence>summary').first().click();
  check('条件与判断边界原样展示',(await page.locator('.conclusion-conditions').textContent()).includes('条款谈稳。')&&(await page.locator('.conclusion-limits').textContent()).includes('不能保证签约日期。'));
  check('缺失条件去重并包含现实补问',await page.locator('.professional-missing li').count()===2&&(await professional.textContent()).includes('谁负责审批？'));
  check('已解决的早期未决项不会重现',!(await professional.textContent()).includes('旧缺口已解决。'));
  check('结果区仅保留三个分页',await page.locator('.result-tabs button').count()===3&&await page.locator('#result-tab-records,#result-records').count()===0);
  check('Log 只保留重新解卦旁的入口',await page.locator('#analysis-records-open').count()===1&&await page.locator('#analysis-view-replies').count()===0&&await page.locator('#analysis-records-open').getAttribute('aria-controls')==='analysis-log-dialog');
  check('审计与原始回复移入日志弹窗',await page.locator('#analysis-log-dialog #audit-report').count()===1&&await page.locator('#analysis-log-dialog #ai-raw-replies').count()===1&&await professional.locator('#audit-report,#ai-raw-replies').count()===0);
  await page.locator('.professional-pager button').last().click();
  check('专业主题分页可用',(await page.locator('.professional-body').textContent()).includes('第二主题。'));
  await page.locator('#result-tab-professional').focus();await page.keyboard.press('End');
  check('三个分页键盘导航可用',await page.locator('#result-tab-chart').getAttribute('aria-selected')==='true');
  await page.keyboard.press('ArrowRight');check('分页末尾可循环到直接答案',await page.locator('#result-tab-answer').getAttribute('aria-selected')==='true');
  await page.evaluate(()=>window.AnalysisStatus.bind({replies(){window.ReportViews.openLog();}}));
  await page.locator('#result-tab-professional').click();
  await page.locator('#analysis-records-open').click();
  check('Log 按钮打开模态弹窗并保留当前页',await page.locator('#analysis-log-dialog').isVisible()&&await page.locator('#result-tab-professional').getAttribute('aria-selected')==='true');
  await page.keyboard.press('Escape');
  check('Escape 关闭 Log 并恢复按钮焦点',!await page.locator('#analysis-log-dialog').isVisible()&&await page.locator('#analysis-records-open').evaluate(node=>node===document.activeElement));
  await page.locator('#analysis-records-open').click();await page.locator('#analysis-log-close').click();
  check('Log 关闭按钮返回原来的专业页',!await page.locator('#analysis-log-dialog').isVisible()&&await professional.isVisible());
  for(const width of [320,360,390,412,1280]){
    await page.setViewportSize({width,height:900});
    check('专业页无横向溢出 '+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1&&document.querySelector('#professional-content').scrollWidth<=document.querySelector('#professional-content').clientWidth+1));
    check('三项结果分页保持同一行 '+width,await page.locator('.result-tabs button').evaluateAll(nodes=>new Set(nodes.map(node=>Math.round(node.getBoundingClientRect().top))).size===1));
    if(width===390)check('核对表格收紧默认阅读长度',await page.locator('.professional-checks').evaluate(node=>node.getBoundingClientRect().height<800));
    if(width===390||width===1280)await page.screenshot({path:path.join(output,'professional-'+width+'.png'),fullPage:true});
    await page.locator('#analysis-records-open').click();
    check('日志弹窗在屏幕内且没有横向溢出 '+width,await page.locator('#analysis-log-dialog').evaluate(node=>{const rect=node.getBoundingClientRect();return rect.left>=0&&rect.right<=innerWidth+1&&rect.top>=0&&rect.bottom<=innerHeight+1&&node.scrollWidth<=node.clientWidth+1;}));
    if(width===390)await page.screenshot({path:path.join(output,'log-390.png'),fullPage:false});
    await page.locator('#analysis-log-close').click();
  }

  await render({}, {stage_outputs:{intent:{status:'needs_clarification',selected_candidate_id:null,candidates:[intent,{...intent,candidate_id:'I2',primary_question:'合同履约是否顺利？'}],clarifying_questions:[{text:'你关注签约还是履约？'}]}}});
  check('待补充状态展示候选而不假装已选定',await page.locator('.professional-intent').count()===2&&(await professional.textContent()).includes('待确认候选')&&!(await professional.textContent()).includes('本次采用'));
  check('意念阶段的补问在专业页可见',(await professional.textContent()).includes('你关注签约还是履约？'));
  await render({}, {stage_outputs:{interpretation:{conclusion:report.conclusion,uncertainties:[]}}});
  check('没有展示报告时仍保留解卦条件',await page.locator('.conclusion-conditions').count()===1);
  await render({summary:'历史报告。'}, {audit_report:{conclusion_conditions:['历史条件。'],conclusion_limits:['历史边界。']}});
  check('历史审计字段可回退展示',(await professional.textContent()).includes('历史条件。')&&(await professional.textContent()).includes('历史边界。'));
  await render({...report,conclusion:{...report.conclusion,key_conditions:[],limits:[]}}, {audit_report:{conclusion_conditions:['不应出现。'],conclusion_limits:['不应出现。']}});
  check('空条件不从审计重新填入',await page.locator('.conclusion-conditions,.conclusion-limits').count()===0);
  await render(report,result,{isDemo:true});
  check('离线演示不冒充真实 AI 核对',await page.locator('.professional-checks,.professional-conclusion').count()===0);
  await render({}, {stage_outputs:{selection:{candidates:[use],unresolved:['原始早期说法。']},interpretation:{uncertainties:[]}}});
  check('旧版最终报告不会重新采用早期缺口',!(await professional.textContent()).includes('原始早期说法。'));
  await render({}, {stage_outputs:{selection:{selected_primary_id:null,candidates:[{...use,subject_reference:'shi_body',six_relative:null,relation:null}],unresolved:['用途待核实。']}}});
  check('主体参照和未完成取用可核对',(await professional.textContent()).includes('世身')&&(await professional.textContent()).includes('用途待核实。'));
  await render(report,{...result,selection_note_reviews:[{current_status:'partially_resolved',current_text:'只剩合同条款待核实。',original_text:'已填日期却称缺日期。'}]});
  check('部分解决项只显示当前剩余条件',(await professional.textContent()).includes('只剩合同条款待核实。')&&!(await professional.textContent()).includes('已填日期却称缺日期。'));
  await render({...report,conclusion:{...report.conclusion,key_conditions:['condition'.repeat(60)],limits:['limit'.repeat(100)]}},result);
  await page.setViewportSize({width:320,height:844});
  check('长条件与边界不会撑开手机页面',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await render({}, {stage_outputs:{intent:{candidates:[{...intent,primary_question:'<img src=x onerror=alert(1)>',evidence_quotes:[null]}]}}});
  check('AI 文本不会作为 HTML 执行',await professional.locator('img').count()===0&&(await professional.textContent()).includes('<img src=x onerror=alert(1)>'));
  await page.evaluate(()=>window.ReportViews.reset());
  check('切换分析会清空上一份核对信息',await page.locator('.professional-checks,.professional-conclusion').count()===0);
  check('旧 WebView API 缺失时无前端异常',errors.length===0);
  const summary={status:'passed',checks,errors,live_api_calls:0};
  fs.writeFileSync(path.join(output,'report_views_results.json'),JSON.stringify(summary,null,2)+'\n');
  console.log(JSON.stringify(summary));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{await browser?.close();});
