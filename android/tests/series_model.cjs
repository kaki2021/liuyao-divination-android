// Exercise the production series model without a browser or third-party modules.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const context = {window:{}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../liuyao_app/static/series.js'),'utf8'),context);
const model = context.window.LiuyaoSeries, plain = value => JSON.parse(JSON.stringify(value));
const current = {caseId:'parent',revision:2,runId:'shown-run',
  input:{question:'适合换工作吗？',lines:['old_yang'],casting:{method:'meibu',results:['1','2','3']},
    actual_cast_time:'2026-09-17T12:00:00Z',buzhai:{topic:'old-topic'},
    person_info:{subject:'self',profile_id:'person',querent_age:32,subject_age:34,relationship:'同事',background:'正在找工作'}},
  runs:[{analysis_run_id:'shown-run',revision_seq:2,outcome:{result:{}}},
    {analysis_run_id:'latest-run',revision_seq:2,outcome:{result:{}}}]};
const saved = plain(current);
const draft = plain(model.relatedDraft(current,'A公司是否合适？','meibu'));
assert.equal(draft.parent.caseId,'parent');
assert.equal(draft.parent.revision,2);
assert.equal(draft.parent.analysisRunId,'shown-run');
assert.equal(draft.input.question,'A公司是否合适？');
assert.equal(draft.input.person_info.profile_id,'person');
assert.equal('background' in draft.input.person_info,false);
assert.equal(current.input.person_info.background,'正在找工作');
for (const field of ['lines','casting','actual_cast_time','buzhai']) assert.equal(field in draft.input,false);
for (const field of ['querent_age','subject_age']) assert.equal(field in draft.input.person_info,false);
assert.deepEqual(plain(current),saved);
assert.equal(model.relatedDraft({...current,revision:3},'',null).parent.analysisRunId,null);
assert.equal(model.relatedDraft({...current,runs:[]},'',null).parent.analysisRunId,null);
assert.equal(model.relatedDraft({...current,runs:[{analysis_run_id:'shown-run',revision_seq:2}]},'',null).parent.analysisRunId,null);
assert.equal(model.relatedDraft({...current,input:{question:'总问'}},'','obsolete').method,'meibu');
const nodes=[{case_id:'root',parent_case_id:null},{case_id:'a',parent_case_id:'root'},
  {case_id:'b',parent_case_id:'root'},{case_id:'c',parent_case_id:'a'}];
const tree=plain(model.orderedNodes(nodes));
assert.deepEqual(tree.map(n=>n.item.case_id),['root','a','c','b']);
assert.deepEqual(tree.map(n=>n.depth),[0,1,2,1]);
assert.equal(tree[2].parentNumber,2);
assert.deepEqual(tree.map(n=>n.number),[1,2,4,3]);
assert.deepEqual(plain(model.orderedNodes([])),[]);
// A long lineage remains iterative and keeps exact parent identities.
const deep=Array.from({length:2000},(_,i)=>({case_id:String(i),parent_case_id:i?String(i-1):null}));
assert.equal(model.orderedNodes(deep).at(-1).depth,1999);
console.log('Series model: parent selection, new casting isolation, input preservation and branching order passed.');
