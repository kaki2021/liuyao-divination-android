/* Contextual reading aids. Examples never enter a case or a model request. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  const el=(tag,text='',cls='')=>{const n=document.createElement(tag);n.textContent=text;n.className=cls;return n;};
  const block=(title,text)=>{const d=el('section','','guide-block');d.append(el('h4',title),el('p',text));return d;};
  const details=(title)=>{const d=el('details','','guide-details');d.append(el('summary',title));return d;};
  const signed=n=>(n>=0?'+':'')+n;
  const intro=details('起卦前：先谋后卜，怎么准备？');intro.id='question-guidance';
  intro.append(block('谋事先有可讨论的计划','先认真考虑现实条件，再说明具体做法和犹疑之处。例如：“我打算下个月按现有条件接下这个项目，担心投入过大；这样推进对我是否有利，主要代价是什么？”'),
    block('还在排查问题时','先明确待查对象、现象、范围和目的。例如：“A 房起居活动区已有这些使用不便，应优先检查哪些环节？”诊断前不必编造整改方案，但要清楚这次想查什么。'),
    block('让本次问题有所指','先读一遍：我关心的是哪个对象的什么事情？结果将帮助我判断什么？需要哪些已知事实？不要为了凑表格而填写猜测。'));
  intro.append(el('p','第一课原文称“谋而后卜”。先谋划，再问尚未拿准之处；判断不利先检视计划、查漏补缺。“使用原理”可查看原文短引和说明。','small-note'));
  const learn=el('button','查看卜筮用途与使用方法','text-button');learn.type='button';intro.append(learn);$('person-details').before(intro);
  $('question').placeholder='我准备做什么？已有条件是什么？哪一点还拿不准？若在查问题，写清待查对象与范围。';
  learn.onclick=()=>{$('rules-open').click();window.RuleWorkbench.show('usage');};
  const how=details('起卦与“重新解卦”有什么区别？');how.append(el('p','起卦是实际摸取或摇卦并记录结果。“保存并排盘”把结果翻译为卦盘；“保存并分析”和“重新解卦”调用 AI 解读已记录的卦，不会自动产生新卦。相关的细问可用“再起一卦”接入本系列，无关问题新建系列。'));
  $('casting-instruction').after(how);

  function ledger(host,traces,title){
    host.replaceChildren(el('h4',title));const label=el('label','选择一个爻，看分数怎么得来'),select=el('select');select.setAttribute('aria-label',title+'爻位');label.append(select);host.append(label);
    traces.forEach(l=>{const o=el('option',`第 ${l.position} 爻 · ${l.name} · ${l.score} 分`);o.value=l.position;select.append(o);});const body=el('div','','score-ledger');host.append(body);
    function render(){const l=traces.find(t=>String(t.position)===select.value);body.replaceChildren();
      const {table,fold}=window.RuleWorkbench;
      body.append(el('p',`只计算第 ${l.position} 爻（${l.name}）。覆盖：${l.coverage}。`,'small-note'));
      const ownSum=l.local_items.reduce((s,c)=>s+c.value,0),effectSum=l.incoming_items.reduce((s,c)=>s+c.value,0);
      body.append(table(['计算阶段','结果'],[['共同起点',l.base+' 分'],['自身加减合计',signed(Math.round(ownSum*1e6)/1e6)+' 分'],['来源局部分',`${l.local_raw} → ${l.local_score} 分（限于 0～10）`],['外来作用合计',signed(Math.round(effectSum*1e6)/1e6)+' 分'],['最终强度',`${l.raw_score} → ${l.score} 分 · ${l.level}`],['强弱分界',`低于 ${l.weak} 为偏弱，高于 ${l.strong} 为偏强；边界及其间为中等。`]],'rule-pairs'));
      body.append(el('h5','自身贡献'));
      if(l.local_items.length)body.append(table(['命中条件','参数','贡献'],l.local_items.map(c=>[`${c.detail}（${c.rule_id}）`,c.enabled?String(c.parameter):'停用',signed(c.value)+' 分']),'rule-contributions'));
      else body.append(el('p','没有可加入的自身贡献。','small-note'));
      body.append(el('h5','外来作用'));
      if(l.incoming_items.length)body.append(table(['来源与作用','权重与系数','贡献'],l.incoming_items.map(c=>{const d=fold(String(c.enabled?c.parameter:0)+' × 系数');d.append(el('p',`${c.name}${c.enabled?'':'（停用）'} × ${c.multipliers.map(m=>`${m.value}（${m.name}）`).join(' × ')} = ${c.value} 分`,'formula'));return [`第 ${c.source} 爻 · ${c.detail}`,d,signed(c.value)+' 分'];}),'rule-contributions'));
      else body.append(el('p','无发动或实验暗动来源，外来作用为 0。','small-note'));
      body.append(el('p','局部分用于来源权重；最终分按引擎合成并限制在 0～10。强弱只描述相对强度，有利与否须结合所问作用。','small-note'));
    }select.onchange=render;render();
  }
  function attachLedger(box,{rule,api,version,input}){
    const host=window.RuleWorkbench.fold('当前卦的计算明细');host.id='rule-calculation';box.append(host);
    const content=el('div');host.append(content);let loaded=false;
    host.addEventListener('toggle',async()=>{if(!host.open||loaded)return;loaded=true;content.replaceChildren(el('p','正在读取本卦计算…'));
      try{const payload={rule_id:rule.id,value:rule.value,enabled:rule.enabled,expected_version:version};if(input)payload.input=input;const r=await api('/api/rules/preview',payload);if(!box.contains(host))return;
        content.replaceChildren(el('p',r.example+' · '+r.chart_name,'guide-lead'));const trace=el('section');content.append(trace);ledger(trace,r.before_trace,'当前参数计算明细');
      }catch(e){loaded=false;content.replaceChildren(el('p',e.message));}
    });
  }
  function comparison(output,result){
    output.replaceChildren(el('p',result.example+' · '+result.chart_name,'small-note'));
    output.append(window.RuleWorkbench.table(['爻位','当前','试调','变化'],result.before.map((a,i)=>{const b=result.after[i];return [`${a.position} ${a.name}`,`${a.score} ${a.level}`,`${b.score} ${b.level}`,signed(Math.round((b.score-a.score)*1000)/1000)];}),'trial-table'));
    if(result.before.every((a,i)=>a.score===result.after[i].score))output.append(el('p','六爻最终分数没有变化。请查看本项类型、是否命中、是否停用或达到 0/10 边界；排序、摘要与结构开关也可能只改变分数以外的内容。','topic-help'));
    if(['switch','branch'].includes(result.rule_kind)){const d=window.RuleWorkbench.fold('比较结构识别与动变标记');d.append(el('p','以下结构仅说明是否识别，不直接代表吉凶。','small-note'));for(const [key,label]of [['before_structures','当前'],['after_structures','试调']]){d.append(el('h4',label));const v=result[key];d.append(window.RuleWorkbench.table(['项目','识别结果'],[['配对',v.pairs.length+' 组'],['三合／半合',v.groups.map(g=>g.type+'：第'+g.positions.join('、')+'爻').join('；')||'无'],...v.changes.map(c=>['第'+c.position+'爻',c.effects.join('、')||'无动变标记'])],'rule-pairs'));}output.append(d);}
    if(result.rule_kind==='ranking')output.append(el('p','本次试算没有执行 AI 取用，不能判断本问应选哪个候选。这类参数只用于同类候选排序，六爻强度保持原样；排序公式见上方说明。','topic-help'));
    if(result.rule_kind==='summary_factor')output.append(el('p','本次未建立主辅功能候选，故不伪造本卦的辅助摘要。此参数只改变摘要乘积，六爻分数不变；可按上方 6 分来源的公式示例核对。','topic-help'));
    if(result.after_hidden.length){const d=window.RuleWorkbench.fold('伏神强度对比');d.append(window.RuleWorkbench.table(['位置','当前','试调'],result.after_hidden.map((h,i)=>['第'+h.position+'爻下',String(result.before_hidden[i]?.strength.score??'—'),String(h.strength.score)])));output.append(d);}
    for(const [key,title]of [['before_trace','当前计算明细'],['after_trace','试调计算明细']]){const d=window.RuleWorkbench.fold(title),host=el('div');d.append(host);ledger(host,result[key],title);output.append(d);}output.append(el('p','本次只试算，参数及历史报告未修改。','small-note'));
  }
  window.RuleGuideUI={attachLedger,comparison};
})();
