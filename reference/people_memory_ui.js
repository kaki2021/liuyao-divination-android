(function(){'use strict';
function snippet(id){
 const items=(st.events||[]).filter(e=>Array.isArray(e.people)&&e.people.includes(id)&&['communication','agreement'].includes(e.type));
 const records=items.map(e=>'<div class="memory-row"><b>'+esc(e.type==='agreement'?'约定':'交流')+'</b> <small>'+esc(e.date||'日期未填写')+'</small><p>'+esc(e.detail||'')+'</p>'+(e.source?'<small>原话：'+esc(e.source)+'</small>':'')+'<button class="ghost tiny" data-action="memory-delete" data-id="'+esc(e.id)+'" data-person="'+esc(id)+'">删除</button></div>').join('');
 const p=person(id),links=(p?.connections||[]).filter(x=>x&&person(x.personId));
 const outgoing=links.map(x=>'<li>关联到 '+esc(person(x.personId).nickname||person(x.personId).name)+'：'+esc(x.label||'认识')+' <button class="ghost tiny" data-action="memory-unlink" data-person="'+esc(id)+'" data-target="'+esc(x.personId)+'">移除</button></li>');
 const incoming=(st.people||[]).filter(q=>q.id!==id&&Array.isArray(q.connections)).flatMap(q=>q.connections.filter(x=>x.personId===id).map(x=>'<li>'+esc(q.nickname||q.name)+' 添加的关系：'+esc(x.label||'认识')+'</li>'));
 const relationships=[...outgoing,...incoming].join('');
 const privateDetails=[['与我的关系',Array.isArray(p?.relationtypes)?p.relationtypes.join('、'):(p?.relationtypes||'')],['认识途径',p?.meetingchannel],['介绍人',p?.introducedby]].filter(x=>x[1]);
 return '<section class="memory-box"><h3>私人关系记录</h3>'+(privateDetails.length?privateDetails.map(([k,v])=>'<p><b>'+esc(k)+'：</b>'+esc(v)+'</p>').join(''):'<p class="hint">可以在编辑资料里选择关系和认识途径。</p>')+'<p class="hint">只保存在你的联系人档案里，不随名片分享。</p><h3>交流与约定</h3>'+(records||'<p class="hint">还没有记录，可以以后慢慢补充。</p>')+
 '<button class="lightbtn tiny" data-action="memory-add" data-person="'+esc(id)+'">添加交流 / 约定</button>'+
 '<details><summary>与其他联系人的关系</summary><ul>'+relationships+'</ul><button class="lightbtn tiny" data-action="memory-link" data-person="'+esc(id)+'">添加关系</button></details></section>';
}
function add(id){const p=person(id);if(!p)return;modal('添加交流与约定 · '+(p.nickname||p.name),'<form id="gongMemoryForm" data-person="'+esc(id)+'"><label>类型<select class="inp" name="kind"><option value="communication">交流记录</option><option value="agreement">约定</option></select></label><label>内容<textarea class="inp" name="content" maxlength="1200" required></textarea></label><label>日期（选填）<input class="inp" type="date" name="date"></label><div class="foot-actions"><button type="button" class="lightbtn" data-action="memory-return" data-person="'+esc(id)+'">返回</button><button class="primary">保存</button></div></form>');}
function link(id){const p=person(id);if(!p)return;const options=st.people.filter(x=>x.id!==id).map(x=>'<option value="'+esc(x.id)+'">'+esc(x.nickname||x.name)+'</option>').join('');modal('添加联系人关系','<form id="gongLinkForm" data-person="'+esc(id)+'"><label>联系人<select class="inp" name="target" required>'+options+'</select></label><label>与此人的关系<select class="inp" name="label" required><option value="">请选择</option><option>亲属</option><option>同学</option><option>现同事</option><option>前同事</option><option>上下级</option><option>行业同行</option><option>邻居</option><option>同乡</option><option>共同兴趣伙伴</option><option>同一社群成员</option><option>客户</option><option>合作伙伴</option><option>供应商</option><option>介绍人</option><option>其他</option></select></label><div class="foot-actions"><button type="button" class="lightbtn" data-action="memory-return" data-person="'+esc(id)+'">返回</button><button class="primary">保存</button></div></form>');}
function upcoming(){
 const now=new Date(),start=new Date(now.getFullYear(),now.getMonth(),now.getDate());
 return (st.people||[]).map(p=>{const m=String(p.birthday||p.birthdayMD||'').match(/(?:^\d{4}-|^)(\d{2})-(\d{2})$/);if(!m)return null;
  const month=Number(m[1])-1,day=Number(m[2]);const make=y=>{let d=new Date(y,month,day);if(month===1&&day===29&&d.getMonth()!==1)d=new Date(y,1,28);return d;};let d=make(start.getFullYear());if(d.getMonth()!==month)return null;if(d<start)d=make(start.getFullYear()+1);if(d.getMonth()!==month)return null;
  return {p,days:Math.round((d-start)/86400000)};}).filter(x=>x&&x.days<=7).sort((a,b)=>a.days-b.days);
}
function birthdays(){const items=upcoming();return '<section class="panel cardpad memory-birthdays"><h3>近期生日</h3>'+(items.length?items.map(x=>'<button class="lightbtn tiny" data-open-person="'+esc(x.p.id)+'">'+esc(x.p.nickname||x.p.name)+' · '+(x.days===0?'今天':x.days+'天后')+'</button>').join(''):'<p class="hint">未来 7 天没有已记录的生日。</p>')+'<p class="hint">按阳历提醒；启用通知后提前 7 天、1 天和当天提醒。2 月 29 日在非闰年按 2 月 28 日提醒。</p><button class="lightbtn tiny" data-action="birthday-enable">启用系统生日提醒</button> <button class="ghost tiny" data-action="birthday-disable">关闭系统生日提醒</button></section>';}
function sync(list){if(!window.LiuyaoAndroid?.syncBirthdayReminders)return;const rows=(list||st.people||[]).map(p=>({name:String(p.nickname||p.name||'联系人').slice(0,80),birthday:String(p.birthday||p.birthdayMD||'')})).filter(x=>x.birthday);window.LiuyaoAndroid.syncBirthdayReminders(JSON.stringify(rows));}
document.addEventListener('click',e=>{const b=e.target.closest('[data-action]');if(!b)return;const action=b.dataset.action,id=b.dataset.person;
 if(!['memory-add','memory-link','memory-return','memory-delete','memory-unlink','birthday-enable','birthday-disable'].includes(action))return;
 e.preventDefault();e.stopImmediatePropagation();
 if(action==='memory-add')add(id);else if(action==='memory-link')link(id);else if(action==='memory-return')detail(id);
 else if(action==='memory-delete'){if(confirm('删除这条记录？')){st.events=st.events.filter(x=>x.id!==b.dataset.id);persist();detail(id);}}
 else if(action==='memory-unlink'){const p=person(id);if(p){p.connections=(p.connections||[]).filter(x=>x.personId!==b.dataset.target);persist();detail(id);}}
 else if(action==='birthday-enable'){if(window.LiuyaoAndroid?.enableBirthdayReminders){sync();window.LiuyaoAndroid.enableBirthdayReminders();}else toast('此环境暂不支持系统通知，可在此查看近期生日');}
 else if(action==='birthday-disable'){window.LiuyaoAndroid?.disableBirthdayReminders?.();toast('已关闭系统生日提醒');}
},true);
document.addEventListener('submit',e=>{const f=e.target;if(!f||!['gongMemoryForm','gongLinkForm'].includes(f.id))return;e.preventDefault();e.stopImmediatePropagation();const id=f.dataset.person,p=person(id);if(!p)return;
 if(f.id==='gongMemoryForm'){const content=f.elements.content.value.trim();if(!content)return;st.events.unshift({id:'evt-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2),date:f.elements.date.value||'',recordedAt:new Date().toISOString(),type:f.elements.kind.value,title:f.elements.kind.value==='agreement'?'约定':'交流记录',detail:content,people:[id]});}
 else{const target=f.elements.target.value,label=f.elements.label.value.trim();if(!target||!label||!person(target))return;p.connections=Array.isArray(p.connections)?p.connections:[];p.connections=p.connections.filter(x=>x.personId!==target);p.connections.push({personId:target,label});}
 persist();detail(id);toast('已保存');
},true);
window.GongPeopleMemory={snippet,birthdays,sync};
})();
