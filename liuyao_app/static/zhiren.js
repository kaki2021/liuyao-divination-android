'use strict';
(function () {
  var state = {people:[], posts:[], cards:[], cardIndex:0, matches:[], selected:{}};
  function el(id) { return document.getElementById(id); }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function node(tag, text, cls) { var n=document.createElement(tag); if(text!==undefined)n.textContent=String(text); if(cls)n.className=cls; return n; }
  function err(text) { el('notice').textContent=text || ''; }
  function id() { return String(Date.now())+'-'+String(Math.random()).slice(2); }
  async function api(path, payload) {
    var options={headers:{'X-App-Request':'1','Accept':'application/json'}};
    if(payload!==undefined) {options.method='POST';options.headers['Content-Type']='application/json';options.headers['X-Idempotency-Key']=id();options.body=JSON.stringify(payload);}
    var response=await fetch(path,options), data=await response.json();
    if(!response.ok)throw new Error((data.error && data.error.message) || '本地请求失败');
    return data;
  }
  async function reload() {
    try {
      var results=await Promise.all([api('/api/zhiren/people'),api('/api/zhiren/posts'),api('/api/zhiren/cards')]);
      state.people=results[0].people;state.posts=results[1].posts;state.cards=results[2].cards;
      renderPeople();renderPosts();renderCards();
    }catch(e){err(e.message);}
  }
  function switchTab(name) {
    document.querySelectorAll('.page').forEach(function(x){x.hidden=x.id!==name;});
    document.querySelectorAll('[data-tab]').forEach(function(x){x.classList.toggle('active',x.getAttribute('data-tab')===name);});
    err('');
  }
  function listFrom(value) {return value.split(/[,，、]/).map(function(s){return s.trim();}).filter(Boolean);}
  function renderPeople(){
    var categories={}, filter=el('people-filter').value.toLowerCase(), sel=el('category-filter');
    state.people.forEach(function(p){(p.categories||[]).forEach(function(c){categories[c]=true;});});
    var selected=sel.value;clear(sel);var all=node('option','全部分类');all.value='';sel.appendChild(all);
    Object.keys(categories).sort().forEach(function(c){var opt=node('option',c);opt.value=c;sel.appendChild(opt);});sel.value=selected;
    var list=el('people-list');clear(list);
    var items=state.people.filter(function(p){return (!sel.value||(p.categories||[]).indexOf(sel.value)!==-1)&&
      (!filter||JSON.stringify(p).toLowerCase().indexOf(filter)!==-1);});
    el('people-count').textContent=items.length+' 人';
    if(!items.length){list.appendChild(node('p','暂无符合条件的人物。','muted'));return;}
    items.forEach(function(p){
      var card=node('article',undefined,'person-card');card.appendChild(node('div',p.name.slice(0,1),'avatar'));
      card.appendChild(node('h3',p.name));card.appendChild(node('p',[p.city,p.industry,p.occupation].filter(Boolean).join(' · '),'muted'));
      card.appendChild(node('p',(p.categories||[]).join(' / '),'muted'));
      var b=node('button','编辑','secondary');b.addEventListener('click',function(){editPerson(p);});card.appendChild(b);list.appendChild(card);
    });
  }
  function editPerson(p){
    el('person-editor').open=true;el('person-id').value=p?p.person_id:'';el('person-version').value=p?p.version:'';
    var form=el('person-form');['name','city','industry','occupation','contact','relationship','notes'].forEach(function(k){form.elements[k].value=p?(p[k]||''):'';});
    ['categories','skills','interests','needs'].forEach(function(k){form.elements[k].value=p?(p[k]||[]).join('、'):'';});
    el('person-editor').scrollIntoView({block:'nearest'});
  }
  el('new-person').addEventListener('click',function(){editPerson(null);});
  el('cancel-person').addEventListener('click',function(){el('person-editor').open=false;});
  el('person-form').addEventListener('submit',async function(e){
    e.preventDefault();var form=e.target,p={};
    ['name','city','industry','occupation','contact','relationship','notes'].forEach(function(k){p[k]=form.elements[k].value;});
    ['categories','skills','interests','needs'].forEach(function(k){p[k]=listFrom(form.elements[k].value);});
    var body={person:p};if(el('person-id').value){body.person_id=el('person-id').value;body.expected_version=Number(el('person-version').value);}
    try{await api('/api/zhiren/people',body);el('person-editor').open=false;err('已保存在本地人物数据库。');await reload();}catch(ex){err(ex.message);}
  });
  el('people-filter').addEventListener('input',renderPeople);el('category-filter').addEventListener('change',renderPeople);
  function renderSelection(targetId, checkedSet) {
    var target=el(targetId);clear(target);
    state.matches.forEach(function(m){
      var row=node('div',undefined,'match-item'),label=node('label');
      var box=document.createElement('input');box.type='checkbox';box.checked=!!checkedSet[m.person_id];
      box.addEventListener('change',function(){checkedSet[m.person_id]=box.checked;});
      label.appendChild(box);label.appendChild(node('strong',' '+m.name));label.appendChild(node('p',m.reasons.join('、'),'muted'));
      row.appendChild(label);target.appendChild(row);
    });
    if(!state.matches.length) target.appendChild(node('p','没有找到有明确资料依据的候选人，可以补充人物的兴趣、行业或城市。','muted'));
  }
  async function doMatch(value,target) {
    var result=await api('/api/zhiren/match',{text:value});
    state.matches=result.matches;state.selected={};state.matches.forEach(function(m){state.selected[m.person_id]=true;});
    renderSelection(target,state.selected);el('use-match').disabled=!state.matches.length;
  }
  el('match-form').addEventListener('submit',async function(e){e.preventDefault();try{await doMatch(el('match-text').value,'match-list');}catch(ex){err(ex.message);}});
  el('use-match').addEventListener('click',function(){
    el('post-text').value=el('match-text').value;
    document.querySelector('input[name=kind][value="活动"]').checked=true;
    renderSelection('post-recipients',state.selected);switchTab('publish');
  });
  el('suggest-people').addEventListener('click',async function(){
    try{await doMatch(el('post-text').value,'post-recipients');}catch(ex){err(ex.message);}
  });
  el('post-form').addEventListener('submit',async function(e){
    e.preventDefault();
    var ids=state.matches.filter(function(m){return state.selected[m.person_id];}).map(function(m){return m.person_id;});
    var data={kind:document.querySelector('input[name=kind]:checked').value,
              content:el('post-text').value,recipient_ids:ids};
    try{await api('/api/zhiren/posts',data);state.matches=[];state.selected={};clear(el('post-recipients'));
      el('post-text').value='';await reload();err('已存本地草稿。当前版本没有发送通知。');
    }catch(ex){err(ex.message);}
  });
  function renderPosts() {
    var box=el('post-list');clear(box);
    state.posts.forEach(function(p){box.appendChild(node('div',p.kind+' · '+p.content+'\n拟通知 '+p.recipient_ids.length+' 人 · 未发送','post-row'));});
    if(!state.posts.length)box.appendChild(node('p','还没有发布草稿。','muted'));
  }
  var allowed=['name','city','industry','occupation','contact','skills','interests','needs'];
  var names=['姓名','城市','行业','职业','联系方式','技能','兴趣','需求'];
  allowed.forEach(function(field,i){
    var label=node('label'),checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.value=field;checkbox.checked=i<4;
    label.appendChild(checkbox);label.appendChild(node('span',names[i]));el('card-fields').appendChild(label);
  });
  function renderCards() {
    var preview=el('card-preview');clear(preview);var count=state.cards.length;
    if(count){state.cardIndex=(state.cardIndex+count)%count;var card=state.cards[state.cardIndex];
      preview.appendChild(node('h3',card.name));preview.appendChild(node('p','展示字段：'+card.fields.map(function(f){return names[allowed.indexOf(f)]||f;}).join('、')));
      preview.appendChild(node('p','适用对象：'+(card.audience||'单次选择'),'muted'));
    }else preview.appendChild(node('p','尚未创建名片'));
    el('card-position').textContent=count?(state.cardIndex+1)+' / '+count:'0 / 0';
  }
  el('prev-card').addEventListener('click',function(){state.cardIndex--;renderCards();});
  el('next-card').addEventListener('click',function(){state.cardIndex++;renderCards();});
  el('card-form').addEventListener('submit',async function(e){
    e.preventDefault();var form=e.target;
    var fields=Array.from(el('card-fields').querySelectorAll('input:checked')).map(function(x){return x.value;});
    try{await api('/api/zhiren/cards',{name:form.elements.name.value,audience:form.elements.audience.value,fields:fields});
      state.cardIndex=state.cards.length;await reload();err('名片模板已本地保存（未分享）。');
    }catch(ex){err(ex.message);}
  });
  document.querySelectorAll('[data-tab]').forEach(function(b){b.addEventListener('click',function(){switchTab(b.getAttribute('data-tab'));});});
  reload();
}());