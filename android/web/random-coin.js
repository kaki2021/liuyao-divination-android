"use strict";
(() => {
  const POSITIONS = ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"];
  const STATES = ["old_yin", "young_yang", "young_yin", "old_yang"];
  const LABELS = ["老阴 · 动", "少阳 · 静", "少阴 · 静", "老阳 · 动"];
  const valid = (value) => typeof value === "string" && /^[23]{3}$/.test(value);
  const TOSS_MS = 2e3;
  let root, fields, drawButton, progress, coins, list, notice;
  let tossing = false, timer, frame, generation = 0;
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== void 0) n.textContent = text;
    return n;
  };
  function drawThree() {
    if (!window.crypto || typeof window.crypto.getRandomValues !== "function") throw new Error("当前环境无法提供系统随机数，请更新系统 WebView，或使用实物起卦录入。");
    const bytes = new Uint8Array(3);
    window.crypto.getRandomValues(bytes);
    return Array.from(bytes, (byte) => String(2 + (byte & 1))).join("");
  }
  function derive(results) {
    return Array.from({ length: 6 }, (_, index) => valid(results == null ? void 0 : results[index]) ? STATES[Array.from(results[index]).filter((v) => v === "3").length] : null);
  }
  function read() {
    return fields.map((field) => valid(field.value) ? field.value : null);
  }
  function refresh() {
    if (!root) return;
    const results = read(), missing = results.findIndex((value) => !value), count = results.filter(Boolean).length;
    progress.textContent = "已模拟 ".concat(count, " / 6 次");
    drawButton.disabled = tossing || missing < 0;
    drawButton.textContent = tossing ? "掷币中…" : missing < 0 ? "六爻已齐 · 请保存" : "模拟第 ".concat(missing + 1, " 次 · ").concat(POSITIONS[missing]);
    root.dataset.tossing = String(tossing);
    root.setAttribute("aria-busy", String(tossing));
    const latest = results.filter(Boolean).slice(-1)[0];
    coins.forEach((coin, i) => {
      const value = tossing ? null : latest == null ? void 0 : latest[i];
      coin.querySelector(".coin-value").textContent = value ? "".concat(value === "2" ? "阴" : "阳", " ").concat(value) : "";
      coin.dataset.face = value || "";
      coin.setAttribute("aria-label", "最近一次第".concat(i + 1, "枚：").concat(value ? value === "2" ? "阴面2" : "阳面3" : "未生成"));
    });
    list.replaceChildren();
    results.forEach((token, i) => {
      const row = el("li", "random-coin-row");
      row.append(
        el("span", "", POSITIONS[i]),
        el("code", "", token ? token.split("").join(" · ") : "— · — · —"),
        el("strong", "", token ? LABELS[Array.from(token).filter((v) => v === "3").length] : "待模拟")
      );
      list.append(row);
    });
  }
  function cancel() {
    if (!tossing) return;
    generation++;
    window.clearTimeout(timer);
    window.cancelAnimationFrame(frame);
    tossing = false;
    refresh();
    notice.textContent = "本次掷币已取消，未生成结果。已完成的记录保留。";
  }
  function fill(results) {
    if (!root) return;
    cancel();
    fields.forEach((field, i) => {
      field.value = valid(results == null ? void 0 : results[i]) ? results[i] : "";
    });
    notice.textContent = "";
    refresh();
  }
  function init(container, onChange) {
    root = container;
    fields = Array.from({ length: 6 }, (_, i) => {
      const field = el("input");
      field.type = "hidden";
      field.id = "random-coin-".concat(i + 1);
      root.append(field);
      return field;
    });
    const heading = el("div", "section-heading");
    progress = el("span", "small-note");
    progress.id = "random-coin-progress";
    heading.append(el("h3", "", "三枚一掷，六次成卦"), progress);
    const faces = el("div", "random-coin-faces");
    faces.setAttribute("aria-label", "最近一次三枚币的模拟结果");
    coins = [0, 1, 2].map(() => {
      const coin = el("span", "random-coin-face"), disc = el("span", "coin-disc");
      const front = el("span", "coin-side coin-front"), back = el("span", "coin-side coin-back");
      front.append(el("span", "coin-value"));
      disc.append(front, back);
      coin.append(disc);
      faces.append(coin);
      return coin;
    });
    drawButton = el("button", "primary-button full-width");
    drawButton.type = "button";
    drawButton.id = "random-coin-draw";
    notice = el("p", "small-note");
    notice.id = "random-coin-message";
    notice.setAttribute("role", "status");
    list = el("ol", "random-coin-history");
    list.id = "random-coin-history";
    list.setAttribute("aria-label", "随机模拟原始记录，初爻至上爻");
    root.append(
      heading,
      faces,
      drawButton,
      notice,
      list,
      el("p", "small-note", "静心想好所问，再点击掷币。约 2 秒动效结束后生成本爻；中途离开则取消本次，已有结果保留。")
    );
    drawButton.addEventListener("click", () => {
      if (drawButton.disabled || tossing) return;
      const results = read(), index = results.findIndex((value) => !value);
      if (index < 0) return;
      tossing = true;
      const current = ++generation;
      notice.textContent = "掷币中，请稍候…";
      refresh();
      const bounds = faces.getBoundingClientRect();
      if (bounds.top < 90 || bounds.bottom > window.innerHeight - 90) faces.scrollIntoView({ block: "center", behavior: "auto" });
      frame = window.requestAnimationFrame(() => {
        timer = window.setTimeout(() => {
          frame = window.requestAnimationFrame(() => {
            if (current !== generation || !tossing) return;
            if (document.hidden || !root.getClientRects().length || document.querySelector("dialog[open]")) {
              cancel();
              return;
            }
            try {
              const token = drawThree();
              fields[index].value = token;
              tossing = false;
              refresh();
              notice.textContent = "".concat(POSITIONS[index], "已记录。");
              onChange({ firstDraw: results.every((value) => !value) });
            } catch (error) {
              tossing = false;
              refresh();
              notice.textContent = error.message || "本次模拟未完成，请重试。";
            }
          });
        }, TOSS_MS);
      });
    });
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) cancel();
    });
    window.addEventListener("pagehide", cancel);
    refresh();
  }
  window.RandomCoinInput = { init, read, derive, fill, refresh, drawThree, cancel };
})();
