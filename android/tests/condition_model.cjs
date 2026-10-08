'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
for(const dir of ['../../liuyao_app/static','../web']){
 const file=path.join(__dirname,dir,'condition-rules.js');if(!fs.existsSync(file))continue;
 const context={window:{}};vm.runInNewContext(fs.readFileSync(path.join(__dirname,dir,'report-views.js'),'utf8'),context);vm.runInNewContext(fs.readFileSync(file,'utf8'),context);const m=context.window.ConditionRules.model,select=context.window.ReportViews.selectReport;
 assert.equal(m.label('unknown'),'未知');assert.equal(m.conjunction([{status:'satisfied'},{status:'unknown'}]),'unknown');
 assert.equal(m.conjunction([{status:'unsatisfied'},{status:'unknown'}]),'unsatisfied');
 const rules=[{id:'empty',name:'化空',scene:'空破',scope:'变支旬空',policy:'保留状态'},{id:'use',name:'取用',scene:'取用',scope:'对象用途',policy:'多现候选'}];
 assert.equal(m.filter(rules,'变支','').length,1);assert.equal(m.filter(rules,'','取用')[0].id,'use');
 const a={checks:[{rule_id:'r',status:'unknown',conditions:[{status:'unknown'}]}]},b={checks:[{rule_id:'r',status:'unsatisfied',conditions:[{status:'unsatisfied'}]}]};
 assert.equal(m.compare(a,b)[0].changed,true);assert.equal(m.compare(a,a)[0].changed,false);
 assert.equal(m.state({moving:true,changed_branch:'亥',empty:false,changed_empty:true,month_break:true}),'原爻月破；动→亥；化空');
 assert.equal(m.state({moving:false,empty:null}),'日月未核对；静');
 const record={analysis_runs:[
  {analysis_run_id:'old',rules_digest:'old-rules',outcome:{result:{report:{user_report:{plain_language:{answer:'旧预测'}}}}}},
  {analysis_run_id:'latest',outcome:{result:{report:{user_report:{plain_language:{answer:'新预测'}}}}}}
 ],feedback:[{analysis_run_id:'old',reported_outcome:'实际结果',match_degree:'partly_matched'},
             {reported_outcome:'未关联反馈',match_degree:'pending'}]};
 const unchanged=JSON.stringify(record),rows=m.caseRows(record);
 assert.equal(rows[0].prediction,'旧预测');assert.equal(rows[0].actual,'实际结果');
 assert.equal(rows[0].rating,'部分符合');assert.equal(rows[0].ruleVersion,'old-rules');
 assert.equal(rows[1].prediction,'未关联可读的分析');assert.equal(rows[1].runId,null);
 assert.equal(rows[1].rating,'尚待验证');assert.equal(JSON.stringify(record),unchanged);
 assert.equal(m.caseRows(null).length,0);
 const legacy={user_report:{},display_report:{summary:'旧版可读预测'}};
 assert.equal(select(legacy),legacy.display_report);
 legacy.user_report={model_info:{rules_version:'old'}};assert.equal(select(legacy),legacy.display_report);
 record.analysis_runs[0].outcome.result.report=legacy;assert.equal(m.caseRows(record)[0].prediction,'旧版可读预测');
 record.analysis_runs[0].outcome.result.report='旧版文本预测';assert.equal(m.caseRows(record)[0].prediction,'旧版文本预测');
 assert.equal(select({user_report:{summary:'正式报告'},display_report:{summary:'备用报告'}}).summary,'正式报告');
 assert.equal(select(undefined),null);assert.equal(select({user_report:{},display_report:{}}).summary,undefined);
 console.log('PASS',dir,'condition states, scenarios, distinct empty labels and feedback bound to its saved analysis');
}
