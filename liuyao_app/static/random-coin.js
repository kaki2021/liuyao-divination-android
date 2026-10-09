'use strict';

// Convenience casting, explicitly separate from physical casting. Each coin
// uses one unbiased bit from the OS-backed Web Crypto generator. No Math.random
// or clock fallback; rendering, restoring and saving never draw new values.
(() => {
  const POSITIONS = ['初爻', '二爻', '三爻', '四爻', '五爻', '上爻'];
  const STATES = ['old_yin', 'young_yang', 'young_yin', 'old_yang'];
  const LABELS = ['老阴 · 动', '少阳 · 静', '少阴 · 静', '老阳 · 动'];
  const valid = value => typeof value === 'string' && /^[23]{3}$/.test(value);
  let root, fields, drawButton, progress, coins, list, notice;
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
  function drawThree() {
    if (!window.crypto || typeof window.crypto.getRandomValues !== 'function') throw new Error('当前环境无法提供系统随机数，请更新系统 WebView，或使用实物起卦录入。');
    const bytes = new Uint8Array(3);
    window.crypto.getRandomValues(bytes);
    // 128 even and 128 odd byte values: P(2) = P(3) = 1/2.
    return Array.from(bytes, byte => String(2 + (byte & 1))).join('');
  }
  function derive(results) {
    return Array.from({ length: 6 }, (_, index) => valid(results?.[index])
      ? STATES[Array.from(results[index]).filter(v => v === '3').length] : null);
  }
  function read() { return fields.map(field => valid(field.value) ? field.value : null); }
  function refresh() {
    if (!root) return;
    const results = read(), missing = results.findIndex(value => !value), count = results.filter(Boolean).length;
    progress.textContent = `已模拟 ${count} / 6 次`;
    drawButton.disabled = missing < 0;
    drawButton.textContent = missing < 0 ? '六爻已齐 · 请保存' : `模拟第 ${missing + 1} 次 · ${POSITIONS[missing]}`;
    const latest = results.filter(Boolean).slice(-1)[0];
    coins.forEach((coin, i) => {
      const value = latest?.[i]; coin.textContent = value ? `${value === '2' ? '阴' : '阳'} ${value}` : '待掷';
      coin.dataset.face = value || ''; coin.setAttribute('aria-label', `最近一次第${i + 1}枚：${value ? value === '2' ? '阴面2' : '阳面3' : '未生成'}`);
    });
    list.replaceChildren();
    results.forEach((token, i) => {
      const row = el('li', 'random-coin-row');
      row.append(el('span', '', POSITIONS[i]), el('code', '', token ? token.split('').join(' · ') : '— · — · —'),
        el('strong', '', token ? LABELS[Array.from(token).filter(v => v === '3').length] : '待模拟'));
      list.append(row);
    });
  }
  function fill(results) {
    if (!root) return;
    fields.forEach((field, i) => { field.value = valid(results?.[i]) ? results[i] : ''; });
    notice.textContent = ''; refresh();
  }
  function init(container, onChange) {
    root = container;
    fields = Array.from({ length: 6 }, (_, i) => { const field = el('input'); field.type = 'hidden'; field.id = `random-coin-${i + 1}`; root.append(field); return field; });
    const heading = el('div', 'section-heading'); progress = el('span', 'small-note'); progress.id = 'random-coin-progress';
    heading.append(el('h3', '', '三枚一掷，六次成卦'), progress);
    const faces = el('div', 'random-coin-faces'); faces.setAttribute('aria-label', '最近一次三枚币的模拟结果');
    coins = [0, 1, 2].map(() => { const coin = el('span', 'random-coin-face'); faces.append(coin); return coin; });
    drawButton = el('button', 'primary-button full-width'); drawButton.type = 'button'; drawButton.id = 'random-coin-draw';
    notice = el('p', 'small-note'); notice.id = 'random-coin-message'; notice.setAttribute('role', 'status');
    list = el('ol', 'random-coin-history'); list.id = 'random-coin-history'; list.setAttribute('aria-label', '随机模拟原始记录，初爻至上爻');
    root.append(heading, faces, drawButton, notice, list,
      el('p', 'small-note', '每次点击才生成下一爻。切换页面、恢复草稿和保存都会保留原结果。要起新卦，请使用“新建系列”或“再起一卦”。'));
    drawButton.addEventListener('click', () => {
      if (drawButton.disabled) return;
      const results = read(), index = results.findIndex(value => !value);
      if (index < 0) return;
      try {
        const token = drawThree(); // If randomness fails, no partial result is stored.
        fields[index].value = token; notice.textContent = '';
        refresh(); onChange({ firstDraw: results.every(value => !value) });
      } catch (error) { notice.textContent = error.message || '本次模拟未完成，请重试。'; }
    });
    refresh();
  }
  window.RandomCoinInput = { init, read, derive, fill, refresh, drawThree };
})();
