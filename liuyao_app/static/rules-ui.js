/* One rules workbench. Reading material never enters case inputs. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  const node=(tag,text='',cls='')=>{const n=document.createElement(tag);n.textContent=text;n.className=cls;return n;};
  function table(headers,rows,cls=''){
    const t=node('table','','rule-table '+cls),head=node('thead'),tr=node('tr'),body=node('tbody');
    headers.forEach(h=>{const th=node('th',h);th.scope='col';tr.append(th);});head.append(tr);t.append(head,body);
    rows.forEach(row=>{const tr=node('tr');row.forEach(value=>{const td=node('td');if(typeof value==='object'&&value!==null)td.append(value);else td.textContent=String(value??'—');tr.append(td);});body.append(tr);});return t;
  }
  function fold(title,cls='') {const d=node('details','','rule-fold '+cls);d.append(node('summary',title));return d;}
  function section(title){const s=node('section','','rule-doc-section');s.append(node('h3',title));return s;}
  const model={
    page(rules,query,kind,index,size=7){
      const q=query.trim().toLowerCase();
      const all=rules.filter(r=>(!kind||r.kind===kind)&&(!q||[r.id,r.name,r.condition,r.meaning].join(' ').toLowerCase().includes(q)));
      const pages=Math.max(1,Math.ceil(all.length/size)),page=Math.max(0,Math.min(Number.isFinite(index)?Math.floor(index):0,pages-1));
      return {rows:all.slice(page*size,page*size+size),total:all.length,pages,page};
    },
    value(rule){return rule.kind==='switch'?(rule.enabled?'已启用':'已停用'):String(rule.value)+(rule.enabled?'':' · 停用');},
    draft(rule,raw,enabled){
      if(rule.required&&!enabled)throw Error('必要参数不能停用。');
      let value=rule.value;
      if(rule.kind!=='switch'){
        if(rule.type==='branch'){if(!'子丑寅卯辰巳午未申酉戌亥'.includes(raw)||raw.length!==1)throw Error('请选择一个地支。');value=raw;}
        else{if(String(raw).trim()==='')throw Error('请填写试调值。');value=Number(raw);if(!Number.isFinite(value)||value<rule.min||value>rule.max)throw Error(`允许范围为 ${rule.min} 至 ${rule.max}。`);}
      }
      return {rule_id:rule.id,value,enabled};
    }
  };
  window.RuleWorkbench={model};
  if(typeof document==='undefined')return;
  let guidePromise=null;
  async function read(path){const r=await fetch(path,{headers:{'X-App-Request':'1'}});if(!r.ok)throw Error('原理读取失败，请重试。');return r.json();}
  async function loadUsage(){
    const host=$('usage-panel');if(host.dataset.loaded==='true')return;
    if(guidePromise)return guidePromise;
    host.replaceChildren(node('p','正在读取使用原理…'));
    guidePromise=(async()=>{
      try{
        const [g,b,l]=await Promise.all([read('/api/usage-guide'),read('/api/principles'),read('/api/calculation-logic')]);
        const logic=section('软件计算逻辑');window.ConditionRules.renderLogic(logic,l);
        const workflow=section('使用流程');workflow.append(node('p',g.purpose,'small-note'),table(['步骤','怎么做'],g.workflow.map((s,i)=>[(i+1)+'. '+s.title,s.text]),'rule-pairs'));
        const layers=fold('四类依据怎样分工');layers.append(table(['依据','作用'],[
          ['原理说明','说明定性关系、适用条件与出处。'],['程序计算','按已编码的规则排盘、识别结构。'],['实验评分','用当前参数表达六爻的相对强弱。'],['AI 解读','结合问题与背景组织判断，成立条件仍需核对。']
        ],'rule-pairs'));workflow.append(layers);
        const scoring=fold('实验评分说明与调校依据'),guide=g.scoring;
        scoring.append(node('p','每个爻单独评分；强度不是整卦的成功率。','small-note'),table(['阶段','计算与用途'],guide.formulas.map(f=>{const body=node('div');body.append(node('p',f.formula,'formula'));const d=fold('作用与边界');d.append(node('p',f.detail));body.append(d);return [f.title,body];}),'rule-pairs'));
        const basis=fold('起点、分值依据与调校方法');basis.id='score-overview';basis.append(node('p',guide.rationale),table(['问题','说明'],guide.intro.map(t=>[t.title,t.text]),'rule-pairs'));scoring.append(basis);
        const kinds=fold('参数类型与影响范围');kinds.append(table(['参数类型','影响什么'],guide.kinds.map(k=>[k.name,k.meaning]),'rule-pairs'));scoring.append(kinds);
        const general=fold(`通用原理 · ${g.rules.length} 条`);general.id='general-principles';general.append(node('p',g.source_note,'small-note'));
        general.append(table(['原理','使用方式'],g.rules.map(r=>{
          const cell=node('div');cell.append(node('p',r.help));const source=fold('原文与适用边界','principle-source');source.append(node('blockquote',r.quote,'guide-quote'),node('p',`出处：《${r.source}》${r.locator}。`,'source-note'),node('h4','软件怎样采用'),node('p',r.review_note),node('p',r.catalog_summary,'small-note'));r.limitations.forEach(t=>source.append(node('p',t,'small-note')));cell.append(source);return [r.title,cell];
        }),'rule-pairs'));
        const residence=fold(`卜宅原理 · ${b.rules.length} 条`);residence.id='residence-principles';residence.append(node('p',b.note,'small-note'));
        const names=fold('五地命名条件');names.append(table(['命名候选','世爻六亲','还须核对旺相'],b.five_lands.map(r=>[r.name,r.shi_relative,r.required_relative])));residence.append(names);
        residence.append(table(['原理','适用条件'],b.rules.map(r=>{
          const cell=node('div');cell.append(node('p',r.statement));const d=fold('范围、边界与出处','principle-entry');d.append(node('p','适用范围：'+r.scope));r.limitations.forEach(t=>d.append(node('p',t,'small-note')));const source=b.sources.find(s=>s.source_id===r.source_id);d.append(node('p',`出处：《${source?.title||r.source_id}》${r.source_locator}。`,'source-note'));cell.append(d);return [r.title,cell];
        }),'rule-pairs'));
        const link=node('a','导出卜宅原理与出处','text-button');link.href='/api/principles/export';link.download='卜宅原理.json';residence.append(link);
        host.replaceChildren(logic,workflow,scoring,general,residence);host.dataset.loaded='true';
      }catch(e){host.replaceChildren(node('p',e.message));const retry=node('button','重新读取','secondary-button');retry.type='button';retry.onclick=loadUsage;host.append(retry);}
      finally{guidePromise=null;}
    })();return guidePromise;
  }
  function show(which){
    for(const [key,panel,button]of [['parameter','parameter-panel','parameter-tab'],['usage','usage-panel','usage-tab'],['package','package-panel','package-tab']]){$(panel).hidden=key!==which;$(button).setAttribute('aria-pressed',String(key===which));}
    if(which==='usage')loadUsage();
    if(which==='parameter')window.ConditionRules?.load();
  }
  for(const key of ['parameter','usage','package'])$(key==='usage'?'usage-tab':key+'-tab').addEventListener('click',()=>show(key));
  function overview(guide){const kind=$('rule-kind'),previous=kind.value;kind.replaceChildren(node('option','全部类型'));kind.firstChild.value='';guide.kinds.forEach(t=>{const o=node('option',t.name);o.value=t.id;kind.append(o);});kind.value=previous||'';}
  window.RuleWorkbench={node,table,fold,model,show,overview,loadUsage};
})();
