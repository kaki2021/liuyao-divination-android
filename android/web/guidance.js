(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const el = (tag, text = "", cls = "") => {
    const n = document.createElement(tag);
    n.textContent = text;
    n.className = cls;
    return n;
  };
  const block = (title, text) => {
    const d = el("section", "", "guide-block");
    d.append(el("h4", title), el("p", text));
    return d;
  };
  const details = (title) => {
    const d = el("details", "", "guide-details");
    d.append(el("summary", title));
    return d;
  };
  const signed = (n) => (n >= 0 ? "+" : "") + n;
  const intro = details("起卦前：先谋后卜，怎么准备？");
  intro.id = "question-guidance";
  intro.append(
    block("谋事先有可讨论的计划", "先认真考虑现实条件，再说明具体做法和犹疑之处。例如：“我打算下个月按现有条件接下这个项目，担心投入过大；这样推进对我是否有利，主要代价是什么？”"),
    block("还在排查问题时", "先明确待查对象、现象、范围和目的。例如：“A 房起居活动区已有这些使用不便，应优先检查哪些环节？”诊断前不必编造整改方案，但要清楚这次想查什么。"),
    block("让本次问题有所指", "先读一遍：我关心的是哪个对象的什么事情？结果将帮助我判断什么？需要哪些已知事实？不要为了凑表格而填写猜测。")
  );
  intro.append(el("p", "第一课原文称“谋而后卜”。先谋划，再问尚未拿准之处；判断不利先检视计划、查漏补缺。“使用与原理”可查看原文短引和说明。", "small-note"));
  const learn = el("button", "查看卜筮用途与使用方法", "text-button");
  learn.type = "button";
  intro.append(learn);
  $("person-details").before(intro);
  $("question").placeholder = "我准备做什么？已有条件是什么？哪一点还拿不准？若在查问题，写清待查对象与范围。";
  const rules = $("rules-page"), tabs = rules.querySelector(".principle-tabs");
  const usage = el("section", "", "usage-guide");
  usage.id = "usage-panel";
  usage.hidden = true;
  const usageTab = el("button", "使用与原理");
  usageTab.type = "button";
  usageTab.id = "usage-tab";
  usageTab.setAttribute("aria-pressed", "false");
  tabs.prepend(usageTab);
  rules.append(usage);
  let guidePromise = null;
  function showUsage() {
    for (const id of ["parameter-panel", "principle-panel"]) $(id).hidden = true;
    usage.hidden = false;
    for (const b of tabs.querySelectorAll("button")) b.setAttribute("aria-pressed", String(b === usageTab));
  }
  for (const b of [...tabs.querySelectorAll("button")].filter((b2) => b2 !== usageTab)) b.addEventListener("click", () => {
    usage.hidden = true;
    usageTab.setAttribute("aria-pressed", "false");
  });
  async function loadUsage() {
    showUsage();
    if (usage.dataset.loaded) return;
    usage.replaceChildren(el("p", "正在读取使用说明…"));
    try {
      if (!guidePromise) guidePromise = fetch("/api/usage-guide").then((r) => {
        if (!r.ok) throw Error("使用说明读取失败，请重试。");
        return r.json();
      });
      const g = await guidePromise;
      usage.replaceChildren(el("h3", g.title), el("p", g.purpose, "guide-lead"));
      const workflow = el("ol", "", "usage-steps");
      g.workflow.forEach((s) => {
        const li = el("li");
        li.append(el("h4", s.title), el("p", s.text));
        workflow.append(li);
      });
      usage.append(workflow);
      usage.append(block("三类依据怎样分清", "原理说明讲关系与适用范围；程序计算展示按已编码规则得出的结构；实验评分用人为参数表达相对强弱。AI 综合解释还需要条件与实际反馈，不能用计算完成代替现实结果。"));
      const evidence = details("原文核对范围与采用方式");
      evidence.append(el("p", g.source_note));
      usage.append(evidence);
      for (const r of g.rules) {
        const d = details(r.title);
        d.append(el("p", r.help));
        const source = details("查看原文短引与采用方式");
        source.append(el("blockquote", r.quote, "guide-quote"), el("p", "出处：《".concat(r.source, "》").concat(r.locator, "。已核对相关正文。"), "source-note"), block("软件怎样采用", r.review_note), el("p", r.catalog_summary, "small-note"));
        r.limitations.forEach((t) => source.append(el("p", t, "small-note")));
        d.append(source);
        usage.append(d);
      }
      usage.dataset.loaded = "true";
    } catch (e) {
      guidePromise = null;
      usage.replaceChildren(el("p", e.message));
    }
  }
  usageTab.onclick = loadUsage;
  learn.onclick = () => {
    window.MobileUI.openRules();
    loadUsage();
  };
  const how = details("起卦与“重新解卦”有什么区别？");
  how.append(el("p", "起卦是实际摸取或摇卦并记录结果。“保存并排盘”把结果翻译为卦盘；“保存并分析”和“重新解卦”调用 AI 解读已记录的卦，不会自动产生新卦。另起了一卦，请新建案例。"));
  $("casting-instruction").after(how);
  function overview(guide) {
    let host = $("score-overview");
    if (!host) {
      host = el("section", "", "score-overview");
      host.id = "score-overview";
      $("parameter-panel").prepend(host);
    }
    host.replaceChildren(el("h3", "先知道这份分数在算什么"));
    const chapters = el("nav", "", "score-learning-tabs"), reading = el("section");
    chapters.setAttribute("aria-label", "评分说明主题");
    const buttons = guide.intro.map((t, i) => {
      const b = el("button", t.title);
      b.type = "button";
      b.onclick = () => {
        buttons.forEach((x, j) => x.setAttribute("aria-pressed", String(i === j)));
        reading.replaceChildren(block(t.title, t.text));
      };
      chapters.append(b);
      return b;
    });
    host.append(chapters, reading);
    buttons[0].click();
    const types = details("九类参数：分别改动什么？");
    guide.kinds.forEach((t) => types.append(block(t.name, t.meaning)));
    host.append(types);
    document.querySelector(".rules-primer").open = false;
    let kind = $("rule-kind");
    if (!kind) {
      const label = el("label", "按参数类型筛选");
      label.htmlFor = "rule-kind";
      kind = el("select");
      kind.id = "rule-kind";
      $("rule-category").after(label, kind);
      kind.addEventListener("change", () => window.LiuyaoV5.refreshRuleList());
    }
    const previous = kind.value;
    kind.replaceChildren(el("option", "全部类型"));
    kind.firstChild.value = "";
    guide.kinds.forEach((t) => {
      const o = el("option", t.name);
      o.value = t.id;
      kind.append(o);
    });
    kind.value = previous || "";
  }
  function ledger(host, traces, title) {
    host.replaceChildren(el("h4", title));
    const label = el("label", "选择一个爻，看分数怎么得来"), select = el("select");
    select.setAttribute("aria-label", title + "爻位");
    label.append(select);
    host.append(label);
    traces.forEach((l) => {
      const o = el("option", "第 ".concat(l.position, " 爻 · ").concat(l.name, " · ").concat(l.score, " 分"));
      o.value = l.position;
      select.append(o);
    });
    const body = el("div", "", "score-ledger");
    host.append(body);
    function render() {
      const l = traces.find((t) => String(t.position) === select.value);
      body.replaceChildren();
      body.append(el("p", "只计算第 ".concat(l.position, " 爻（").concat(l.name, "）。覆盖：").concat(l.coverage, "。"), "small-note"), block("① 共同起点", "本爻从 ".concat(l.base, " 分起算。其他五个爻会各自再算一份。")));
      const local = block("② 本爻自身的加减项", "");
      local.lastChild.remove();
      if (!l.local_items.length) local.append(el("p", "没有可加入的自身贡献。"));
      l.local_items.forEach((c) => local.append(el("p", "".concat(c.detail, "：").concat(c.enabled ? signed(c.value) + " 分" : "已停用，计 0 分", "（").concat(c.rule_id, "）"))));
      local.append(el("p", "".concat(l.base).concat(l.local_items.map((c) => " + (" + c.value + ")").join(""), " = ").concat(l.local_raw, " → 限在 0～10 后为 ").concat(l.local_score, " 分"), "formula"), el("p", "这是第一轮局部分，供本爻作为来源时使用。合计显示保留三位小数。", "small-note"));
      body.append(local);
      const incoming = block("③ 其他来源对本爻的作用", "");
      incoming.lastChild.remove();
      if (!l.incoming_items.length) incoming.append(el("p", "本卦没有其他发动或实验暗动来源，本项为 0。"));
      l.incoming_items.forEach((c) => {
        const d = details("".concat(c.detail, "：").concat(signed(c.value), " 分"));
        d.append(el("p", "".concat(c.enabled ? c.parameter : 0, "（").concat(c.name).concat(c.enabled ? "" : "，已停用", "） × ").concat(c.multipliers.map((m) => "".concat(m.value, "（").concat(m.name, "）")).join(" × "), " = ").concat(c.value, " 分"), "formula"));
        incoming.append(d);
      });
      body.append(incoming);
      const ownSum = l.local_items.reduce((s, c) => s + c.value, 0), effectSum = l.incoming_items.reduce((s, c) => s + c.value, 0);
      body.append(
        block("④ 合成最终强度", "".concat(l.base, "（起点） + (").concat(Math.round(ownSum * 1e6) / 1e6, ")（自身项） + (").concat(Math.round(effectSum * 1e6) / 1e6, ")（外来作用） = ").concat(l.raw_score, "；限制在 0～10 后为 ").concat(l.score, " 分。")),
        block("⑤ 分数怎样使用", "低于 ".concat(l.weak, " 为偏弱，高于 ").concat(l.strong, " 为偏强，两端之间及边界为中等。本爻标为“").concat(l.level, "”。这只描述实验相对强度，是否有利须看它在本问中的作用。"))
      );
    }
    select.onchange = render;
    render();
  }
  function attachLedger(box, { rule, api, version, input }) {
    const host = details("查看实际计算：这张卦每个爻的分数从哪来");
    host.id = "rule-calculation";
    box.append(host);
    const content = el("div");
    host.append(content);
    let loaded = false;
    host.addEventListener("toggle", async () => {
      if (!host.open || loaded) return;
      loaded = true;
      content.replaceChildren(el("p", "正在读取本卦计算…"));
      try {
        const payload = { rule_id: rule.id, value: rule.value, enabled: rule.enabled, expected_version: version };
        if (input) payload.input = input;
        const r = await api("/api/rules/preview", payload);
        if (!box.contains(host)) return;
        content.replaceChildren(el("p", r.example + " · " + r.chart_name, "guide-lead"));
        const trace = el("section");
        content.append(trace);
        ledger(trace, r.before_trace, "当前参数计算明细");
      } catch (e) {
        loaded = false;
        content.replaceChildren(el("p", e.message));
      }
    });
  }
  function comparison(output, result) {
    output.replaceChildren(el("p", result.example + " · " + result.chart_name, "small-note"));
    const table = el("table", "", "trial-table"), head = el("tr");
    ["爻位", "调整前", "调整后", "变化"].forEach((t) => head.append(el("th", t)));
    table.append(head);
    result.before.forEach((a, i) => {
      const b = result.after[i], tr = el("tr");
      ["".concat(a.position, " ").concat(a.name), "".concat(a.score, " ").concat(a.level), "".concat(b.score, " ").concat(b.level), signed(Math.round((b.score - a.score) * 1e3) / 1e3)].forEach((t) => tr.append(el("td", String(t))));
      table.append(tr);
    });
    output.append(table);
    if (result.before.every((a, i) => a.score === result.after[i].score)) output.append(el("p", "六爻最终分数没有变化。请查看本项类型、是否命中、是否停用或达到 0/10 边界；排序、摘要与结构开关也可能只改变分数以外的内容。", "topic-help"));
    if (["switch", "branch"].includes(result.rule_kind)) {
      const d = details("比较结构识别与动变标记");
      d.append(el("p", "以下结构仅说明是否识别，不直接代表吉凶。", "small-note"));
      for (const [key, label] of [["before_structures", "调整前"], ["after_structures", "调整后"]]) {
        d.append(el("h4", label));
        const v = result[key];
        d.append(el("p", "配对 ".concat(v.pairs.length, " 组，三合／半合 ").concat(v.groups.length, " 组")));
        v.groups.forEach((g) => d.append(el("p", g.type + "：第" + g.positions.join("、") + "爻")));
        v.changes.forEach((c) => d.append(el("p", "第" + c.position + "爻：" + (c.effects.join("、") || "无动变标记"))));
      }
      output.append(d);
    }
    if (result.rule_kind === "ranking") output.append(el("p", "本次试算没有执行 AI 取用，不能判断本问应选哪个候选。这类参数只用于同类候选排序，六爻强度保持原样；排序公式见上方说明。", "topic-help"));
    if (result.rule_kind === "summary_factor") output.append(el("p", "本次未建立主辅功能候选，故不伪造本卦的辅助摘要。此参数只改变摘要乘积，六爻分数不变；可按上方 6 分来源的公式示例核对。", "topic-help"));
    result.after_hidden.forEach((h, i) => {
      var _a, _b;
      return output.append(el("p", "第".concat(h.position, "爻下伏神：").concat((_b = (_a = result.before_hidden[i]) == null ? void 0 : _a.strength.score) != null ? _b : "—", " → ").concat(h.strength.score, " 分"), "small-note"));
    });
    for (const [key, title] of [["before_trace", "调整前完整账单"], ["after_trace", "调整后完整账单"]]) {
      const d = details(title), host = el("div");
      d.append(host);
      ledger(host, result[key], title);
      output.append(d);
    }
    output.append(el("p", result.note, "small-note"));
  }
  window.RuleGuideUI = { overview, attachLedger, comparison };
})();
