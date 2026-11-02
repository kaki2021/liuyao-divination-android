/* Review every proposed change before it reaches the local people database. */
(function(){'use strict';
const labels={name:'姓名',nickname:'称呼',city:'所在地',industry:'行业',role:'职业',company:'公司',skills:'技能',interests:'兴趣',needs:'需求',wechat:'微信',phone:'电话',email:'邮箱',birthday:'出生日期',bio:'简介',career:'工作经历',education:'教育经历',metAt:'认识地点 / 事件（私人）',offers:'能提供的资源',relationshipstatus:'情感 / 婚姻状态',childrenstatus:'子女情况',personalgoals:'理想追求',shorttermgoals:'近期目标',contactpreference:'沟通偏好',relationtypes:'与我的关系（私人）',meetingchannel:'认识途径（私人）',introducedby:'介绍人（私人）'};
const multi=new Set(['industry','role','company','skills','interests','needs','relationtypes','career','education']);
const privateFields=new Set(['relationtypes','meetingchannel','introducedby','metAt']);
const choices={relationshipstatus:['单身','恋爱中','已婚','其他'],childrenstatus:['有子女','无子女','其他'],contactpreference:['微信','电话','邮件','当面交流','其他'],relationtypes:['家人','亲属','同学','校友','老师','学生','现同事','前同事','现上级','前上级','现下属','前下属','行业同行','邻居','同乡','共同兴趣伙伴','同一活动参与者','同一社群成员','同一协会成员','客户','合作伙伴','供应商','商务对接人','服务提供者'],meetingchannel:['同学介绍','同事介绍','家人介绍','活动认识','线上认识','共同兴趣','工作认识','社群认识','其他']};
const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);return n;};
function render(turn,host,request,reload,key){
 const result=turn.result||{};
 if(result.applied){host.append(el('p','这份整理已保存。'));return;}
 if(!Array.isArray(result.people)||!result.people.length)return;
 const root=el('div');root.className='people-review';
 const status=el('p','正在读取本机人物资料…');root.append(status);host.append(root);
 request('/api/zhiren/v09/state').then(snapshot=>{
  if(!root.isConnected)return;
  status.textContent='核对每个人、字段和交流记录后保存。所选 AI 服务会收到你在此模式输入的内容。';
  const state=snapshot.state||{}, existing=Array.isArray(state.people)?state.people:[], cards=[];
  for(const proposed of result.people){
   const section=el('section');section.className='people-review-card';
   section.append(el('strong',proposed.subject==='self'?'我的资料':(proposed.label||'待确认联系人')));
   const select=el('select');select.className='people-review-input';
   const option=(value,label)=>{const o=el('option',label);o.value=value;select.append(o);};
   if(proposed.subject==='self'){option('self','我的资料');option('new','新增联系人');}
   else{option('new','新增联系人');option('self','我的资料');}
   for(const p of existing)if(p&&p.id)option(p.id,(p.name||p.nickname||'未命名')+' · '+(p.city||'未记录城市'));
   section.append(el('p','保存到：'),select);
   const name=el('input');name.className='people-review-input';name.placeholder='新增联系人时填写姓名或称呼';name.value=proposed.label||'';section.append(name);
   const fields=[];
   for(const item of proposed.fields||[]){
    if(!labels[item.field])continue;
    const wrap=el('div');wrap.className='people-review-field';wrap.append(el('label',labels[item.field]));
    const value=el('textarea');value.className='people-review-input';value.rows=2;value.maxLength=600;value.value=item.value||'';wrap.append(value);
    if(choices[item.field]){const pick=el('select');pick.className='people-review-input';const hint=el('option','可选：改用标准选项');hint.value='';pick.append(hint);for(const choice of choices[item.field]){const o=el('option',choice);o.value=choice;pick.append(o);}pick.addEventListener('change',()=>{if(pick.value)value.value=pick.value;});wrap.append(pick);}
    const old=el('small');wrap.append(old);const op=el('select');op.className='people-review-input';
    for(const [v,t] of [['keep','保留原值'],['append','追加'],['replace','使用这条内容']]){const o=el('option',t);o.value=v;op.append(o);}
    wrap.append(op);if(item.evidence)wrap.append(el('small','原话：'+item.evidence));section.append(wrap);
    fields.push({field:item.field,value,op,old});
   }
   const records=[];
   for(const rec of proposed.records||[]){
    const wrap=el('div');wrap.className='people-review-field';const include=el('input');include.type='checkbox';include.checked=true;
    const label=el('label',rec.kind==='agreement'?'保存这条约定':'保存这条交流记录');label.prepend(include);wrap.append(label);
    const value=el('textarea');value.className='people-review-input';value.rows=2;value.value=rec.content||'';wrap.append(value);
    const date=el('input');date.type='date';date.className='people-review-input';date.value=rec.date||'';wrap.append(el('small','日期不确定可留空'),date);
    if(rec.evidence)wrap.append(el('small','原话：'+rec.evidence));section.append(wrap);records.push({include,value,date,kind:rec.kind,source:rec.evidence||''});
   }
   const missing=Array.isArray(proposed.missing)?proposed.missing:[];if(missing.length)section.append(el('small','可选补充：'+missing.join('、')));
   function update(){
    const id=select.value;name.hidden=id!=='new';const obj=id==='self'?(state.self||{}):existing.find(x=>x.id===id)||{};
    for(const field of fields){const oldValue=obj[field.field]||(field.field==='birthday'?obj.birthdayMD:'');const value=Array.isArray(oldValue)?oldValue.join('、'):String(oldValue||'');
     field.old.textContent=id==='self'&&privateFields.has(field.field)?'关系信息仅能保存到联系人；请选择联系人或保留原值。':value?'已有：'+value:'目前未填写';
     field.op.value=value?(multi.has(field.field)?'append':'keep'):'replace';
    }
   }
   select.addEventListener('change',update);update();root.append(section);cards.push({select,name,fields,records});
  }
  const save=el('button','确认保存');save.type='button';save.className='primary-button';const error=el('p');root.append(save,error);
  save.onclick=async()=>{
   const changes=cards.map(c=>({target:c.select.value,name:c.name.value.trim(),fields:c.fields.map(f=>({field:f.field,value:f.value.value.trim(),operation:f.op.value})),records:c.records.filter(x=>x.include.checked).map(x=>({kind:x.kind,content:x.value.value.trim(),date:x.date.value,source:x.source}))}));
   save.disabled=true;error.textContent='正在保存…';
   try{await request('/api/zhiren/assistant/apply',{revision:snapshot.revision,changes,turn_id:turn.turn_id},'people-edit-'+turn.turn_id);
    if(window.LiuyaoAndroid?.syncBirthdayReminders){const updated=await request('/api/zhiren/v09/state');const rows=(updated.state.people||[]).map(p=>({name:p.nickname||p.name||'联系人',birthday:p.birthday||p.birthdayMD||''})).filter(p=>p.birthday);window.LiuyaoAndroid.syncBirthdayReminders(JSON.stringify(rows));}
    error.textContent='已保存';await reload();}
   catch(e){error.textContent=e.message;save.disabled=false;}
  };
 }).catch(e=>{status.textContent='读取人物资料失败：'+e.message;});
}
window.GongPeopleAssistant={render};
})();
