(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const el = (tag, text = "", cls = "") => {
    const n = document.createElement(tag);
    n.textContent = text;
    n.className = cls;
    return n;
  };
  const section = $("results-section"), analysis = $("analysis-card");
  const tabs = el("nav", "", "result-tabs");
  tabs.setAttribute("role", "tablist");
  tabs.setAttribute("aria-label", "结果阅读方式");
  const panels = {}, buttons = {};
  for (const [key, label] of [["answer", "直接答案"], ["professional", "专业分析"], ["chart", "卦盘与计算"], ["records", "Log"]]) {
    const b = el("button", label);
    b.type = "button";
    b.id = "result-tab-" + key;
    b.setAttribute("role", "tab");
    b.setAttribute("aria-controls", "result-" + key);
    tabs.append(b);
    buttons[key] = b;
    const p = el("div", "", "result-panel");
    p.id = "result-" + key;
    p.setAttribute("role", "tabpanel");
    p.setAttribute("aria-labelledby", b.id);
    panels[key] = p;
    b.addEventListener("click", () => show(key));
    b.addEventListener("keydown", (e) => {
      const keys = Object.keys(buttons), i = keys.indexOf(key);
      let next;
      if (e.key === "ArrowRight") next = (i + 1) % 4;
      else if (e.key === "ArrowLeft") next = (i + 3) % 4;
      else if (e.key === "Home") next = 0;
      else if (e.key === "End") next = 3;
      else return;
      e.preventDefault();
      show(keys[next]);
      buttons[keys[next]].focus();
    });
  }
  const toolbar = el("div", "", "report-toolbar");
  toolbar.append(analysis.querySelector(".analysis-actions"), $("run-history"), $("analysis-progress"));
  analysis.querySelector(".section-heading").remove();
  const chart = section.querySelector(".chart-card"), foundation = $("foundation-card");
  panels.chart.append(chart, foundation);
  panels.answer.append(analysis);
  const professional = el("section", "", "paper-card professional-card");
  professional.id = "professional-content";
  panels.professional.append(professional);
  const records = el("section", "", "paper-card log-card");
  records.append(el("h3", "分析 Log"));
  const model = el("div");
  model.id = "model-info-content";
  records.append(model, analysis.querySelector("#audit-report"), analysis.querySelector("#ai-raw-replies"));
  panels.records.append(records);
  const followup = section.querySelector(".follow-up-card");
  $("feedback-section").append(followup);
  section.append(toolbar, tabs, ...Object.values(panels));
  function show(key) {
    for (const k of Object.keys(panels)) {
      panels[k].hidden = k !== key;
      buttons[k].setAttribute("aria-selected", String(k === key));
      buttons[k].tabIndex = k === key ? 0 : -1;
    }
  }
  function reset() {
    professional.replaceChildren(el("p", "本次尚无专业报告。", "empty-state"));
    model.replaceChildren();
    $("audit-report").open = false;
  }
  function readableValue(value) {
    if (value === void 0 || value === null) return "";
    if (typeof value === "string" || typeof value === "number") return String(value);
    if (Array.isArray(value)) return value.map(readableValue).filter(Boolean).join("\n");
    if (typeof value === "object") return readableValue(value.text || value.content || value.message || value.description || value.question || value.reason || value.summary || value.impact || value.gap || "");
    return "";
  }
  function values(items) {
    return (Array.isArray(items) ? items : items ? [items] : []).map(readableValue).filter(Boolean);
  }
  function appendList(parent, items, title, cls = "professional-list") {
    const listItems = values(items);
    if (!listItems.length) return false;
    const block = el("section", "", cls);
    block.append(el("h4", title));
    const list = el("ul");
    listItems.forEach((text) => list.append(el("li", text)));
    block.append(list);
    parent.append(block);
    return true;
  }
  function appendFields(parent, fields) {
    const rows = fields.filter(([_, value]) => readableValue(value));
    if (!rows.length) return false;
    const dl = el("dl", "", "professional-fields");
    rows.forEach(([label, value]) => {
      dl.append(el("dt", label), el("dd", readableValue(value)));
    });
    parent.append(dl);
    return true;
  }
  function candidates(stage) {
    return (Array.isArray(stage == null ? void 0 : stage.candidates) ? stage.candidates : []).filter((item) => item && typeof item === "object");
  }
  function candidateTitle(label, candidate, selectedId, index) {
    return label + (selectedId ? candidate.candidate_id === selectedId ? " · 本次采用" : " · 其他候选" : " · 待确认候选 " + (index + 1));
  }
  function appendQuotes(parent, quotes) {
    appendList(parent, (Array.isArray(quotes) ? quotes : []).map((q) => (q == null ? void 0 : q.quote) || q), "用户原文依据");
  }
  function useLabel(candidate) {
    if (!candidate) return "";
    if (candidate.subject_reference === "shi") return "世爻（社会身份、角色或外部资源尺度）";
    if (candidate.subject_reference === "shi_body") return "世身（个人状态、身体或自身处境尺度）";
    const relatives = { parents: "父母", siblings: "兄弟", offspring: "子孙", wealth: "妻财", official_ghost: "官鬼" };
    return relatives[candidate.six_relative] || candidate.six_relative || "";
  }
  function selectionNotes(result) {
    var _a, _b, _c;
    const selection = (_a = result == null ? void 0 : result.stage_outputs) == null ? void 0 : _a.selection, interpretation = (_b = result == null ? void 0 : result.stage_outputs) == null ? void 0 : _b.interpretation;
    const reviews = (result == null ? void 0 : result.selection_note_reviews) || ((_c = result == null ? void 0 : result.audit_report) == null ? void 0 : _c.selection_note_reviews);
    if (Array.isArray(reviews)) return reviews.filter((r) => r && r.current_status !== "resolved").map((r) => {
      var _a2, _b2;
      return (_b2 = (_a2 = r.current_text) != null ? _a2 : r.review_text) != null ? _b2 : r.original_text;
    });
    if (interpretation) return [];
    return selection == null ? void 0 : selection.unresolved;
  }
  function renderCheck(result, report) {
    var _a, _b, _c;
    const intent = (_a = result == null ? void 0 : result.stage_outputs) == null ? void 0 : _a.intent, selection = (_b = result == null ? void 0 : result.stage_outputs) == null ? void 0 : _b.selection, interpretation = (_c = result == null ? void 0 : result.stage_outputs) == null ? void 0 : _c.interpretation;
    const intents = candidates(intent), uses = candidates(selection);
    const missing = [...new Set([
      result == null ? void 0 : result.unresolved,
      result == null ? void 0 : result.clarifying_questions,
      report == null ? void 0 : report.uncertainties,
      report == null ? void 0 : report.clarifying_questions,
      intent == null ? void 0 : intent.clarifying_questions,
      interpretation == null ? void 0 : interpretation.uncertainties,
      interpretation == null ? void 0 : interpretation.clarifying_questions,
      selectionNotes(result),
      selection == null ? void 0 : selection.clarifying_questions
    ].reduce((all, items) => all.concat(values(items)), []))];
    if (!intents.length && !uses.length && !missing.length) return false;
    const wrap = el("section", "", "professional-checks");
    wrap.append(el("h3", "原始意念与取象核对"));
    const grid = el("div", "", "professional-check-grid");
    intents.forEach((candidate, index) => {
      const card = el("section", "", "professional-check-card professional-intent");
      card.append(el("h4", candidateTitle("AI 抓取的原始意念", candidate, intent.selected_candidate_id, index)));
      appendFields(card, [["所问事项", candidate.primary_question], ["主体", candidate.actor], ["对象", candidate.object], ["拟采取行动", candidate.action], ["想要结果", candidate.desired_outcome], ["时间范围", candidate.time_scope]]);
      appendList(card, candidate.facets, "关注维度");
      appendQuotes(card, candidate.evidence_quotes);
      grid.append(card);
    });
    const relations = { generates_me: "生我者", same_as_me: "同我者", generated_by_me: "我生者", controlled_by_me: "我克者", controls_me: "克我者" }, purposes = { primary: "主目标", supporting: "支持因素", cost: "代价", carrier: "载体" };
    uses.forEach((candidate, index) => {
      const card = el("section", "", "professional-check-card professional-use");
      card.append(el("h4", candidateTitle("AI 取象与关注对象", candidate, selection.selected_primary_id, index)));
      appendFields(card, [["关注对象", candidate.object_role], ["本次作用", candidate.function], ["用途", purposes[candidate.purpose] || candidate.purpose], ["对应六亲 / 主体", useLabel(candidate)], ["功能关系", relations[candidate.relation] || candidate.relation]]);
      appendList(card, candidate.assumptions, "取象成立假设");
      appendQuotes(card, candidate.evidence_quotes);
      grid.append(card);
    });
    if (grid.childElementCount) wrap.append(grid);
    appendList(wrap, missing, "仍缺条件 / 待核实项", "professional-missing");
    professional.append(wrap);
    return true;
  }
  function renderConclusionMeta(c, result) {
    var _a, _b;
    const audit = result == null ? void 0 : result.audit_report, conditions = (_a = c == null ? void 0 : c.key_conditions) != null ? _a : audit == null ? void 0 : audit.conclusion_conditions, limits = (_b = c == null ? void 0 : c.limits) != null ? _b : audit == null ? void 0 : audit.conclusion_limits;
    if (!c && !values(conditions).length && !values(limits).length) return false;
    const directions = { favorable: "偏顺利", unfavorable: "阻力较多", mixed: "有利有弊", undetermined: "暂不能判断" };
    const card = el("section", "", "conclusion-card conclusion-" + ((c == null ? void 0 : c.direction) || "undetermined")), head = el("div", "", "conclusion-heading");
    head.append(el("h3", "综合判断核对"));
    if (c) {
      head.append(el("span", directions[c.direction] || directions.undetermined, "conclusion-direction"));
    }
    card.append(head);
    if (readableValue(c == null ? void 0 : c.answer)) card.append(el("p", readableValue(c.answer), "conclusion-answer"));
    appendList(card, conditions, "结论成立条件", "conclusion-conditions");
    appendList(card, limits, "判断边界", "conclusion-limits");
    professional.append(card);
    return true;
  }
  const jargon = /用神|官鬼|妻财|父母爻|兄弟爻|子孙|世爻|应爻|应克世|持世|动爻|变爻|旬空|月令|日辰|生扶|回头生克|实验|综合分|结构性|第[一二三四五六1-6]爻/;
  function fallback(c) {
    let text = ((c == null ? void 0 : c.answer) || "").split(/[：:；;。\n]/)[0].replace(/^按本次卦象[，,]?/, "");
    if (!text || text.length > 110 || jargon.test(text)) text = { favorable: "这件事偏向能成，但仍有条件需要落实。", unfavorable: "这件事目前偏向难成，需要重新评估条件。", mixed: "这件事有机会，但推进中可能反复。" }[c == null ? void 0 : c.direction] || "目前还不能明确判断结果。";
    return { answer: text, source: "compatibility" };
  }
  function render(report, container, { isDemo = false, result = null } = {}) {
    var _a, _b, _c;
    const c = report.conclusion || ((_b = (_a = result == null ? void 0 : result.stage_outputs) == null ? void 0 : _a.interpretation) == null ? void 0 : _b.conclusion), plain = !isDemo && (report.plain_language || (c ? fallback(c) : null));
    let shown = false;
    if (plain) {
      const hero = el("div", "", "answer-hero");
      hero.append(el("p", "这次的答案", "eyebrow"), el("h3", plain.answer, "direct-answer"));
      if (plain.reason) hero.append(el("p", plain.reason, "answer-reason"));
      container.append(hero);
      shown = true;
      const grid = el("div", "", "answer-grid");
      for (const [key, label] of [["watch_for", "需要留意"], ["next_steps", "接下来怎么做"]]) {
        if (!((_c = plain[key]) == null ? void 0 : _c.length)) continue;
        const card = el("section", "", "answer-note");
        card.append(el("h4", label));
        const list = el("ul");
        plain[key].slice(0, 3).forEach((t) => list.append(el("li", t)));
        card.append(list);
        grid.append(card);
      }
      container.append(grid);
      if (plain.timing) container.append(el("p", "时间判断：" + plain.timing, "answer-timing"));
      if (plain.source === "compatibility") container.append(el("p", "当前展示简要答案；完整原文和依据在“专业分析”。", "small-note"));
    } else if (report.summary) {
      container.append(el("p", report.summary, "report-summary"));
      shown = true;
    }
    const sections = (report.sections || []).filter((x) => x.content || x.body || x.text);
    professional.replaceChildren();
    if (!isDemo) {
      shown = renderCheck(result, report) || shown;
      shown = renderConclusionMeta(c, result) || shown;
    }
    if (sections.length) {
      let page = function(i) {
        current = i;
        const s = sections[i];
        body.replaceChildren(el("h3", s.heading || s.title || "分析说明"), el("p", s.content || s.body || s.text));
        body.setAttribute("aria-labelledby", controls[i].id);
        controls.forEach((b, j) => {
          b.setAttribute("aria-selected", String(i === j));
          b.tabIndex = i === j ? 0 : -1;
        });
        prev.disabled = i === 0;
        next.disabled = i === sections.length - 1;
        count.textContent = "".concat(i + 1, " / ").concat(sections.length);
      };
      shown = true;
      let current = 0;
      const nav = el("div", "", "professional-nav");
      nav.setAttribute("role", "tablist");
      nav.setAttribute("aria-label", "专业分析主题");
      const body = el("section", "", "professional-body");
      body.id = "professional-topic";
      body.setAttribute("role", "tabpanel");
      const footer = el("div", "", "professional-pager"), prev = el("button", "← 上一页", "secondary-button"), next = el("button", "下一页 →", "secondary-button"), count = el("span");
      prev.type = next.type = "button";
      const controls = sections.map((s, i) => {
        const b = el("button", i + 1 + " " + (s.heading || s.title || "分析说明"));
        b.type = "button";
        b.id = "professional-topic-" + i;
        b.setAttribute("role", "tab");
        b.setAttribute("aria-controls", body.id);
        b.addEventListener("click", () => page(i));
        b.addEventListener("keydown", (e) => {
          if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(e.key)) return;
          e.preventDefault();
          page(e.key === "Home" ? 0 : e.key === "End" ? sections.length - 1 : (i + (e.key === "ArrowRight" ? 1 : sections.length - 1)) % sections.length);
          controls[current].focus();
        });
        nav.append(b);
        return b;
      });
      prev.addEventListener("click", () => page(current - 1));
      next.addEventListener("click", () => page(current + 1));
      footer.append(prev, count, next);
      professional.append(nav, body, footer);
      page(0);
      if (!plain) container.append(el("p", "分段说明可在“专业分析”中查看。", "small-note"));
    } else professional.append(el("p", "本次没有分段推演。", "empty-state"));
    return shown;
  }
  window.ReportViews = { render, reset, show };
  reset();
  show("answer");
})();
