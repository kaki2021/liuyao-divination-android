/* Shared navigation for the in-app guide and the self-contained HTML export. */
(() => {
  'use strict';
  function mount(root, options = {}) {
    if (!root) return;
    const tabs = [...root.querySelectorAll('[data-help-tab]')];
    const panels = [...root.querySelectorAll('[data-help-panel]')];
    const selector = root.querySelector('#help-method');
    function section(name, focus = false) {
      if (!tabs.some(tab => tab.dataset.helpTab === name)) name = 'start';
      tabs.forEach(tab => {
        const active = tab.dataset.helpTab === name;
        tab.setAttribute('aria-selected', String(active)); tab.tabIndex = active ? 0 : -1;
        if (active && focus) tab.focus();
      });
      panels.forEach(panel => { panel.hidden = panel.dataset.helpPanel !== name; });
      root.dataset.section = name;
      const scroller = root.closest('#user-help-body');
      if (scroller) scroller.scrollTop = 0;
      else if (focus) root.querySelector('.help-tabs').scrollIntoView({block:'start'});
    }
    function method(value) {
      if (![...selector.options].some(option => option.value === value)) value = 'meibu';
      selector.value = value;
      root.querySelectorAll('[data-help-method]').forEach(panel => { panel.hidden = panel.dataset.helpMethod !== value; });
    }
    if (!root.dataset.enhanced) {
      root.dataset.enhanced = 'true';
      root.addEventListener('click', event => {
        const tab = event.target.closest('[data-help-tab]');
        if (tab) section(tab.dataset.helpTab, true);
        const jump = event.target.closest('[data-help-jump]');
        if (jump) section(jump.dataset.helpJump, true);
      });
      root.querySelector('.help-tabs').addEventListener('keydown', event => {
        if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
        const index = tabs.indexOf(document.activeElement); if (index < 0) return;
        event.preventDefault();
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        section(tabs[next].dataset.helpTab, true);
      });
      selector.addEventListener('change', () => method(selector.value));
    }
    section(options.section || 'start'); method(options.method || selector.value);
  }
  window.LiuyaoHelp = {mount};
  // The exported document carries the same script and requires no network access.
  mount(document.querySelector('body > .help-document'));
})();
