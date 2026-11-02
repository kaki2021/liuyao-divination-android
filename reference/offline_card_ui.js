/* 工：离线名片交换。二维码内容仅在当前设备生成和解析。 */
(function(){
"use strict";
let stream=null, frame=0, incoming=null, candidateId=null;
function stop(){if(frame)cancelAnimationFrame(frame);frame=0;if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}}
function safe(v){return String(v||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}
function encode(v){return String(v||"").replace(/\\/g,"\\\\").replace(/\r?\n/g,"\\n").replace(/;/g,"\\;").replace(/,/g,"\\,");}
function decode(v){return String(v||"").replace(/\\n/gi,"\n").replace(/\\,/g,",").replace(/\\;/g,";").replace(/\\\\/g,"\\");}
const keys=["name","nickname","city","industry","company","role","skills","interests","needs","offers","wechat","email","bio","relationshipstatus","childrenstatus","personalgoals","shorttermgoals","contactpreference"];
const captions={name:"姓名",nickname:"称呼",city:"城市",industry:"行业",company:"公司",role:"职业",skills:"技能",interests:"兴趣",needs:"需求",offers:"提供",wechat:"微信",email:"邮箱",bio:"简介",phone:"电话",relationshipstatus:"情感 / 婚姻状态",childrenstatus:"子女情况",personalgoals:"理想追求",shorttermgoals:"近期目标",contactpreference:"沟通偏好"};
function selected(){
 const c=currentCardData(),fields={};
 for(const key of keys){if(c.fields[key]){const value=String(c.fields[key]);if(value.length>240)throw Error("「"+(captions[key]||key)+"」内容过长，请缩短后再生成二维码");fields[key]=value;}}
 if(!fields.name&&!fields.nickname)throw Error("请先填写姓名或昵称，并在这张名片中选择分享");
 return {fields,id:st.cards[cardIx].id,title:st.cards[cardIx].title,
 issuerId:st.self?.gongIssuerId||"",updatedAt:st.cards[cardIx].updatedAt||""};
}
function toVcard(item){
 const f=item.fields;
 let rows=["BEGIN:VCARD","VERSION:3.0","FN:"+encode(f.name||f.nickname),"X-GONG-CARD:1","X-GONG-CARD-ID:"+encode(item.id)];
 if(item.issuerId)rows.push("X-GONG-ISSUER-ID:"+encode(item.issuerId));
 if(item.updatedAt){
  const stamp=new Date(item.updatedAt);
  if(!Number.isNaN(stamp.getTime())){
   const iso=stamp.toISOString();
   rows.push("REV:"+iso.replace(/[-:]/g,"").replace(/\.\d{3}/,""));
   rows.push("X-GONG-UPDATED-AT:"+iso);
  }
 }
 for(const pair of [["company","ORG"],["role","TITLE"],["email","EMAIL"],["wechat","X-GONG-WECHAT"]]){
  if(f[pair[0]])rows.push(pair[1]+":"+encode(f[pair[0]]));
 }
 if(f.city)rows.push("ADR:;;;"+encode(f.city)+";;;");
 for(const k of ["nickname","industry","skills","interests","needs","offers","bio","relationshipstatus","childrenstatus","personalgoals","shorttermgoals","contactpreference"]){
  if(f[k])rows.push("X-GONG-"+k.toUpperCase()+":"+encode(f[k]));
 }
 rows.push("END:VCARD");return rows.join("\r\n")+"\r\n";
}
function parseVcard(txt){
 if(typeof txt!=="string"||txt.length>6000)throw Error("二维码内容不符合名片格式");
 const str=txt.replace(/\r?\n[ \t]/g,"").trim();
 if(!/^BEGIN:VCARD\r?\n/i.test(str)||!/\r?\nEND:VCARD$/i.test(str))throw Error("这不是可识别的 vCard 名片");
 const result={fields:{},id:"",issuerId:"",updatedAt:""};
 let n=0;
 for(const line of str.split(/\r?\n/)){
  const colon=line.indexOf(":");if(colon<0)continue;
  const k=line.slice(0,colon).toUpperCase().split(";")[0],v=decode(line.slice(colon+1)).trim().slice(0,260);
  if(++n>55)throw Error("二维码字段过多");
  if(k==="FN")result.fields.name=v;
  else if(k==="ORG")result.fields.company=v;
  else if(k==="TITLE")result.fields.role=v;
  else if(k==="EMAIL")result.fields.email=v;
  else if(k==="TEL")result.fields.phone=v;
  else if(k==="ADR")result.fields.city=v.split(";").find(x=>x.trim())||v.replace(/;/g," ").trim();
  else if(k==="X-GONG-CARD-ID")result.id=v;
  else if(k==="X-GONG-ISSUER-ID")result.issuerId=v;
  else if(k==="X-GONG-UPDATED-AT")result.updatedAt=v;
  else if(k==="REV"&&!result.updatedAt&&/^\d{8}T\d{6}Z$/.test(v))
   result.updatedAt=v.replace(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/,"$1-$2-$3T$4:$5:$6Z");
  else if(k==="X-GONG-WECHAT")result.fields.wechat=v;
  else if(k.startsWith("X-GONG-")){
   const key=k.slice(7).toLowerCase();
   if(keys.includes(key))result.fields[key]=v;
  }
 }
 if(!result.fields.name&&!result.fields.nickname)throw Error("名片没有姓名");
 return result;
}
function showQR(){
 stop();
 let data,card;
 try{data=selected();card=toVcard(data);
  if(new TextEncoder().encode(card).length>1350)throw Error("名片资料过长，请减少勾选字段");
 }catch(e){toast(e.message);return;}
 modal("我的名片二维码",'<p class="hint">只包含当前名片选择分享的资料，不包含私密备注、照片和出生信息。</p><div id="gongQR" style="display:flex;justify-content:center;margin:18px 0"><canvas id="gongQRCanvas" width="280" height="280"></canvas></div><p class="hint">「工」可扫描并添加，微信等扫码软件可能显示 vCard 联系人资料或原文，展示方式由扫码软件决定。</p><div class="foot-actions"><button class="primary" data-action="close-modal">完成</button></div>');
 if(!window.GongQR?.toCanvas){toast("二维码组件未加载");return;}
 window.GongQR.toCanvas(document.querySelector("#gongQRCanvas"),card,{width:280,margin:2,errorCorrectionLevel:"M"}).catch(e=>toast(e.message));
}
function scanModal(){
 stop();
 modal("扫一扫",'<div class="gong-scanner-stage"><video id="gongVideo" autoplay muted playsinline></video><div class="gong-scanner-target"><i></i><i></i><i></i><i></i><div class="gong-scanner-line"></div></div><span class="gong-scanner-label">将名片二维码放入框内</span></div><p class="gong-scanner-status" id="gongStatus" aria-live="polite">正在启动摄像头…</p><div class="gong-scanner-controls"><label class="lightbtn gong-scanner-gallery">从相册识别<input id="gongImage" type="file" accept="image/*" hidden></label><button class="lightbtn" data-action="gong-start">重试相机</button><button class="lightbtn" data-action="close-modal">返回</button></div><p class="gong-scanner-privacy">本地识别，无需服务器；识别后核对资料再保存。</p>');
 document.querySelector("#overlay .modal")?.classList.add("gong-scanner-modal");
 // Called directly from the user tap: do not require a second "启动相机" click.
 useCamera();
}
function scanPixels(img){
 if(!window.GongQR?.decode)throw Error("二维码识别组件未加载");
 const w=img.videoWidth||img.naturalWidth||img.width,h=img.videoHeight||img.naturalHeight||img.height;
 if(!w||!h)return null;
 const canvas=document.createElement("canvas"),ratio=Math.min(1,850/Math.max(w,h));
 canvas.width=Math.round(w*ratio);canvas.height=Math.round(h*ratio);
 const ctx=canvas.getContext("2d",{willReadFrequently:true});
 ctx.drawImage(img,0,0,canvas.width,canvas.height);
 const pixels=ctx.getImageData(0,0,canvas.width,canvas.height);
 return window.GongQR.decode(pixels.data,pixels.width,pixels.height,{inversionAttempts:"attemptBoth"})?.data||null;
}
function preview(card){
 stop();incoming=card;
 const f=card.fields;
 const target=st.people.find(p=>
 (card.issuerId&&card.id&&p.sourceCardRefs?.some(r=>r.issuerId===card.issuerId&&r.cardId===card.id))||
 (!card.issuerId&&card.id&&p.sourceCardIds?.includes(card.id))||
 (f.wechat&&p.wechat===f.wechat)||(f.email&&p.email===f.email));
 candidateId=target?.id||null;
 const known=target?.sourceCardRefs?.find(r=>card.issuerId&&r.issuerId===card.issuerId&&r.cardId===card.id);
 const incomingTime=Date.parse(card.updatedAt||"");
 const savedTime=Date.parse(known?.updatedAt||"");
 const fresh=known&&Number.isFinite(incomingTime)&&(!Number.isFinite(savedTime)||incomingTime>savedTime);
 const old=known&&Number.isFinite(incomingTime)&&Number.isFinite(savedTime)&&incomingTime<=savedTime;
 let html='<p class="hint">'+(old?"这张名片已保存了相同或更新的版本，不需要再次覆盖。":fresh?"检测到同一张名片有更新，确认后只更新来自对方的共享字段。":target?"可能是已有联系人；仅补充缺失字段，不覆盖私人备注。":"核对后保存到本机人物档案。")+'</p>';
 if(card.updatedAt)html+='<p class="hint">对方名片最近更新：'+safe(card.updatedAt.replace("T"," ").replace("Z"," UTC"))+'</p>';
 html+='<div class="fieldrows">';
 for(const [k,v] of Object.entries(f))html+='<span class="sub">'+safe(captions[k]||k)+'</span><span>'+safe(v)+'</span>';
 html+='</div><div class="formfield"><label>人物分类（可选）</label><select id="gongGroup" class="inp"><option value="">暂不分类</option>';
 for(const g of st.categories)html+='<option value="'+safe(g)+'">'+safe(g)+'</option>';
 html+='</select></div><div class="foot-actions"><button class="lightbtn" data-action="gong-scan">重新扫描</button><button class="primary" data-action="gong-import">'+(target?"补充已有档案":"确认添加人物")+'</button></div>';
 modal("确认导入名片",html);
}
function importPerson(){
 if(!incoming)return;
 const f=incoming.fields,group=document.querySelector("#gongGroup")?.value||"";
 let personObj=candidateId?st.people.find(p=>p.id===candidateId):null;
 if(!personObj){personObj={id:ID("p"),color:st.people.length,groups:[]};st.people.unshift(personObj);}
 const ref=personObj.sourceCardRefs?.find(x=>incoming.issuerId&&x.issuerId===incoming.issuerId&&x.cardId===incoming.id);
 const newStamp=Date.parse(incoming.updatedAt||""),oldStamp=Date.parse(ref?.updatedAt||"");
 if(ref&&Number.isFinite(newStamp)&&Number.isFinite(oldStamp)&&newStamp<=oldStamp){
  toast("本地已保存这张名片的相同或更新内容");closeModal();return;
 }
 const isRefresh=!!ref&&Number.isFinite(newStamp)&&(!Number.isFinite(oldStamp)||newStamp>oldStamp);
 // Update only fields previously supplied by this specific issuer/card.
 // If the recipient edited one of those fields themselves, keep their edit.
 const sharedKeys=["name","nickname","city","industry","company","role","wechat","email","phone","skills","interests","needs","offers","relationshipstatus","childrenstatus","personalgoals","shorttermgoals","contactpreference"];
 for(const key of sharedKeys){
  const oldValue=ref?.fields?.[key];
  const localValue=Array.isArray(personObj[key])?personObj[key].join("、"):String(personObj[key]||"");
  const owned=isRefresh&&oldValue!==undefined&&localValue===String(oldValue);
  if(owned&&!(key in f)){delete personObj[key];continue;}
  if(!(key in f))continue;
  const next=["skills","interests","needs"].includes(key)?
    String(f[key]).split(/[、,，;；]/).map(t=>t.trim()).filter(Boolean):f[key];
  if(owned||!personObj[key]||(Array.isArray(personObj[key])&&!personObj[key].length))personObj[key]=next;
 }
 // Public card description is not the recipient's private relationship note.
 if(f.bio)personObj.publicBio=f.bio;
 if(incoming.issuerId&&incoming.id){
  personObj.sourceCardRefs=Array.isArray(personObj.sourceCardRefs)?personObj.sourceCardRefs:[];
  const next={issuerId:incoming.issuerId,cardId:incoming.id,updatedAt:incoming.updatedAt||"",
              fields:Object.fromEntries(sharedKeys.filter(k=>f[k]!==undefined).map(k=>[k,String(f[k])]))};
  if(ref)Object.assign(ref,next);else personObj.sourceCardRefs.push(next);
  if(incoming.updatedAt)personObj.cardLastUpdated=incoming.updatedAt;
 }
 if(group){const old=groupsOf(personObj);if(!old.includes(group))setPersonGroups(personObj,[...old,group]);}
 if(incoming.id){
  personObj.sourceCardIds=Array.isArray(personObj.sourceCardIds)?personObj.sourceCardIds:[];
  if(!personObj.sourceCardIds.includes(incoming.id))personObj.sourceCardIds.push(incoming.id);
 }
 personObj.importSource="offline-vcard";
 persist();closeModal();navigate("people");toast("已保存到人物档案");incoming=null;candidateId=null;
}
async function useCamera(){
 stop();
 const label=document.querySelector("#gongStatus");
 if(!navigator.mediaDevices?.getUserMedia){if(label)label.textContent="当前 WebView 不支持直接扫码，请从相册选择二维码图片";return;}
 try{
  stream=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:{ideal:"environment"}}});
  const vid=document.querySelector("#gongVideo");if(!vid){stop();return;}
  vid.srcObject=stream;await vid.play();if(label)label.textContent="对准二维码，识别后将显示资料预览";
  let ticks=0;
  const tick=()=>{if(!stream||!document.querySelector("#gongVideo")){stop();return;}
   if((++ticks)%4===0)try{const data=scanPixels(vid);if(data){preview(parseVcard(data));return;}}
   catch(e){stop();if(label)label.textContent=e.message;return;}
   frame=requestAnimationFrame(tick);
  };frame=requestAnimationFrame(tick);
 }catch(e){stop();if(label)label.textContent="无法使用相机："+e.message+"。可以从相册选择图片。";}
}
async function useImage(file){
 if(!file)return;
 if(!file.type.startsWith("image/")||file.size>10*1024*1024){toast("请选择不超过10MB的图片");return;}
 try{
  const img=new Image(),url=URL.createObjectURL(file);
  try{await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=()=>reject(Error("读取图片失败"));img.src=url;});}
  finally{URL.revokeObjectURL(url);}
  const raw=scanPixels(img);if(!raw)throw Error("没有找到二维码，请选清晰截图");
  preview(parseVcard(raw));
 }catch(e){toast(e.message);}
}
document.addEventListener("click",e=>{
 const target=e.target.closest("[data-action]");if(!target)return;
 const action=target.dataset.action;
 if(["gong-scan","gong-show","gong-start","gong-import"].includes(action)){
  e.preventDefault();e.stopImmediatePropagation();
  if(action==="gong-scan")scanModal();
  else if(action==="gong-show")showQR();
  else if(action==="gong-start")useCamera();
  else if(action==="gong-import")importPerson();
 }
 if(action==="close-modal")stop();
},true);
document.addEventListener("change",e=>{if(e.target?.id==="gongImage"){e.stopImmediatePropagation();useImage(e.target.files?.[0]);}},true);
document.addEventListener("keydown",e=>{if(e.key==="Escape")stop();});
new MutationObserver(()=>{if(stream&&!document.querySelector("#gongVideo"))stop();}).observe(document.querySelector("#overlay"),{subtree:true,childList:true});
window.GongOfflineCard={toVcard,parseVcard,selected,stop};
})();