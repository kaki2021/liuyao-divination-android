(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  const el=(tag,text='',cls='')=>{const n=document.createElement(tag);n.textContent=text;n.className=cls;return n;};
  const section=$('results-section'), analysis=$('analysis-card');
  const tabs=el('nav','','result-tabs');tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','结果阅读方式');
  const panels={},buttons={};
  for(const [key,label] of [['answer','直接答案'],['professional','专业分析'],['chart','卦盘与计算'],['records','分析记录']]){
    const b=el('button',label);b.type='button';b.id='result-tab-'+key;b.setAttribute('role','tab');b.setAttribute('aria-controls','result-'+key);tabs.append(b);buttons[key]=b;
    const p=el('div','','result-panel');p.id='result-'+key;p.setAttribute('role','tabpanel');p.setAttribute('aria-labelledby',b.id);panels[key]=p;
    b.addEventListener('click',()=>show(key));
    b.addEventListener('keydown',e=>{const keys=Object.keys(buttons),i=keys.indexOf(key);let next;if(e.key==='ArrowRight')next=(i+1)%4;else if(e.key==='ArrowLeft')next=(i+3)%4;else if(e.key==='Home')next=0;else if(e.key==='End')next=3;else return;e.preventDefault();show(keys[next]);buttons[keys[next]].focus();});
  }
  const toolbar=el('div','','report-toolbar'); toolbar.append(analysis.querySelector('.analysis-actions'),$('run-history'),$('analysis-progress'));
  analysis.querySelector('.section-heading').remove();
  const chart=section.querySelector('.chart-card'),foundation=$('foundation-card');panels.chart.append(chart,foundation);
  panels.answer.append(analysis);
  const professional=el('section','','paper-card professional-card');professional.id='professional-content';panels.professional.append(professional);
  const records=el('section','','paper-card');records.append(el('h3','分析过程与模型说明'));const model=el('div');model.id='model-info-content';records.append(model,analysis.querySelector('#audit-report'),analysis.querySelector('#ai-raw-replies'));panels.records.append(records);
  const followup=section.querySelector('.follow-up-card');$('feedback-section').append(followup);
  section.append(toolbar,tabs,...Object.values(panels));
  function show(key){for(const k of Object.keys(panels)){panels[k].hidden=k!==key;buttons[k].setAttribute('aria-selected',String(k===key));buttons[k].tabIndex=k===key?0:-1;}}
  function reset(){professional.replaceChildren(el('p','本次尚无专业报告。','empty-state'));model.replaceChildren();$('audit-report').open=false;}
  const jargon=/用神|官鬼|妻财|父母爻|兄弟爻|子孙|世爻|应爻|应克世|持世|动爻|变爻|旬空|月令|日辰|生扶|回头生克|实验|综合分|结构性|第[一二三四五六1-6]爻/;
  function fallback(c){let text=(c?.answer||'').split(/[：:；;。\n]/)[0].replace(/^按本次卦象[，,]?/,'');if(!text||text.length>110||jargon.test(text))text=({favorable:'这件事偏向能成，但仍有条件需要落实。',unfavorable:'这件事目前偏向难成，需要重新评估条件。',mixed:'这件事有机会，但推进中可能反复。'})[c?.direction]||'目前还不能明确判断结果。';return {answer:text,source:'compatibility'};}
  function render(report,container,{isDemo=false}={}){
    const c=report.conclusion,plain=!isDemo&&(report.plain_language|| (c?fallback(c):null));
    let shown=false;
    if(plain){const hero=el('div','','answer-hero');hero.append(el('p','这次的答案','eyebrow'),el('h3',plain.answer,'direct-answer'));if(plain.reason)hero.append(el('p',plain.reason,'answer-reason'));container.append(hero);shown=true;
      const grid=el('div','','answer-grid');for(const [key,label] of [['watch_for','需要留意'],['next_steps','接下来怎么做']]){if(!plain[key]?.length)continue;const card=el('section','','answer-note');card.append(el('h4',label));const list=el('ul');plain[key].slice(0,3).forEach(t=>list.append(el('li',t)));card.append(list);grid.append(card);}container.append(grid);
      if(plain.timing)container.append(el('p','时间判断：'+plain.timing,'answer-timing'));
      if(plain.source==='compatibility')container.append(el('p','当前展示简要答案；完整原文和依据在“专业分析”。','small-note'));
    }else if(report.summary){container.append(el('p',report.summary,'report-summary'));shown=true;}
    const sections=(report.sections||[]).filter(x=>x.content||x.body||x.text);
    professional.replaceChildren(el('p','保留完整依据，按主题逐页阅读。','small-note'));
    if(c?.answer&&!isDemo){const d=el('details');d.append(el('summary','查看原始综合判断'),el('p',c.answer));professional.append(d);}
    if(sections.length){shown=true;let current=0;const nav=el('div','','professional-nav');nav.setAttribute('role','tablist');nav.setAttribute('aria-label','专业分析主题');const body=el('section','','professional-body');body.id='professional-topic';body.setAttribute('role','tabpanel');
      const footer=el('div','','professional-pager'),prev=el('button','← 上一页','secondary-button'),next=el('button','下一页 →','secondary-button'),count=el('span');prev.type=next.type='button';
      const controls=sections.map((s,i)=>{const b=el('button',(i+1)+' '+(s.heading||s.title||'分析说明'));b.type='button';b.id='professional-topic-'+i;b.setAttribute('role','tab');b.setAttribute('aria-controls',body.id);b.addEventListener('click',()=>page(i));b.addEventListener('keydown',e=>{if(!['ArrowRight','ArrowLeft','Home','End'].includes(e.key))return;e.preventDefault();page(e.key==='Home'?0:e.key==='End'?sections.length-1:(i+(e.key==='ArrowRight'?1:sections.length-1))%sections.length);controls[current].focus();});nav.append(b);return b;});
      function page(i){current=i;const s=sections[i];body.replaceChildren(el('h3',s.heading||s.title||'分析说明'),el('p',s.content||s.body||s.text));body.setAttribute('aria-labelledby',controls[i].id);controls.forEach((b,j)=>{b.setAttribute('aria-selected',String(i===j));b.tabIndex=i===j?0:-1;});prev.disabled=i===0;next.disabled=i===sections.length-1;count.textContent=`${i+1} / ${sections.length}`;}
      prev.addEventListener('click',()=>page(current-1));next.addEventListener('click',()=>page(current+1));footer.append(prev,count,next);professional.append(nav,body,footer);page(0);
      if(!plain)container.append(el('p','分段说明可在“专业分析”中查看。','small-note'));
    }else professional.append(el('p','本次没有分段推演。','empty-state'));
    return shown;
  }
  window.ReportViews={render,reset,show};reset();show('answer');
})();
