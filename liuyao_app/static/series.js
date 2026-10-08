(() => {
  'use strict';
  function relatedDraft(current, question, method) {
    const selected = current.runs.find(run => run.analysis_run_id === current.runId);
    const person = current.input.person_info ? {...current.input.person_info} : null;
    if (person) { delete person.querent_age; delete person.subject_age; delete person.background; }
    return {
      parent:{caseId:current.caseId,revision:current.revision,question:current.input.question,
        analysisRunId:selected?.outcome && selected.revision_seq === current.revision ? selected.analysis_run_id : null},
      // Background stays shared with its source; do not copy it as a new fact.
      // Never carry a parent's casting, lines, time, or topic-specific fields.
      input:{question:question || '',...(person ? {person_info:person} : {})},
      method:['direct','meibu','taiji'].includes(method) ? method : 'meibu'
    };
  }
  function orderedNodes(nodes) {
    const numbers = new Map(nodes.map((item,index) => [item.case_id,index+1]));
    const children = new Map();
    nodes.forEach(item => { const key = item.parent_case_id || ''; if (!children.has(key)) children.set(key,[]); children.get(key).push(item); });
    const pending = (children.get('') || []).map(item => ({item,depth:0})).reverse(), result = [];
    while (pending.length) {
      const next = pending.pop();
      result.push({...next,number:numbers.get(next.item.case_id),parentNumber:numbers.get(next.item.parent_case_id)});
      [...(children.get(next.item.case_id) || [])].reverse().forEach(item => pending.push({item,depth:next.depth+1}));
    }
    return result;
  }
  window.LiuyaoSeries = {relatedDraft,orderedNodes};
})();
