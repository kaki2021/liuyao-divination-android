"use strict";
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
  var _a;
  const $ = (id) => document.getElementById(id);
  const STATES = [
    { value: "old_yin", label: "老阴", marker: "×", yang: false, moving: true },
    { value: "young_yang", label: "少阳", marker: "─", yang: true, moving: false },
    { value: "young_yin", label: "少阴", marker: "╌", yang: false, moving: false },
    { value: "old_yang", label: "老阳", marker: "○", yang: true, moving: true }
  ];
  const POSITIONS = ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"];
  const MEIBU = [
    { value: "circle", label: "⚪ 圆", trigram: "天 · 乾", bits: [1, 1, 1] },
    { value: "square", label: "囗 方", trigram: "地 · 坤", bits: [0, 0, 0] },
    { value: "1", label: "1", trigram: "雷 · 震", bits: [1, 0, 0] },
    { value: "2", label: "2", trigram: "泽 · 兑", bits: [1, 1, 0] },
    { value: "3", label: "3", trigram: "水 · 坎", bits: [0, 1, 0] },
    { value: "4", label: "4", trigram: "山 · 艮", bits: [0, 0, 1] },
    { value: "5", label: "5", trigram: "火 · 离", bits: [1, 0, 1] },
    { value: "6", label: "6", trigram: "风 · 巽", bits: [0, 1, 1] }
  ];
  const TAIJI = { "222": "old_yin", "223": "young_yang", "233": "young_yin", "333": "old_yang" };
  const STATUS = { queued: "等待分析", running: "分析中", completed: "已完成", partial: "部分完成", unresolved: "待补充", failed: "分析未完成", saved: "已排盘", recorded: "已记录" };
  const STAGES = { intent_clarification: "正在梳理所问与真念", intent: "正在梳理所问与真念", selection: "正在分析取用关系", use_spirit_selection: "正在分析取用关系", use_spirit: "正在分析取用关系", interpretation: "正在核对关系与依据", report: "正在整理分析报告", report_generation: "正在整理分析报告" };
  const state = { config: null, caseId: null, revision: 0, input: null, chart: null, runs: [], runId: null, reportCurrent: true, busy: false, analyzing: false, loadToken: 0, rawReplyToken: 0, rawReplyLoaded: false, originalTime: null, originalTimeLocal: null, originalCasting: null, view: "input", pendingContext: null };
  let runSelect = null, currentJob = null, wakePoll = null, rawLoading = false, rawSignature = null, lastRawCheck = 0, rawReloadPending = false;
  function node(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== void 0 && text !== null) el.textContent = String(text);
    return el;
  }
  function clear(el) {
    el.replaceChildren();
  }
  function readable(value) {
    var _a2, _b, _c, _d, _e, _f, _g, _h;
    if (value === void 0 || value === null) return "";
    if (typeof value === "string" || typeof value === "number") return String(value);
    if (Array.isArray(value)) return value.map(readable).filter(Boolean).join("\n");
    if (typeof value === "object") return readable((_h = (_g = (_f = (_e = (_d = (_c = (_b = (_a2 = value.text) != null ? _a2 : value.content) != null ? _b : value.message) != null ? _c : value.description) != null ? _d : value.question) != null ? _e : value.reason) != null ? _f : value.summary) != null ? _g : value.gap) != null ? _h : "");
    return "";
  }
  function dateText(value) {
    const date = new Date(value);
    return !value || Number.isNaN(date.valueOf()) ? "时间未记录" : date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
  }
  function analysisLabel(run) {
    const index = state.runs.findIndex((item) => item.analysis_run_id === (run == null ? void 0 : run.analysis_run_id));
    const date = new Date(run == null ? void 0 : run.analyzed_at);
    const stamp = (run == null ? void 0 : run.analyzed_at) && !Number.isNaN(date.valueOf()) ? date.toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }) : "时间未记录";
    return "".concat(index >= 0 ? "第 ".concat(index + 1, " 次分析") : "所选分析", " · ").concat(stamp, " · ").concat(STATUS[run == null ? void 0 : run.status] || "已记录");
  }
  function banner(text, kind = "") {
    const el = $("global-message");
    el.textContent = text;
    el.className = "message-banner ".concat(kind);
    el.hidden = !text;
    if (text && kind === "error" && matchMedia("(max-width:760px)").matches) el.scrollIntoView({ block: "center" });
  }
  function getError(error) {
    return error && error.message ? error.message : "操作未完成，请稍后重试。";
  }
  function uuid() {
    return window.LiuyaoCompat.requestId();
  }
  async function api(path, { method = "GET", data } = {}) {
    var _a2, _b;
    const headers = { "X-App-Request": "1", Accept: "application/json" };
    if (method !== "GET") {
      headers["Content-Type"] = "application/json";
      headers["X-Idempotency-Key"] = uuid();
    }
    const response = await new Promise((resolve, reject) => {
      const request = new XMLHttpRequest();
      request.open(method, path);
      request.timeout = 12e3;
      Object.entries(headers).forEach(([key, value]) => request.setRequestHeader(key, value));
      request.onload = () => resolve({ ok: request.status >= 200 && request.status < 300, text: request.responseText });
      request.onerror = () => reject(new Error("本地状态连接中断，请检查应用是否仍在运行。"));
      request.ontimeout = () => reject(new Error("本地服务 12 秒内未响应。"));
      request.send(data === void 0 ? null : JSON.stringify(data));
    });
    let payload;
    try {
      payload = JSON.parse(response.text);
    } catch (_) {
      throw new Error("服务没有返回可读取的结果，请重试。");
    }
    if (!response.ok || payload.error && !payload.status) {
      const error = new Error(((_a2 = payload.error) == null ? void 0 : _a2.message) || "操作未完成，请重试。");
      error.code = (_b = payload.error) == null ? void 0 : _b.code;
      throw error;
    }
    return payload;
  }
  function setBusy(value) {
    state.busy = value;
    document.querySelectorAll("#case-form button, #case-form input, #case-form textarea, #case-form select, #context-form button, #feedback-form button, #new-case, .history-item").forEach((el) => {
      el.disabled = value;
    });
    updatePersonFields();
    $("case-form").setAttribute("aria-busy", String(value));
    $("analyze-current-case").disabled = value;
    $("analyze-current-case").textContent = value && state.analyzing ? "分析进行中…" : "重新解卦";
    if (runSelect) runSelect.disabled = value;
  }
  function showView(view, { scroll = false } = {}) {
    var _a2;
    const requested = ["input", "results", "feedback"].includes(view) ? view : "input";
    state.view = state.caseId ? requested : "input";
    document.body.dataset.view = state.view;
    ["input", "results", "feedback"].forEach((name) => {
      const selected = name === state.view;
      const tab = $("tab-".concat(name));
      $("".concat(name, "-section")).hidden = !selected;
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
      tab.disabled = name !== "input" && !state.caseId;
    });
    const headings = { input: ["从一个真实的问题开始。", "选择起卦方式，记录结果，理清此刻关心的事。"], results: ["看清卦象，回答所问。", "查看排盘、综合结论与判断依据，也可以补充情况继续解卦。"], feedback: ["记下后来发生的事。", "将实际进展与这次案例的分析保存在一起。"] };
    $("workspace-title").textContent = headings[state.view][0];
    $("workspace-description").textContent = headings[state.view][1];
    $("feedback-question").textContent = ((_a2 = state.input) == null ? void 0 : _a2.question) || "";
    if (scroll) $("".concat(state.view, "-section")).scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function createYao(stateValue, sizeClass = "") {
    const definition = STATES.find((item) => item.value === stateValue);
    const el = node("span", "yao ".concat(sizeClass, " ").concat(!definition ? "unknown" : "", " ").concat((definition == null ? void 0 : definition.moving) ? "moving" : "").trim());
    el.setAttribute("aria-hidden", "true");
    el.append(node("span"));
    if (!definition || !definition.yang) el.append(node("span"));
    return el;
  }
  function buildInputs() {
    POSITIONS.forEach((label, index) => {
      const row = node("div", "line-row");
      row.append(node("span", "line-label", label));
      const fieldset = node("fieldset", "line-options");
      fieldset.append(node("legend", "sr-only", "第".concat(index + 1, "次，").concat(label)));
      STATES.forEach((definition) => {
        const option = node("label", "state-option");
        const radio = document.createElement("input");
        radio.type = "radio";
        radio.name = "line-".concat(index + 1);
        radio.value = definition.value;
        radio.required = true;
        radio.setAttribute("aria-label", "".concat(label, "，").concat(definition.label).concat(definition.moving ? "，动爻" : "，静爻"));
        const face = node("span", "option-face");
        face.append(node("span", "option-mark", definition.marker), node("span", "", definition.label));
        option.append(radio, face);
        fieldset.append(option);
        radio.addEventListener("change", onInputChange);
      });
      row.append(fieldset);
      $("line-inputs").append(row);
    });
    ["第一次 · 下卦", "第二次 · 上卦", "第三次 · 动爻"].forEach((label, index) => {
      const fieldset = node("fieldset", "meibu-group");
      fieldset.append(node("legend", "", label), node("p", "meibu-group-note", index < 2 ? "这次的数字对应八卦" : "这次的数字对应爻位"));
      const options = node("div", "meibu-options");
      MEIBU.forEach((definition) => {
        const detail = index < 2 ? definition.trigram : definition.value === "circle" ? "六爻全动" : definition.value === "square" ? "六爻全静" : "".concat(POSITIONS[Number(definition.value) - 1], "动");
        options.append(makeCastingOption("meibu-".concat(index + 1), definition.value, definition.label, detail, "".concat(label, "，").concat(definition.label, "，").concat(detail), "meibu-option"));
      });
      fieldset.append(options);
      $("meibu-inputs").append(fieldset);
    });
    POSITIONS.forEach((label, index) => {
      const row = node("div", "line-row taiji-row");
      row.append(node("span", "line-label", "第".concat(index + 1, "次")));
      const fieldset = node("fieldset", "line-options taiji-options");
      fieldset.append(node("legend", "sr-only", "第".concat(index + 1, "次，").concat(label)));
      Object.entries(TAIJI).forEach(([combo, value]) => {
        const definition = STATES.find((item) => item.value === value);
        fieldset.append(makeCastingOption("taiji-".concat(index + 1), combo, combo, "".concat(definition.label).concat(definition.moving ? " · 动" : ""), "第".concat(index + 1, "次，组合").concat(combo, "，").concat(definition.label), "taiji-option"));
      });
      row.append(fieldset);
      $("taiji-inputs").append(row);
    });
    document.querySelectorAll('input[name="casting-method"]').forEach((radio) => radio.addEventListener("change", updateCastingMode));
    updateCastingMode();
  }
  function makeCastingOption(name, value, label, detail, accessibleLabel, extraClass) {
    const option = node("label", "state-option ".concat(extraClass));
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = name;
    radio.value = value;
    radio.setAttribute("aria-label", accessibleLabel);
    const face = node("span", "option-face");
    face.append(node("strong", "casting-option-label", label), node("small", "casting-option-detail", detail));
    option.append(radio, face);
    radio.addEventListener("change", onInputChange);
    return option;
  }
  function castingMethod() {
    var _a2;
    return ((_a2 = document.querySelector('input[name="casting-method"]:checked')) == null ? void 0 : _a2.value) || "meibu";
  }
  function selectedCastingResults(method = castingMethod()) {
    const count = method === "meibu" ? 3 : 6;
    return Array.from({ length: count }, (_, index) => {
      var _a2;
      return ((_a2 = document.querySelector('input[name="'.concat(method, "-").concat(index + 1, '"]:checked'))) == null ? void 0 : _a2.value) || null;
    });
  }
  function taijiCombination(value) {
    return typeof value === "string" && /^[23]{3}$/.test(value) ? [...value].sort().join("") : null;
  }
  function linesFromCasting(method, results) {
    if (method === "taiji") return Array.from({ length: 6 }, (_, index) => TAIJI[taijiCombination(results[index])] || null);
    if (method !== "meibu" || results.length !== 3 || results.some((value) => !MEIBU.some((item) => item.value === value))) return Array(6).fill(null);
    const bits = [...MEIBU.find((item) => item.value === results[0]).bits, ...MEIBU.find((item) => item.value === results[1]).bits];
    return bits.map((yang, index) => {
      const moving = results[2] === "circle" || results[2] === String(index + 1);
      return yang ? moving ? "old_yang" : "young_yang" : moving ? "old_yin" : "young_yin";
    });
  }
  function selectedLines() {
    const method = castingMethod();
    if (method === "direct") return POSITIONS.map((_, index) => {
      var _a2;
      return ((_a2 = document.querySelector('input[name="line-'.concat(index + 1, '"]:checked'))) == null ? void 0 : _a2.value) || null;
    });
    return linesFromCasting(method, selectedCastingResults(method));
  }
  function updateCastingMode() {
    const method = castingMethod();
    $("meibu-inputs").hidden = method !== "meibu";
    $("taiji-inputs").hidden = method !== "taiji";
    $("line-inputs").hidden = method !== "direct";
    $("casting-instruction").textContent = method === "meibu" ? "三次摸取：第一次定下卦，第二次定上卦，第三次定动爻。" : method === "taiji" ? "每次选三颗丸显示的组合，共记录六次；223、233 不区分数字先后。" : "已有六爻结果时，从初爻到上爻依次选择阴阳动静。";
    document.querySelector(".casting-layout").classList.toggle("meibu-layout", method === "meibu");
    onInputChange();
  }
  function hasEnteredData() {
    var _a2;
    return Boolean($("question").value.trim() || $("cast-time").value || getPersonInfo(false) || ((_a2 = window.Buzhai) == null ? void 0 : _a2.read(false)) || document.querySelector('#case-form input[type="radio"]:checked:not([name="casting-method"])'));
  }
  function updatePersonFields({ clearIrrelevant = false } = {}) {
    const isSelf = ($("person-subject").value || "unspecified") === "self";
    if (isSelf && clearIrrelevant) ["subject-age", "person-relationship"].forEach((id) => {
      $(id).value = "";
    });
    const hasRelationship = Boolean($("person-relationship").value.trim());
    $("subject-fields").hidden = isSelf && !hasRelationship;
    $("subject-age-field").hidden = isSelf;
    $("subject-age").disabled = isSelf || state.busy;
    $("person-relationship").disabled = isSelf && !hasRelationship || state.busy;
  }
  function canonicalPersonInfo(value) {
    if (!value || typeof value !== "object") return null;
    const subject = ["self", "other", "unspecified"].includes(value.subject) ? value.subject : "unspecified";
    const result = { subject };
    if (value.querent_age !== void 0 && value.querent_age !== null && value.querent_age !== "") result.querent_age = value.querent_age;
    if (subject !== "self") {
      if (value.subject_age !== void 0 && value.subject_age !== null && value.subject_age !== "") result.subject_age = value.subject_age;
    }
    if (typeof value.profile_id === "string" && value.profile_id) result.profile_id = value.profile_id;
    if (typeof value.relationship === "string" && value.relationship.trim()) result.relationship = value.relationship.trim();
    if (typeof value.background === "string" && value.background.trim()) result.background = value.background.trim();
    return subject === "unspecified" && Object.keys(result).length === 1 ? null : result;
  }
  function getPersonInfo(validate = true) {
    var _a2;
    const subject = $("person-subject").value || "unspecified";
    const result = { subject, background: $("person-background").value, relationship: $("person-relationship").value, profile_id: ((_a2 = $("profile-select")) == null ? void 0 : _a2.value) || "" };
    [["querent-age", "querent_age", "问卦人"], ["subject-age", "subject_age", "所问对象"]].forEach(([id, key, label]) => {
      if (key === "subject_age" && subject === "self") return;
      const raw = $(id).value.trim();
      if (!raw) return;
      const age = Number(raw);
      if (validate && (!Number.isInteger(age) || age < 0 || age > 150)) {
        $(id).focus();
        throw new Error("".concat(label, "的年龄请填写 0 至 150 的整数周岁，或留空。"));
      }
      result[key] = Number.isFinite(age) ? age : raw;
    });
    return canonicalPersonInfo(result);
  }
  function renderPreview() {
    var _a2;
    const lines = selectedLines();
    const view = window.LiuyaoChartDisplay.preview(lines);
    clear($("hex-preview-lines"));
    clear($("changed-preview-lines"));
    for (let index = 5; index >= 0; index--) {
      const definition = STATES.find((item) => item.value === lines[index]);
      const row = node("div", "preview-line");
      row.setAttribute("aria-label", "".concat(POSITIONS[index], "：").concat(definition ? definition.label : "未选择"));
      row.append(node("span", "preview-position", index === 0 ? "初" : index === 5 ? "上" : String(index + 1)), createYao(lines[index]), node("span", "motion-marker", (definition == null ? void 0 : definition.moving) ? definition.marker : ""));
      $("hex-preview-lines").append(row);
      if (view.changed_structure) {
        const changedState = view.changed_structure.bits[index] ? "young_yang" : "young_yin";
        const changed = node("div", "preview-line ".concat((definition == null ? void 0 : definition.moving) ? "changed-position" : ""));
        changed.setAttribute("aria-label", "".concat(POSITIONS[index], "：变后").concat(view.changed_structure.bits[index] ? "阳爻" : "阴爻").concat((definition == null ? void 0 : definition.moving) ? "，由动爻变化" : ""));
        changed.append(node("span", "preview-position", index === 0 ? "初" : index === 5 ? "上" : String(index + 1)), createYao(changedState), node("span", "motion-marker", (definition == null ? void 0 : definition.moving) ? "←" : ""));
        $("changed-preview-lines").append(changed);
      }
    }
    $("preview-main-name").textContent = view.main.name;
    $("preview-changed-name").textContent = ((_a2 = view.changed_structure) == null ? void 0 : _a2.name) || (view.complete ? "静卦" : "待录入完整");
    $("changed-preview-lines").hidden = !view.changed_structure;
    $("preview-changed-status").hidden = Boolean(view.changed_structure);
    $("preview-changed-status").textContent = view.complete ? "六爻皆静，无变卦" : "录入完整后显示";
    $("preview-hint").textContent = !view.complete ? "完成选择后立即显示本卦与变卦，不需要先调用 AI。" : view.moving_positions.length ? "动爻：".concat(view.moving_positions.map((position) => POSITIONS[position - 1]).join("、"), "。保存后可查看六亲、纳支和逐爻对照。") : "六爻皆静；保存后可查看本卦完整排盘。";
  }
  function localDateTime(date) {
    const pad = (n) => String(n).padStart(2, "0");
    return "".concat(date.getFullYear(), "-").concat(pad(date.getMonth() + 1), "-").concat(pad(date.getDate()), "T").concat(pad(date.getHours()), ":").concat(pad(date.getMinutes()), ":").concat(pad(date.getSeconds()));
  }
  function getInput(validate = true) {
    var _a2, _b;
    const question = $("question").value;
    if (validate && !question.trim()) {
      $("question").focus();
      throw new Error("先写下这次想问的问题。");
    }
    const method = castingMethod();
    const input = { question };
    if (method === "direct") {
      const lines = selectedLines();
      const missing = lines.findIndex((item) => !item);
      if (validate && missing !== -1) {
        document.querySelector('input[name="line-'.concat(missing + 1, '"]')).focus();
        throw new Error("请补选".concat(POSITIONS[missing], "，六爻都需要明确的阴阳动静。"));
      }
      input.lines = lines;
    } else {
      let results = selectedCastingResults(method);
      const missing = results.findIndex((item) => !item);
      if (validate && missing !== -1) {
        document.querySelector('input[name="'.concat(method, "-").concat(missing + 1, '"]')).focus();
        throw new Error(method === "meibu" ? "请补选第".concat(missing + 1, "次摸取的结果。") : "请补选第".concat(missing + 1, "次摇卦的数字组合。"));
      }
      if (method === "taiji" && ((_a2 = state.originalCasting) == null ? void 0 : _a2.method) === "taiji") results = results.map((value, index) => taijiCombination(state.originalCasting.results[index]) === value ? state.originalCasting.results[index] : value);
      input.casting = { method, results };
    }
    if ($("cast-time").value) {
      const date = new Date($("cast-time").value);
      if (Number.isNaN(date.valueOf())) throw new Error("请检查实际起卦时间。");
      input.actual_cast_time = state.originalTimeLocal === $("cast-time").value && state.originalTime ? state.originalTime : date.toISOString();
    }
    const personInfo = getPersonInfo(validate);
    if (personInfo) input.person_info = personInfo;
    const buzhai = (_b = window.Buzhai) == null ? void 0 : _b.read(validate);
    if (buzhai) input.buzhai = buzhai;
    return input;
  }
  function inputsEqual(first, second) {
    var _a2, _b;
    if (!first || !second || first.question !== second.question || (first.actual_cast_time || null) !== (second.actual_cast_time || null)) return false;
    if (JSON.stringify(canonicalPersonInfo(first.person_info)) !== JSON.stringify(canonicalPersonInfo(second.person_info))) return false;
    if (((_a2 = window.Buzhai) == null ? void 0 : _a2.canonical(first.buzhai)) !== ((_b = window.Buzhai) == null ? void 0 : _b.canonical(second.buzhai))) return false;
    if (first.casting || second.casting) return Boolean(first.casting && second.casting && first.casting.method === second.casting.method && JSON.stringify(first.casting.results) === JSON.stringify(second.casting.results));
    return JSON.stringify(first.lines) === JSON.stringify(second.lines);
  }
  function onInputChange() {
    renderPreview();
    $("question-count").textContent = "".concat($("question").value.length, " / 2000");
    let changed = false;
    try {
      changed = state.caseId && !inputsEqual(getInput(false), state.input);
    } catch (_) {
      changed = Boolean(state.caseId);
    }
    $("revision-fields").hidden = !changed;
    $("save-case").textContent = changed ? "保存修改并排盘" : "保存并排盘";
    $("analyze-case").replaceChildren(document.createTextNode(state.caseId && !changed ? "重新分析 " : "保存并分析 "), node("span", "", "↗"));
    if (changed) $("case-state").textContent = "有未保存的修改";
    else $("case-state").textContent = state.caseId ? "已保存" : "新案例";
  }
  function fillInput(input) {
    var _a2, _b, _c, _d;
    $("case-form").reset();
    $("question").value = (input == null ? void 0 : input.question) || "";
    (_a2 = window.Buzhai) == null ? void 0 : _a2.fill(input == null ? void 0 : input.buzhai);
    const person = canonicalPersonInfo(input == null ? void 0 : input.person_info);
    $("person-subject").value = (person == null ? void 0 : person.subject) || "unspecified";
    (_b = window.LiuyaoV5) == null ? void 0 : _b.setProfile((person == null ? void 0 : person.profile_id) || "");
    $("querent-age").value = (person == null ? void 0 : person.querent_age) === void 0 ? "" : String(person.querent_age);
    $("subject-age").value = (person == null ? void 0 : person.subject_age) === void 0 ? "" : String(person.subject_age);
    $("person-relationship").value = (person == null ? void 0 : person.relationship) || "";
    $("person-background").value = (person == null ? void 0 : person.background) || "";
    $("person-details").open = Boolean(person);
    updatePersonFields();
    state.originalCasting = (input == null ? void 0 : input.casting) ? { method: input.casting.method, results: [...input.casting.results] } : null;
    const method = ["meibu", "taiji"].includes((_c = input == null ? void 0 : input.casting) == null ? void 0 : _c.method) ? input.casting.method : input ? "direct" : "meibu";
    document.querySelector('input[name="casting-method"][value="'.concat(method, '"]')).checked = true;
    if (method !== "direct") (((_d = input == null ? void 0 : input.casting) == null ? void 0 : _d.results) || []).forEach((raw, index) => {
      const value = method === "taiji" ? taijiCombination(raw) : raw;
      if (method === "meibu" && MEIBU.some((item) => item.value === value) || method === "taiji" && TAIJI[value]) {
        const radio = document.querySelector('input[name="'.concat(method, "-").concat(index + 1, '"][value="').concat(value, '"]'));
        if (radio) radio.checked = true;
      }
    });
    ((input == null ? void 0 : input.lines) || []).forEach((value, index) => {
      if (STATES.some((item) => item.value === value)) {
        const radio = document.querySelector('input[name="line-'.concat(index + 1, '"][value="').concat(value, '"]'));
        if (radio) radio.checked = true;
      }
    });
    const rawTime = input == null ? void 0 : input.actual_cast_time;
    const date = rawTime ? new Date(rawTime) : null;
    state.originalTime = rawTime || null;
    state.originalTimeLocal = date && !Number.isNaN(date.valueOf()) ? localDateTime(date) : null;
    $("cast-time").value = state.originalTimeLocal || "";
    $("time-details").open = Boolean(rawTime);
    $("revision-reason").value = "";
    updateCastingMode();
  }
  function resetCase() {
    if (state.busy) return;
    if (!mayDiscard()) return;
    window.AnalysisStatus.clear();
    currentJob = null;
    state.loadToken++;
    state.caseId = null;
    state.revision = 0;
    state.input = null;
    state.chart = null;
    state.runs = [];
    state.runId = null;
    state.pendingContext = null;
    resetRawReplies();
    fillInput(null);
    $("results-section").hidden = true;
    $("form-title").textContent = "此刻，你想问什么？";
    $("context-text").value = "";
    $("feedback-text").value = "";
    if ($("feedback-occurred")) $("feedback-occurred").value = "";
    if ($("feedback-notes")) $("feedback-notes").value = "";
    if ($("feedback-match")) $("feedback-match").value = "pending";
    banner("");
    renderHistoryActive();
    showView("input");
    $("question").focus();
  }
  function mayDiscard() {
    let dirty = false;
    try {
      dirty = hasEnteredData() && !inputsEqual(getInput(false), state.input);
    } catch (_) {
      dirty = true;
    }
    dirty = dirty || Boolean($("context-text").value.trim() || $("feedback-text").value.trim());
    return !dirty || window.confirm("还有未完成的输入，确定离开这次案例吗？");
  }
  async function refreshHistory() {
    const result = await api("/api/cases");
    const list = $("history-list");
    clear(list);
    if (!(result.cases || []).length) {
      list.append(node("p", "empty-state", "还没有案例。第一卦，从这里开始。"));
      return;
    }
    const cases = [...result.cases].sort((a, b) => String(b.recorded_at || "").localeCompare(String(a.recorded_at || "")));
    cases.forEach((item) => {
      const button = node("button", "history-item");
      button.type = "button";
      button.dataset.caseId = item.case_id;
      button.disabled = state.busy;
      button.append(node("span", "history-question", item.question || "未命名的问题"));
      const meta = node("span", "history-meta");
      meta.append(node("span", "", dateText(item.recorded_at)), node("span", "", STATUS[item.status] || "已记录"));
      button.append(meta);
      button.addEventListener("click", () => {
        if (!state.busy && mayDiscard()) loadCase(item.case_id).catch((error) => banner(getError(error), "error"));
      });
      list.append(button);
    });
    renderHistoryActive();
  }
  function renderHistoryActive() {
    document.querySelectorAll(".history-item").forEach((el) => {
      el.classList.toggle("active", el.dataset.caseId === state.caseId);
      if (el.dataset.caseId === state.caseId) el.setAttribute("aria-current", "true");
      else el.removeAttribute("aria-current");
    });
  }
  function latestInput(record) {
    var _a2, _b;
    return ((_b = (_a2 = record.revisions) == null ? void 0 : _a2.at(-1)) == null ? void 0 : _b.input) || record.original_input || record.input || {};
  }
  async function loadCase(caseId, { keepForm = false, quiet = false, keepView = false } = {}) {
    var _a2, _b;
    const token = ++state.loadToken;
    const payload = await api("/api/cases/".concat(encodeURIComponent(caseId)));
    if (token !== state.loadToken) return;
    const record = payload.case || payload;
    if (state.caseId !== caseId) {
      window.AnalysisStatus.clear();
      currentJob = null;
      $("context-text").value = "";
      $("feedback-text").value = "";
      state.pendingContext = null;
    }
    state.caseId = caseId;
    state.revision = ((_b = (_a2 = record.revisions) == null ? void 0 : _a2.at(-1)) == null ? void 0 : _b.revision_seq) || payload.revision_seq || record.revision_seq || 1;
    state.input = latestInput(record);
    state.chart = payload.chart || record.chart;
    state.runs = record.analysis_runs || [];
    state.reportCurrent = payload.report_is_current !== false;
    if (!keepForm) fillInput(state.input);
    $("form-title").textContent = "回看这次所问";
    $("case-state").textContent = "已保存";
    $("results-section").hidden = false;
    $("export-case").href = "/api/cases/".concat(encodeURIComponent(caseId), "/export");
    $("export-diagnostics").href = "/api/cases/".concat(encodeURIComponent(caseId), "/diagnostics");
    renderChart(state.chart);
    renderEvents(record);
    renderRunSelector();
    const latestRun = state.runs.at(-1);
    if (payload.result) renderAnalysis(payload.result, (latestRun == null ? void 0 : latestRun.status) || payload.status || "completed", latestRun == null ? void 0 : latestRun.analysis_run_id);
    else if (payload.display_report) renderAnalysis({ display_report: payload.display_report }, (latestRun == null ? void 0 : latestRun.status) || "completed", latestRun == null ? void 0 : latestRun.analysis_run_id);
    else if (latestRun) renderRun(latestRun);
    else renderAnalysis(null, "saved");
    onInputChange();
    renderHistoryActive();
    if (!quiet) banner("");
    showView(keepView ? state.view : "results");
    if (payload.active_job_id && !state.analyzing) resumeJob(payload.active_job_id, caseId);
  }
  function appendMiniChart(container, structure, label) {
    const block = node("div", "chart-hex");
    const picture = node("div", "chart-mini");
    [...structure.bits || []].reverse().forEach((bit) => picture.append(createYao(bit ? "young_yang" : "young_yin")));
    const words = node("div");
    words.append(node("p", "chart-description", label), node("p", "chart-name", structure.name || "卦象"), node("p", "chart-description", "".concat(structure.upper_trigram || "", "上 · ").concat(structure.lower_trigram || "", "下").concat(structure.palace ? "　".concat(structure.palace, "宫").concat(structure.palace_element || "") : "")));
    block.append(picture, words);
    container.append(block);
  }
  function renderChart(chart, input = state.input, scope = "当前已保存输入的排盘") {
    var _a2, _b, _c, _d;
    (_a2 = window.LiuyaoV5) == null ? void 0 : _a2.setAnalysisContext(input);
    (_b = window.Buzhai) == null ? void 0 : _b.render(chart);
    $("result-question").textContent = (input == null ? void 0 : input.question) || "这次的排盘与解卦";
    clear($("chart-summary"));
    clear($("chart-lines"));
    $("chart-context").textContent = scope;
    $("chart-question").textContent = (input == null ? void 0 : input.question) || "";
    $("chart-question").hidden = !(input == null ? void 0 : input.question);
    renderPersonSummary(input == null ? void 0 : input.person_info);
    (_c = window.LiuyaoV5) == null ? void 0 : _c.renderComprehensive(chart);
    renderFoundation(chart == null ? void 0 : chart.basic_analysis);
    renderChartContext(chart);
    const casting = input == null ? void 0 : input.casting;
    const record = $("casting-record");
    record.hidden = !casting;
    if ((casting == null ? void 0 : casting.method) === "meibu") record.textContent = "枚卜丸原始记录：".concat(casting.results.map((value, index) => {
      var _a3;
      return "".concat(["下卦", "上卦", "动爻"][index], " ").concat(((_a3 = MEIBU.find((item) => item.value === value)) == null ? void 0 : _a3.label) || value);
    }).join(" → "));
    else if ((casting == null ? void 0 : casting.method) === "taiji") record.textContent = "太极丸原始记录（初爻至上爻）：".concat(casting.results.join(" / "));
    else record.textContent = "";
    if (!(chart == null ? void 0 : chart.main)) {
      window.LiuyaoPhoneChart.render(null);
      $("chart-summary").append(node("p", "empty-state", "这份记录没有可显示的排盘快照。"));
      document.querySelector(".chart-note").textContent = "";
      return;
    }
    appendMiniChart($("chart-summary"), chart.main, "本卦");
    if (chart.changed_structure) {
      $("chart-summary").append(node("span", "chart-arrow", "→"));
      appendMiniChart($("chart-summary"), chart.changed_structure, "变卦");
    } else {
      const staticBlock = node("div", "chart-static");
      staticBlock.append(node("p", "chart-description", "变卦"), node("p", "chart-name", "静卦"), node("p", "", "六爻皆静，无变卦"));
      $("chart-summary").append(node("span", "chart-arrow", "→"), staticBlock);
    }
    [...chart.main.lines || []].sort((a, b) => b.position - a.position).forEach((line) => {
      var _a3;
      const row = node("tr");
      row.append(node("td", "", POSITIONS[line.position - 1] || "".concat(line.position, "爻")), node("td", "six-spirit-cell", line.six_spirit ? line.six_spirit.replace("腾蛇", "螣蛇") : "—"));
      const yaoCell = node("td");
      const graphic = node("span", "table-yao");
      const definition = STATES.find((item) => item.value === line.state);
      graphic.append(createYao(line.state), node("span", "motion-marker", (definition == null ? void 0 : definition.moving) ? definition.marker : ""));
      graphic.setAttribute("aria-label", (definition == null ? void 0 : definition.label) || "");
      yaoCell.append(graphic);
      row.append(yaoCell);
      row.append(node("td", "", "".concat(line.branch || "").concat(line.element || "")), node("td", "", line.relative || "—"));
      const tags = node("td");
      if (line.is_shi) tags.append(node("span", "line-tag", "世"));
      if (line.is_ying) tags.append(node("span", "line-tag", "应"));
      if (line.is_shi_body) tags.append(node("span", "line-tag body-tag", "世身"));
      if (line.matches_gua_body) tags.append(node("span", "line-tag body-tag", "卦身"));
      if (!tags.childElementCount) tags.append(node("span", "small-note", "—"));
      row.append(tags);
      row.classList.toggle("moving-row", Boolean(line.moving));
      row.append(node("td", "line-transition", line.moving ? "".concat(line.yang ? "阳变阴" : "阴变阳", " →") : "—"));
      const changedCell = node("td", "changed-yao-cell");
      const changedBranch = node("td");
      if (chart.changed_structure) {
        const index = line.position - 1;
        const yang = Boolean(chart.changed_structure.bits[index]);
        const changedGraphic = node("span", "table-yao");
        changedGraphic.setAttribute("aria-label", "变卦".concat(POSITIONS[index], "，").concat(yang ? "阳爻" : "阴爻"));
        changedGraphic.append(createYao(yang ? "young_yang" : "young_yin"));
        changedCell.append(changedGraphic);
        const branch = ((_a3 = chart.changed_structure.branches) == null ? void 0 : _a3[index]) || "";
        changedBranch.textContent = branch + (window.LiuyaoChartDisplay.branchElement(branch) || "");
      } else {
        changedCell.textContent = "—";
        changedBranch.textContent = "—";
      }
      row.append(changedCell, changedBranch);
      $("chart-lines").append(row);
    });
    window.LiuyaoPhoneChart.render(chart);
    const bodyText = chart.gua_body_branch ? "卦身为".concat(chart.gua_body_branch).concat(((_d = chart.gua_body_positions) == null ? void 0 : _d.length) ? "，对应爻位已标出" : "，本卦未见对应地支", "。") : "";
    document.querySelector(".chart-note").textContent = "".concat(bodyText, " ").concat(chart.changed_structure ? "变卦整卦重新纳支，仅本卦动爻发生阴阳变化；动爻的变爻六亲按本卦宫五行确定。" : "六爻皆静，无变卦。", " 世应及身位标记属于本卦。");
  }
  function renderPersonSummary(value) {
    const container = $("chart-person-info");
    clear(container);
    const person = canonicalPersonInfo(value);
    container.hidden = !person;
    if (!person) return;
    const subjectLabels = { self: "问自己", other: "问他人", unspecified: "暂不指定或涉及多人" };
    const parts = [subjectLabels[person.subject]];
    if (person.querent_age !== void 0) parts.push("问卦人起卦时 ".concat(person.querent_age, " 周岁"));
    if (person.subject_age !== void 0) parts.push("所问对象起卦时 ".concat(person.subject_age, " 周岁"));
    if (person.relationship) parts.push("关系：".concat(person.relationship));
    container.append(node("p", "", parts.join(" · ")));
    if (person.background) container.append(node("p", "person-background-summary", person.background));
  }
  function renderFoundation(analysis) {
    const container = $("foundation-content");
    clear(container);
    const sections = Array.isArray(analysis == null ? void 0 : analysis.sections) ? analysis.sections : [];
    if (!sections.length) {
      container.append(node("p", "empty-state", "这份排盘记录没有基础分析快照。重新解卦后可查看本次计算结果。"));
      return;
    }
    sections.forEach((section, index) => {
      const items = (Array.isArray(section.items) ? section.items : []).filter((item) => item && typeof item.text === "string" && item.text);
      if (!items.length) return;
      const block = node("details", "foundation-section");
      block.open = index < 2 && items.length <= 6;
      block.append(node("summary", "", "".concat(section.title || "基础关系").concat(items.length > 6 ? "（".concat(items.length, " 项）") : "")));
      const list = node("ul", "foundation-items");
      items.forEach((item) => {
        const row = node("li", "", item.text);
        if (typeof item.id === "string") row.dataset.factId = item.id;
        list.append(row);
      });
      block.append(list);
      container.append(block);
    });
  }
  function renderChartContext(chart) {
    var _a2, _b;
    const summary = $("calendar-summary");
    clear(summary);
    const calendar = chart == null ? void 0 : chart.calendar;
    const computed = (calendar == null ? void 0 : calendar.status) === "computed";
    if (computed) {
      const pillars = node("dl", "four-pillars");
      [["year", "年柱"], ["month", "月柱"], ["day", "日柱"], ["hour", "时柱"]].forEach(([key, label]) => {
        var _a3;
        const pair = node("div");
        pair.append(node("dt", "", label), node("dd", "", ((_a3 = calendar.pillars) == null ? void 0 : _a3[key]) || "—"));
        pillars.append(pair);
      });
      summary.append(pillars);
      if (calendar.cast_time) summary.append(node("p", "calendar-time", "起卦时间：".concat(calendar.cast_time.slice(0, 19).replace("T", " "), " · 北京时间（UTC+08:00）")));
    } else summary.append(node("p", "small-note", (calendar == null ? void 0 : calendar.message) || "这份记录尚无四柱与六神资料。"));
    $("calendar-details").hidden = !(calendar == null ? void 0 : calendar.convention_label);
    $("calendar-convention").textContent = (calendar == null ? void 0 : calendar.convention_label) || "";
    const bodyLine = (_b = (_a2 = chart == null ? void 0 : chart.main) == null ? void 0 : _a2.lines) == null ? void 0 : _b.find((line) => line.is_shi_body || line.position === chart.shi_body_position);
    const bodyPosition = bodyLine ? POSITIONS[bodyLine.position - 1] : null;
    const guaPositions = (chart == null ? void 0 : chart.gua_body_positions) || [];
    $("body-summary").hidden = !(chart == null ? void 0 : chart.main);
    $("body-summary").textContent = (chart == null ? void 0 : chart.main) ? "世身：".concat(bodyPosition || "未确定").concat((bodyLine == null ? void 0 : bodyLine.branch) ? " · ".concat(bodyLine.branch).concat(bodyLine.element || "") : "", "　卦身：").concat(chart.gua_body_branch || "未确定").concat(guaPositions.length ? " · ".concat(guaPositions.map((position) => POSITIONS[position - 1]).join("、")) : chart.gua_body_branch ? " · 本卦未见对应地支" : "") : "";
  }
  function appendListBlock(container, items, title, className) {
    const values = (Array.isArray(items) ? items : items ? [items] : []).map(readable).filter(Boolean);
    if (!values.length) return;
    const block = node("div", className);
    block.append(node("h4", "", title));
    const list = node("ul");
    values.forEach((text) => list.append(node("li", "", text)));
    block.append(list);
    container.append(block);
  }
  function renderConclusion(container, conclusion) {
    const directions = { favorable: "偏顺利", unfavorable: "阻力较多", mixed: "有利有弊", undetermined: "暂不能判断" };
    const direction = Object.hasOwn(directions, conclusion.direction) ? conclusion.direction : "undetermined";
    const card = node("section", "conclusion-card conclusion-".concat(direction));
    const heading = node("div", "conclusion-heading");
    heading.append(node("h3", "", "综合结论"), node("span", "conclusion-direction", directions[direction]));
    card.append(heading, node("p", "conclusion-answer", readable(conclusion.answer)), node("p", "conclusion-source", "AI 条件判断"));
    container.append(card);
  }
  function renderAnalysisError(container, error) {
    const detail = typeof error === "object" && error ? error : { message: readable(error) };
    const stages = { intent: "理解问题", intent_clarification: "理解问题", selection: "确定取用", use_spirit: "取用", use_spirit_selection: "取用", interpretation: "解卦", report: "报告", report_generation: "报告" };
    const stage = stages[detail.stage];
    const block = node("section", "analysis-error");
    block.append(node("h3", "", stage ? "".concat(stage, "阶段未完成") : "这次分析未完成"));
    block.append(node("p", "analysis-error-message", readable(detail.message) || "本次分析未完成，输入与排盘已保留。"));
    block.append(node("p", "analysis-error-suggestion", readable(detail.suggestion) || "可以点击“重新解卦”。如果再次失败，导出诊断文件后可据此排查。"));
    if (detail.validation_detail || detail.code || detail.stage) {
      const technical = node("details", "analysis-error-details");
      technical.append(node("summary", "", "查看技术详情"));
      const lines = [detail.code && "错误代码：".concat(detail.code), detail.stage && "分析阶段：".concat(detail.stage), detail.attempts && "尝试次数：".concat(detail.attempts), readable(detail.validation_detail)].filter(Boolean);
      technical.append(node("pre", "", lines.join("\n")));
      block.append(technical);
    }
    container.append(block);
  }
  function resetRawReplies() {
    state.rawReplyToken++;
    state.rawReplyLoaded = false;
    const details = $("ai-raw-replies");
    if (details.dataset.runId !== (state.runId || "")) details.open = false;
    details.dataset.runId = state.runId || "";
    details.hidden = !state.runId;
    clear($("ai-raw-replies-content"));
    const run = state.runs.find((item) => item.analysis_run_id === state.runId);
    $("ai-raw-replies-context").textContent = state.runId ? "当前查看：".concat(run ? analysisLabel(run) : "所选分析", "。").concat(state.runs.length > 1 ? "本案例共 ".concat(state.runs.length, " 次分析，可通过“回看分析”切换。") : "") : "";
  }
  function appendSelectionDraft(container, attempt, raw) {
    if (!["selection", "use_spirit"].includes(attempt.stage)) return;
    let selection;
    try {
      const trimmed = raw.trim();
      const fenced = trimmed.match(/^```(?:json)?\s*\n([\s\S]*?)\n```$/i);
      selection = JSON.parse(fenced ? fenced[1] : trimmed);
    } catch (_) {
      return;
    }
    if (!selection || typeof selection !== "object" || Array.isArray(selection)) return;
    const draft = node("section", "ai-selection-draft");
    draft.append(node("h4", "", attempt.adopted ? "取用回复摘要 · 已通过校验" : "取用草稿摘要 · 未采用"));
    draft.append(node("p", "small-note", "以下按 AI 原回复中的字段整理，便于查看它选了什么。"));
    const statuses = { ready: "可继续", needs_clarification: "需要补充", unresolved: "尚未确定", needs_review: "待核对", needs_rule_review: "规则适用待核对" };
    const fields = node("dl");
    const field = (label, value) => fields.append(node("dt", "", label), node("dd", "", value));
    const rawStatus = typeof selection.status === "string" ? selection.status : "未填写";
    field("AI 自报状态", Object.hasOwn(statuses, rawStatus) ? "".concat(statuses[rawStatus], "（").concat(rawStatus, "）") : rawStatus);
    const selected = typeof selection.selected_primary_id === "string" ? selection.selected_primary_id : null;
    const candidates = Array.isArray(selection.candidates) ? selection.candidates.filter((candidate) => candidate && typeof candidate === "object") : [];
    field("AI 填写的主候选编号", selected ? "".concat(selected).concat(candidates.some((candidate) => candidate.candidate_id === selected) ? "" : "（候选列表中没有这个编号）") : "未填写");
    draft.append(fields);
    const purposes = { primary: "主用", supporting: "辅助", cost: "代价", carrier: "承载" };
    const relatives = { parents: "父母", siblings: "兄弟", offspring: "子孙", wealth: "妻财", official_ghost: "官鬼" };
    if (!candidates.length) draft.append(node("p", "small-note", "AI 没有列出候选对象。"));
    candidates.forEach((candidate) => {
      const card = node("div", "ai-candidate-draft");
      const label = typeof candidate.candidate_id === "string" ? candidate.candidate_id : "未填写编号";
      card.append(node("p", "ai-candidate-title", label));
      const entries = node("dl");
      const add = (name, value) => entries.append(node("dt", "", name), node("dd", "", typeof value === "string" && value ? value : "未填写"));
      add("对象", candidate.object_role);
      add("作用", candidate.function);
      add("用途", typeof candidate.purpose === "string" && Object.hasOwn(purposes, candidate.purpose) ? purposes[candidate.purpose] : candidate.purpose);
      add("六亲 / 主体位置", candidate.subject_reference === "shi" ? "世爻" : candidate.subject_reference === "shi_body" ? "世身" : typeof candidate.six_relative === "string" && Object.hasOwn(relatives, candidate.six_relative) ? relatives[candidate.six_relative] : candidate.six_relative);
      card.append(entries);
      appendListBlock(card, candidate.assumptions, "假定条件", "small-note");
      draft.append(card);
    });
    appendListBlock(draft, selection.unresolved, "AI 列出的未决条件", "ai-draft-questions");
    appendListBlock(draft, selection.clarifying_questions, "AI 想补充询问", "ai-draft-questions");
    container.append(draft);
  }
  async function loadRawReplies(force = false) {
    var _a2, _b;
    const details = $("ai-raw-replies");
    if (!details.open || !state.caseId || !state.runId) return;
    if (rawLoading) {
      if (force) rawReloadPending = true;
      return;
    }
    if (state.rawReplyLoaded && !force) return;
    rawLoading = true;
    lastRawCheck = Date.now();
    const token = ++state.rawReplyToken;
    const caseId = state.caseId;
    const runId = state.runId;
    const container = $("ai-raw-replies-content");
    if (!state.rawReplyLoaded) {
      clear(container);
      container.append(node("p", "small-note", "正在读取这次分析的回复…"));
    }
    try {
      const payload = await api("/api/cases/".concat(encodeURIComponent(caseId), "/ai-attempts?run_id=").concat(encodeURIComponent(runId)));
      if (token !== state.rawReplyToken || caseId !== state.caseId || runId !== state.runId) return;
      const signature = JSON.stringify(payload);
      if (state.rawReplyLoaded && rawSignature === signature) return;
      rawSignature = signature;
      clear(container);
      state.rawReplyLoaded = true;
      const attempts = ((_b = (_a2 = payload.analysis_runs) == null ? void 0 : _a2.find((run) => run.analysis_run_id === runId)) == null ? void 0 : _b.attempts) || [];
      if (!attempts.length) {
        container.append(node("p", "small-note", "尚未收到完整回复。AI 正在处理时不会逐字显示；每一步返回后这里自动更新。若调用失败，这里会显示报错。"));
        return;
      }
      const stages = { intent: "理解问题", selection: "确定取用", use_spirit: "确定取用", interpretation: "解卦", report: "整理报告" };
      attempts.forEach((attempt) => {
        var _a3;
        const item = node("section", "ai-raw-attempt");
        const heading = node("div", "ai-raw-heading");
        const attemptLabel = attempt.attempt_number === 1 ? "首次生成" : attempt.attempt_number === 2 ? "自动修复" : "回复 ".concat(attempt.attempt_number || "未编号");
        heading.append(node("h4", "", "".concat(stages[attempt.stage] || attempt.stage || "分析", " · ").concat(attemptLabel)));
        heading.append(node("span", "soft-tag ".concat(attempt.adopted ? "" : "warning"), attempt.adopted ? "已通过校验" : "未通过校验的草稿"));
        item.append(heading);
        const timing = [attempt.http_status ? "HTTP " + attempt.http_status : "", Number.isFinite(attempt.elapsed_ms) ? "本次调用 " + (attempt.elapsed_ms / 1e3).toFixed(1) + " 秒" : ""].filter(Boolean);
        if (timing.length) item.append(node("p", "small-note", timing.join(" · ")));
        const errors = (attempt.validation_errors || []).map((error) => {
          const message = [error.code, readable(error.message || error)].filter(Boolean).join("：");
          return error.path ? "".concat(error.path, ": ").concat(message) : message;
        }).filter(Boolean);
        if (errors.length) item.append(node("p", "ai-raw-errors", "未采用原因：".concat(errors.join("\n"))));
        if ((_a3 = attempt.normalization_changes) == null ? void 0 : _a3.length) {
          const changes = node("details", "ai-normalization");
          changes.append(node("summary", "", "程序对回复的整理记录"), node("p", "", attempt.normalization_changes.join("\n")));
          item.append(changes);
        }
        const raw = typeof attempt.raw_output === "string" ? attempt.raw_output : "";
        appendSelectionDraft(item, attempt, raw);
        const text = node("pre", "ai-raw-text", raw || "没有返回正文。");
        text.tabIndex = 0;
        text.setAttribute("aria-label", "".concat(stages[attempt.stage] || "AI", "原始回复"));
        item.append(text);
        if (raw) {
          const copy = node("button", "secondary-button", "复制原始回复");
          copy.type = "button";
          const status = node("span", "small-note ai-copy-status");
          status.setAttribute("role", "status");
          copy.addEventListener("click", async () => {
            var _a4, _b2;
            try {
              if (!((_b2 = (_a4 = window.navigator) == null ? void 0 : _a4.clipboard) == null ? void 0 : _b2.writeText)) throw new Error("clipboard unavailable");
              await window.navigator.clipboard.writeText(raw);
              status.textContent = "已复制。";
            } catch (_) {
              status.textContent = "浏览器未允许复制，请在上方正文中手动选取并复制。";
              text.focus();
            }
          });
          item.append(copy, status);
        }
        container.append(item);
      });
    } catch (error) {
      if (token !== state.rawReplyToken || caseId !== state.caseId || runId !== state.runId) return;
      clear(container);
      container.append(node("p", "ai-raw-errors", "".concat(getError(error), " 收起后重新展开可重试。")));
    } finally {
      rawLoading = false;
      if (rawReloadPending) {
        rawReloadPending = false;
        loadRawReplies(true);
      }
    }
  }
  function renderAnalysis(result, status = "saved", runId = null, notice = "") {
    var _a2, _b, _c, _d, _e, _f, _g, _h, _i, _j, _k, _l, _m;
    $("analysis-content").removeAttribute("data-preview-run");
    $("run-history").hidden = status === "running" || state.runs.length < 2;
    state.runId = runId || null;
    if (runSelect) runSelect.value = state.runId || "";
    resetRawReplies();
    if ($("ai-raw-replies").open) loadRawReplies(true);
    if ($("audit-report")) $("audit-report").hidden = true;
    if (runId) {
      const run = state.runs.find((item) => item.analysis_run_id === runId);
      const snapshotChart = ((_b = (_a2 = run == null ? void 0 : run.outcome) == null ? void 0 : _a2.result) == null ? void 0 : _b.chart_snapshot) || ((_e = (_d = (_c = run == null ? void 0 : run.outcome) == null ? void 0 : _c.result) == null ? void 0 : _d.report) == null ? void 0 : _e.chart) || (result == null ? void 0 : result.chart) || null;
      renderChart(snapshotChart, ((_f = run == null ? void 0 : run.input_snapshot) == null ? void 0 : _f.input) || null, "所选分析当时的排盘".concat((run == null ? void 0 : run.analyzed_at) ? " · " + dateText(run.analyzed_at) : ""));
    } else renderChart(state.chart, state.input);
    const container = $("analysis-content");
    clear(container);
    window.ReportViews.reset();
    if (notice) container.append(node("p", "demo-banner", notice));
    if (((_g = result == null ? void 0 : result.report_status) == null ? void 0 : _g.mode) === "fallback") container.append(node("p", "demo-banner", result.report_status.message));
    const tag = $("analysis-status");
    tag.textContent = STATUS[status] || "已记录";
    tag.className = "soft-tag ".concat(status === "failed" ? "error" : ["partial", "unresolved"].includes(status) ? "warning" : "");
    const historical = runId && (!state.reportCurrent || runId !== ((_h = state.runs.at(-1)) == null ? void 0 : _h.analysis_run_id));
    if (historical) container.append(node("p", "demo-banner", "历史分析：本报告对应当时保存的输入与背景，默认展示当时排盘。切换“当前已保存排盘”后，请按排盘标题区分；录入区始终显示当前输入。"));
    if (!result) {
      container.append(node("p", "empty-state", status === "running" ? "正在生成新的分析，完成后将自动显示结果。".concat(state.runs.length ? "此前的分析保留在“回看分析”中。" : "") : "卦象已经排好。选择模型后，可以进一步梳理问题。"));
      return;
    }
    if (result.is_demo) container.append(node("p", "demo-banner", "离线演示：以下用于体验流程，没有调用 AI，也不作占断结论。"));
    const report = result.user_report || result.display_report || result.report;
    if ($("feedback-run-label")) $("feedback-run-label").textContent = runId ? "反馈对应当前所选分析；规则版本：".concat(result.rules_version || "旧版未记录") : "反馈保存在案例中；选择一次分析可关联当时的预测。";
    const errorMessage = readable(result.error);
    const duplicateFailureReport = Boolean(result.error && status === "failed" && !(report == null ? void 0 : report.conclusion) && (typeof report === "string" ? report === errorMessage : report && !((_i = report.sections) == null ? void 0 : _i.length)));
    const conclusion = !result.is_demo && report && typeof report === "object" && readable((_j = report.conclusion) == null ? void 0 : _j.answer) ? report.conclusion : null;
    if (conclusion && status === "partial") tag.textContent = conclusion.qualification === "undetermined" ? "已解读 · 待判断" : "已解读 · 有条件";
    let hasReport = false;
    if (typeof report === "string" && !duplicateFailureReport) {
      container.append(node("p", "report-summary", report));
      hasReport = true;
    } else if (report && typeof report === "object" && !duplicateFailureReport) {
      hasReport = window.ReportViews.render(report, container, { isDemo: Boolean(result.is_demo) });
    }
    appendListBlock(container, result.clarifying_questions, "还想和你确认", "clarifying-block");
    if (!conclusion) appendListBlock(container, result.unresolved, "本次仍未确定的部分", "unresolved-block");
    if (result.error) renderAnalysisError(container, result.error);
    (_k = window.LiuyaoV5) == null ? void 0 : _k.renderAudit(result);
    if (!hasReport && !((_l = result.clarifying_questions) == null ? void 0 : _l.length) && !((_m = result.unresolved) == null ? void 0 : _m.length) && !result.error) container.append(node("p", "empty-state", status === "failed" ? "本次分析未完成，输入与排盘已保留。可以重试或更换模型。" : "尚未形成可展示的完整报告。输入与本次分析过程已经保留。"));
  }
  function renderRun(run, { notice = "" } = {}) {
    var _a2, _b;
    const stored = ((_a2 = run.outcome) == null ? void 0 : _a2.result) || run.result || null;
    const result = (stored == null ? void 0 : stored.report) && (stored.report.display_report || stored.report.stage_outputs || stored.report.is_demo !== void 0) ? stored.report : stored;
    renderAnalysis(result, run.status || ((_b = run.outcome) == null ? void 0 : _b.status) || "running", run.analysis_run_id, notice);
  }
  function renderRunSelector() {
    const area = $("run-history");
    clear(area);
    area.hidden = state.runs.length < 2;
    runSelect = null;
    if (state.runs.length < 2) return;
    const label = node("label", "", "回看分析");
    label.htmlFor = "past-run-select";
    const select = document.createElement("select");
    select.id = "past-run-select";
    select.disabled = state.busy;
    runSelect = select;
    [...state.runs].reverse().forEach((run, index) => {
      const option = node("option", "", "".concat(index === 0 ? "最近 · " : "").concat(analysisLabel(run)));
      option.value = run.analysis_run_id;
      select.append(option);
    });
    select.value = state.runs.some((run) => run.analysis_run_id === state.runId) ? state.runId : state.runs.at(-1).analysis_run_id;
    select.addEventListener("change", () => {
      if (state.busy) return;
      window.AnalysisStatus.clear();
      currentJob = null;
      const run = state.runs.find((item) => item.analysis_run_id === select.value);
      if (run) renderRun(run);
    });
    area.append(label, select);
  }
  function renderEvents(record) {
    clear($("context-list"));
    clear($("feedback-list"));
    const appendEvent = (container, text, stamp) => {
      if (!text) return;
      const item = node("p", "event-item");
      const time = node("time", "", dateText(stamp));
      if (stamp) time.dateTime = stamp;
      item.append(time, document.createTextNode(text));
      container.append(item);
    };
    (record.context_events || []).forEach((item) => appendEvent($("context-list"), readable(item.content), item.recorded_at));
    (record.feedback || []).forEach((item) => {
      var _a2;
      return appendEvent($("feedback-list"), [readable((_a2 = item.reported_outcome) != null ? _a2 : item.text), item.occurred_at ? "发生时间：" + dateText(item.occurred_at) : "", item.rules_version ? "规则版本：" + item.rules_version : "", item.match_degree ? "符合程度：" + ({ matched: "符合", partly_matched: "部分符合", unmatched: "不符合", pending: "尚待验证" }[item.match_degree] || item.match_degree) : "", item.user_notes || ""].filter(Boolean).join("\n"), item.recorded_at);
    });
  }
  async function saveCase() {
    const input = getInput();
    if (state.caseId && inputsEqual(input, state.input)) return state.caseId;
    let payload;
    if (state.caseId) {
      const reason = $("revision-reason").value;
      if (!reason.trim()) {
        $("revision-fields").hidden = false;
        $("revision-reason").focus();
        throw new Error("请写一句修改原因，便于以后回看。");
      }
      payload = await api("/api/cases/".concat(encodeURIComponent(state.caseId), "/revisions"), { method: "POST", data: { input, reason, expected_revision_seq: state.revision } });
    } else payload = await api("/api/cases", { method: "POST", data: { input } });
    state.caseId = payload.case_id || state.caseId;
    state.revision = payload.revision_seq || state.revision + 1;
    state.input = input;
    $("revision-reason").value = "";
    if (!state.caseId) throw new Error("案例没有成功保存，请重试。");
    await loadCase(state.caseId, { quiet: true });
    await refreshHistory();
    return state.caseId;
  }
  function chosenProvider() {
    var _a2, _b;
    return (_b = (_a2 = state.config) == null ? void 0 : _a2.providers) == null ? void 0 : _b.find((item) => item.id === $("provider-select").value);
  }
  function modelSettings() {
    return { provider: $("provider-select").value, model: $("model-select").value };
  }
  function storePreference() {
    var _a2;
    try {
      const preference = JSON.stringify(__spreadProps(__spreadValues({}, modelSettings()), { defaults: "deepseek-pro-max" }));
      localStorage.setItem("liuyao-model-preference", preference);
      (_a2 = window.LiuyaoAndroid) == null ? void 0 : _a2.savePreference(preference);
    } catch (_) {
    }
  }
  function updateModelLabel() {
    const provider = chosenProvider();
    const quality = provider == null ? void 0 : provider.reasoning_effort;
    $("model-current").textContent = provider ? "".concat(provider.name, " · ").concat($("model-select").value || "未配置模型").concat(quality ? " · 质量 " + quality : "").concat(provider.configured || provider.id === "demo" ? "" : " · 待配置") : "模型设置暂不可用";
    $("model-quality").hidden = !quality;
    $("model-quality").textContent = quality ? "思考质量：".concat(quality).concat(provider.thinking === "enabled" ? " · 深度思考已启用" : " · 思考已关闭") : "";
  }
  function updateModels(preferredModel) {
    var _a2;
    const provider = chosenProvider();
    const select = $("model-select");
    clear(select);
    if (!provider) return;
    const models = ((_a2 = provider.models) == null ? void 0 : _a2.length) ? provider.models : provider.default_model ? [provider.default_model] : [];
    models.forEach((model) => {
      const value = typeof model === "string" ? model : model.id;
      if (!value) return;
      const option = node("option", "", typeof model === "string" ? model : model.name || model.id);
      option.value = value;
      select.append(option);
    });
    if (!models.length) {
      const option = node("option", "", "尚未配置模型");
      option.value = "";
      select.append(option);
    }
    if ([...select.options].some((item) => item.value === preferredModel)) select.value = preferredModel;
    else if ([...select.options].some((item) => item.value === provider.default_model)) select.value = provider.default_model;
    const note = $("provider-note");
    note.className = "provider-note ".concat(!provider.configured || provider.id === "demo" ? "warning" : "");
    note.textContent = provider.id === "demo" ? "离线演示用于检查输入、排盘和反馈流程，不会调用 AI，也不会给出占断结论。" : provider.configured ? window.LiuyaoAndroid ? "已配置。点击分析后，将发送本次问题、卦象与补充说明。" : "服务端已提供 API 配置。点击分析后，将发送本次问题、卦象与补充说明。" : window.LiuyaoAndroid ? "点击下方“配置 API 密钥”即可启用。现在也可以离线保存案例和排盘。" : "此厂商尚未配置。请在服务端 .env 中填写对应 API 密钥与模型配置，然后重启服务。现在仍可保存案例和排盘。";
    updateModelLabel();
  }
  async function loadConfig() {
    var _a2, _b;
    state.config = await api("/api/config");
    const select = $("provider-select");
    clear(select);
    const paths = state.config.storage_paths;
    $("storage-paths").hidden = !paths;
    $("storage-data-directory").textContent = (paths == null ? void 0 : paths.data_directory) || "未读取到保存位置";
    $("storage-configuration-file").textContent = (paths == null ? void 0 : paths.configuration_file) || "未读取到配置位置";
    (state.config.providers || []).forEach((provider) => {
      const option = node("option", "", "".concat(provider.name).concat(provider.configured || provider.id === "demo" ? "" : "（待配置）"));
      option.value = provider.id;
      select.append(option);
    });
    let preference = null;
    try {
      preference = JSON.parse(((_a2 = window.LiuyaoAndroid) == null ? void 0 : _a2.readPreference()) || localStorage.getItem("liuyao-model-preference") || "null");
    } catch (_) {
    }
    const deepseek = (_b = state.config.providers) == null ? void 0 : _b.find((p) => p.id === "deepseek");
    if ((preference == null ? void 0 : preference.defaults) !== "deepseek-pro-max" && (preference == null ? void 0 : preference.provider) === "deepseek" && ["deepseek-flash", "deepseek-v4-flash", "deepseek-chat", "deepseek-reasoner"].includes(preference.model) && (deepseek == null ? void 0 : deepseek.default_model) === "deepseek-v4-pro") preference = __spreadProps(__spreadValues({}, preference), { model: deepseek.default_model });
    if ([...select.options].some((item) => item.value === (preference == null ? void 0 : preference.provider))) select.value = preference.provider;
    else if ([...select.options].some((item) => item.value === state.config.default_provider)) select.value = state.config.default_provider;
    updateModels(preference == null ? void 0 : preference.model);
    storePreference();
  }
  async function analyzeSavedCase(caseId) {
    var _a2, _b, _c, _d, _e;
    const provider = chosenProvider();
    if (!provider || !provider.configured && provider.id !== "demo" || !$("model-select").value) {
      $("settings-dialog").showModal();
      banner("案例与补充说明已保存。请配置并选择模型后继续解卦，也可以明确选择离线演示。", "warning");
      return null;
    }
    const previousRun = state.runs.find((run) => run.analysis_run_id === state.runId);
    const model = modelSettings();
    storePreference();
    showView("results");
    window.ReportViews.show("answer");
    let response;
    try {
      response = await api("/api/cases/".concat(encodeURIComponent(caseId), "/analyze"), { method: "POST", data: __spreadProps(__spreadValues({}, model), { expected_revision_seq: state.revision }) });
    } catch (error) {
      const detail = await api("/api/cases/".concat(encodeURIComponent(caseId))).catch(() => null);
      if (!(detail == null ? void 0 : detail.active_job_id)) throw error;
      response = { job_id: detail.active_job_id };
    }
    renderAnalysis(null, "running");
    state.analyzing = true;
    setBusy(true);
    $("analysis-progress").hidden = false;
    $("analysis-progress-text").textContent = "正在准备分析…";
    $("analysis-status").textContent = "分析中";
    persistDraft();
    window.AnalysisStatus.start(response.job_id, caseId);
    window.AnalysisStatus.focus();
    let job;
    try {
      job = await pollJob(response.job_id, caseId);
    } catch (error) {
      if (state.caseId === caseId && previousRun) renderRun(previousRun, { notice: "尚未确认新分析是否完成。以下恢复显示先前选中的已保存分析；稍后重新打开案例，可查看最新进度。" });
      throw error;
    }
    state.analyzing = false;
    await loadCase(caseId, { keepForm: true, quiet: true });
    if (job.result || job.error) renderAnalysis(__spreadProps(__spreadValues({}, job.result), { error: ((_a2 = job.result) == null ? void 0 : _a2.error) || job.error }), job.status, job.analysis_run_id);
    if (job.status === "failed") banner("");
    else banner(job.status === "completed" || ((_c = (_b = job.result) == null ? void 0 : _b.display_report) == null ? void 0 : _c.conclusion) ? "解卦已保存。可以补充情况继续分析，或在后续反馈中记录实际进展。" : "本次分析已保存，请查看需要补充或尚未确定的部分。", job.status === "completed" || ((_e = (_d = job.result) == null ? void 0 : _d.display_report) == null ? void 0 : _e.conclusion) ? "" : "warning");
    await refreshHistory();
    return job;
  }
  async function startAnalysis({ savedCase = false } = {}) {
    if (state.busy) return;
    setBusy(true);
    banner("");
    try {
      const caseId = savedCase ? state.caseId : await saveCase();
      if (!caseId) throw new Error("请先保存这次问题与卦象。");
      await analyzeSavedCase(caseId);
    } catch (error) {
      banner(getError(error), "error");
    } finally {
      state.analyzing = false;
      setBusy(false);
    }
  }
  async function resumeJob(jobId, caseId) {
    var _a2;
    if (state.analyzing) return;
    renderAnalysis(null, "running");
    state.analyzing = true;
    setBusy(true);
    $("analysis-progress").hidden = false;
    $("analysis-progress-text").textContent = "已恢复正在进行的分析…";
    try {
      const job = await pollJob(jobId, caseId);
      await loadCase(caseId, { quiet: true });
      if (job.result || job.error) renderAnalysis(__spreadProps(__spreadValues({}, job.result), { error: ((_a2 = job.result) == null ? void 0 : _a2.error) || job.error }), job.status, job.analysis_run_id);
      if (job.status === "failed") banner("");
      await refreshHistory();
    } catch (error) {
      banner(getError(error), "error");
    } finally {
      state.analyzing = false;
      setBusy(false);
    }
  }
  async function readJob(jobId, caseId) {
    const job = await api("/api/jobs/".concat(encodeURIComponent(jobId)));
    if (state.caseId !== caseId) return job;
    const previous = currentJob;
    currentJob = job;
    window.AnalysisStatus.update(job);
    if (job.analysis_run_id && state.runId !== job.analysis_run_id) {
      const wasOpen = $("ai-raw-replies").open;
      state.runId = job.analysis_run_id;
      resetRawReplies();
      $("ai-raw-replies").open = wasOpen;
      $("ai-raw-replies-context").textContent = "本次正在进行的分析；每个阶段返回后自动更新。";
    }
    if (job.preview_report && $("analysis-content").dataset.previewRun !== job.analysis_run_id) {
      const container = $("analysis-content");
      clear(container);
      window.ReportViews.reset();
      container.append(node("p", "demo-banner", "解卦结论已生成，可以先看答案。正在整理通俗说明，超时会保留当前结论。"));
      window.ReportViews.render(job.preview_report, container);
      container.dataset.previewRun = job.analysis_run_id;
      $("analysis-status").textContent = "已解卦 · 整理中";
      $("run-history").hidden = true;
    }
    if ((previous == null ? void 0 : previous.reply_count) !== job.reply_count || !state.rawReplyLoaded || Date.now() - lastRawCheck > 4500 || !["queued", "running"].includes(job.status)) loadRawReplies(true);
    return job;
  }
  async function pollJob(jobId, caseId) {
    if (!jobId) throw new Error("服务未返回分析任务编号，已保存的案例不会丢失。");
    let failures = 0;
    currentJob = { job_id: jobId, case_id: caseId, status: "running" };
    window.AnalysisStatus.start(jobId, caseId);
    for (; ; ) {
      try {
        const job = await readJob(jobId, caseId);
        failures = 0;
        if (!["queued", "running"].includes(job.status)) return job;
      } catch (error) {
        failures++;
        window.AnalysisStatus.offline(getError(error));
        if (["SESSION_REQUIRED", "NOT_FOUND", "ACCESS_DENIED"].includes(error.code)) throw error;
      }
      await new Promise((resolve) => {
        const timer = setTimeout(() => {
          wakePoll = null;
          resolve();
        }, failures ? 5e3 : 1200);
        wakePoll = () => {
          clearTimeout(timer);
          wakePoll = null;
          resolve();
        };
      });
    }
  }
  window.AnalysisStatus.bind({
    answer() {
      showView("results");
      window.ReportViews.show("answer");
      $("analysis-content").scrollIntoView({ block: "start", behavior: "smooth" });
    },
    async replies() {
      showView("results");
      window.ReportViews.show("records");
      const details = $("ai-raw-replies");
      details.hidden = false;
      details.open = true;
      if (!state.runId) $("ai-raw-replies-content").replaceChildren(node("p", "small-note", "正在建立分析记录，尚未收到 AI 回复。"));
      else await loadRawReplies(true);
      details.scrollIntoView({ block: "start", behavior: "smooth" });
    },
    async refresh() {
      if (!currentJob) return;
      if (state.analyzing) {
        state.rawReplyLoaded = false;
        if (wakePoll) wakePoll();
        return;
      }
      try {
        const job = await readJob(currentJob.job_id, currentJob.case_id);
        if (["queued", "running"].includes(job.status)) resumeJob(job.job_id, job.case_id);
      } catch (error) {
        window.AnalysisStatus.offline(getError(error));
      }
    }
  });
  async function appendCaseEvent(kind, { reanalyze = false } = {}) {
    var _a2, _b, _c, _d, _e;
    if (state.busy || !state.caseId) return;
    const field = $(kind === "context" ? "context-text" : "feedback-text");
    const text = field.value;
    if (!text.trim()) {
      field.focus();
      banner(kind === "context" ? "请先写下需要补充的说明。" : "请先写下实际进展或结果。", "warning");
      return;
    }
    const caseId = state.caseId;
    const payload = { text };
    if (kind === "feedback") {
      if (state.runId) payload.analysis_run_id = state.runId;
      if ((_a2 = $("feedback-occurred")) == null ? void 0 : _a2.value) payload.occurred_at = new Date($("feedback-occurred").value).toISOString();
      payload.match_degree = ((_b = $("feedback-match")) == null ? void 0 : _b.value) || "pending";
      payload.user_notes = ((_c = $("feedback-notes")) == null ? void 0 : _c.value) || "";
    }
    setBusy(true);
    banner("");
    try {
      const alreadySaved = kind === "context" && ((_d = state.pendingContext) == null ? void 0 : _d.caseId) === caseId && state.pendingContext.text === text;
      if (!alreadySaved) {
        await api("/api/cases/".concat(encodeURIComponent(caseId), "/").concat(kind), { method: "POST", data: payload });
        if (kind === "context") state.pendingContext = { caseId, text };
      }
      await loadCase(caseId, { keepForm: true, quiet: true, keepView: true });
      if (kind === "context" && reanalyze) {
        const job = await analyzeSavedCase(caseId);
        if (!job || job.status === "failed") return;
      } else banner(kind === "context" ? "补充说明已保存。可以点击“重新解卦”，把新情况一并纳入。" : "反馈已独立保存，可继续补充后续进展。");
      if (field.value === text) field.value = "";
      if (kind === "feedback") {
        $("feedback-occurred").value = "";
        $("feedback-notes").value = "";
        $("feedback-match").value = "pending";
      }
      if (kind === "context") state.pendingContext = null;
    } catch (error) {
      banner("".concat(getError(error)).concat(kind === "context" && ((_e = state.pendingContext) == null ? void 0 : _e.caseId) === caseId ? " 补充说明已保存，可以重试解卦。" : " 输入仍保留，请重试。"), "error");
    } finally {
      state.analyzing = false;
      setBusy(false);
    }
  }
  buildInputs();
  showView("input");
  $("timezone-note").textContent = "使用当前浏览器时区：".concat(Intl.DateTimeFormat().resolvedOptions().timeZone || "本地时区", "。");
  $("question").addEventListener("input", onInputChange);
  $("buzhai-details").addEventListener("input", onInputChange);
  $("buzhai-details").addEventListener("change", onInputChange);
  (_a = $("profile-select")) == null ? void 0 : _a.addEventListener("change", onInputChange);
  $("person-subject").addEventListener("change", () => {
    var _a2;
    (_a2 = window.LiuyaoV5) == null ? void 0 : _a2.selectSelf();
    updatePersonFields({ clearIrrelevant: true });
    onInputChange();
  });
  ["querent-age", "subject-age", "person-relationship", "person-background"].forEach((id) => $(id).addEventListener("input", onInputChange));
  $("cast-time").addEventListener("change", onInputChange);
  $("cast-now").addEventListener("click", () => {
    $("cast-time").value = localDateTime(/* @__PURE__ */ new Date());
    $("time-details").open = true;
    onInputChange();
  });
  $("cast-clear").addEventListener("click", () => {
    $("cast-time").value = "";
    onInputChange();
  });
  $("new-case").addEventListener("click", resetCase);
  $("show-current-chart").addEventListener("click", () => renderChart(state.chart, state.input));
  $("ai-raw-replies").addEventListener("toggle", () => loadRawReplies());
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && wakePoll) wakePoll();
  });
  $("refresh-history").addEventListener("click", () => refreshHistory().catch((error) => banner(getError(error), "error")));
  $("case-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.busy) return;
    setBusy(true);
    banner("");
    try {
      await saveCase();
      showView("results", { scroll: true });
      window.ReportViews.show("chart");
      banner("案例已保存，基础排盘已生成。");
    } catch (error) {
      banner(getError(error), "error");
    } finally {
      setBusy(false);
    }
  });
  $("analyze-case").addEventListener("click", () => startAnalysis());
  $("analyze-current-case").addEventListener("click", () => startAnalysis({ savedCase: true }));
  $("context-form").addEventListener("submit", (event) => {
    event.preventDefault();
    appendCaseEvent("context", { reanalyze: true });
  });
  $("context-save-only").addEventListener("click", () => appendCaseEvent("context"));
  ["input", "results", "feedback"].forEach((name) => {
    const tab = $("tab-".concat(name));
    tab.addEventListener("click", () => showView(name));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      const names = state.caseId ? ["input", "results", "feedback"] : ["input"];
      const current = names.indexOf(name);
      const next = event.key === "Home" ? 0 : event.key === "End" ? names.length - 1 : (current + (event.key === "ArrowRight" ? 1 : -1) + names.length) % names.length;
      event.preventDefault();
      showView(names[next]);
      $("tab-".concat(names[next])).focus();
    });
  });
  $("edit-case-input").addEventListener("click", () => showView("input", { scroll: true }));
  $("open-feedback").addEventListener("click", () => showView("feedback", { scroll: true }));
  $("feedback-return").addEventListener("click", () => showView("results", { scroll: true }));
  $("feedback-form").addEventListener("submit", (event) => {
    event.preventDefault();
    appendCaseEvent("feedback");
  });
  $("settings-open").addEventListener("click", () => $("settings-dialog").showModal());
  $("guide-open").addEventListener("click", () => $("guide-dialog").showModal());
  $("settings-done").addEventListener("click", () => {
    storePreference();
    updateModelLabel();
    $("settings-dialog").close();
  });
  $("provider-select").addEventListener("change", () => updateModels());
  $("model-select").addEventListener("change", updateModelLabel);
  $("settings-dialog").addEventListener("click", (event) => {
    if (event.target === $("settings-dialog")) {
      const rect = event.target.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) event.target.close();
    }
  });
  window.addEventListener("beforeunload", (event) => {
    let dirty = false;
    try {
      dirty = hasEnteredData() && !inputsEqual(getInput(false), state.input);
    } catch (_) {
      dirty = true;
    }
    dirty = dirty || Boolean($("context-text").value.trim() || $("feedback-text").value.trim());
    if (dirty) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
  function persistDraft() {
    if (!window.LiuyaoAndroid) return;
    const fields = {};
    document.querySelectorAll("#case-form input,#case-form textarea,#case-form select,#context-text,#feedback-form input,#feedback-form textarea,#feedback-form select").forEach((el, index) => {
      if (el.type === "file") return;
      fields[el.id || el.name + "::" + el.value] = { value: el.value, checked: el.checked };
    });
    window.LiuyaoAndroid.saveDraft(JSON.stringify({ caseId: state.caseId, fields, view: state.view }));
  }
  let draftTimer;
  document.addEventListener("input", () => {
    if (window.LiuyaoAndroid) {
      clearTimeout(draftTimer);
      draftTimer = setTimeout(persistDraft, 300);
    }
  });
  document.addEventListener("change", () => {
    if (window.LiuyaoAndroid) {
      clearTimeout(draftTimer);
      draftTimer = setTimeout(persistDraft, 300);
    }
  });
  window.LiuyaoApp = { reloadConfig: loadConfig, persistDraft, canLeave: mayDiscard, isAnalyzing: () => state.analyzing };
  Promise.allSettled([loadConfig(), refreshHistory()]).then(async (results) => {
    results.forEach((result) => {
      if (result.status === "rejected") banner(getError(result.reason), "error");
    });
    if (!window.LiuyaoAndroid) return;
    try {
      const draft = JSON.parse(window.LiuyaoAndroid.readDraft() || "null");
      if (!draft) return;
      if (draft.caseId) await loadCase(draft.caseId, { quiet: true });
      const fields = draft.fields || {};
      document.querySelectorAll("#case-form input,#case-form textarea,#case-form select,#context-text,#feedback-form input,#feedback-form textarea,#feedback-form select").forEach((el) => {
        const f = fields[el.id || el.name + "::" + el.value];
        if (f && el.type !== "file") {
          el.value = f.value;
          if ("checked" in f) el.checked = f.checked;
        }
      });
      updateCastingMode();
      updatePersonFields();
      $("buzhai-enabled").dispatchEvent(new Event("change", { bubbles: true }));
      onInputChange();
      showView(draft.view);
      if (!draft.caseId && $("question").value) banner("已恢复上次尚未保存的输入。");
    } catch (_) {
      banner("上次输入未能完整恢复，已保存的案例可在档案中查看。", "warning");
    }
  });
})();
