(() => {
 'use strict';
 const $=id=>document.getElementById(id), phone=matchMedia('(max-width:760px)'), native=window.LiuyaoAndroid;
 const make=(tag,cls,text)=>{const x=document.createElement(tag);x.className=cls||'';if(text)x.textContent=text;return x;};
 const form=$('case-form'), question=make('div','mobile-question-step'), casting=make('div','mobile-casting-step');
 let phase=question;
 for(const child of [...form.children]){if(child.classList.contains('divider')){phase=casting;child.remove();}else phase.append(child);}
 const steps=make('nav','mobile-steps');steps.setAttribute('aria-label','输入进度');
 for(const [n,label] of [[1,'写下所问'],[2,'记录卦象']]){const b=make('button');b.type='button';b.dataset.step=n;b.append(make('span','',String(n)),document.createTextNode(label));b.addEventListener('click',()=>step(n));steps.append(b);}
 const next=make('button','primary-button mobile-only mobile-next','下一步 · 记录卦象 →');next.type='button';next.id='mobile-next';next.onclick=()=>step(2);
 const back=make('button','text-button mobile-only mobile-step-back','← 返回修改所问');back.type='button';back.onclick=()=>step(1);question.append(next);casting.prepend(back);form.append(steps,question,casting);
 function step(n,scroll=true){if(n===2&&!$('question').value.trim()){ $('question').focus();$('question').reportValidity();return;}form.dataset.mobileStep=String(n);steps.querySelectorAll('button').forEach(b=>{if(Number(b.dataset.step)===n)b.setAttribute('aria-current','step');else b.removeAttribute('aria-current');});if(phone.matches&&scroll)form.scrollIntoView({block:'start',behavior:'smooth'});}
 step(1,false);
 // Keep each of the three draws legible instead of stacking 24 choices.
 const draws=[...$('meibu-inputs').querySelectorAll('.meibu-group')], drawNav=make('nav','mobile-only mobile-draw-nav');drawNav.setAttribute('aria-label','枚卜丸摸取进度');
 let draw=0;
 const drawButtons=['下卦','上卦','动爻'].map((label,i)=>{const b=make('button','',label);b.type='button';b.onclick=()=>showDraw(i);drawNav.append(b);return b;});
 const drawNext=make('button','secondary-button mobile-only mobile-draw-next');drawNext.type='button';drawNext.onclick=()=>showDraw(Math.min(draw+1,2));
 function showDraw(i){draw=i;draws.forEach((d,j)=>d.classList.toggle('mobile-inactive-draw',i!==j));drawButtons.forEach((b,j)=>b.setAttribute('aria-pressed',String(i===j)));drawNext.textContent=i===0?'第二次 · 记录上卦 →':'第三次 · 记录动爻 →';drawNext.hidden=i===2;drawNext.disabled=!document.querySelector(`input[name="meibu-${i+1}"]:checked`);}
 $('meibu-inputs').prepend(drawNav);$('meibu-inputs').append(drawNext);$('meibu-inputs').addEventListener('change',()=>{showDraw(draw);drawButtons.forEach((b,i)=>b.textContent=['下卦','上卦','动爻'][i]+(document.querySelector(`input[name="meibu-${i+1}"]:checked`)?' ✓':''));});showDraw(0);
 for(const id of ['save-case','analyze-case'])$(id).addEventListener('click',()=>{if(phone.matches&&document.querySelector('input[name="casting-method"]:checked')?.value==='meibu'){const missing=draws.findIndex((_,i)=>!document.querySelector(`input[name="meibu-${i+1}"]:checked`));if(missing!==-1)showDraw(missing);}},true);
 const preview=document.querySelector('.casting-preview'), previewDetails=make('details','mobile-preview');previewDetails.append(make('summary','','本卦与变卦预览'));preview.before(previewDetails);previewDetails.append(preview);
 function previewMode(){previewDetails.open=!phone.matches;}if(phone.addEventListener)phone.addEventListener('change',previewMode);else phone.addListener(previewMode);previewMode();
 const icons={work:'<path d="M5 5h14M5 10h5m4 0h5M5 15h14M5 20h5m4 0h5"/>',history:'<rect x="4" y="4" width="16" height="17" rx="3"/><path d="M8 2v4m8-4v4M8 11h8m-8 5h5"/>',rules:'<path d="M12 5v16M12 5C8 2 3 4 3 4v15s5-2 9 2c4-4 9-2 9-2V4s-5-2-9 1Z"/>',settings:'<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>'};
 const nav=make('nav','mobile-nav');nav.setAttribute('aria-label','主导航');
 for(const [key,label] of [['work','问卦'],['history','档案'],['rules','规则']]){const b=make('button');b.type='button';b.dataset.page=key;b.id='mobile-'+key;b.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true">'+icons[key]+'</svg>';b.append(make('span','',label));b.onclick=()=>{if(key==='rules')$('rules-open').click();else page(key);};nav.append(b);}document.body.append(nav);
 const rulesPage=$('rules-page');document.querySelector('.workspace').append(rulesPage);let rulesReturn='work';
 function page(key,scroll=true){document.body.dataset.mobilePage=key;rulesPage.hidden=key!=='rules';nav.querySelectorAll('button').forEach(b=>{if(b.dataset.page===key)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});if(scroll)window.scrollTo({top:0,behavior:'smooth'});}
 page('work',false);
 new MutationObserver(()=>{if(document.body.dataset.mobilePage!=='rules')page('work',false);if(document.body.dataset.view==='input'&&$('case-state').textContent==='新案例')step(1,false);}).observe(document.body,{attributes:true,attributeFilter:['data-view']});
 $('new-case').addEventListener('click',()=>{if($('case-state').textContent==='新案例'){step(1,false);showDraw(0);drawButtons.forEach((b,i)=>b.textContent=['下卦','上卦','动爻'][i]);page('work');}});
 document.querySelector('.brand').addEventListener('click',e=>{if(phone.matches||document.body.dataset.mobilePage==='rules'){e.preventDefault();page('work');}});
 document.querySelectorAll('.professional-pager').forEach(x=>x.setAttribute('aria-label','翻页'));
 $('professional-content').addEventListener('click',e=>{if(phone.matches&&e.target.closest('.professional-pager button'))$('professional-content').scrollIntoView({block:'start',behavior:'smooth'});});
 $('rule-list').addEventListener('click',()=>{if(phone.matches)setTimeout(()=>$('rule-detail').scrollIntoView({block:'start',behavior:'smooth'}),0);});
 const notes=[...$('settings-dialog').querySelectorAll('p')];notes.find(p=>p.textContent.includes('API 密钥在'))?.classList.add('mobile-desktop-note');
 const initialHeight=window.innerHeight;
 window.visualViewport?.addEventListener('resize',()=>document.body.classList.toggle('keyboard-open',window.visualViewport.height<initialHeight*.72&&/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName||'')));
 $('rules-back').addEventListener('click',()=>page(rulesReturn));
 window.MobileUI={openRules(){if(document.body.dataset.mobilePage!=='rules')rulesReturn=document.body.dataset.mobilePage||'work';page('rules');},back(){const dialog=document.querySelector('dialog[open]');if(dialog){dialog.close();return true;}if(document.body.dataset.mobilePage==='rules'){page(rulesReturn);return true;}if(document.body.dataset.mobilePage==='history'){page('work');return true;}if(document.body.dataset.view!=='input'){$('tab-input').click();return true;}if(form.dataset.mobileStep==='2'){step(1);return true;}return false;},toast(text){const t=make('div','mobile-toast',text);t.setAttribute('role','status');document.body.append(t);setTimeout(()=>t.remove(),3500);}};
 if(native){
  document.body.classList.add('android-app');
  const button=make('button','secondary-button mobile-key-button','配置 API 密钥');button.type='button';button.id='mobile-key';button.onclick=()=>native.configureModel($('provider-select').value);$('settings-done').before(button);
  const hint=make('p','small-note','密钥加密保存在此手机。排盘与档案可离线使用，AI 分析需要联网。');button.after(hint);
  document.addEventListener('click',e=>{const a=e.target.closest('a[download]');if(a&&a.href.startsWith(location.origin+'/api/')){e.preventDefault();native.exportFile(a.href,a.download||'六爻记录.json');}},true);
  new MutationObserver(()=>native.analysisState($('analysis-progress').dataset.running==='true')).observe($('analysis-progress'),{attributes:true,attributeFilter:['data-running']});
  window.addEventListener('pagehide',()=>window.LiuyaoApp?.persistDraft());
  document.addEventListener('visibilitychange',()=>{if(document.hidden)window.LiuyaoApp?.persistDraft();});
 }
})();
