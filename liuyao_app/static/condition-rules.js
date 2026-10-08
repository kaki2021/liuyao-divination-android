/* Conditional rules and the installed software's own calculation manual. */
(() => {
  'use strict';
  const labels={satisfied:'满足',unsatisfied:'不满足',unknown:'未知'};
  const model={
    label(status){return labels[status]||'未知';},
    caseRows(record){const names={matched:'符合',partly_matched:'部分符合',unmatched:'不符合',pending:'尚待验证'};return (record?.feedback||[]).map(f=>{const run=(record.analysis_runs||[]).find(r=>r.analysis_run_id===f.analysis_run_id),report=window.ReportViews.selectReport(run?.outcome?.result?.report);return {prediction:(typeof report==='string'?report:report?.plain_language?.answer||report?.conclusion?.answer||report?.summary)||'未关联可读的分析',actual:f.reported_outcome||f.text||'尚未说明',rating:names[f.match_degree]||'尚待验证',ruleVersion:f.rules_version||run?.rules_digest||'',runId:f.analysis_run_id||null};});},
    filter(rules,query,scene){const q=String(query||'').trim().toLowerCase();return rules.filter(r=>(!scene||r.scene===scene)&&(!q||[r.name,r.scope,r.policy,r.id].join(' ').toLowerCase().includes(q)));},
    conjunction(checks){return checks.some(c=>c.status==='unsatisfied')?'unsatisfied':checks.some(c=>c.status==='unknown')?'unknown':'satisfied';},
    compare(before,after){return after.checks.map(a=>{const b=before.checks.find(c=>c.rule_id===a.rule_id);return {id:a.rule_id,before:b?.status||'unknown',after:a.status,changed:!b||b.status!==a.status||JSON.stringify(b.conditions)!==JSON.stringify(a.conditions),conditions:a.conditions};});},
    state(line){const flags=[];for(const [key,name]of [['empty','原爻旬空'],['month_break','原爻月破'],['day_clash','日冲']])if(line[key]===true)flags.push(name);if(line.empty===null)flags.push('日月未核对');if(line.moving){flags.push('动→'+line.changed_branch);if(line.changed_empty===true)flags.push('化空');if(line.changed_month_break===true)flags.push('化月破');}else flags.push('静');return flags.join('；');}
  };
  window.ConditionRules={model};if(typeof document==='undefined')return;
  const $=id=>document.getElementById(id),{node,table,fold}=window.RuleWorkbench;
  let guide=null,input=null,chart=null,snapshot=null,caseRecord=null,installedLogic=null,selected='functional_use',request=0,loading=null;
  async function api(path,body){const response=await fetch(path,body===undefined?{headers:{'X-App-Request':'1'}}:{method:'POST',headers:{'X-App-Request':'1','Content-Type':'application/json','X-Idempotency-Key':window.LiuyaoCompat.requestId()},body:JSON.stringify(body)});const result=await response.json();if(!response.ok)throw Error(result.error?.message||'读取未完成');return result;}
  function current(){return chart?.conditional_analysis||null;}
  function render(){
    if(!guide)return;const rows=model.filter(guide.rules,$('condition-search').value,$('condition-scene').value);
    if(rows.length&&!rows.some(r=>r.id===selected))selected=rows[0].id;
    $('condition-list').replaceChildren(rows.length?table(['规则','当前策略'],rows.map(r=>{const b=node('button',r.name,'rule-item');b.type='button';b.setAttribute('aria-pressed',String(selected===r.id));b.setAttribute('aria-controls','condition-detail');b.onclick=()=>{selected=r.id;render();detail();if(window.matchMedia('(max-width:760px)').matches)$('condition-detail').scrollIntoView({block:'start',behavior:'smooth'});};return [b,r.policy];}),'condition-table'):node('p','没有匹配的规则。','empty-state'));
    if(!rows.length)$('condition-detail').replaceChildren(node('p','调整筛选条件可查看其他规则。','empty-state'));
  }
  function detail(){
    ++request;const r=model.filter(guide?.rules||[],$('condition-search').value,$('condition-scene').value).find(r=>r.id===selected),box=$('condition-detail');if(!r){box.replaceChildren(node('p','调整筛选条件可查看其他规则。','empty-state'));return;}
    box.replaceChildren(node('h3',r.name),table(['项目','说明'],r.details||[['适用范围',r.scope],['判断原则',r.policy]],'rule-pairs'));
    const checked=current()?.checks.find(c=>c.rule_id===r.id);
    if(checked){box.append(node('p','当前显示卦盘：'+model.label(checked.status),'condition-status '+checked.status));box.append(table(['条件','状态'],checked.conditions.map(c=>{const cell=node('div');cell.append(node('span',model.label(c.status),'condition-status '+c.status));if(c.note)cell.append(node('p',c.note,'small-note'));return [c.label,cell];}),'rule-pairs'));}
    else box.append(node('p','保存卦盘后可查看本次条件。以下也可用固定演示卦试算。','small-note'));
    const source=fold('依据、例外与边界');if(r.sources.length)r.sources.forEach(s=>source.append(node('p',s.statement),node('p',s.title+' · '+s.locator,'source-note')));else source.append(node('p','本项是软件结构识别或能力边界；资料未提供完整的通用判断算法。'));
    source.append(node('p','未知保留未知；规则前提满足也不等于目标必成。','small-note'));box.append(source);
    const review=fold('案例对照 · 预测与实际反馈');const caseRows=model.caseRows(caseRecord);
    review.append(node('p',caseRecord?'所选案例：'+caseRecord.case_id:'在档案中打开案例后，可在此对照当时判断与后续反馈。','small-note'));
    if(caseRows.length)review.append(table(['当时预测','实际反馈','用户自评'],caseRows.map(row=>[row.prediction,row.actual,row.rating]),'case-review-table'));else if(caseRecord)review.append(node('p','本案尚未记录实际反馈。','small-note'));
    review.append(node('p','采用与反馈明确关联的分析，不把最新报告替代旧预测；自评不等于经过验证的准确率。','small-note'));box.append(review);
    const trial=fold('情景试算 · 不保存');trial.append(node('p',input?'基于当前显示的起卦记录，仅改变专题场景。':'固定演示卦，非你的案例；仅改变专题场景。','small-note'));
    const form=node('form','','condition-trial'),context=input?.buzhai||{},selects={};
    for(const [key,label,options,initial]of [
      ['enabled','卜宅专题',[['false','未启用'],['true','启用']],context.stage?'true':'false'],
      ['stage','本次阶段',[['site_choice','选房'],['scope_check','核对范围'],['diagnosis','分析问题'],['remedy_check','验证方案']],context.stage||'site_choice'],
      ['site_kind','场所',[['yang','阳宅'],['yin','阴宅']],context.site_kind||'yang'],
      ['role','起卦身份',[['host','使用者本人'],['consultant','卦师勘察'],['other','代问／未明确']],context.role||'host'],
      ['residence','入住状态',[['unknown','未说明'],['not_occupied','尚未入住'],['occupied','已入住']],context.residence||'unknown']
    ]){const wrap=node('div'),id='condition-trial-'+key,labelNode=node('label',label),s=node('select');s.id=id;labelNode.htmlFor=id;options.forEach(([value,text])=>{const o=node('option',text);o.value=value;s.append(o);});s.value=initial;selects[key]=s;wrap.append(labelNode,s);form.append(wrap);}
    const output=node('div','','condition-trial-result'),button=node('button','比较条件变化','primary-button');button.type='submit';form.append(button);trial.append(form,output);box.append(trial);
    for(const select of Object.values(selects))select.onchange=()=>{++request;output.replaceChildren();};
    form.onsubmit=async event=>{event.preventDefault();const token=++request;button.disabled=true;output.replaceChildren(node('p','正在核对条件…'));
      try{const context=Object.fromEntries(Object.entries(selects).map(([key,value])=>[key,key==='enabled'?value.value==='true':value.value]));const data={context,expected_version:guide.version};if(input)data.input=input;
        const result=await api('/api/condition-rules/preview',data);if(token!==request)return;
        const names=new Map(guide.rules.map(r=>[r.id,r.name]));output.replaceChildren(node('p',(result.is_demo?'固定演示卦':'当前显示卦盘')+' · '+result.chart_name,'small-note'));
        const differences=model.compare(result.before,result.after);output.append(table(['规则','原条件 → 试算'],differences.map(d=>[names.get(d.id)||d.id,model.label(d.before)+' → '+model.label(d.after)+(d.changed?' · 有变化':'')]),'rule-pairs'));
        const chosen=differences.find(d=>d.id===r.id);if(chosen)output.append(table(['本项前提','试算状态'],chosen.conditions.map(c=>[c.label,model.label(c.status)+(c.note?'：'+c.note:'')]),'rule-pairs'));
        output.append(node('p',result.note,'small-note'));
      }catch(e){if(token===request)output.replaceChildren(node('p',e.message));}finally{button.disabled=false;}
    };
  }
  async function load(){
    if(loading)return loading;
    loading=(async()=>{try{guide=await api('/api/condition-rules');const previous=$('condition-scene').value;$('condition-scene').replaceChildren(node('option','全部场景'));$('condition-scene').firstChild.value='';[...new Set(guide.rules.map(r=>r.scene))].forEach(scene=>{const o=node('option',scene);o.value=scene;$('condition-scene').append(o);});$('condition-scene').value=previous;render();detail();}
      catch(e){$('condition-list').replaceChildren(node('p',e.message));const retry=node('button','重新读取','secondary-button');retry.type='button';retry.onclick=load;$('condition-list').append(retry);}finally{loading=null;}})();return loading;
  }
  for(const id of ['condition-search','condition-scene'])$(id).addEventListener(id==='condition-search'?'input':'change',()=>{render();if(model.filter(guide?.rules||[],$('condition-search').value,$('condition-scene').value).length)detail();});
  function renderLogic(host,installed){
    host.querySelectorAll('a[href^="blob:"]').forEach(a=>URL.revokeObjectURL(a.href));host.id='calculation-logic-section';host.replaceChildren(node('h3','软件计算逻辑'));
    const selector=node('select');selector.setAttribute('aria-label','计算逻辑版本');const currentOption=node('option','当前安装版本');currentOption.value='current';selector.append(currentOption);
    if(snapshot){const o=node('option','所选分析当时的版本');o.value='snapshot';selector.append(o);}host.append(selector);const content=node('div');host.append(content);
    function display(){const g=selector.value==='snapshot'?snapshot:installed;if(!g)return;content.replaceChildren(node('p',g.summary),node('p',g.model_version+' · 逻辑 '+g.logic_version.slice(0,12)+' · 实现 '+g.build_digest.slice(0,12),'small-note'));
      content.append(table(['处理顺序','怎样计算与判断'],g.steps.map((s,i)=>{const body=node('div');body.append(node('p',s.formula));const d=fold('输入、方法与边界');d.append(node('p',s.detail));body.append(d);return [(i+1)+'. '+s.title,body];}),'rule-pairs'));
      for(const t of g.tables){const d=fold(t.title);d.append(table(t.headers,t.rows,'rule-pairs'));content.append(d);}
      const legacy=fold('实验评分计算 · 仅供对照');legacy.append(node('p',g.legacy_scoring.rationale),table(['步骤','公式与边界'],g.legacy_scoring.formulas.map(f=>[f.title,f.formula+'\n'+f.detail]),'rule-pairs'));content.append(legacy);
      const versions=fold('版本与代码对应');versions.append(node('p',g.version_note),node('p','实验参数版本：'+(g.parameter_version||'未安装'),'small-note'),table(['计算文件','摘要'],Object.entries(g.code_manifest).map(([path,digest])=>[path,digest.slice(0,16)]),'rule-pairs'));content.append(versions);
      const download=node('a','导出计算逻辑','secondary-button');download.download='calculation-logic.md';if(selector.value==='current')download.href='/api/calculation-logic/export';else{download.href=URL.createObjectURL(new Blob([JSON.stringify(g,null,2)],{type:'application/json'}));download.download='calculation-logic-snapshot.json';}content.append(download);
    }
    selector.onchange=()=>{content.querySelectorAll('a[href^="blob:"]').forEach(a=>URL.revokeObjectURL(a.href));display();};display();
  }
  window.ConditionRules={model,load,renderLogic(host,guide){installedLogic=guide;renderLogic(host,guide);},
    invalidateLogic(){installedLogic=null;},
    setInput(value){input=value;++request;if(guide&&!$('rules-page').hidden)detail();},
    setChart(value){chart=value;++request;if(guide&&!$('rules-page').hidden)detail();},getChart(){return chart;},
    setCase(value){caseRecord=value||null;if(guide&&!$('rules-page').hidden)detail();},
    setSnapshot(value){snapshot=value||null;const host=$('calculation-logic-section');if(host&&installedLogic)renderLogic(host,installedLogic);}};
  $('calculation-logic-open').onclick=async()=>{window.RuleWorkbench.show('usage');await window.RuleWorkbench.loadUsage();$('calculation-logic-section')?.scrollIntoView({block:'start',behavior:'smooth'});};
})();
