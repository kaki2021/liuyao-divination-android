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
  const $ = (id) => document.getElementById(id);
  const fields = ["name", "gender", "birth_date", "birth_place", "bazi", "occupation", "industry", "tags", "notes"];
  const rulePackageFormat = "cn.guanxiang.liuyao.rules-package", rulePackageAad = "liuyao-rules-package-v1";
  let profiles = [], requestedProfile = "", rulesVersion = "", editingVersion = null, birthRequest = 0, birthTimer, guide = null, rulePage = 0, selectedRule = "", analysisInput = null, previewRequest = 0;
  const node = (tag, text, cls = "") => {
    const el = document.createElement(tag);
    el.textContent = text;
    el.className = cls;
    return el;
  };
  async function api(path, data) {
    var _a;
    const response = await fetch(path, data === void 0 ? {} : { method: "POST", headers: { "X-App-Request": "1", "Content-Type": "application/json", "X-Idempotency-Key": window.LiuyaoCompat.requestId() }, body: JSON.stringify(data) });
    const result = await response.json();
    if (!response.ok) throw new Error(((_a = result.error) == null ? void 0 : _a.message) || result.message || "操作未完成");
    return result;
  }
  function fillOptions(select, empty, value) {
    select.replaceChildren(node("option", empty));
    select.firstChild.value = "";
    profiles.forEach((p) => {
      const option = node("option", p.profile.name + (p.is_self ? "（本人）" : ""));
      option.value = p.person_id;
      select.append(option);
    });
    if (value && !profiles.some((p) => p.person_id === value)) {
      const o = node("option", "已关联的历史档案");
      o.value = value;
      select.append(o);
    }
    select.value = value || "";
  }
  async function loadProfiles() {
    profiles = (await api("/api/profiles")).profiles;
    fillOptions($("profile-select"), "临时人物", requestedProfile || $("profile-select").value);
    fillOptions($("profile-edit-select"), "新建人物", $("profile-edit-select").value);
  }
  function setProfile(id) {
    requestedProfile = id;
    if ($("profile-select")) fillOptions($("profile-select"), "临时人物", id);
  }
  function selectSelf() {
    if ($("person-subject").value === "self") {
      const p = profiles.find((x) => x.is_self);
      if (p) {
        setProfile(p.person_id);
        $("profile-select").dispatchEvent(new Event("change"));
      }
    }
  }
  function birthValues() {
    const date = $("profile-birth_date").value, time = $("profile-birth-clock").value;
    return { birth_date: date, birth_time: date && time ? date + "T" + time + (time.length === 5 ? ":00" : "") + "+08:00" : "" };
  }
  function displayBirth(chart) {
    var _a;
    $("birth-pillars").replaceChildren();
    for (const [key, label] of [["year", "年柱"], ["month", "月柱"], ["day", "日柱"], ["hour", "时柱"]]) {
      const p = node("div", "");
      p.append(node("span", label), node("strong", ((_a = chart.pillars) == null ? void 0 : _a[key]) || "待补"));
      $("birth-pillars").append(p);
    }
    $("birth-message").textContent = chart.message || "";
  }
  async function previewBirth() {
    const request = ++birthRequest;
    const values = birthValues();
    try {
      if ($("profile-birth-clock").value && !values.birth_date) throw new Error("请先填写出生日期。");
      const chart = await api("/api/profiles/bazi", values);
      if (request !== birthRequest) return;
      displayBirth(chart);
      if (values.birth_date) $("profile-bazi").value = chart.text;
      $("profile-bazi").hidden = Boolean(values.birth_date) || !$("profile-bazi").value;
    } catch (e) {
      if (request === birthRequest) displayBirth({ message: e.message });
    }
  }
  function editProfile(id = "") {
    var _a, _b;
    ++birthRequest;
    clearTimeout(birthTimer);
    const p = profiles.find((x) => x.person_id === id);
    editingVersion = (p == null ? void 0 : p.version) || null;
    $("profile-edit-select").value = id;
    fields.forEach((k) => {
      $("profile-" + k).value = (p == null ? void 0 : p.profile[k]) || "";
    });
    $("profile-birth_date").value = (p == null ? void 0 : p.profile.birth_date) || ((_a = p == null ? void 0 : p.profile.birth_time) == null ? void 0 : _a.slice(0, 10)) || "";
    $("profile-birth-clock").value = ((_b = p == null ? void 0 : p.profile.birth_time) == null ? void 0 : _b.includes("T")) ? p.profile.birth_time.slice(11, 19) : "";
    $("profile-is-self").checked = Boolean(p == null ? void 0 : p.is_self);
    $("profile-message").textContent = "";
    previewBirth();
  }
  for (const id of ["profile-birth_date", "profile-birth-clock"]) $(id).addEventListener("input", () => {
    ++birthRequest;
    clearTimeout(birthTimer);
    $("profile-bazi").value = "";
    birthTimer = setTimeout(previewBirth, 180);
  });
  async function openProfiles() {
    try {
      await loadProfiles();
      editProfile($("profile-select").value);
      $("profiles-dialog").showModal();
    } catch (e) {
      $("global-message").textContent = e.message;
      $("global-message").hidden = false;
    }
  }
  $("profiles-open").addEventListener("click", openProfiles);
  $("profile-create").addEventListener("click", openProfiles);
  $("profile-edit-select").addEventListener("change", () => editProfile($("profile-edit-select").value));
  $("profile-select").addEventListener("change", () => {
    requestedProfile = $("profile-select").value;
  });
  $("profile-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    $("profile-save").disabled = true;
    try {
      if ($("profile-birth-clock").value && !$("profile-birth_date").value) throw new Error("请先填写出生日期。");
      const profile = __spreadValues(__spreadValues({}, Object.fromEntries(fields.map((k) => [k, $("profile-" + k).value]))), birthValues());
      const body = { profile, is_self: $("profile-is-self").checked };
      if ($("profile-edit-select").value) {
        body.person_id = $("profile-edit-select").value;
        body.expected_version = editingVersion;
      }
      const p = await api("/api/profiles", body);
      requestedProfile = p.person_id;
      await loadProfiles();
      editProfile(p.person_id);
      $("profile-select").dispatchEvent(new Event("change"));
      $("profile-message").textContent = "档案与自动计算的八字已保存，并选用于当前录入。";
    } catch (e2) {
      $("profile-message").textContent = e2.message;
    } finally {
      $("profile-save").disabled = false;
    }
  });
  function showRuleContent(value) {
    document.querySelector(".rule-browser").hidden = !value;
    $("rules-empty").hidden = value;
    $("rules-export").hidden = !value;
  }
  async function loadRules() {
    ++previewRequest;
    const status = await api("/api/rules");
    if (!status.installed) {
      guide = null;
      rulesVersion = "";
      showRuleContent(false);
      $("rules-version").textContent = "尚未安装规则包 · 使用原理可直接阅读";
      if ($("parameter-tab").getAttribute("aria-pressed") === "true") window.RuleWorkbench.show("package");
      return false;
    }
    guide = await api("/api/rules/guide");
    const kinds = new Map(guide.kinds.map((k, i) => [k.id, i]));
    guide.rules.sort((a, b) => kinds.get(a.kind) - kinds.get(b.kind) || a.id.localeCompare(b.id));
    rulesVersion = guide.version;
    showRuleContent(true);
    window.RuleWorkbench.overview(guide);
    $("rules-version").textContent = "".concat(guide.rules.length, " 项参数 · ").concat(guide.version);
    if (!guide.rules.some((r) => r.id === selectedRule)) selectedRule = "BASE_SCORE";
    refreshRules();
    return true;
  }
  function renderRules() {
    if (!guide) return;
    const { table, model } = window.RuleWorkbench, page = model.page(guide.rules, $("rule-search").value, $("rule-kind").value, rulePage);
    rulePage = page.page;
    const list = table(["参数", "当前值"], page.rows.map((r) => {
      const b = node("button", "", "rule-item");
      b.type = "button";
      b.setAttribute("aria-pressed", String(r.id === selectedRule));
      b.setAttribute("aria-controls", "rule-detail");
      b.append(node("span", r.name), node("small", r.id));
      b.addEventListener("click", () => {
        selectRule(r.id);
        if (window.matchMedia("(max-width:760px)").matches) $("rule-detail").scrollIntoView({ block: "start", behavior: "smooth" });
      });
      return [b, model.value(r)];
    }), "rule-parameter-table");
    [...list.querySelectorAll("tbody tr")].forEach((tr, i) => {
      tr.dataset.selected = String(page.rows[i].id === selectedRule);
    });
    $("rule-list").replaceChildren(page.rows.length ? list : node("p", "没有匹配的参数。", "empty-state"));
    $("rule-page").textContent = "".concat(rulePage + 1, " / ").concat(page.pages, " · ").concat(page.total, " 项");
    $("rule-prev").disabled = rulePage === 0;
    $("rule-next").disabled = rulePage === page.pages - 1;
  }
  function refreshRules() {
    if (!guide) return;
    const page = window.RuleWorkbench.model.page(guide.rules, $("rule-search").value, $("rule-kind").value, rulePage);
    rulePage = page.page;
    if (page.rows.length) selectRule(page.rows.some((r) => r.id === selectedRule) ? selectedRule : page.rows[0].id);
    else {
      ++previewRequest;
      renderRules();
      $("rule-detail").replaceChildren(node("p", "没有匹配的参数，请调整筛选条件。", "empty-state"));
    }
  }
  function selectRule(id) {
    ++previewRequest;
    selectedRule = id;
    const r = guide.rules.find((r2) => r2.id === id);
    if (!r) return;
    renderRules();
    const { table, fold, model } = window.RuleWorkbench, box = $("rule-detail");
    box.replaceChildren(node("p", r.id, "eyebrow"), node("h3", r.name), node("p", r.kind_label + " · " + r.category, "rule-type-label"));
    box.append(table(["项目", "说明"], [["作用范围", r.affects], ["生效条件", r.condition], ["计算方式", r.formula]], "rule-pairs"));
    const form = node("form", "", "rule-trial");
    form.append(node("h4", "试调这一项"));
    const valueCell = node("div"), label = node("label", "试调值", "sr-only");
    label.htmlFor = "trial-value";
    const input = node(r.type === "branch" ? "select" : "input");
    input.id = "trial-value";
    if (r.type === "branch") for (const b of "子丑寅卯辰巳午未申酉戌亥") input.append(node("option", b));
    else {
      input.type = "number";
      input.step = "any";
      input.min = r.min;
      input.max = r.max;
    }
    input.value = r.value;
    input.disabled = r.kind === "switch";
    input.hidden = r.kind === "switch";
    input.required = true;
    valueCell.append(label, input);
    if (r.kind === "switch") valueCell.append(node("span", "通过启用切换"));
    const checkLabel = node("label", "", "checkbox-line"), check = node("input");
    check.type = "checkbox";
    check.id = "trial-enabled";
    check.checked = r.enabled;
    check.disabled = r.required;
    checkLabel.append(check, document.createTextNode(r.required ? "启用（必要）" : "启用"));
    form.append(table(["设置", "当前", "试调"], [["参数值", r.kind === "switch" ? "不计分" : String(r.value), valueCell], ["状态", r.enabled ? "启用" : "停用", checkLabel]], "rule-values"));
    form.append(node("p", r.kind === "switch" ? "结构开关只改变识别结果。" : r.type === "branch" ? "地支约定可能改变动变标记。" : "允许范围 ".concat(r.min, " ～ ").concat(r.max, "。"), "small-note"));
    form.append(node("p", analysisInput ? "试算对象：当前显示卦盘（按当前规则计算）" : "试算对象：固定演示卦，非你的案例", "small-note"));
    const actions = node("div", "", "rule-trial-actions"), button = node("button", "试算对比", "primary-button"), reset = node("button", "恢复当前值", "secondary-button");
    button.type = "submit";
    reset.type = "button";
    actions.append(button, reset);
    const draftStatus = node("p", "与当前设置一致", "small-note");
    draftStatus.id = "trial-draft-status";
    draftStatus.setAttribute("role", "status");
    const output = node("div");
    output.id = "rule-trial-result";
    output.setAttribute("role", "status");
    form.append(draftStatus, actions, output);
    box.append(form);
    function invalidate() {
      ++previewRequest;
      output.replaceChildren();
      const changed = String(input.value) !== String(r.value) || check.checked !== r.enabled;
      draftStatus.textContent = changed ? "有试调改动 · 尚未试算" : "与当前设置一致";
    }
    input.addEventListener("input", invalidate);
    input.addEventListener("change", invalidate);
    check.addEventListener("change", invalidate);
    reset.onclick = () => {
      input.value = r.value;
      check.checked = r.enabled;
      invalidate();
    };
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const request = ++previewRequest;
      button.disabled = reset.disabled = true;
      output.replaceChildren(node("p", "正在试算…"));
      try {
        const payload = __spreadProps(__spreadValues({}, model.draft(r, input.value, check.checked)), { expected_version: rulesVersion });
        if (analysisInput) payload.input = analysisInput;
        const result = await api("/api/rules/preview", payload);
        if (request !== previewRequest) return;
        draftStatus.textContent = "已完成对比 · 试调值未保存";
        window.RuleGuideUI.comparison(output, result);
      } catch (e2) {
        if (request === previewRequest) output.replaceChildren(node("p", e2.message));
      } finally {
        button.disabled = reset.disabled = false;
      }
    });
    window.RuleGuideUI.attachLedger(box, { rule: r, api, version: rulesVersion, input: analysisInput });
    const explanation = fold("参数含义、调整影响与依据");
    explanation.append(table(["项目", "说明"], [["含义", r.meaning], ["调整影响", r.increase], ["示例", r.example], ["设定理由", r.rationale], ["数值依据", r.source_note]], "rule-pairs"));
    box.append(explanation);
    const save = node("button", "保存试调的方法", "text-button");
    save.type = "button";
    save.onclick = () => window.RuleWorkbench.show("package");
    box.append(save);
  }
  for (const id of ["rule-search", "rule-kind"]) $(id).addEventListener(id === "rule-search" ? "input" : "change", () => {
    rulePage = 0;
    refreshRules();
  });
  $("rule-prev").addEventListener("click", () => {
    rulePage--;
    refreshRules();
  });
  $("rule-next").addEventListener("click", () => {
    rulePage++;
    refreshRules();
  });
  $("rules-open").addEventListener("click", async () => {
    window.MobileUI.openRules();
    $("rules-message").textContent = "";
    try {
      await loadRules();
    } catch (e) {
      $("rules-message").textContent = e.message;
    }
  });
  function readFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(new Uint8Array(reader.result));
      reader.onerror = () => reject(new Error("无法读取规则包。"));
      reader.readAsArrayBuffer(file);
    });
  }
  function fromBase64(value, label) {
    if (typeof value !== "string" || value.length > 1e7 || !/^[A-Za-z0-9+/]*={0,2}$/.test(value)) throw new Error(label + "格式无效。");
    let raw;
    try {
      raw = atob(value);
    } catch (_) {
      throw new Error(label + "格式无效。");
    }
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    return bytes;
  }
  function toBase64(bytes) {
    let text = "";
    for (let i = 0; i < bytes.length; i += 8192) text += String.fromCharCode(...bytes.subarray(i, i + 8192));
    return btoa(text);
  }
  async function sha256(bytes) {
    const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
    return Array.from(digest, (b) => b.toString(16).padStart(2, "0")).join("");
  }
  async function ruleWorkbook(file) {
    var _a, _b, _c, _d, _e, _f;
    const source = await readFile(file);
    if (source.length >= 4 && source[0] === 80 && source[1] === 75 && source[2] === 3 && source[3] === 4) return source;
    if (!((_a = window.crypto) == null ? void 0 : _a.subtle)) throw new Error("当前系统 WebView 不支持规则包解密，请升级 Android System WebView。");
    let pack;
    try {
      pack = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(source));
    } catch (_) {
      throw new Error("文件不是有效的 .lyrules 规则包或 XLSX。");
    }
    if ((pack == null ? void 0 : pack.format) !== rulePackageFormat || pack.version !== 1) throw new Error("规则包版本不受支持。");
    const iterations = (_b = pack.kdf) == null ? void 0 : _b.iterations;
    if (((_c = pack.kdf) == null ? void 0 : _c.name) !== "PBKDF2-HMAC-SHA-256" || !Number.isInteger(iterations) || iterations < 1e5 || iterations > 2e6) throw new Error("规则包密钥参数无效。");
    if (((_d = pack.cipher) == null ? void 0 : _d.name) !== "AES-256-GCM" || ((_e = pack.cipher) == null ? void 0 : _e.tag_length) !== 128) throw new Error("规则包加密参数无效。");
    const salt = fromBase64(pack.kdf.salt, "盐值"), iv = fromBase64(pack.cipher.iv, "随机向量"), ciphertext = fromBase64(pack.ciphertext, "密文");
    if (salt.length < 16 || salt.length > 64 || iv.length !== 12 || ciphertext.length < 17 || ciphertext.length > 6e6) throw new Error("规则包长度无效。");
    const password = $("rules-password").value;
    if (!password) throw new Error("请输入规则包口令。");
    try {
      const encoder = new TextEncoder(), material = await crypto.subtle.importKey("raw", encoder.encode(password), "PBKDF2", false, ["deriveKey"]), key = await crypto.subtle.deriveKey({ name: "PBKDF2", salt, iterations, hash: "SHA-256" }, material, { name: "AES-GCM", length: 256 }, false, ["decrypt"]), plain = new Uint8Array(await crypto.subtle.decrypt({ name: "AES-GCM", iv, additionalData: encoder.encode(rulePackageAad), tagLength: 128 }, key, ciphertext));
      if (plain.length > 5e6 || plain[0] !== 80 || plain[1] !== 75 || plain[2] !== 3 || plain[3] !== 4) throw new Error("解密内容不是规则表。");
      if (((_f = pack.payload) == null ? void 0 : _f.sha256) && await sha256(plain) !== pack.payload.sha256) throw new Error("规则包摘要不匹配。");
      return plain;
    } catch (e) {
      if (e.message === "解密内容不是规则表。" || e.message === "规则包摘要不匹配。") throw e;
      throw new Error("规则包口令不正确，或文件已经损坏。");
    }
  }
  $("rules-import").addEventListener("click", async () => {
    const file = $("rules-file").files[0];
    if (!file) {
      $("rules-message").textContent = "请先选择 .lyrules 规则包或 XLSX 文件。";
      return;
    }
    if (file.size > 7e6) {
      $("rules-message").textContent = "规则包超过 7 MB。";
      return;
    }
    $("rules-import").disabled = true;
    try {
      const bytes = await ruleWorkbook(file);
      await api("/api/rules/import", { xlsx_base64: toBase64(bytes), expected_version: rulesVersion || null });
      await loadRules();
      $("rules-message").textContent = "解密与校验通过，规则已安装。下一次分析使用新规则。";
      $("rules-file").value = "";
      $("rules-password").value = "";
    } catch (e) {
      $("rules-message").textContent = e.message;
    } finally {
      $("rules-import").disabled = false;
    }
  });
  function renderComprehensive(chart) {
    var _a;
    const box = $("comprehensive-content");
    box.replaceChildren();
    const a = chart == null ? void 0 : chart.comprehensive_analysis;
    if (!a) {
      box.append(node("p", "旧版分析未记录综合强度。"));
      return;
    }
    box.append(node("p", "规则版本：".concat(a.rules_version, "。分数为实验强度，范围 0–10。"), "small-note"));
    const table = document.createElement("table");
    const header = document.createElement("tr");
    ["爻位", "本爻", "日月与空破", "动变", "综合分"].forEach((t) => header.append(node("th", t)));
    table.append(header);
    [...a.lines].reverse().forEach((l) => {
      const dm = l.day_month;
      const tags = [dm.month_class ? "月令" + dm.month_class : "缺日月", dm.empty ? "旬空" : "", dm.month_break ? "月破" : "", dm.day_clash ? "日冲" : "", dm.hidden_moving ? "暗动（实验）" : "", dm.day_break ? "日破（实验）" : ""].filter(Boolean);
      const tr = document.createElement("tr");
      const c = l.change;
      [String(l.position), l.relative + l.branch + l.element, tags.join("、"), c ? "".concat(c.relative).concat(c.changed).concat(c.changed_element, "；").concat(c.effects.join("、") || "普通变化") : "静", "".concat(l.strength.score, "/10 ").concat(l.strength.level)].forEach((t) => tr.append(node("td", t)));
      table.append(tr);
    });
    box.append(table);
    a.hidden_spirits.forEach((f) => box.append(node("p", "第".concat(f.position, "爻下伏").concat(f.relative).concat(f.branch).concat(f.element, "；飞神").concat(f.flying_relative).concat(f.flying_branch, "，伏神实验分 ").concat(f.strength.score, "/10。"), "small-note")));
    const u = (_a = a.use_selection) == null ? void 0 : _a.primary;
    if (u == null ? void 0 : u.chosen) {
      const c = u.chosen;
      box.append(node("p", "主用：".concat(c.layer === "hidden" ? "伏神" : "", "第").concat(c.position, "爻").concat(c.relative).concat(c.branch).concat(c.element).concat(u.tied_positions.length ? "；并列候选：" + u.tied_positions.join("、") : "")));
    }
    const details = node("details", "");
    details.append(node("summary", "逐项查看分数依据"));
    a.lines.forEach((l) => {
      details.append(node("h4", "第".concat(l.position, "爻 · 未截断合计 ").concat(l.strength.raw_score)));
      details.append(node("p", "基础分 ".concat(l.strength.base, "\n") + l.strength.contributions.map((c) => "".concat(c.detail, "：").concat(c.value >= 0 ? "+" : "").concat(c.value)).join("\n"), "score-detail"));
    });
    box.append(details);
  }
  function renderAudit(result) {
    var _a, _b;
    const audit = result.audit_report, box = $("audit-content");
    box.replaceChildren();
    $("audit-report").hidden = !audit;
    if (audit) {
      box.append(node("p", "审计警告 ".concat((audit.warnings || []).length, " 项。预测和审计分别保存。")));
      box.append(node("pre", JSON.stringify(audit, null, 2)));
    }
    const info = ((_a = result.user_report) == null ? void 0 : _a.model_info) || ((_b = result.display_report) == null ? void 0 : _b.model_info);
    if (info && Object.keys(info).length) {
      const d = node("details", "", "model-info");
      d.append(node("summary", "模型说明"));
      d.append(node("p", "版本：".concat(info.rules_version, "；").concat(info.strength, "；").concat(info.timing, "。")));
      $("model-info-content").append(d);
    }
  }
  window.LiuyaoV5 = { refreshRuleList() {
    rulePage = 0;
    refreshRules();
  }, setProfile, selectSelf, renderComprehensive, renderAudit, setAnalysisContext(input) {
    analysisInput = input;
    if (guide && !$("rules-page").hidden) refreshRules();
  } };
  loadProfiles().catch(() => {
  });
})();
