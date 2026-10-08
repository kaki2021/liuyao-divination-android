'use strict';
// State transitions and delayed API responses using the production functions;
// these are not browser layout or real-device checks.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
class Element {
  constructor(){this.children=[];this.dataset={};this.hidden=false;this.value='';this.textContent='';}
  append(...items){this.children.push(...items);}
  replaceChildren(...items){this.children=[...items];}
  setAttribute(){}
  addEventListener(){}
  querySelectorAll(){return [];}
  focus(){}
  get firstChild(){return this.children[0];}
}
function scopedFunction(source,name,next,context){
  const declaration=source.indexOf('function '+name+'('),start=source.slice(0,declaration).endsWith('async ')?declaration-6:declaration,end=source.indexOf('function '+next+'(',declaration);
  assert.ok(start>=0&&end>start,'Production function boundaries');
  return vm.runInNewContext(source.slice(start,end)+'\n'+name,context);
}
async function check(dir){
  const read=name=>fs.readFileSync(path.join(__dirname,dir,name),'utf8'),nodes=new Map();
  const $=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
  const calls=[],state={busy:true,caseId:'old',chart:{main:{}},input:{question:'old'},seriesId:'series',loadToken:0};
  let allowDiscard=false;
  const context={state,$,currentJob:{},runId:'old',mayDiscard:()=>allowDiscard,window:{
    AnalysisStatus:{clear(){calls.push('status');}},ConditionRules:{setCase(value){calls.push(['case',value]);}},
    ReportViews:{reset(){calls.push('report');}}
  },renderChart(chart,input){calls.push(['chart',chart,input]);},renderBranchDraft(){},resetRawReplies(){},fillInput(){},
  banner(){},renderHistoryActive(){},showView(){},persistDraft(){calls.push('draft');},
  document:{dispatchEvent(){calls.push('event');}},Event:class {}};
  const reset=scopedFunction(read('app.js'),'resetCase','mayDiscard',context);
  assert.equal(reset(),false);assert.equal(calls.length,0);assert.equal(state.caseId,'old');
  state.busy=false;assert.equal(reset(),false);assert.equal(calls.length,0);assert.equal(state.chart.main!=null,true);
  allowDiscard=true;assert.equal(reset(),true);assert.equal(state.caseId,null);assert.equal(state.seriesId,null);
  assert.equal(state.input,null);assert.equal(state.chart,null);assert.equal(state.runId,null);
  assert.deepEqual(calls.find(call=>Array.isArray(call)&&call[0]==='case'),['case',null]);
  assert.deepEqual(calls.find(call=>Array.isArray(call)&&call[0]==='chart'),['chart',null,null]);
  assert.ok(calls.includes('report')&&calls.includes('draft'));

  let installed=true,version='v1',invalidations=0;
  const ruleContext={window:{RuleWorkbench:{overview(){},async invalidateUsage(){invalidations++;}}},$,previewRequest:0,
    rulesVersion:'',guide:null,selectedRule:'',showRuleContent(){},refreshRules(){},
    async api(url){return url==='/api/rules'?{installed}:{version,kinds:[],rules:[{id:'BASE_SCORE'}]};}};
  const loadRules=scopedFunction(read('v5-features.js'),'loadRules','renderRules',ruleContext);
  await loadRules();assert.equal(invalidations,1);await loadRules();assert.equal(invalidations,1);
  version='v2';await loadRules();assert.equal(invalidations,2);assert.equal(ruleContext.rulesVersion,'v2');
  installed=false;await loadRules();assert.equal(invalidations,3);assert.equal(ruleContext.rulesVersion,'');

  const pending=[],shown=[];let logicClears=0;
  const usage={purpose:'演示',workflow:[],scoring:{formulas:[],intro:[],kinds:[]},rules:[]};
  const principles={rules:[],five_lands:[],sources:[]};
  const uiContext={document:{getElementById:$,createElement:()=>new Element()},window:{ConditionRules:{
    renderLogic(host,logic){shown.push(logic.parameter_version);},invalidateLogic(){logicClears++;}
  }},URL:{revokeObjectURL(){}},async fetch(url){
    const result=url==='/api/calculation-logic'?new Promise((resolve,reject)=>pending.push({resolve,reject})):
      Promise.resolve(url==='/api/usage-guide'?usage:principles);
    return {ok:true,json:()=>result};
  }};
  vm.runInNewContext(read('rules-ui.js'),uiContext);const work=uiContext.window.RuleWorkbench,host=$('usage-panel');
  const old=work.loadUsage();assert.equal(pending.length,1);
  const fresh=work.invalidateUsage();assert.equal(pending.length,2);assert.equal(logicClears,1);
  pending[0].resolve({parameter_version:'old'});await old;
  assert.equal(host.dataset.loaded,undefined);assert.equal(shown.length,0);
  const joined=work.loadUsage();assert.equal(pending.length,2);
  pending[1].resolve({parameter_version:'new'});await Promise.all([fresh,joined]);
  assert.deepEqual(shown,['new']);assert.equal(host.dataset.loaded,'true');
  await work.loadUsage();assert.equal(pending.length,2);
  host.hidden=true;await work.invalidateUsage();assert.equal(pending.length,2);assert.equal(host.dataset.loaded,undefined);
  host.hidden=false;const obsolete=work.loadUsage(),latest=work.invalidateUsage();
  pending[3].resolve({parameter_version:'latest'});await latest;
  pending[2].reject(Error('obsolete response failed'));await obsolete;
  assert.deepEqual(shown,['new','latest']);assert.equal(host.dataset.loaded,'true');
  assert.equal(host.children.length,5);assert.equal(logicClears,3);
  console.log('PASS',dir,'accepted/cancelled reset, parameter-version invalidation, delayed responses and cache reuse');
}
(async()=>{for(const dir of ['../../liuyao_app/static','../web'])await check(dir);})().catch(error=>{console.error(error);process.exitCode=1;});
