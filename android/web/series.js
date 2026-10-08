var __defProp = Object.defineProperty;
var __defProps = Object.defineProperties;
var __getOwnPropDescs = Object.getOwnPropertyDescriptors;
var __getOwnPropSymbols = Object.getOwnPropertySymbols;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __propIsEnum = Object.prototype.propertyIsEnumerable;
var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
var __spreadValues = (a, b) => {
  for (var prop in b || (b = {}))
    if (__hasOwnProp.call(b, prop))
      __defNormalProp(a, prop, b[prop]);
  if (__getOwnPropSymbols)
    for (var prop of __getOwnPropSymbols(b)) {
      if (__propIsEnum.call(b, prop))
        __defNormalProp(a, prop, b[prop]);
    }
  return a;
};
var __spreadProps = (a, b) => __defProps(a, __getOwnPropDescs(b));
(() => {
  "use strict";
  function relatedDraft(current, question, method) {
    const selected = current.runs.find((run) => run.analysis_run_id === current.runId);
    const person = current.input.person_info ? __spreadValues({}, current.input.person_info) : null;
    if (person) {
      delete person.querent_age;
      delete person.subject_age;
      delete person.background;
    }
    return {
      parent: {
        caseId: current.caseId,
        revision: current.revision,
        question: current.input.question,
        analysisRunId: (selected == null ? void 0 : selected.outcome) && selected.revision_seq === current.revision ? selected.analysis_run_id : null
      },
      // Background stays shared with its source; do not copy it as a new fact.
      // Never carry a parent's casting, lines, time, or topic-specific fields.
      input: __spreadValues({ question: question || "" }, person ? { person_info: person } : {}),
      method: ["direct", "meibu", "taiji"].includes(method) ? method : "meibu"
    };
  }
  function orderedNodes(nodes) {
    const numbers = new Map(nodes.map((item, index) => [item.case_id, index + 1]));
    const children = /* @__PURE__ */ new Map();
    nodes.forEach((item) => {
      const key = item.parent_case_id || "";
      if (!children.has(key)) children.set(key, []);
      children.get(key).push(item);
    });
    const pending = (children.get("") || []).map((item) => ({ item, depth: 0 })).reverse(), result = [];
    while (pending.length) {
      const next = pending.pop();
      result.push(__spreadProps(__spreadValues({}, next), { number: numbers.get(next.item.case_id), parentNumber: numbers.get(next.item.parent_case_id) }));
      [...children.get(next.item.case_id) || []].reverse().forEach((item) => pending.push({ item, depth: next.depth + 1 }));
    }
    return result;
  }
  window.LiuyaoSeries = { relatedDraft, orderedNodes };
})();
