/* The phone provides a location; Python computes the saved calendar convention. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  let location=null,pending=null,generation=0,previewToken=0,timer,api,changed;
  const note=text=>{$('location-status').textContent=text;};
  function read(validate=true){
    if(validate&&pending)throw new Error('正在获取起卦地点，请稍等或手动填写经度。');
    const basis=$('time-basis').value,raw=$('cast-longitude').value.trim(),result={};
    if(basis!=='beijing_standard')result.time_basis=basis;
    if(raw){
      const longitude=Number(raw);
      if(!Number.isFinite(longitude)||longitude < -180||longitude > 180)throw new Error('经度应在 −180 至 180 之间，东经为正，西经为负。');
      result.cast_location=location&&location.longitude===longitude?{...location}:{longitude,source:'manual'};
    }
    if(validate&&basis==='true_solar'&&!result.cast_location)throw new Error('请选择定位或手动填写起卦地点的经度。');
    return result;
  }
  function update(){
    $('solar-location-fields').hidden=$('time-basis').value!=='true_solar';
    clearTimeout(timer);const token=++previewToken;
    $('solar-time-preview').textContent='';
    timer=setTimeout(async()=>{
      if(!api||!$('cast-time').value)return;
      try{
        const details=read(false);
        if(details.time_basis==='true_solar'&&!details.cast_location)return;
        const date=new Date($('cast-time').value);if(Number.isNaN(date.valueOf()))return;
        const value=await api('/api/calendar',{method:'POST',data:{...details,actual_cast_time:date.toISOString()}});
        if(token!==previewToken)return;
        $('solar-time-preview').textContent=value.status==='computed'
          ?`${value.time_basis==='true_solar'?'当地真太阳时':'北京时间'}：${value.cast_time.slice(0,19).replace('T',' ')}${value.solar_time?`（较北京时间 ${value.solar_time.total_correction_minutes>=0?'+':''}${value.solar_time.total_correction_minutes.toFixed(2)} 分钟）`:''}`
          :value.message;
      }catch(error){if(token===previewToken)$('solar-time-preview').textContent=error.message;}
    },250);
  }
  async function locate(){
    if(pending)return;
    const epoch=generation,id='location_'+Date.now();
    $('location-button').disabled=true;note('正在获取起卦地点…');
    try{
      const value=await new Promise((resolve,reject)=>{
        const timeout=setTimeout(()=>{if(pending?.id===id){pending=null;reject(new Error('定位未完成，可以重试或手动填写经度。'));}},35000);
        pending={id,resolve:value=>{clearTimeout(timeout);resolve(value);},reject:error=>{clearTimeout(timeout);reject(error);}};
        if(window.LiuyaoAndroid?.requestLocation)window.LiuyaoAndroid.requestLocation(id);
        else if(navigator.geolocation)navigator.geolocation.getCurrentPosition(position=>receive(id,{
          longitude:position.coords.longitude,latitude:position.coords.latitude,accuracy_m:position.coords.accuracy,
          captured_at:new Date(position.timestamp).toISOString(),source:'device'}),()=>receive(id,{error:'未能获取定位，请检查定位权限，或手动填写经度。'}),{enableHighAccuracy:true,timeout:20000,maximumAge:0});
        else receive(id,{error:'当前环境无法定位，请手动填写起卦地点的经度。'});
      });
      if(epoch!==generation)return;
      location=value;$('cast-longitude').value=String(value.longitude);$('time-basis').value='true_solar';
      note(`已定位：${value.longitude.toFixed(5)}°${value.latitude!==undefined?`，${value.latitude.toFixed(5)}°`:''}${value.accuracy_m!==undefined?`；精度约 ${Math.round(value.accuracy_m)} 米`:''}。补录旧卦请填写当时地点。`);
      update();changed();
    }catch(error){if(epoch===generation)note(error.message);}
    finally{if(epoch===generation){pending=null;$('location-button').disabled=false;}}
  }
  function receive(id,value){
    if(pending?.id!==id)return;
    const request=pending;pending=null;
    if(value?.error)request.reject(new Error(value.error));else request.resolve(value);
  }
  function fill(input){
    generation++;if(pending){pending.reject(new Error('已切换案例。'));pending=null;}
    location=input?.cast_location?{...input.cast_location}:null;
    $('time-basis').value=input?.time_basis||'beijing_standard';
    $('cast-longitude').value=location?String(location.longitude):'';
    $('location-button').disabled=false;
    note(location?'已保存起卦地点；可手动更正经度。':'定位仅在起卦时获取；补录旧卦请填写当时地点。');update();
  }
  window.LiuyaoLocation={receive};
  window.LiuyaoSolarTime={read,fill,update,locate,bind(options){
    api=options.api;changed=options.changed;
    $('time-basis').addEventListener('change',()=>{update();changed();if($('time-basis').value==='true_solar'&&!$('cast-longitude').value)locate();});
    $('location-button').addEventListener('click',locate);
    $('cast-longitude').addEventListener('input',()=>{generation++;if(pending){pending.reject(new Error('已改用手动经度。'));pending=null;}location=null;$('location-button').disabled=false;note('使用手动填写的起卦地点。');update();changed();});
    $('cast-time').addEventListener('change',update);fill(null);
  }};
})();
