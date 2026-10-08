(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  const el=(tag,text='',cls='')=>{const n=document.createElement(tag);n.textContent=text;n.className=cls;return n;};
  const section=$('results-section'), analysis=$('analysis-card');
  const tabs=el('nav','','result-tabs');tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','结果阅读方式');
  const panels={},buttons={};
  for(const [key,label] of [['answer','直接答案'],['professional','专业分析'],['chart','卦盘与计算']]){
    const b=el('button',label);b.type='button';b.id='result-tab-'+key;b.setAttribute('role','tab');b.setAttribute('aria-controls','result-'+key);tabs.append(b);buttons[key]=b;
    const p=el('div','','result-panel');p.id='result-'+key;p.setAttribute('role','tabpanel');p.setAttribute('aria-labelledby',b.id);panels[key]=p;
    b.addEventListener('click',()=>show(key));
    b.addEventListener('keydown',e=>{const keys=Object.keys(buttons),i=keys.indexOf(key);let next;if(e.key==='ArrowRight')next=(i+1)%keys.length;else if(e.key==='ArrowLeft')next=(i+keys.length-1)%keys.length;else if(e.key==='Home')next=0;else if(e.key==='End')next=keys.length-1;else return;e.preventDefault();show(keys[next]);buttons[keys[next]].focus();});
  }
  const toolbar=el('div','','report-toolbar'); toolbar.append(analysis.querySelector('.analysis-actions'),$('run-history'),$('analysis-progress'));
  analysis.querySelector('.section-heading').remove();
  const chart=section.querySelector('.chart-card'),foundation=$('foundation-card');panels.chart.append(chart,foundation);
  panels.answer.append(analysis);
  const professional=el('section','','paper-card professional-card');professional.id='professional-content';panels.professional.append(professional);
  const log=el('dialog','','analysis-log-dialog');log.id='analysis-log-dialog';log.setAttribute('aria-labelledby','analysis-log-title');
  const logHeading=el('div','','log-heading'),logTitle=el('h2','分析 Log');logTitle.id='analysis-log-title';
  const closeLog=el('button','×','icon-button');closeLog.id='analysis-log-close';closeLog.type='button';closeLog.title='关闭 Log';closeLog.setAttribute('aria-label','关闭 Log');closeLog.onclick=()=>log.close();
  logHeading.append(logTitle,closeLog);const model=el('div');model.id='model-info-content';log.append(logHeading,model,analysis.querySelector('#audit-report'),analysis.querySelector('#ai-raw-replies'));document.body.append(log);
  log.addEventListener('click',event=>{if(event.target===log){const rect=log.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)log.close();}});
  const followup=$('context-card');panels.answer.append(followup);
  section.append(toolbar,tabs,...Object.values(panels));
  function show(key){if(!panels[key])return;for(const k of Object.keys(panels)){panels[k].hidden=k!==key;buttons[k].setAttribute('aria-selected',String(k===key));buttons[k].tabIndex=k===key?0:-1;}}
  function openLog(){if(!log.open)log.showModal();}
  function focusFollowup(){show('answer');followup.scrollIntoView({block:'start',behavior:'smooth'});$('context-text').focus({preventScroll:true});}
  function reset(){professional.replaceChildren(el('p','本次尚无专业报告。','empty-state'));model.replaceChildren();$('audit-report').open=false;}
  function readableValue(value){if(value===undefined||value===null)return '';if(typeof value==='string'||typeof value==='number')return String(value);if(Array.isArray(value))return value.map(readableValue).filter(Boolean).join('\n');if(typeof value==='object')return readableValue(value.text||value.content||value.message||value.description||value.question||value.reason||value.summary||value.impact||value.gap||'');return '';}
  function values(items){return (Array.isArray(items)?items:items?[items]:[]).map(readableValue).filter(Boolean);}
  function table(title,cls=''){const node=el('table','','professional-table '+cls);node.append(el('caption',title),el('tbody'));return node;}
  function row(node,label,value,cls=''){if(!readableValue(value))return null;const tr=el('tr','',cls),th=el('th',label),td=el('td',readableValue(value));th.scope='row';tr.append(th,td);node.tBodies[0].append(tr);return td;}
  function listRow(node,label,items,cls=''){const texts=values(items);if(!texts.length)return;const td=row(node,label,texts,cls);td.replaceChildren();const list=el('ul');texts.forEach(text=>list.append(el('li',text)));td.append(list);}
  function appendFields(node,fields){fields.forEach(([label,value])=>row(node,label,value));}
  function pair(first,second){return [readableValue(first)||'未说明',readableValue(second)||'未说明'].join(' / ');}
  function candidates(stage){return (Array.isArray(stage?.candidates)?stage.candidates:[]).filter(item=>item&&typeof item==='object');}
  function candidateTitle(label,candidate,selectedId,index){return label+(selectedId?(candidate.candidate_id===selectedId?' · 本次采用':' · 其他候选'):' · 待确认候选 '+(index+1));}
  function appendQuotes(node,quotes){const texts=values((Array.isArray(quotes)?quotes:[]).map(q=>q?.quote||q));if(!texts.length)return;const td=row(node,'原文依据',' '),details=el('details','','professional-evidence');td.replaceChildren();details.append(el('summary','查看 '+texts.length+' 处原文'));texts.forEach(text=>details.append(el('p',text)));td.append(details);}
  function appendCandidates(parent,stage,selectedId,label,renderCandidate){const entries=candidates(stage),chosen=entries.find(candidate=>selectedId&&candidate.candidate_id===selectedId);if(!chosen){entries.forEach((candidate,index)=>parent.append(renderCandidate(candidate,candidateTitle(label,candidate,null,index))));return;}parent.append(renderCandidate(chosen,candidateTitle(label,chosen,selectedId,0)));const others=entries.filter(candidate=>candidate!==chosen);if(others.length){const details=el('details','','professional-alternatives');details.append(el('summary','其他'+label+'候选（'+others.length+'）'));others.forEach((candidate,index)=>details.append(renderCandidate(candidate,candidateTitle(label,candidate,selectedId,index))));parent.append(details);}}
  function useLabel(candidate){if(!candidate)return '';if(candidate.subject_reference==='shi')return '世爻（社会身份、角色或外部资源尺度）';if(candidate.subject_reference==='shi_body')return '世身（个人状态、身体或自身处境尺度）';const relatives={parents:'父母',siblings:'兄弟',offspring:'子孙',wealth:'妻财',official_ghost:'官鬼'};return relatives[candidate.six_relative]||candidate.six_relative||'';}
  function selectionNotes(result){
    const selection=result?.stage_outputs?.selection,interpretation=result?.stage_outputs?.interpretation;
    const reviews=result?.selection_note_reviews||result?.audit_report?.selection_note_reviews;
    if(Array.isArray(reviews))return reviews.filter(r=>r&&r.current_status!=='resolved').map(r=>r.current_text??r.review_text??r.original_text);
    // Final uncertainties have already been checked against the saved input and chart.
    if(interpretation)return [];
    return selection?.unresolved;
  }
  function renderChecks(result,report,c){
    const intent=result?.stage_outputs?.intent,selection=result?.stage_outputs?.selection,interpretation=result?.stage_outputs?.interpretation;
    const intents=candidates(intent),uses=candidates(selection);
    const missing=[...new Set([result?.unresolved,result?.clarifying_questions,report?.uncertainties,report?.clarifying_questions,
      intent?.clarifying_questions,interpretation?.uncertainties,interpretation?.clarifying_questions,selectionNotes(result),selection?.clarifying_questions].reduce((all,items)=>all.concat(values(items)),[]))];
    const audit=result?.audit_report,conditions=c?.key_conditions??audit?.conclusion_conditions,limits=c?.limits??audit?.conclusion_limits;
    if(!intents.length&&!uses.length&&!missing.length&&!c&&!values(conditions).length&&!values(limits).length)return false;
    const wrap=el('section','','professional-checks');
    appendCandidates(wrap,intent,intent?.selected_candidate_id,'意念',(candidate,title)=>{const node=table(title,'professional-intent');appendFields(node,[['所问事项',candidate.primary_question],['主体 / 对象',pair(candidate.actor,candidate.object)],['行动 / 目标',pair(candidate.action,candidate.desired_outcome)],['时间范围',candidate.time_scope],['关注维度',values(candidate.facets).join('；')]]);appendQuotes(node,candidate.evidence_quotes);return node;});
    const relations={generates_me:'生我者',same_as_me:'同我者',generated_by_me:'我生者',controlled_by_me:'我克者',controls_me:'克我者'},purposes={primary:'主目标',supporting:'支持因素',cost:'代价',carrier:'载体'};
    appendCandidates(wrap,selection,selection?.selected_primary_id,'取象',(candidate,title)=>{const node=table(title,'professional-use');appendFields(node,[['关注对象',candidate.object_role],['本次作用',candidate.function],['用途 / 对应',[purposes[candidate.purpose]||candidate.purpose,useLabel(candidate)].filter(Boolean).join(' / ')],['功能关系',relations[candidate.relation]||candidate.relation]]);listRow(node,'成立假设',candidate.assumptions);appendQuotes(node,candidate.evidence_quotes);return node;});
    const directions={favorable:'偏顺利',unfavorable:'阻力较多',mixed:'有利有弊',undetermined:'暂不能判断'};
    if(c||values(conditions).length||values(limits).length||missing.length){const node=table('结论与条件','professional-conclusion');const answer=row(node,'综合判断',c?.answer);if(answer&&c?.direction)answer.prepend(el('span',directions[c.direction]||directions.undetermined,'professional-direction'));listRow(node,'成立条件',conditions,'conclusion-conditions');listRow(node,'判断边界',limits,'conclusion-limits');listRow(node,'待补 / 核实',missing,'professional-missing');wrap.append(node);}
    professional.append(wrap);return true;
  }
  const jargon=/用神|官鬼|妻财|父母爻|兄弟爻|子孙|世爻|应爻|应克世|持世|动爻|变爻|旬空|月令|日辰|生扶|回头生克|实验|综合分|结构性|第[一二三四五六1-6]爻/;
  function fallback(c){let text=(c?.answer||'').split(/[：:；;。\n]/)[0].replace(/^按本次卦象[，,]?/,'');if(!text||text.length>110||jargon.test(text))text=({favorable:'这件事偏向能成，但仍有条件需要落实。',unfavorable:'这件事目前偏向难成，需要重新评估条件。',mixed:'这件事有机会，但推进中可能反复。'})[c?.direction]||'目前还不能明确判断结果。';return {answer:text,source:'compatibility'};}
  function render(report,container,{isDemo=false,result=null}={}){
    const c=report.conclusion||result?.stage_outputs?.interpretation?.conclusion,plain=!isDemo&&(report.plain_language|| (c?fallback(c):null));
    let shown=false;
    if(plain){const hero=el('div','','answer-hero');hero.append(el('p','这次的答案','eyebrow'),el('h3',plain.answer,'direct-answer'));if(plain.reason)hero.append(el('p',plain.reason,'answer-reason'));const ask=el('button','继续问 AI ↓','text-button answer-followup-link');ask.type='button';ask.setAttribute('aria-controls','context-form');ask.addEventListener('click',focusFollowup);hero.append(ask);container.append(hero);shown=true;
      const grid=el('div','','answer-grid');for(const [key,label] of [['watch_for','需要留意'],['next_steps','接下来怎么做']]){if(!plain[key]?.length)continue;const card=el('section','','answer-note');card.append(el('h4',label));const list=el('ul');plain[key].slice(0,3).forEach(t=>list.append(el('li',t)));card.append(list);grid.append(card);}container.append(grid);
      if(plain.timing)container.append(el('p','时间判断：'+plain.timing,'answer-timing'));
      if(plain.source==='compatibility')container.append(el('p','当前展示简要答案；完整原文和依据在“专业分析”。','small-note'));
    }else if(report.summary){container.append(el('p',report.summary,'report-summary'));shown=true;}
    const sections=(report.sections||[]).filter(x=>x.content||x.body||x.text);
    professional.replaceChildren();
    if(!isDemo)shown=renderChecks(result,report,c)||shown;
    if(sections.length){shown=true;let current=0;const nav=el('div','','professional-nav');nav.setAttribute('role','tablist');nav.setAttribute('aria-label','专业分析主题');const body=el('section','','professional-body');body.id='professional-topic';body.setAttribute('role','tabpanel');
      const footer=el('div','','professional-pager'),prev=el('button','← 上一页','secondary-button'),next=el('button','下一页 →','secondary-button'),count=el('span');prev.type=next.type='button';
      const controls=sections.map((s,i)=>{const b=el('button',(i+1)+' '+(s.heading||s.title||'分析说明'));b.type='button';b.id='professional-topic-'+i;b.setAttribute('role','tab');b.setAttribute('aria-controls',body.id);b.addEventListener('click',()=>page(i));b.addEventListener('keydown',e=>{if(!['ArrowRight','ArrowLeft','Home','End'].includes(e.key))return;e.preventDefault();page(e.key==='Home'?0:e.key==='End'?sections.length-1:(i+(e.key==='ArrowRight'?1:sections.length-1))%sections.length);controls[current].focus();});nav.append(b);return b;});
      function page(i){current=i;const s=sections[i];body.replaceChildren(el('h3',s.heading||s.title||'分析说明'),el('p',s.content||s.body||s.text));body.setAttribute('aria-labelledby',controls[i].id);controls.forEach((b,j)=>{b.setAttribute('aria-selected',String(i===j));b.tabIndex=i===j?0:-1;});prev.disabled=i===0;next.disabled=i===sections.length-1;count.textContent=`${i+1} / ${sections.length}`;}
      prev.addEventListener('click',()=>page(current-1));next.addEventListener('click',()=>page(current+1));footer.append(prev,count,next);professional.append(nav,body,footer);page(0);
      if(!plain)container.append(el('p','分段说明可在“专业分析”中查看。','small-note'));
    }else professional.append(el('p','本次没有分段推演。','empty-state'));
    return shown;
  }
  window.ReportViews={render,reset,show,openLog};reset();show('answer');
})();
