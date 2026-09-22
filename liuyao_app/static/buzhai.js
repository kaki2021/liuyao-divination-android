(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  const node=(tag,text='',cls='')=>{const n=document.createElement(tag);n.textContent=text;n.className=cls;return n;};
  const fields=['stage','site_kind','role','residence','beneficiary','site','proposal','previous_case_id'];
  const details=node('details','','person-details');details.id='buzhai-details';
  details.innerHTML=`<summary>卜宅／选房专题 <span>按需启用</span></summary>
    <div class="person-fields"><label class="topic-switch"><input type="checkbox" id="buzhai-enabled"> 本次启用卜宅专题</label>
    <p class="small-note">一案对应一个对象、地点和方案。多个备选地点分别建案，再结合实际条件比较。</p>
    <div id="buzhai-fields" hidden>
      <div class="person-grid"><div><label for="buzhai-stage">本次要做什么</label><select id="buzhai-stage"><option value="site_choice">择地／选房</option><option value="scope_check">核对问题范围（先辨关联）</option><option value="diagnosis">分析具体问题（再查环节）</option><option value="remedy_check">验证整改方案（评估效果）</option></select></div><div><label for="buzhai-site_kind">场所类型</label><select id="buzhai-site_kind"><option value="yang">阳宅</option><option value="yin">阴宅</option></select></div></div>
      <section id="buzhai-stage-help" class="topic-help" aria-live="polite"></section>
      <div class="person-grid"><div><label for="buzhai-role">是谁起的这一卦</label><select id="buzhai-role"><option value="other">其他代问或尚未明确</option><option value="host">使用者／主家本人</option><option value="consultant">卦师独立勘察</option></select></div><div><label for="buzhai-residence">入住情况</label><select id="buzhai-residence"><option value="unknown">未说明／不适用</option><option value="not_occupied">尚未入住</option><option value="occupied">已经入住</option></select></div></div>
      <div class="person-grid"><div><label for="buzhai-beneficiary">针对谁（可用称呼）</label><input id="buzhai-beneficiary" maxlength="80" placeholder="例如：我和共同居住的家人"></div><div><label for="buzhai-site">哪个具体地点（可用代号）</label><input id="buzhai-site" maxlength="120" placeholder="例如：备选房 A，不必填完整住址"></div></div>
      <label for="buzhai-proposal">本次方案或待查范围</label><textarea id="buzhai-proposal" rows="2" maxlength="800" placeholder="例如：按目前户型自住，不改变内部布局"></textarea>
      <label for="buzhai-previous_case_id">前序案例编号（选填）</label><input id="buzhai-previous_case_id" placeholder="case_…"><p class="small-note">仅作关联记录；需要旧案内容时请补充到背景。发起 AI 分析时，以上资料会随问题提交。</p>
    </div></div>`;
  $('person-details').after(details);
  const stageHelp={
    site_choice:{name:'择地／选房',when:'已经有一个具体备选地点和使用计划，想判断它是否适合指定的人与目标。',ask:'这个地点按这个方案使用，对指定对象是否适合？',example:'我计划把 A 房按现有布局作为一家三口的长期住所，这一方案对我们的居住目标是否合适？',proposal:'准备怎样使用这个地点',placeholder:'例如：一家三口长期自住，保留当前布局',next:'结合现实条件比较备选。不同地点或明显不同的方案分别建案，不用一卦给所有地点排序。'},
    scope_check:{name:'核对问题范围',when:'治风水的第一步：已经有具体困扰，先核对宅地、布局或其他怀疑范围，不能直接认定就是房屋造成。',ask:'本次怀疑的这个范围，是否值得继续排查？',example:'针对 A 房目前居住使用中的不便，本次是否适合从宅地与布局方面继续排查？',proposal:'已经知道什么，想核对哪个范围',placeholder:'例如：已入住 A 房，日常使用多有不便；还不确定是否与布局有关',next:'本步用于厘清后续排查范围。卦象不能证明现实因果，已有现场事实要另行记录。'},
    diagnosis:{name:'分析具体问题',when:'治风水的第二步：前一步已经核对待查范围，再另起一卦问其中具体问题；请交代前一步的依据。',ask:'这个具体问题优先检查什么环节？',example:'针对 A 房目前已记录的使用不便，应优先检查哪些布置或使用环节？',proposal:'本次待查的具体问题及已知现象',placeholder:'例如：前一步记录了待查范围；本次只查 A 房起居活动区的具体问题',next:'根据诊断方向核对现场并拟定整改方案，再单独验证方案。若尚未核对范围，请先返回“核对问题范围”。本步不证明某个建筑缺陷已经存在。'},
    remedy_check:{name:'验证整改方案',when:'治风水的第三步：已查明待处理的问题并拟定具体措施，再另起一卦判断方案是否对症。',ask:'按这项措施调整，是否有助于本次目标？',example:'拟将 A 房的书房移到 B 位置并改善采光，这一方案是否有利于我的长期使用？',proposal:'打算改哪里、怎样改、解决什么问题',placeholder:'例如：将书房移到 B 位置；目标是改善目前的使用不便',next:'原文要求方案判断不利时重新审视诊断、调整方案后再占；不是保持原题一直摇到吉。实施后的效果另记反馈，卦象不能代替实际验收。'}
  };
  const chooseGuide=node('details','','guide-details');chooseGuide.id='buzhai-choice-guide';chooseGuide.append(node('summary','四个选项怎么选？治理的三步怎么衔接？'),node('p','择地／选房是一类主问，不要求每次走完四项。治风水则依《卜筮正术》044 依次核对范围 → 另问具体问题 → 再问整改方案；每步另有主问和实际起卦。你可以从当前已具备依据的阶段记录，但要交代前序判断，不能选一步就声称完成全流程。'));
  Object.values(stageHelp).forEach(g=>{const section=node('section','','guide-block');section.append(node('h4',g.name),node('p',g.when));chooseGuide.append(section);});$('buzhai-stage-help').before(chooseGuide);
  const roleHelp=node('details','','guide-details');roleHelp.append(node('summary','场所类型、起卦人和入住情况怎么填？'),node('p','阳宅用于居住或日常使用的场所；阴宅用于安葬相关场所。选择实际对象，不按问题吉凶来选。'),node('p','起卦人填实际取得这一卦的人：使用者或主家亲自起卦选“本人”；卦师按自己的独立勘察起卦选“卦师”；替他人记录或角色尚不清楚选“其他”。请勿为了套用选房规则而改身份。'),node('p','入住情况填起卦当时的事实。尚未入住只会在适用条件下提示相应原理，不会全局取消旬空扣分。阴宅或不涉及入住时选“未说明／不适用”。'),node('p','“针对谁”填主要使用者或受益人；“地点”可用 A 房等代号。前序案例编号可留空，只用来关联记录，不会自动读取旧案内容。'));
  $('buzhai-previous_case_id').parentElement.append(roleHelp);
  function update(){
    $('buzhai-fields').hidden=!$('buzhai-enabled').checked;
    const g=stageHelp[$('buzhai-stage').value];
    const help=$('buzhai-stage-help');help.replaceChildren(node('h4','适合在什么情况下选'),node('p',g.when),node('h4','这次回答什么'),node('p',g.ask),node('h4','问法示例（不会自动填入案例）'),node('p',g.example),node('p',g.next,'small-note'));
    document.querySelector('label[for="buzhai-proposal"]').textContent=g.proposal;
    $('buzhai-proposal').placeholder=g.placeholder;
  }
  details.addEventListener('change',update);update();
  function read(validate=true){
    if(!$('buzhai-enabled').checked)return null;
    const value={};for(const k of fields){const input=$('buzhai-'+k);const text=input.value.trim();if(k==='previous_case_id'&&!text)continue;value[k]=text;
      if(validate&&['beneficiary','site','proposal'].includes(k)&&!text){input.focus();throw new Error('请填写：'+document.querySelector('label[for="buzhai-'+k+'"]').textContent+'。');}}
    if(validate&&value.previous_case_id&&!/^case_[a-f0-9]{32}$/.test(value.previous_case_id)){$('buzhai-previous_case_id').focus();throw new Error('前序案例编号应为 case_ 开头的完整编号；没有请留空。');}
    return value;
  }
  function fill(value){$('buzhai-enabled').checked=Boolean(value);for(const k of fields){const input=$('buzhai-'+k);input.value=value?.[k]||({stage:'site_choice',site_kind:'yang',role:'other',residence:'unknown'}[k]||'');}details.open=Boolean(value);update();}
  const canonical=value=>value?JSON.stringify(Object.fromEntries(fields.filter(k=>value[k]!==undefined).map(k=>[k,value[k]]))):'';

  const panel=node('section','','paper-card topic-card');panel.id='buzhai-result';panel.hidden=true;$('result-professional').prepend(panel);
  const flag=value=>value===null||value===undefined?'待核对':value?'是':'否';
  function render(chart){
    const t=chart?.buzhai_analysis;panel.hidden=!t;panel.replaceChildren();if(!t)return;
    panel.append(node('p','卜宅专题 · '+t.stage_label,'eyebrow'),node('h3',t.context.site+' · '+t.context.beneficiary));
    panel.append(node('p',t.role_label+'；'+t.context.proposal,'small-note'));
    const d=node('details');d.open=true;d.append(node('summary','五地候选与成立条件'));
    const f=t.five_lands;d.append(node('p',f.candidate_name+'（命名候选）','topic-candidate'),node('p',f.condition),node('p',f.note,'small-note'));
    const lines=f.observations.map(l=>`${l.layer==='hidden'?'伏神':'本卦'}第${l.position}爻${l.branch}：普通月令${l.month_class||'未知'}，旬空${flag(l.empty)}，月破${flag(l.month_break)}`);
    d.append(node('p',lines.join('；')||'本卦及伏神未找到所需六亲。','small-note'));panel.append(d);
    const r=t.residence_choice;
    if(r.applicable){const choice=node('details');choice.append(node('summary','选房条件核对'));const list=node('ul');
      [`全卦静：${flag(r.all_static)}；动爻 ${r.moving_count} 个。静不等于旺。`,`六冲卦：${flag(r.six_clash)}；六合卦：${flag(r.six_combine)}。`,`世爻日冲：${flag(r.shi_day_clash)}；实验暗动：${flag(r.shi_hidden_moving_experimental)}。`,`世爻旬空：${flag(r.shi_empty)}；普通月令：${r.shi_month_class||'未知'}。`,r.empty_exception==='conditional_only'?'尚未入住：可在世旺前提成立时讨论世空例外，目前不自动认定。':'本次不启用“尚未入住且世旺”的旬空例外。'].forEach(s=>list.append(node('li',s)));choice.append(list,node('p',r.note,'small-note'));panel.append(choice);}
    else panel.append(node('p','本次不是主家本人起卦的阳宅选房，不套用该场景的静旺、冲动和未入住世空偏好。','small-note'));
    const limits=node('details');limits.append(node('summary','出处与当前能力范围'),node('p','《卜筮正术补充卜宅》043、044；《太卜风水术》PDF 第130、149～150页。全部原理可在规则库查看、导出。','small-note'));t.limitations.forEach(s=>limits.append(node('p',s,'small-note')));panel.append(limits);
  }

  const dialog=$('rules-page'),parameter=node('div'),principles=node('div');parameter.id='parameter-panel';principles.id='principle-panel';principles.hidden=true;
  for(const child of [...dialog.children])if(child.matches('#rules-version,.rules-tools,#rules-message,.rules-primer,.rule-browser'))parameter.append(child);
  const tabs=node('div','','principle-tabs'),parameterTab=node('button','评分参数'),principleTab=node('button','卜宅原理 · 10 条');
  for(const b of [parameterTab,principleTab]){b.type='button';tabs.append(b);}parameterTab.setAttribute('aria-pressed','true');principleTab.setAttribute('aria-pressed','false');dialog.append(tabs,parameter,principles);
  let guide=null;
  function show(which){parameter.hidden=which!=='parameter';principles.hidden=which!=='principles';parameterTab.setAttribute('aria-pressed',String(which==='parameter'));principleTab.setAttribute('aria-pressed',String(which==='principles'));}
  parameterTab.addEventListener('click',()=>show('parameter'));
  principleTab.addEventListener('click',async()=>{show('principles');if(guide)return;principles.replaceChildren(node('p','正在读取原理…'));
    try{const response=await fetch('/api/principles',{headers:{'X-App-Request':'1'}});if(!response.ok)throw new Error('原理未能读取，请重试。');guide=await response.json();principles.replaceChildren(node('p',guide.note,'topic-help'));
      const link=node('a','导出原理及出处（JSON）','secondary-button');link.href='/api/principles/export';link.download='卜宅原理.json';principles.append(link);
      const table=node('table','','principle-table');const head=node('tr');['命名候选','世爻六亲','还须核对旺相的六亲'].forEach(t=>head.append(node('th',t)));table.append(head);guide.five_lands.forEach(r=>{const tr=node('tr');[r.name,r.shi_relative,r.required_relative].forEach(t=>tr.append(node('td',t)));table.append(tr);});principles.append(table);
      principles.append(node('p','下面各条可展开。这里没有需要修改的数值；实验加减分仍在“评分参数”中单独说明。','small-note'));
      guide.rules.forEach(r=>{const d=node('details','','principle-entry');d.append(node('summary',r.title),node('p',r.statement),node('p','适用范围：'+r.scope,'small-note'));r.limitations.forEach(t=>d.append(node('p','边界：'+t,'small-note')));const source=guide.sources.find(s=>s.source_id===r.source_id);d.append(node('p','出处：《'+source.title+'》'+r.source_locator,'source-note'));principles.append(d);});
    }catch(e){guide=null;principles.replaceChildren(node('p',e.message));}
  });
  window.Buzhai={read,fill,canonical,render};
})();
