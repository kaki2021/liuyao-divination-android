/* 工 / 我的资料：可选可搜的本地字典、分区块简介、三类地理位置 */
(function(){
'use strict';
const builtin={
 industries:['互联网','软件与信息技术','人工智能','制造业','汽车','教育','医疗健康','金融','法律','建筑','能源','农业','餐饮','住宿与旅游','传媒','文化艺术','物流','零售','科研','公共服务','自由职业','其他'],
 roles:['软件工程师','AI应用工程师','测试工程师','测试开发工程师','产品经理','项目经理','设计师','平面设计师','摄影师','视频剪辑师','教师','讲师','学生','研究员','咨询顾问','销售经理','市场经理','运营经理','创业者','公司负责人','创作者','医生','护士','律师','会计师','建筑师','电气工程师','机械工程师','汽车工程师','网络工程师','系统架构师','自由职业者','其他'],
 skills:['Python','JavaScript','Java','SQL','AI Agent','RAG','自动化测试','软件测试','项目管理','产品设计','UX设计','摄影','视频剪辑','文案写作','活动策划','市场推广','数据分析','演讲','英语','日语','沟通协调','书法','露营','运营'],
 interests:['阅读','徒步','露营','摄影','旅行','音乐','绘画','书法','健身','跑步','骑行','羽毛球','登山','历史','哲学','心理学','科技','编程','电影','美食','园艺','茶文化','写作','志愿活动']
};
// The user can always add their own entries; these are common starting points.
builtin.industries.push('计算机软件','互联网服务','游戏','电子商务','通信','半导体','硬件','新能源','航空航天','房地产','工程','设计','咨询','人力资源','会展','公益','政府','保险','银行','投资','制造','消费品','影视','出版','体育','环保','宠物','其他服务');
builtin.roles.push('AI工程师','算法工程师','数据工程师','数据分析师','前端工程师','后端工程师','全栈工程师','移动开发工程师','软件测试员','自动化工程师','质量工程师','运维工程师','技术支持','销售','市场专员','运营','商务','财务','人力资源','招聘专员','律师助理','翻译','自媒体创作者','民宿主理人','导游','厨师','手工艺人');
builtin.skills.push('机器学习','深度学习','Dify','n8n','大语言模型','提示词设计','知识库','MCP','自动化','接口测试','性能测试','Git','GitHub','Linux','Shell','PostgreSQL','Excel','数据可视化','商务谈判','组织协调','项目策划','社区运营','日语N2','翻译','烹饪','绘画');
builtin.interests.push('国学','易学','六爻','心理咨询','冥想','瑜伽','太极','茶','咖啡','烘焙','旅行','户外','露营','观星','动漫','游戏','桌游','音乐演奏','舞蹈','戏剧','传统文化','创业','科技','人工智能','宠物','收藏');
// Categories help discovery; the actual saved values remain ordinary user-editable tags.
const taxonomy={
 skills:{
  '沟通与协作':{'表达与沟通':['倾听','表达','演讲','跨文化沟通','客户沟通'],'协作与关系':['团队协作','沟通协调','冲突调解','谈判','会议组织']},
  '商业与经营':{'销售与客户':['销售','客户服务','商务谈判','客户维护'],'市场与运营':['市场调研','市场推广','品牌策划','商业分析','电商运营'],'供应与采购':['供应链管理','采购','物流管理']},
  '管理与组织':{'管理与培训':['团队管理','项目管理','人员培训','招聘','财务管理'],'策划与流程':['活动策划','项目策划','时间管理','流程优化','风险管理']},
  '办公与数据':{'办公与文档':['文档写作','Excel','PPT制作','资料整理','行政管理'],'数据与研究':['数据分析','数据可视化','统计分析','问卷设计','财务报表']},
  '计算机与技术':{'软件与编程':['Python','JavaScript','Java','SQL','软件测试','自动化测试'],'产品与系统':['产品设计','UX设计','系统运维','网络安全','数据工程'],'人工智能':['AI应用','机器学习','提示词设计','知识库']},
  '创意与媒体':{'视觉与影像':['摄影','视频剪辑','平面设计','插画','动画制作'],'内容与传播':['文案写作','音频制作','直播','内容运营','排版设计']},
  '语言与教育':{'语言与翻译':['英语','日语','韩语','法语','翻译'],'教育与培训':['教学','课程设计','培训','儿童教育','语言表达']},
  '工程与工艺':{'工程与维修':['机械维修','电工','电子维修','焊接','建筑设计','工程制图'],'制作与工艺':['木工','手工制作','陶艺','缝纫']},
  '生活与服务':{'饮食与家居':['烹饪','烘焙','园艺','家居整理'],'照护与服务':['汽车驾驶','宠物照护','急救','健康管理','导游','礼仪接待']},
  '艺术与表演':{'音乐与表演':['唱歌','乐器演奏','舞蹈','戏剧表演','主持','配音','作曲'],'视觉与传统艺术':['绘画','书法','插花','雕刻']},
  '专业服务':{'咨询与管理':['法律咨询','会计','人力资源','保险规划'],'健康与农业':['医疗护理','心理咨询','农业种植','营养配餐']}
 },
 interests:{
  '运动与健身':{'球类运动':['羽毛球','篮球','足球','网球','乒乓球','排球'],'个人运动':['跑步','健身','游泳','瑜伽','骑行','太极','滑雪']},
  '户外与旅行':{'户外探索':['徒步','登山','露营','观星','钓鱼','自然观察','潜水'],'旅行方式':['旅行','自驾游','骑行旅行','城市漫步']},
  '阅读与学习':{'人文与社会':['阅读','历史','哲学','心理学','经济'],'学习与表达':['语言学习','科普','写作','图书收藏']},
  '音乐与表演':{'音乐':['音乐','唱歌','乐器','音乐会'],'表演艺术':['舞蹈','戏剧','话剧','歌剧','相声']},
  '美术与手作':{'视觉艺术':['绘画','书法','摄影','设计'],'手工创作':['手工','陶艺','编织','模型制作','剪纸']},
  '影视与游戏':{'影视与动漫':['电影','电视剧','动漫','纪录片','短视频'],'游戏与互动':['电子游戏','桌游','剧本杀','拼图']},
  '美食与生活':{'饮食与饮品':['美食','烹饪','烘焙','咖啡','茶文化','葡萄酒'],'日常生活':['家居','园艺','家居收纳','手账']},
  '家庭与伙伴':{'家庭与陪伴':['亲子活动','家庭聚会','宠物'],'社交与公益':['社交聚会','志愿活动','公益','社区活动']},
  '文化与传统':{'文化遗产':['传统文化','国学','戏曲','民俗','文物','古建筑'],'传统技艺与思想':['书法','易学','六爻','古琴']},
  '科技与创作':{'科技与数码':['科技','人工智能','编程','数码产品','机器人'],'探索与创作':['科学实验','创作','天文','摄影']},
  '自然与动物':{'植物与自然':['植物','花卉','环保','海洋'],'动物观察':['观鸟','动物','自然摄影','昆虫']},
  '收藏与休闲':{'收藏与鉴赏':['收藏','逛展','文玩'],'休闲与放松':['棋牌','钓鱼','冥想','手账']}
 }
};
for(const kind of ['skills','interests'])for(const group of Object.values(taxonomy[kind]))builtin[kind].push(...Object.values(group).flat());
const tagDict={industry:'industries',role:'roles',company:'companies',skills:'skills',interests:'interests'};
const tagLabel={industry:'行业',role:'职业',company:'公司 / 组织',skills:'技能',interests:'兴趣爱好'};
const labels={birth:'出生地点',residence:'常住地',current:'当前所在地'};
let places=null,placeLoading=null,selected={birth:null,residence:null,current:null};
const normalized=s=>String(s||'').trim();
function escape(s){return String(s??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));}
function dict(){
 st.selfDictionaries=st.selfDictionaries&&typeof st.selfDictionaries==='object'?st.selfDictionaries:{};
 for(const k of ['industries','roles','companies','skills','interests']){
  if(!Array.isArray(st.selfDictionaries[k]))st.selfDictionaries[k]=[];
 }
 return st.selfDictionaries;
}
function names(k){
 const values=[...(builtin[k]||[]),...dict()[k].map(x=>typeof x==='string'?x:x.name||'')];
 if(k==='companies'){
  for(const p of st.people||[])if(p.company)values.push(...String(p.company).split(/[、\n]+/));
  if(st.self.company)values.push(...String(st.self.company).split(/[、\n]+/));
 }
 return [...new Set(values.map(normalized).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'zh'));
}
function multiValues(kind){
 const raw=st.self[kind];
 return Array.isArray(raw)?raw.map(normalized).filter(Boolean):
  String(raw||'').split(['industry','role','company'].includes(kind)?/[、\n]+/:/[、,，;；\n]+/).map(normalized).filter(Boolean);
}
function fold(label,body,initiallyOpen=false,extraClass=''){
 return '<details class="gong-profile-block gong-fold '+extraClass+'"'+(initiallyOpen?' open':'')+'><summary>'+escape(label)+'</summary><div class="gong-fold-body">'+body+'</div></details>';
}
function taxGroups(kind,chosen){
 return Object.entries(taxonomy[kind]||{}).map(([group,subgroups])=>'<details class="gong-tax-group"><summary>'+escape(group)+'</summary><div class="gong-tax-subgroups">'+
 Object.entries(subgroups).map(([subgroup,values])=>'<details class="gong-tax-subgroup"><summary>'+escape(subgroup)+'</summary><div class="gong-tag-suggestions">'+
 [...new Set(values)].map(value=>'<button type="button" class="gong-suggestion" data-action="profile-tax-toggle" data-tax-kind="'+escape(kind)+'" data-kind="'+escape(kind)+'" data-value="'+escape(value)+'" aria-pressed="'+(chosen.includes(value)?'true':'false')+'">'+(chosen.includes(value)?'✓ ':'＋ ')+escape(value)+'</button>').join('')+'</div></details>').join('')+'</div></details>').join('');
}
function tags(kind,values){
 const chosen=[...new Set(values)].slice(0,32);
 const body='<div class="gong-tag-chips" data-chips="'+kind+'">'+chosen.map(x=>
   '<span class="gong-tag">'+escape(x)+'<button type="button" data-action="profile-remove-tag" data-kind="'+kind+'" data-value="'+escape(x)+'" aria-label="移除 '+escape(x)+'">×</button></span>').join('')+'</div>'+
  '<input type="hidden" name="'+kind+'" value="'+escape(chosen.join('、'))+'">'+
  '<div class="gong-combo"><input class="inp" data-tag-input="'+kind+'" maxlength="64" autocomplete="off" placeholder="输入关键词搜索；也可输入自定义项">'+
  '<div class="gong-combo-results" data-tag-results="'+kind+'" hidden></div></div>'+
  (['skills','interests'].includes(kind)?'<p class="hint">展开类别，选择具体项目；支持多选、搜索和自定义。</p><div class="gong-taxonomy" data-taxonomy="'+kind+'">'+taxGroups(kind,chosen)+'</div>':'')+
  (kind==='company'?'<p class="hint">本机公司优先；输入时可联网搜索免费 LEI 企业记录，不覆盖全部企业。</p>':'');
 return fold(tagLabel[kind],body,false,'gong-tag-section');
}
function placeField(kind,existing){
 const data=selected[kind],text=existing||data?.place_name||'';
 return '<div class="gong-location-block"><label>'+labels[kind]+'</label><div class="gong-combo">'+
 '<input class="inp gong-location-input" name="'+(kind==='birth'?'birthPlace':kind==='residence'?'residentCity':'city')+'" data-location-kind="'+kind+'" autocomplete="off" value="'+escape(text)+'" placeholder="搜索省、市、区县；也支持手动输入">'+
 '<div class="gong-location-results gong-combo-results" data-location-results="'+kind+'" hidden></div></div>'+
 '<p class="hint gong-geo-status" data-geo-status="'+kind+'">'+(data&&Number.isFinite(data.latitude)&&Number.isFinite(data.longitude)?
  '已记录 '+(data.source==='device'?'设备实测':'行政区近似参考')+'坐标：'+data.latitude.toFixed(4)+', '+data.longitude.toFixed(4):
  '')+'</p></div>';
}
function bioControls(){
 const original=String(st.self.bio||'');
 return fold('个人简介','<p class="hint">简介中已有的内容会保留；分享简介时会包含整段内容。</p>'+
 '<div class="gong-bio-actions"><button type="button" class="gong-topic" data-action="profile-bio-section" data-topic="关于我">＋ 关于我</button></div>'+
 '<textarea class="inp gong-bio-editor" name="bio" rows="4" maxlength="4000" placeholder="介绍你的经历、专业、兴趣…">'+escape(original)+'</textarea>'+
 '<div class="gong-bio-preview" id="gongBioPreview"></div>');
}
const goalSections=[['personalgoals','理想追求'],['shorttermgoals','近期目标'],['needs','正在寻找'],['offers','能够提供']];
function goalText(data){
 const initial=String(data.goalnotes||'').trim();
 return [initial,...goalSections.filter(([key])=>data[key]).map(([key,label])=>'【'+label+'】\n'+String(Array.isArray(data[key])?data[key].join('、'):data[key]))].filter(Boolean).join('\n\n');
}
function goalControls(){return fold('目标与合作','<p class="hint">点击主题添加内容；每一项可在名片中单独选择分享。</p><div class="gong-bio-actions">'+
 goalSections.map(([,label])=>'<button type="button" class="gong-topic" data-action="profile-goal-section" data-topic="'+escape(label)+'">＋ '+escape(label)+'</button>').join('')+
 '</div><textarea class="inp gong-bio-editor" name="goaltext" rows="6" maxlength="8000" placeholder="点击上方主题，填写自己的目标与合作内容…">'+escape(goalText(st.self))+'</textarea><div class="gong-bio-preview" id="gongGoalPreview"></div>');}
function parseGoals(text){
 const parts=String(text||'').split(/【(理想追求|近期目标|正在寻找|能够提供)】/);
 const out={personalgoals:'',shorttermgoals:'',needs:'',offers:'',goalnotes:parts[0].trim()};
 const mapping=Object.fromEntries(goalSections.map(([key,label])=>[label,key]));
 for(let i=1;i<parts.length-1;i+=2){const key=mapping[parts[i]],value=parts[i+1].trim();if(value)out[key]+=(out[key]?'\n\n':'')+value;}
 return out;
}
function optionField(name,label,options,value){value=String(value||'');const extra=value&&!options.includes(value)?[value]:[];return '<label class="formfield">'+escape(label)+'<select class="inp" name="'+escape(name)+'"><option value="">未填写</option>'+[...options,...extra].map(x=>'<option value="'+escape(x)+'" '+(x===value?'selected':'')+'>'+escape(x)+'</option>').join('')+'</select></label>';}
const emailDomains=['qq.com','163.com','126.com','gmail.com','outlook.com','hotmail.com','icloud.com','yahoo.com','foxmail.com','sina.com'];
function emailField(value){
 value=String(value||'');const suffix=value.includes('@')?value.slice(value.lastIndexOf('@')+1).toLowerCase():'';
 return '<label class="formfield">邮箱<input class="inp" type="text" inputmode="email" autocomplete="email" name="email" value="'+escape(value)+'" placeholder="可直接输入完整邮箱"></label>'+
 '<label class="formfield">邮箱后缀（可选）<select class="inp" data-email-domain><option value="">手动输入 / 选择后缀</option>'+emailDomains.map(x=>'<option value="'+escape(x)+'" '+(x===suffix?'selected':'')+'>@'+escape(x)+'</option>').join('')+'</select></label>';
}
function applyEmailSuffix(input,suffix){
 if(!input||!suffix||!emailDomains.includes(suffix))return;
 const value=String(input.value||'').trim(),at=value.lastIndexOf('@'),local=at>=0?value.slice(0,at):value;
 input.value=local+'@'+suffix;input.focus();if(input.setSelectionRange)input.setSelectionRange(local.length,local.length);
}
const experienceTemplates={
 career:{'任职经历':'【任职经历】\n时间：\n公司 / 组织：\n职位：\n主要工作：\n成果或收获：\n',
         '项目 / 自由职业':'【项目 / 自由职业】\n时间：\n项目或业务：\n我的角色：\n完成的工作：\n成果或收获：\n'},
 education:{'学校经历':'【学校经历】\n时间：\n学校：\n专业：\n学历 / 学位：\n收获或活动：\n',
            '培训 / 进修':'【培训 / 进修】\n时间：\n课程或机构：\n学习内容：\n证书或收获：\n'}
};
function experienceEditor(kind,value){
 const isCareer=kind==='career',title=isCareer?'工作经历':'教育经历',preview='gongExperiencePreview-'+kind;
 const sample=isCareer?'【任职经历】&#10;时间：&#10;公司 / 组织：&#10;职位：&#10;主要工作：&#10;成果或收获：':'【学校经历】&#10;时间：&#10;学校：&#10;专业：&#10;学历 / 学位：&#10;收获或活动：';
 const buttons=Object.keys(experienceTemplates[kind]).map(name=>'<button type="button" class="gong-topic" data-action="profile-experience-template" data-experience="'+escape(kind)+'" data-template="'+escape(name)+'">＋ '+escape(name)+'</button>').join('');
 return fold(title,'<p class="hint">点击模板后填写；可以继续编辑，已有内容会保留。</p><div class="gong-bio-actions">'+buttons+'</div>'+
 '<textarea class="inp gong-bio-editor" name="'+kind+'" rows="5" maxlength="'+(isCareer?'2500':'900')+'" placeholder="'+sample+'">'+escape(value||'')+'</textarea>'+
 '<div class="gong-bio-preview" id="'+preview+'"></div>');
}
function updateExperiencePreview(kind){
 const area=document.querySelector('#selfForm [name="'+kind+'"]'),preview=document.querySelector('#gongExperiencePreview-'+kind);if(!area||!preview)return;
 preview.innerHTML=String(area.value||'').split(/(【[^【】\n]{1,30}】)/g).map(part=>/^【[^【】\n]+】$/.test(part)?'<mark class="gong-bio-key">'+escape(part)+'</mark>':'<span>'+escape(part).replace(/\n/g,'<br>')+'</span>').join('')||'<span class="hint">填写后在这里预览主题</span>';
}
function insertExperienceTemplate(kind,name){
 const area=document.querySelector('#selfForm [name="'+kind+'"]'),template=experienceTemplates[kind]?.[name];if(!area||!template)return;
 const pos=typeof area.selectionEnd==='number'?area.selectionEnd:area.value.length;
 const prefix=pos>0&&area.value[pos-1]!=='\n'?'\n\n':'',suffix=pos<area.value.length&&area.value[pos]!=='\n'?'\n\n':'';
 const content=prefix+template+suffix,limit=area.maxLength>0?area.maxLength:Infinity;
 if(area.value.length+content.length>limit){toast('内容较长，请精简后再插入模板');return;}
 area.setRangeText(content,pos,pos,'end');area.focus();updateExperiencePreview(kind);
}
function render(){
 dict();
 const data=st.self;
 selected={
  birth:structuredClone(data.locations?.birth||null),
  residence:structuredClone(data.locations?.residence||null),
  current:structuredClone(data.locations?.current||null)
 };
 const general=[['name','姓名'],['nickname','称呼 / 昵称']];
 const basics='<div class="gong-compact-grid">'+general.map(([k,label])=>'<label class="formfield">'+label+'<input class="inp" name="'+k+'" value="'+escape(data[k]||'')+'" autocomplete="off"></label>').join('')+emailField(data.email)+'</div>'+
 '<label class="formfield">头像（可选）<input class="inp" type="file" name="selfPhoto" accept="image/*"></label>'+
 '<button type="button" class="lightbtn" data-action="profile-camera-open">拍照</button><div id="profileCamera" hidden><video id="profileCameraVideo" autoplay playsinline muted></video><button type="button" class="lightbtn" data-action="profile-camera-shot">拍照并预览</button><button type="button" class="lightbtn" data-action="profile-camera-close">关闭相机</button><img id="profileCameraPreview" alt="头像预览" hidden></div>';
 const life='<p class="hint">这些内容只有在具体名片中主动勾选才会分享。没有的信息可以留空。</p><div class="gong-compact-grid">'+
 optionField('relationshipstatus','情感 / 婚姻状态',['单身','恋爱中','已婚','其他'],data.relationshipstatus)+
 optionField('childrenstatus','子女情况',['有子女','无子女','其他'],data.childrenstatus)+'</div>'+tags('interests',multiValues('interests'));
 const contactPreference=optionField('contactpreference','沟通偏好',['微信','电话','邮件','当面交流','其他'],data.contactpreference);
 const work=tags('industry',multiValues('industry'))+tags('role',multiValues('role'))+tags('company',multiValues('company'))+
 '<label class="formfield">职业说明（可选）<textarea class="inp" name="roleDescription" rows="2" maxlength="600">'+escape(data.roleDescription||'')+'</textarea></label>'+
 '<label class="formfield">公司 / 组织介绍（可选）<textarea class="inp" name="companyDescription" rows="2" maxlength="600">'+escape(data.companyDescription||'')+'</textarea></label>'+tags('skills',multiValues('skills'));
 const placesContent=placeField('birth',data.birthPlace)+placeField('residence',data.residentCity)+placeField('current',data.city)+
 '<p class="hint">地区坐标为近似参考。国外城市名称改编自 GeoNames（geonames.org），CC BY 4.0（creativecommons.org/licenses/by/4.0/）；离线数据可能缺少中文名称或坐标。</p>';
 const birthday='<div class="gong-birth-inputs"><input class="inp" type="date" name="birthday" aria-label="出生日期" value="'+escape(data.birthday||'')+'">'+
 '<input class="inp" type="time" name="birthTime" aria-label="出生时分（选填）" value="'+escape(data.birthTime||'')+'"></div><p class="hint">出生时分可选填，归在出生日期栏目内。</p>';
 const experiences=bioControls()+experienceEditor('career',data.career)+experienceEditor('education',data.education);
 const basicAll=basics+fold('联系方式',contactPreference+fold('手机号',gongContactRows('phone',data.phones||[]))+fold('微信号',gongContactRows('wechat',data.wechats||[])))+fold('出生日期',birthday)+fold('地点资料',placesContent);
 let form='<form id="selfForm" class="gong-structured-form">'+
 '<div class="gong-editor-actions"><button type="button" class="lightbtn" data-action="resume-open">导入我的履历 / AI 整理</button></div>'+
 '<p class="hint">点击栏目展开或折叠；只有名片勾选的字段才可被分享。</p>'+
 fold('基本信息',basicAll,true)+fold('职业与技能',work)+fold('生活与兴趣',life)+
 fold('个人简介与经历',experiences)+goalControls()+
 '<div class="foot-actions"><button type="button" class="lightbtn" data-action="close-modal">取消</button><button class="primary" type="submit">保存个人资料</button></div></form>';
 modal('编辑我的完整资料',form);
 updateBioPreview();updateGoalPreview();updateExperiencePreview('career');updateExperiencePreview('education');
 loadPlaces();
 window.GongProfile?.updateCity?.(true);
}
function updateTags(kind,values){
 const box=document.querySelector('[data-chips="'+kind+'"]');
 const input=document.querySelector('[name="'+kind+'"]');
 if(!box||!input)return;
 const unique=[...new Set(values.map(normalized).filter(Boolean))].slice(0,32);
 box.innerHTML=unique.map(x=>'<span class="gong-tag">'+escape(x)+'<button type="button" data-action="profile-remove-tag" data-kind="'+kind+'" data-value="'+escape(x)+'" aria-label="移除 '+escape(x)+'">×</button></span>').join('');
 input.value=unique.join('、');
 document.querySelectorAll('[data-tax-kind="'+kind+'"]').forEach(button=>{const selected=unique.includes(button.dataset.value);button.setAttribute('aria-pressed',String(selected));button.textContent=(selected?'✓ ':'＋ ')+button.dataset.value;});
}
function tagValues(kind){return (document.querySelector('[name="'+kind+'"]')?.value||'').split('、').filter(Boolean);}
function addTag(kind,value){
 value=normalized(value);
 if(!value)return;
 if(value.length>64){toast('项目名称过长');return;}
 suggestionRevision++;clearTimeout(suggestionTimer);
 updateTags(kind,[...tagValues(kind),value]);
 const input=document.querySelector('[data-tag-input="'+kind+'"]');
 if(input){input.value='';input.focus();}
 const host=document.querySelector('[data-tag-results="'+kind+'"]');if(host){host.hidden=true;host.innerHTML='';}
}
let suggestionTimer=null,suggestionRevision=0;
function showTagSuggestions(kind,query){
 const host=document.querySelector('[data-tag-results="'+kind+'"]');if(!host)return;
 const q=normalized(query).toLowerCase();suggestionRevision++;const revision=suggestionRevision;
 clearTimeout(suggestionTimer);
 const values=names(tagDict[kind]).filter(x=>(!q||x.toLowerCase().includes(q))&&!tagValues(kind).includes(x)).slice(0,q?10:24);
 function paint(items,loading,failed){
  if(!document.contains(host)||revision!==suggestionRevision)return;
  host.innerHTML=items.map(x=>{const item=typeof x==='string'?{name:x}:x;return '<button type="button" data-action="profile-tag-suggestion" data-kind="'+kind+'" data-value="'+escape(item.name)+'">'+escape(item.name)+(item.country?' <small> · '+escape(item.country)+'</small>':'')+'</button>';}).join('')+
   (loading?'<p class="hint">正在搜索免费企业数据…</p>':'')+
   (failed?'<p class="hint">在线企业库暂不可用，可选本机候选或手动输入。</p>':'')+
   (!items.length&&!loading?'<p class="hint">没有候选，可按回车添加输入内容</p>':'');
  host.hidden=false;
 }
 const online=kind==='company'&&q.length>=2&&window.GongGlobalSearch;
 paint(values,!!online);
 if(online)suggestionTimer=setTimeout(async()=>{
  try{
   const result=await window.GongGlobalSearch.lookup('company',query);
   const used=new Set(values.map(x=>x.toLowerCase()));
   const extra=(result.items||[]).filter(x=>x.name&&!used.has(x.name.toLowerCase())&&!tagValues(kind).includes(x.name));
   paint([...values,...extra].slice(0,15),false,false);
  }catch(e){paint(values,false,true);}
 },850);
}
let worldPlaces=null,worldPromise=null;
function loadWorldPlaces(){
 if(worldPlaces)return Promise.resolve(worldPlaces);
 if(worldPromise)return worldPromise;
 worldPromise=fetch('/static/world-places.json').then(r=>{if(!r.ok)throw Error('no world data');return r.json();}).then(rows=>{
  worldPlaces=rows.map(row=>({place_name:row[0],place_code:'world:'+row[1],alias:row[2]||'',latitude:null,longitude:null,source:'world',accuracy:'name-only'}));return worldPlaces;
 }).catch(()=>{worldPlaces=[];return [];});
 return worldPromise;
}
let cameraStream=null,cameraPhoto=null;
function stopCamera(){
 if(cameraStream){cameraStream.getTracks().forEach(t=>t.stop());cameraStream=null;}
 const video=document.querySelector('#profileCameraVideo');if(video)video.srcObject=null;
}
async function openCamera(){
 const panel=document.querySelector('#profileCamera'),video=document.querySelector('#profileCameraVideo');
 if(!panel||!video)return;
 if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){toast('此设备暂不支持拍照，请从相册选择');return;}
 try{stopCamera();cameraStream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user'},audio:false});
  if(!document.contains(video)){stopCamera();return;}video.srcObject=cameraStream;panel.hidden=false;await video.play();
 }catch(e){stopCamera();toast('无法打开相机，请检查相机权限或从相册选择');}
}
function takePhoto(){
 const video=document.querySelector('#profileCameraVideo'),preview=document.querySelector('#profileCameraPreview');
 if(!video||!video.videoWidth){toast('相机尚未准备好');return;}
 const scale=Math.min(1,640/Math.max(video.videoWidth,video.videoHeight));
 const canvas=document.createElement('canvas');canvas.width=Math.round(video.videoWidth*scale);canvas.height=Math.round(video.videoHeight*scale);
 canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);cameraPhoto=canvas.toDataURL('image/jpeg',0.8);
 if(preview){preview.src=cameraPhoto;preview.hidden=false;}stopCamera();toast('已拍照，保存资料后生效');
}
document.addEventListener('change',event=>{if(event.target?.matches('#selfForm [data-email-domain]')){applyEmailSuffix(document.querySelector('#selfForm [name="email"]'),event.target.value);return;}if(event.target?.matches('#selfForm [name="selfPhoto"]')&&event.target.files?.length){cameraPhoto=null;stopCamera();}},true);
document.addEventListener('click',event=>{
 if(event.target.closest('.gong-combo'))return;
 document.querySelectorAll('.gong-combo-results').forEach(x=>{x.hidden=true;});
},false);
new MutationObserver(()=>{if(!document.querySelector('#selfForm')){stopCamera();cameraPhoto=null;}}).observe(document.body,{childList:true,subtree:true});
function updateBioPreview(){
 const textarea=document.querySelector('#selfForm [name="bio"]'),preview=document.querySelector('#gongBioPreview');
 if(!textarea||!preview)return;
 let raw=textarea.value;
 const segments=raw.split(/(【(?:我能提供|我正在寻找|关于我)】)/g);
 preview.innerHTML=segments.map(part=>/^【/.test(part)?'<mark class="gong-bio-key">'+escape(part)+'</mark>':
 '<span>'+escape(part).replace(/\n/g,'<br>')+'</span>').join('')||'<span class="hint">这里会显示结构化简介预览</span>';
}
function updateGoalPreview(){const area=document.querySelector('#selfForm [name="goaltext"]'),preview=document.querySelector('#gongGoalPreview');if(!area||!preview)return;preview.innerHTML=area.value.split(/(【(?:理想追求|近期目标|正在寻找|能够提供)】)/g).map(part=>/^【/.test(part)?'<mark class="gong-bio-key">'+escape(part)+'</mark>':'<span>'+escape(part).replace(/\n/g,'<br>')+'</span>').join('')||'<span class="hint">这里显示高亮预览</span>';}
function parseBlocks(bio){
 const parts=bio.split(/【(我能提供|我正在寻找|关于我)】/);
 let offers='',needs='';
 for(let i=1;i<parts.length-1;i+=2){
  const value=(parts[i+1]||'').split(/\n\s*\n/)[0].trim().slice(0,500);
  if(parts[i]==='我能提供')offers=value;
  if(parts[i]==='我正在寻找')needs=value;
 }
 return {offers,needs};
}
function preserveDictionary(kind,value,description){
 const target=dict()[kind];
 if(!value)return;
 const found=target.find(x=>typeof x==='string'?x===value:x.name===value);
 if(found&&typeof found==='object'){if(description!==undefined)found.description=description;return;}
 if(!found&&target.length<300)target.push({name:value,description:description||'',createdAt:new Date().toISOString()});
}
function onSubmit(event){
 const form=event.target;if(form?.id!=='selfForm')return;
 // Keep a typed but not explicitly selected value when the form is saved.
 for(const kind of Object.keys(tagDict)){
  const pending=normalized(form.querySelector('[data-tag-input="'+kind+'"]')?.value);
  if(pending)updateTags(kind,[...tagValues(kind),...pending.split(['industry','role','company'].includes(kind)?/[、\n]+/:/[、,，;；\n]+/)]);
 }
 const formValue=key=>normalized(form.elements[key]?.value);
 st.self.birthTime=formValue('birthTime').slice(0,5);
 st.self.roleDescription=formValue('roleDescription').slice(0,600);
 st.self.companyDescription=formValue('companyDescription').slice(0,600);
 st.self.residentCity=formValue('residentCity');
 st.self.locations={birth:makeLocation('birth',formValue('birthPlace')),
  residence:makeLocation('residence',st.self.residentCity),
  current:makeLocation('current',formValue('city'))};
 if(form.elements.goaltext){const block=parseGoals(form.elements.goaltext.value);for(const key of ['personalgoals','shorttermgoals','needs','offers','goalnotes'])st.self[key]=block[key];}
 for(const kind of Object.keys(tagDict)){
  for(const item of tagValues(kind))preserveDictionary(tagDict[kind],item);
 }
 if(cameraPhoto)st.self.photo=cameraPhoto;
 stopCamera();
}
function makeLocation(kind,text){
 const entry=selected[kind];
 if(!text)return null;
 if(entry&&entry.place_name===text)return entry;
 return {place_name:text,place_code:null,latitude:null,longitude:null,source:'manual'};
}
async function loadPlaces(){
 if(places)return places;
 if(placeLoading)return placeLoading;
 placeLoading=fetch('/static/china-places.json').then(r=>{if(!r.ok)throw Error('地点数据读取失败');return r.json()})
 .then(json=>{
  if(!Array.isArray(json.provinces)||!Array.isArray(json.cities)||!Array.isArray(json.areas))throw Error('地点数据格式无效');
  const prov=new Map(json.provinces.map(p=>[p[0],p]));
  const cities=new Map(json.cities.map(c=>[c[0],c]));
  const entries=[];
  for(const c of json.cities){
   const parent=prov.get(c[1]);if(!parent)continue;
   const province=String(parent[1]),town=['市辖区','县'].includes(c[2])?'':String(c[2]);
   const text=[province,town].filter(Boolean).join(' ');
   if(Number.isFinite(c[3])&&Number.isFinite(c[4]))
    entries.push({place_name:text,place_code:c[0],longitude:c[3],latitude:c[4],source:'place',accuracy:'city-reference'});
  }
  for(const a of json.areas){
   const c=cities.get(a[1]),p=c&&prov.get(c[1]);if(!p)continue;
   const town=['市辖区','县'].includes(c[2])?'':String(c[2]);
   const text=[String(p[1]),town,String(a[2])].filter(Boolean).join(' ');
   entries.push({place_name:text,place_code:a[0],
    longitude:Number.isFinite(a[3])?a[3]:null,latitude:Number.isFinite(a[4])?a[4]:null,
    source:'place',accuracy:'district-reference'});
  }
  places=entries;return entries;
 }).catch(err=>{placeLoading=null;places=[];return [];});
 return placeLoading;
}
function searchPlace(kind,query){
 const host=document.querySelector('[data-location-results="'+kind+'"]');if(!host)return;
 const q=normalized(query).replace(/\s+/g,'');
 if(q.length<1){host.innerHTML='';host.hidden=true;return;}
 const matches=[...(places||[]),...(worldPlaces||[])].filter(p=>(p.place_name+' '+(p.alias||'')).toLowerCase().replace(/\s+/g,'').includes(q.toLowerCase())).slice(0,16);
 host.innerHTML=matches.map(item=>
 '<button type="button" data-action="profile-place-select" data-kind="'+kind+'" data-code="'+escape(item.place_code)+'">'+
 escape(item.place_name)+'<small>'+(Number.isFinite(item.longitude)?'参考坐标可用':'暂缺坐标')+'</small></button>').join('')+
 (!matches.length?'<p class="hint">没有匹配的地区，可自行填写名称（暂不附经纬度）</p>':'');
 host.hidden=false;
}
function choosePlace(kind,code){
 const place=[...(places||[]),...(worldPlaces||[])].find(p=>p.place_code===code);if(!place)return;
 selected[kind]=structuredClone(place);
 const input=document.querySelector('#selfForm [data-location-kind="'+kind+'"]');
 if(input){input.value=place.place_name;input.dataset.userEdited='';}
 const host=document.querySelector('[data-location-results="'+kind+'"]');if(host){host.innerHTML='';host.hidden=true;}
 status(kind,place);
}
function status(kind,place){
 const n=document.querySelector('[data-geo-status="'+kind+'"]');if(!n)return;
 n.textContent=place&&Number.isFinite(place.latitude)&&Number.isFinite(place.longitude)?
  '已选：'+(place.source==='device'?'设备定位':'行政区近似坐标')+'（纬 '+place.latitude.toFixed(4)+'，经 '+place.longitude.toFixed(4)+'）':
  '暂未获得可靠经纬度；保存的是地点名称';
}
function applyImported(fields){
 const form=document.querySelector('#selfForm');if(!form)return;
 for(const [key,value] of Object.entries(fields)){
  if(!value)continue;
 if(tagDict[key]){
   updateTags(key,String(value).split(['industry','role','company'].includes(key)?/[、\n]+/:/[、,，;；\n]+/).map(normalized).filter(Boolean));
  }else if(goalSections.some(([field])=>field===key)){
   const area=form.elements.goaltext;if(!area)continue;
   const parsed=parseGoals(area.value);parsed[key]=String(value);area.value=goalText(parsed);updateGoalPreview();
  }else if(form.elements[key]){
   form.elements[key].value=value;if(key==='career'||key==='education')updateExperiencePreview(key);
  }
 }
}
function chooseExternalPlace(kind,place){
 if(!['birth','residence','current'].includes(kind)||!place)return;
 const lat=Number(place.latitude),lon=Number(place.longitude);
 if(!Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180)return;
 const data={place_name:String(place.place_name||'').slice(0,260),place_code:String(place.place_code||''),
  latitude:lat,longitude:lon,source:'osm',accuracy:'map-reference',
  attribution:'© OpenStreetMap contributors',captured_at:new Date().toISOString()};
 selected[kind]=data;
 const input=document.querySelector('#selfForm [data-location-kind="'+kind+'"]');
 if(input){input.value=data.place_name;delete input.dataset.userEdited;}
 status(kind,data);
}
function receiveGeo(result){
 const input=document.querySelector('#selfForm [data-location-kind="current"]');
 if(!input)return;
 if(input.dataset.userEdited==='true')return;
 const place_name=String(result?.city||'').trim();
 if(!place_name)return;
 const latitude=Number(result.latitude),longitude=Number(result.longitude);
 const coords=Number.isFinite(latitude)&&Math.abs(latitude)<=90&&Number.isFinite(longitude)&&Math.abs(longitude)<=180;
 selected.current={place_name,source:coords?'device':'geocoded-name',
  latitude:coords?latitude:null,longitude:coords?longitude:null,
  accuracy_m:Number.isFinite(Number(result.accuracy_m))?Number(result.accuracy_m):null,
  captured_at:result.captured_at||new Date().toISOString()};
 input.value=place_name;status('current',selected.current);
}
document.addEventListener('click',event=>{
 const b=event.target.closest('[data-action]');if(!b)return;
 const action=b.dataset.action;
 if(!['profile-add-tag','profile-tag-suggestion','profile-remove-tag','profile-tax-toggle','profile-bio-section','profile-goal-section','profile-experience-template','profile-place-select','profile-camera-open','profile-camera-shot','profile-camera-close'].includes(action))return;
 event.preventDefault();event.stopImmediatePropagation();
 const kind=b.dataset.kind;
 if(action==='profile-tax-toggle'){const value=b.dataset.value||'',old=tagValues(kind);if(!old.includes(value)&&old.length>=32){toast('最多选择 32 项');return;}updateTags(kind,old.includes(value)?old.filter(x=>x!==value):[...old,value]);return;}
 if(action==='profile-experience-template'){insertExperienceTemplate(b.dataset.experience,b.dataset.template);return;}
 if(action==='profile-camera-open'){openCamera();return;}
 if(action==='profile-camera-shot'){takePhoto();return;}
 if(action==='profile-camera-close'){stopCamera();return;}
 if(action==='profile-add-tag')addTag(kind,document.querySelector('[data-tag-input="'+kind+'"]')?.value||'');
 else if(action==='profile-tag-suggestion')addTag(kind,b.dataset.value||'');
 else if(action==='profile-remove-tag')updateTags(kind,tagValues(kind).filter(v=>v!==b.dataset.value));
 else if(action==='profile-place-select')choosePlace(kind,b.dataset.code);
 else if(action==='profile-goal-section'){
  const area=document.querySelector('#selfForm [name="goaltext"]');if(!area)return;const marker='【'+b.dataset.topic+'】';let pos=area.value.indexOf(marker);if(pos<0){area.value+=(area.value.trim()?'\n\n':'')+marker+'\n';pos=area.value.length;}else pos+=marker.length;area.focus();area.selectionStart=area.selectionEnd=pos;updateGoalPreview();
 }
 else if(action==='profile-bio-section'){
  const area=document.querySelector('#selfForm [name="bio"]');if(!area)return;
  const tag='【'+b.dataset.topic+'】\n';
  if(area.value.includes('【'+b.dataset.topic+'】')){area.focus();area.selectionStart=area.value.indexOf('【'+b.dataset.topic+'】');return;}
  const pos=area.selectionStart??area.value.length;
  area.setRangeText((pos>0&&area.value[pos-1]!=='\n'?'\n\n':'')+tag,pos,pos,'end');
  area.focus();updateBioPreview();
 }
},true);
document.addEventListener('focusin',event=>{const el=event.target;if(el?.matches('#selfForm [data-tag-input]'))showTagSuggestions(el.dataset.tagInput,el.value);},true);
document.addEventListener('input',event=>{
 const el=event.target;
 if(el?.matches('#selfForm [name="bio"]'))updateBioPreview();
 if(el?.matches('#selfForm [name="goaltext"]'))updateGoalPreview();
 if(el?.matches('#selfForm [name="career"]'))updateExperiencePreview('career');
 if(el?.matches('#selfForm [name="education"]'))updateExperiencePreview('education');
 if(el?.matches('#selfForm [data-tag-input]'))showTagSuggestions(el.dataset.tagInput,el.value);
 if(el?.matches('#selfForm [data-location-kind]')){
  const kind=el.dataset.locationKind;
  selected[kind]=null;el.dataset.userEdited='true';status(kind,null);
  Promise.all([loadPlaces(),loadWorldPlaces()]).then(()=>{if(document.contains(el))searchPlace(kind,el.value);});
 }
 if(el?.matches('#selfForm [name="role"]')){
  const desc=dict().roles.find(x=>typeof x==='object'&&x.name===el.value)?.description;
  const box=document.querySelector('#selfForm [name="roleDescription"]');if(desc&&box)box.value=desc;
 }
 if(el?.matches('#selfForm [name="company"]')){
  const desc=dict().companies.find(x=>typeof x==='object'&&x.name===el.value)?.description;
  const box=document.querySelector('#selfForm [name="companyDescription"]');if(desc&&box)box.value=desc;
 }
},true);
document.addEventListener('keydown',event=>{
 if(event.key==='Enter'&&event.target?.matches('[data-tag-input]')){
  event.preventDefault();addTag(event.target.dataset.tagInput,event.target.value);
 }
},true);
document.addEventListener('submit',onSubmit,true);
window.GongStructuredProfile={render,receiveGeo,dict,applyImported,chooseExternalPlace};
})();
