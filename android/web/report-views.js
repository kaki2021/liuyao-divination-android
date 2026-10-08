(() => {
  "use strict";
  function selectReport(result) {
    const reports = [result == null ? void 0 : result.user_report, result == null ? void 0 : result.display_report, result == null ? void 0 : result.report, result];
    const readable = (value) => typeof value === "string" ? Boolean(value.trim()) : value && typeof value === "object" && [value.summary, value.plain_language, value.conclusion, value.sections].some((part) => typeof part === "string" ? Boolean(part.trim()) : part && typeof part === "object" && Object.keys(part).length > 0);
    return reports.find(readable) || reports.find((value) => value && typeof value === "object" && Object.keys(value).length > 0) || null;
  }
  window.ReportViews = { selectReport };
  if (typeof document === "undefined") return;
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
  for (const [key, label] of [["answer", "解卦结论"], ["professional", "专业分析"], ["chart", "卦盘与计算"]]) {
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
      if (e.key === "ArrowRight") next = (i + 1) % keys.length;
      else if (e.key === "ArrowLeft") next = (i + keys.length - 1) % keys.length;
      else if (e.key === "Home") next = 0;
      else if (e.key === "End") next = keys.length - 1;
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
  const log = el("dialog", "", "analysis-log-dialog");
  log.id = "analysis-log-dialog";
  log.setAttribute("aria-labelledby", "analysis-log-title");
  const logHeading = el("div", "", "log-heading"), logTitle = el("h2", "分析 Log");
  logTitle.id = "analysis-log-title";
  const closeLog = el("button", "×", "icon-button");
  closeLog.id = "analysis-log-close";
  closeLog.type = "button";
  closeLog.title = "关闭 Log";
  closeLog.setAttribute("aria-label", "关闭 Log");
  closeLog.onclick = () => log.close();
  logHeading.append(logTitle, closeLog);
  const model = el("div");
  model.id = "model-info-content";
  log.append(logHeading, model, analysis.querySelector("#audit-report"), analysis.querySelector("#ai-raw-replies"));
  document.body.append(log);
  log.addEventListener("click", (event) => {
    if (event.target === log) {
      const rect = log.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) log.close();
    }
  });
  const followup = $("context-card");
  panels.answer.append(followup);
  section.append(toolbar, tabs, ...Object.values(panels));
  function show(key) {
    if (!panels[key]) return;
    for (const k of Object.keys(panels)) {
      panels[k].hidden = k !== key;
      buttons[k].setAttribute("aria-selected", String(k === key));
      buttons[k].tabIndex = k === key ? 0 : -1;
    }
  }
  function openLog() {
    if (!log.open) log.showModal();
  }
  function reset() {
    var _a;
    (_a = window.ConditionRules) == null ? void 0 : _a.setSnapshot(null);
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
  function table(title, cls = "") {
    const node = el("table", "", "professional-table " + cls);
    node.append(el("caption", title), el("tbody"));
    return node;
  }
  function row(node, label, value, cls = "") {
    if (!readableValue(value)) return null;
    const tr = el("tr", "", cls), th = el("th", label), td = el("td", readableValue(value));
    th.scope = "row";
    tr.append(th, td);
    node.tBodies[0].append(tr);
    return td;
  }
  function listRow(node, label, items, cls = "") {
    const texts = values(items);
    if (!texts.length) return;
    const td = row(node, label, texts, cls);
    td.replaceChildren();
    const list = el("ul");
    texts.forEach((text) => list.append(el("li", text)));
    td.append(list);
  }
  function appendFields(node, fields) {
    fields.forEach(([label, value]) => row(node, label, value));
  }
  function pair(first, second) {
    return [readableValue(first) || "未说明", readableValue(second) || "未说明"].join(" / ");
  }
  function candidates(stage) {
    return (Array.isArray(stage == null ? void 0 : stage.candidates) ? stage.candidates : []).filter((item) => item && typeof item === "object");
  }
  function candidateTitle(label, candidate, selectedId, index) {
    return label + (selectedId ? candidate.candidate_id === selectedId ? " · 本次采用" : " · 其他候选" : " · 待确认候选 " + (index + 1));
  }
  function appendQuotes(node, quotes) {
    const texts = values((Array.isArray(quotes) ? quotes : []).map((q) => (q == null ? void 0 : q.quote) || q));
    if (!texts.length) return;
    const td = row(node, "原文依据", " "), details = el("details", "", "professional-evidence");
    td.replaceChildren();
    details.append(el("summary", "查看 " + texts.length + " 处原文"));
    texts.forEach((text) => details.append(el("p", text)));
    td.append(details);
  }
  function appendCandidates(parent, stage, selectedId, label, renderCandidate) {
    const entries = candidates(stage), chosen = entries.find((candidate) => selectedId && candidate.candidate_id === selectedId);
    if (!chosen) {
      entries.forEach((candidate, index) => parent.append(renderCandidate(candidate, candidateTitle(label, candidate, null, index))));
      return;
    }
    parent.append(renderCandidate(chosen, candidateTitle(label, chosen, selectedId, 0)));
    const others = entries.filter((candidate) => candidate !== chosen);
    if (others.length) {
      const details = el("details", "", "professional-alternatives");
      details.append(el("summary", "其他" + label + "候选（" + others.length + "）"));
      others.forEach((candidate, index) => details.append(renderCandidate(candidate, candidateTitle(label, candidate, selectedId, index))));
      parent.append(details);
    }
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
  function renderChecks(result, report, c) {
    var _a, _b, _c, _d, _e, _f, _g, _h, _i, _j;
    const conditional = (result == null ? void 0 : result.chart) ? result.chart.conditional_analysis : (_b = (_a = window.ConditionRules) == null ? void 0 : _a.getChart()) == null ? void 0 : _b.conditional_analysis;
    const intent = (_c = result == null ? void 0 : result.stage_outputs) == null ? void 0 : _c.intent, selection = (_d = result == null ? void 0 : result.stage_outputs) == null ? void 0 : _d.selection, interpretation = (_e = result == null ? void 0 : result.stage_outputs) == null ? void 0 : _e.interpretation;
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
    const audit = result == null ? void 0 : result.audit_report, conditions = (_f = c == null ? void 0 : c.key_conditions) != null ? _f : audit == null ? void 0 : audit.conclusion_conditions, limits = (_g = c == null ? void 0 : c.limits) != null ? _g : audit == null ? void 0 : audit.conclusion_limits;
    if (!conditional && !intents.length && !uses.length && !missing.length && !c && !values(conditions).length && !values(limits).length) return false;
    const wrap = el("section", "", "professional-checks");
    appendCandidates(wrap, intent, intent == null ? void 0 : intent.selected_candidate_id, "意念", (candidate, title) => {
      const node = table(title, "professional-intent");
      appendFields(node, [["所问事项", candidate.primary_question], ["主体 / 对象", pair(candidate.actor, candidate.object)], ["行动 / 目标", pair(candidate.action, candidate.desired_outcome)], ["时间范围", candidate.time_scope], ["关注维度", values(candidate.facets).join("；")]]);
      appendQuotes(node, candidate.evidence_quotes);
      return node;
    });
    const relations = { generates_me: "生我者", same_as_me: "同我者", generated_by_me: "我生者", controlled_by_me: "我克者", controls_me: "克我者" }, purposes = { primary: "主目标", supporting: "支持因素", cost: "代价", carrier: "载体" };
    appendCandidates(wrap, selection, selection == null ? void 0 : selection.selected_primary_id, "取象", (candidate, title) => {
      const node = table(title, "professional-use");
      appendFields(node, [["关注对象", candidate.object_role], ["本次作用", candidate.function], ["用途 / 对应", [purposes[candidate.purpose] || candidate.purpose, useLabel(candidate)].filter(Boolean).join(" / ")], ["功能关系", relations[candidate.relation] || candidate.relation]]);
      listRow(node, "成立假设", candidate.assumptions);
      appendQuotes(node, candidate.evidence_quotes);
      return node;
    });
    if (conditional) {
      const focus = new Set(conditional.primary_matches.filter((l) => l.layer === "visible").map((l) => l.position));
      conditional.lines.filter((l) => l.moving).forEach((l) => focus.add(l.position));
      const shi = ((_h = result == null ? void 0 : result.chart) == null ? void 0 : _h.shi_position) || ((_j = (_i = window.ConditionRules) == null ? void 0 : _i.getChart()) == null ? void 0 : _j.shi_position);
      if (shi) focus.add(shi);
      const states = (lines, title) => {
        const t = table(title, "professional-states");
        const head = el("thead"), tr = el("tr");
        ["爻", "日月依据", "状态", "本问作用"].forEach((name) => {
          const h = el("th", name);
          h.scope = "col";
          tr.append(h);
        });
        head.append(tr);
        t.prepend(head);
        for (const l of lines) {
          const tr2 = el("tr"), effects = conditional.effects.filter((e) => e.target_position === l.position && e.target_layer === l.layer && e.status !== "unsatisfied");
          const text = effects.length ? effects.map((e) => "第" + e.source_position + "爻→本爻：" + e.relation_label + "（待核定）").join("；") : conditional.primary_matches.some((m) => m.position === l.position && m.layer === l.layer) ? "已匹配候选，作用待判断" : "保留结构，未定本问作用";
          [String(l.position) + (l.layer === "hidden" ? "伏" : "") + " " + l.relative + l.branch + l.element, (l.month_class ? "月令" + l.month_class + "；日辰" + ({ same: "同类", generates: "生本爻", controls: "克本爻", drains: "本爻生日辰", consumes: "本爻克日辰" }[l.day_relation] || "关系待核对") : "日月未核对") + "；综合旺衰待判断", window.ConditionRules.model.state(l), text].forEach((value) => tr2.append(el("td", value)));
          t.tBodies[0].append(tr2);
        }
        return t;
      };
      wrap.append(states(conditional.lines.filter((l) => focus.has(l.position)).concat(conditional.primary_matches.filter((l) => l.layer === "hidden")), "爻的状态与本问作用"));
      const others = conditional.lines.filter((l) => !focus.has(l.position));
      if (others.length) {
        const d = el("details", "", "professional-alternatives");
        d.append(el("summary", "其他爻的状态（" + others.length + "）"), states(others, "其他爻"));
        wrap.append(d);
      }
    }
    const directions = { favorable: "偏顺利", unfavorable: "阻力较多", mixed: "有利有弊", undetermined: "暂不能判断" };
    if (c || values(conditions).length || values(limits).length || missing.length) {
      const node = table("结论与条件", "professional-conclusion");
      const answer = row(node, "综合判断", c == null ? void 0 : c.answer);
      if (answer && (c == null ? void 0 : c.direction)) answer.prepend(el("span", directions[c.direction] || directions.undetermined, "professional-direction"));
      listRow(node, "成立条件", conditions, "conclusion-conditions");
      listRow(node, "判断边界", limits, "conclusion-limits");
      listRow(node, "待补 / 核实", missing, "professional-missing");
      if (conditional) {
        listRow(node, "系统判断范围", conditional.limits);
        const td = row(node, "规则条件核对", " "), d = el("details", "", "professional-evidence");
        td.replaceChildren();
        d.append(el("summary", "查看满足、不满足与未知条件"));
        conditional.checks.forEach((check) => {
          d.append(el("h4", check.name || check.rule_id), el("p", check.conditions.map((x) => x.label + "：" + window.ConditionRules.model.label(x.status) + (x.note ? "（" + x.note + "）" : "")).join("；")));
        });
        td.append(d);
      }
      wrap.append(node);
    }
    professional.append(wrap);
    return true;
  }
  const jargon = /用神|官鬼|妻财|父母爻|兄弟爻|子孙|世爻|应爻|应克世|持世|动爻|变爻|旬空|月令|日辰|生扶|回头生克|实验|综合分|结构性|第[一二三四五六1-6]爻/;
  function fallback(c) {
    let text = ((c == null ? void 0 : c.answer) || "").split(/[：:；;。\n]/)[0].replace(/^按本次卦象[，,]?/, "");
    if (!text || text.length > 110 || jargon.test(text)) text = { favorable: "这件事偏向能成，但仍有条件需要落实。", unfavorable: "这件事目前偏向难成，需要重新评估条件。", mixed: "这件事有机会，但推进中可能反复。" }[c == null ? void 0 : c.direction] || "目前还不能明确判断结果。";
    return { answer: text, source: "compatibility" };
  }
  function render(report, container, { isDemo = false, result = null } = {}) {
    var _a, _b, _c, _d;
    (_a = window.ConditionRules) == null ? void 0 : _a.setSnapshot(result == null ? void 0 : result.logic_snapshot);
    const c = report.conclusion || ((_c = (_b = result == null ? void 0 : result.stage_outputs) == null ? void 0 : _b.interpretation) == null ? void 0 : _c.conclusion), plain = !isDemo && (report.plain_language || (c ? fallback(c) : null));
    let shown = false;
    if (plain) {
      const hero = el("div", "", "answer-hero");
      hero.append(el("p", "本次结论", "eyebrow"), el("h3", plain.answer, "direct-answer"));
      if (plain.reason) hero.append(el("p", plain.reason, "answer-reason"));
      container.append(hero);
      shown = true;
      const grid = el("div", "", "answer-grid");
      for (const [key, label] of [["watch_for", "需要留意"], ["next_steps", "接下来怎么做"]]) {
        if (!((_d = plain[key]) == null ? void 0 : _d.length)) continue;
        const card = el("section", "", "answer-note");
        card.append(el("h4", label));
        const list = el("ul");
        plain[key].slice(0, 3).forEach((t) => list.append(el("li", t)));
        card.append(list);
        grid.append(card);
      }
      container.append(grid);
      if (plain.timing) container.append(el("p", "时间判断：" + plain.timing, "answer-timing"));
      if (plain.source === "compatibility") container.append(el("p", "当前展示简要结论；完整原文和依据在“专业分析”。", "small-note"));
    } else if (report.summary) {
      container.append(el("p", report.summary, "report-summary"));
      shown = true;
    }
    const sections = (report.sections || []).filter((x) => x.content || x.body || x.text);
    professional.replaceChildren();
    if (!isDemo) shown = renderChecks(result, report, c) || shown;
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
      const detail = el("details", "", "professional-explanation");
      detail.append(el("summary", "分段推演与详细解读"), nav, body, footer);
      professional.append(detail);
      page(0);
      if (!plain) container.append(el("p", "分段说明可在“专业分析”中查看。", "small-note"));
    } else professional.append(el("p", "本次没有分段推演。", "empty-state"));
    return shown;
  }
  window.ReportViews = { render, reset, show, openLog, selectReport };
  reset();
  show("answer");
})();
