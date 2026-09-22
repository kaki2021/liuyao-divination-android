/* Phone views use the same saved chart snapshot as the desktop tables. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  const el=(tag,text='',cls='')=>{const n=document.createElement(tag);n.className=cls;n.textContent=text;return n;};
  const names=['初爻','二爻','三爻','四爻','五爻','上爻'];
  const table=document.querySelector('.chart-comparison');
  table.closest('.table-scroll').classList.add('desktop-chart-table');
  const panel=el('section','','phone-chart');panel.id='phone-chart';panel.hidden=true;
  table.closest('.table-scroll').before(panel);
  let mode='main',snapshot=null;
  function yao(yang,moving=false){
    const line=el('span','','yao'+(moving?' moving':''));line.setAttribute('aria-label',yang?'阳爻':'阴爻');
    line.append(el('span'));if(!yang)line.append(el('span'));return line;
  }
  function show(which){mode=which;draw();}
  function draw(){
    panel.replaceChildren();panel.hidden=!snapshot?.main;if(panel.hidden)return;
    const chart=snapshot,changed=chart.changed_structure;
    if(!changed)mode='main';
    const nav=el('nav','','phone-chart-tabs');nav.setAttribute('aria-label','选择卦盘');
    for(const [key,label]of [['main','本卦'],['changed','变卦']]){
      const b=el('button',label);b.type='button';b.setAttribute('aria-pressed',String(key===mode));b.disabled=key==='changed'&&!changed;
      b.addEventListener('click',()=>show(key));nav.append(b);
    }
    panel.append(nav,el('p',mode==='main'?'从上爻到初爻，逐爻查看。':'整卦重新纳支；标记“发动”的位置才发生阴阳变化。','small-note'));
    const list=el('div','','phone-line-list');
    for(const original of [...chart.main.lines].reverse()){
      const computed=chart.comprehensive_analysis?.lines.find(x=>x.position===original.position);
      const change=computed?.change,index=original.position-1;
      const yang=mode==='main'?original.yang:Boolean(changed.bits[index]);
      const branch=mode==='main'?original.branch:changed.branches?.[index]||'';
      const element=mode==='main'?original.element:window.LiuyaoChartDisplay.branchElement(branch)||'';
      const card=el('article','','phone-line-card'+(original.moving?' is-moving':''));card.dataset.position=original.position;
      const header=el('div','','phone-line-heading');header.append(el('h4',names[index]),el('span',original.six_spirit?.replace('腾蛇','螣蛇')||'六神未排','small-note'));
      if(original.moving)header.append(el('span','发动','line-tag'));
      card.append(header);
      const core=el('div','','phone-line-core');core.append(yao(yang,original.moving),el('strong',branch+element));
      core.append(el('span',mode==='main'?original.relative:(change?.relative||'静位纳支')));card.append(core);
      const tags=[];
      if(mode==='main'){
        if(original.is_shi)tags.push('世爻');if(original.is_ying)tags.push('应爻');
        if(original.is_shi_body)tags.push('世身');if(original.matches_gua_body)tags.push('卦身');
        tags.push(original.moving?(original.yang?'老阳 · 阳变阴':'老阴 · 阴变阳'):(original.yang?'少阳 · 静爻':'少阴 · 静爻'));
      }else tags.push(original.moving?`由本卦${original.branch}${original.element}${original.relative}变出`:'本卦此位未发动');
      card.append(el('p',tags.join(' · '),'phone-line-note'));
      if(change)card.append(el('p',`变爻 ${change.changed}${change.changed_element}${change.relative}${change.effects.length?' · '+change.effects.join('、'):''}`,'phone-change-note'));
      list.append(card);
    }
    panel.append(list);
  }
  function strengthCards(chart){
    const box=$('comprehensive-content');box.querySelector('.phone-strength')?.remove();
    if(!chart?.comprehensive_analysis)return;
    const list=el('div','','phone-strength');
    for(const line of [...chart.comprehensive_analysis.lines].reverse()){
      const card=el('article','','phone-strength-card'),dm=line.day_month;
      const heading=el('div','','phone-strength-heading');heading.append(el('strong',`${names[line.position-1]} · ${line.branch}${line.element}${line.relative}`),el('span',`${line.strength.score} 分 · ${line.strength.level}`));card.append(heading);
      const tags=[dm.month_class?'月令'+dm.month_class:'日月未排',dm.empty?'旬空':'',dm.month_break?'月破':'',dm.day_clash?'日冲':'',dm.hidden_moving?'暗动（实验）':'',dm.day_break?'日破（实验）':''].filter(Boolean);
      card.append(el('p',tags.join(' · '),'small-note'));
      if(line.change)card.append(el('p',`变出${line.change.changed}${line.change.changed_element}${line.change.relative} · ${line.change.effects.join('、')||'普通变化'}`,'small-note'));
      list.append(card);
    }
    box.querySelector('table')?.before(list);
  }
  window.LiuyaoPhoneChart={render(chart){snapshot=chart;draw();strengthCards(chart);}};
})();
