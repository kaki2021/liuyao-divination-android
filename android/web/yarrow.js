"use strict";
(() => {
  const PAIRS = { "13": "3", "31": "3", "22": "2", "44": "2", "04": "3", "40": "3" };
  const ORDER = ["13", "31", "22", "44", "04", "40"];
  const POSITIONS = ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"];
  const STATES = ["old_yin", "young_yang", "young_yin", "old_yang"];
  const LABELS = ["老阴 · 动", "少阳 · 静", "少阴 · 静", "老阳 · 动"];
  let root, cursor, lineNav, changeNav, panels, title, status, hint, before, after, previous, next;
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== void 0) n.textContent = text;
    return n;
  };
  const button = (label, action) => {
    const n = el("button", "", label);
    n.type = "button";
    n.addEventListener("click", action);
    return n;
  };
  const groupName = (line, change) => "yarrow-".concat(line + 1, "-").concat(change + 1);
  function read() {
    return Array.from({ length: 6 }, (_, line) => Array.from({ length: 3 }, (_2, change) => {
      var _a;
      return ((_a = root.querySelector('input[name="'.concat(groupName(line, change), '"]:checked'))) == null ? void 0 : _a.value) || null;
    }));
  }
  function derive(results) {
    return Array.from({ length: 6 }, (_, line) => {
      const changes = results == null ? void 0 : results[line];
      return Array.isArray(changes) && changes.length === 3 && changes.every((pair) => Object.prototype.hasOwnProperty.call(PAIRS, pair)) ? STATES[changes.filter((pair) => PAIRS[pair] === "3").length] : null;
    });
  }
  function active() {
    return Math.max(0, Math.min(17, Math.floor(Number(cursor.value)) || 0));
  }
  function show(step, focus = false) {
    cursor.value = String(Math.max(0, Math.min(17, step)));
    refresh();
    if (focus) panels[active()].querySelector("input").focus();
    cursor.dispatchEvent(new Event("change", { bubbles: true }));
  }
  function refresh() {
    if (!root) return;
    const results = read(), lines = derive(results), step = active(), line = Math.floor(step / 3), change = step % 3;
    const pairs = results[line], pair = pairs[change], done = [].concat(...results).filter(Boolean).length;
    title.textContent = "".concat(POSITIONS[line], " · 第 ").concat(change + 1, " 变");
    status.textContent = "已记录 ".concat(done, " / 18 变");
    panels.forEach((panel, i) => {
      panel.hidden = i !== step;
    });
    lineNav.forEach((b, i) => {
      b.textContent = POSITIONS[i] + (lines[i] ? " ✓" : "");
      b.setAttribute("aria-pressed", String(i === line));
    });
    changeNav.forEach((b, i) => {
      b.textContent = "第 ".concat(i + 1, " 变 · ").concat(pairs[i] ? "".concat(pairs[i][0], "与").concat(pairs[i][1]) : "待录");
      b.setAttribute("aria-pressed", String(i === change));
    });
    const prior = pairs.slice(0, change);
    const count = prior.every(Boolean) ? 49 - prior.reduce((total, item) => total + Number(item[0]) + Number(item[1]), 0) : null;
    before.textContent = count === null ? "前面的变尚未记录，暂不能核对本变根数。" : change === 0 ? "本爻从 49 根开始，包含阴阳签。" : "本变应取 ".concat(count, " 根，包含已放回的阴阳签。");
    if (!pair) after.textContent = "实际揲四后，选择左右两侧余策；软件不会代替你起卦。";
    else {
      const remaining = count === null ? null : count - Number(pair[0]) - Number(pair[1]);
      after.textContent = "本变为".concat(PAIRS[pair] === "3" ? "阳象 3" : "阴象 2", "。") + (remaining === null ? "" : "留出余策、放回阴阳签后剩 ".concat(remaining, " 根。"));
    }
    if (lines[line]) hint.textContent = "本爻三变：".concat(pairs.map((item) => PAIRS[item]).join(" → "), "，合成").concat(LABELS[STATES.indexOf(lines[line])], "。") + (line < 5 ? "完成后收回全部余策，恢复 49 根，再起下一爻。" : "六爻录完后，核对下方卦象并保存。");
    else hint.textContent = "每爻连续操作三变；两变之间只放回阴阳签，余策留在旁边。";
    previous.disabled = step === 0;
    next.disabled = !pair || step === 17;
    next.textContent = step === 17 ? "十八变录入结束" : change === 2 ? "下一爻 · 复原 49 根" : "下一变 →";
  }
  function fill(results) {
    var _a;
    if (!root) return;
    root.querySelectorAll('input[type="radio"]').forEach((n) => {
      n.checked = false;
    });
    for (let line = 0; line < 6; line++) for (let change = 0; change < 3; change++) {
      const pair = (_a = results == null ? void 0 : results[line]) == null ? void 0 : _a[change];
      if (ORDER.includes(pair)) root.querySelector('input[name="'.concat(groupName(line, change), '"][value="').concat(pair, '"]')).checked = true;
    }
    const missing = [].concat(...read()).findIndex((pair) => !pair);
    cursor.value = String(missing < 0 ? 0 : missing);
    refresh();
  }
  function focusMissing() {
    const missing = [].concat(...read()).findIndex((pair) => !pair);
    if (missing >= 0) show(missing, true);
    return missing;
  }
  function init(container, onChange) {
    root = container;
    cursor = el("input");
    cursor.type = "hidden";
    cursor.id = "yarrow-step";
    cursor.value = "0";
    const heading = el("div", "section-heading");
    title = el("h3");
    title.id = "yarrow-title";
    status = el("span", "small-note");
    status.id = "yarrow-progress";
    heading.append(title, status);
    const navigation = el("nav", "yarrow-lines");
    navigation.setAttribute("aria-label", "筹策爻位");
    lineNav = POSITIONS.map((label, line) => {
      const b = button(label, () => show(line * 3));
      navigation.append(b);
      return b;
    });
    const changes = el("nav", "yarrow-changes");
    changes.setAttribute("aria-label", "本爻三变");
    changeNav = [0, 1, 2].map((change) => {
      const b = button("", () => show(Math.floor(active() / 3) * 3 + change));
      changes.append(b);
      return b;
    });
    before = el("p", "yarrow-count");
    before.id = "yarrow-count";
    const instruction = el("p", "small-note", "分二 → 取出阴阳签 → 两侧分别揲四。非空侧留 1—4 根，整四留四；空侧记 0。");
    root.append(cursor, navigation, heading, changes, before, instruction);
    panels = Array.from({ length: 18 }, (_, step) => {
      const line = Math.floor(step / 3), change = step % 3, field = el("fieldset", "yarrow-pairs");
      field.append(el("legend", "sr-only", "".concat(POSITIONS[line], "第").concat(change + 1, "变两侧余策")));
      ORDER.forEach((pair) => {
        const label = el("label", "state-option"), radio = el("input");
        radio.type = "radio";
        radio.name = groupName(line, change);
        radio.value = pair;
        radio.setAttribute("aria-label", "".concat(POSITIONS[line], "第").concat(change + 1, "变，左").concat(pair[0], "右").concat(pair[1]));
        const face = el("span", "option-face");
        face.append(el("strong", "", "".concat(pair[0], " 与 ").concat(pair[1])), el("small", "", PAIRS[pair] === "3" ? "阳象 3" : "阴象 2"));
        label.append(radio, face);
        field.append(label);
        radio.addEventListener("change", () => {
          refresh();
          onChange();
        });
      });
      root.append(field);
      return field;
    });
    after = el("p", "yarrow-result");
    after.id = "yarrow-result";
    after.setAttribute("aria-live", "polite");
    hint = el("p", "yarrow-hint");
    hint.id = "yarrow-hint";
    const actions = el("div", "yarrow-actions");
    previous = button("← 上一变", () => {
      if (active() > 0) show(active() - 1);
    });
    previous.id = "yarrow-prev";
    next = button("下一变 →", () => {
      if ([].concat(...read())[active()] && active() < 17) show(active() + 1);
    });
    next.id = "yarrow-next";
    actions.append(previous, next);
    root.append(after, hint, actions);
    refresh();
  }
  window.YarrowInput = { init, read, derive, fill, refresh, focusMissing };
})();
