(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const state = {page: 'liuyao', chatId: null, chat: null, pendingAsk: null, pendingChat: null,
    pendingIssue: null, jobs: new Map(), restore: null};
  const ISSUE_STATUS = {recorded: '已保存', processing: 'AI 正在处理', applied: '已更新本机技能',
    needs_development: '待开发修复', needs_sources: '待核对资料', needs_information: '需要补充信息',
    needs_model: '待配置模型', reviewed: '已分析，无修改', conflict: '版本变化，尚未应用', failed: '处理未完成'};
  const PREF = {concise: '简洁', balanced: '适中', detailed: '详细', paragraphs: '段落', steps: '步骤', plain: '直接表达', beginner: '解释术语'};
  const node = (tag, cls, text) => {const n = document.createElement(tag);if (cls) n.className = cls;if (text !== undefined) n.textContent = String(text);return n;};
  const clear = el => {while (el.firstChild) el.removeChild(el.firstChild);};
  const key = () => window.LiuyaoCompat.requestId();
  function status(id, message, error = false) {
    // A pending local request may settle after WebView navigation/disposal.
    if (typeof document === 'undefined') return;
    const element = $(id);if (!element) return;
    element.textContent = message;element.classList.toggle('is-error', error);
  }
  function model() {return {provider: $('provider-select').value, model: $('model-select').value};}
  function nativeBusy() {window.LiuyaoAndroid?.analysisState(Boolean(state.jobs.size || window.LiuyaoApp?.isAnalyzing() || window.DialogueUI?.isBusy()));}
  function persist() {window.LiuyaoApp?.persistDraft();}
  async function api(path, data, idempotencyKey) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();xhr.open(data === undefined ? 'GET' : 'POST', '/api/workbench/' + path);xhr.timeout = 15000;
      xhr.setRequestHeader('X-App-Request', '1');xhr.setRequestHeader('Accept', 'application/json');
      if (data !== undefined) {xhr.setRequestHeader('Content-Type', 'application/json');xhr.setRequestHeader('X-Idempotency-Key', idempotencyKey || key());}
      xhr.onload = () => {try {const value = JSON.parse(xhr.responseText);if (xhr.status < 200 || xhr.status >= 300) reject(new Error(value.error?.message || '操作未完成。'));else resolve(value);}catch (_) {reject(new Error('本地服务返回格式无效。'));}};
      xhr.onerror = () => reject(new Error('本地连接中断。输入已保留，可重试原请求。'));
      xhr.ontimeout = () => reject(new Error('本地服务未及时响应。输入已保留，可重试原请求。'));
      xhr.send(data === undefined ? null : JSON.stringify(data));
    });
  }
  function page(name, scroll = true) {
    if (!['liuyao', 'knowledge', 'issues'].includes(name)) name = 'liuyao';
    state.page = name;document.body.dataset.workbenchPage = name;
    $('knowledge-workspace').hidden = name !== 'knowledge';$('issues-workspace').hidden = name !== 'issues';
    document.querySelectorAll('[data-skill-page]').forEach(b => {if (b.dataset.skillPage === name) b.setAttribute('aria-current', 'page');else b.removeAttribute('aria-current');});
    if (name === 'knowledge') {loadDocuments().catch(error => status('kb-status', error.message, true));loadChats().catch(error => status('kb-status', error.message, true));}
    if (name === 'issues') refreshIssues().catch(error => status('skill-issue-status', error.message, true));
    if (scroll) window.scrollTo({top: 0, behavior: 'smooth'});
    if (scroll) persist();
  }
  async function loadDocuments() {
    const result = await api('documents');clear($('kb-documents'));$('kb-document-count').textContent = String(result.documents.length);
    if (!result.documents.length) {$('kb-documents').append(node('p', 'small-note', '还没有导入资料。可以先添加一份文档或粘贴原文。'));return;}
    for (const document of result.documents) {
      const row = node('div', 'kb-document'), info = node('div');
      info.append(node('strong', '', document.title), node('p', 'small-note', `${document.characters} 字 · ${document.chunks} 个检索片段`));
      const remove = node('button', 'text-button', '移出检索');remove.type = 'button';
      remove.onclick = async () => {if (!window.confirm('将这份资料移出后续检索？已保存的历史引用仍会保留。')) return;remove.disabled = true;try {await api('documents/' + document.document_id + '/remove', {});await loadDocuments();status('kb-status', '已移出后续检索。历史对话与引用保留。');}catch (error) {status('kb-status', error.message, true);remove.disabled = false;}};
      row.append(info, remove);$('kb-documents').append(row);
    }
  }
  function readFile(file) {return new Promise((resolve, reject) => {const reader = new FileReader();reader.onload = () => resolve(String(reader.result).split(',')[1]);reader.onerror = () => reject(new Error('无法读取文件。'));reader.readAsDataURL(file);});}
  async function importDocument(event) {
    event.preventDefault();$('kb-import-button').disabled = true;
    try {
      const file = $('kb-file').files[0], text = $('kb-import-text').value;
      if (file && text.trim()) throw new Error('请选择文件或粘贴文字其中一种方式。');
      const body = {title: $('kb-document-title').value};
      if (file) {if (file.size > 4000000) throw new Error('单个文件请控制在 4 MB 以内。');body.filename = file.name;body.file_base64 = await readFile(file);}else body.text = text;
      const result = await api('documents', body);$('kb-import-form').reset();await loadDocuments();
      status('kb-status', result.duplicate ? '相同正文已在资料库中，已恢复用于检索。' : '资料已保存，现在可以提问。');
    } catch (error) {status('kb-status', error.message, true);}finally {$('kb-import-button').disabled = false;}
  }
  async function loadChats() {
    const result = await api('chats');const selected = state.chatId;clear($('kb-chat-select'));
    const empty = node('option', '', '开始一段新对话');empty.value = '';$('kb-chat-select').append(empty);
    for (const chat of result.chats) {const option = node('option', '', chat.title);option.value = chat.chat_id;$('kb-chat-select').append(option);}
    $('kb-chat-select').value = selected || '';
  }
  function renderChat(chat) {
    state.chat = chat;clear($('kb-turns'));
    if (!chat?.turns.length) $('kb-turns').append(node('p', 'empty-state', '可以问：“资料中怎样解释五行？”'));
    for (const turn of chat?.turns || []) {
      const row = node('article', 'kb-turn');row.append(node('div', 'kb-question-bubble', turn.question));
      const result = turn.result;
      row.append(node('div', 'kb-answer', result?.answer || result?.error?.message || (turn.status === 'failed' ? '回答未完成，提问已保留。' : '正在检索资料并回答…')));
      if (result?.demo) row.append(node('p', 'small-note', '离线演示 · 未调用模型'));
      if (result?.insufficient) row.append(node('p', 'small-note', '资料不足：请结合回答补充原文。'));
      for (const source of result?.citations || []) {
        const detail = node('details', 'kb-citation');detail.append(node('summary', '', `${source.title} · 第 ${source.sequence} 段 · 版本 ${source.version}`), node('blockquote', '', source.text));row.append(detail);
      }
      row.append(node('p', 'small-note', `技能偏好版本 ${turn.skill_version} · ${turn.status === 'completed' ? '已保存' : turn.status === 'failed' ? '未完成' : '进行中'}`));$('kb-turns').append(row);
    }
    $('kb-export').hidden = !state.chatId;
    if (state.chatId) $('kb-export').href = '/api/workbench/chats/' + state.chatId + '/export';
  }
  async function loadChat(chatId) {
    const chat = await api('chats/' + encodeURIComponent(chatId));
    if (state.chatId === chatId) renderChat(chat);
  }
  function busyKnowledge() {return Array.from(state.jobs.values()).some(j => j.kind === 'knowledge' && j.chatId === state.chatId);}
  function updateSend() {$('kb-send').disabled = busyKnowledge();$('kb-send').textContent = busyKnowledge() ? '正在回答…' : '发送问题 ↗';}
  function watch(jobId, kind, chatId) {
    if (state.jobs.has(jobId)) return;
    const job = {kind, chatId};state.jobs.set(jobId, job);updateSend();nativeBusy();
    async function tick() {
      try {
        const result = await api('jobs/' + jobId);
        if (['completed', 'failed'].includes(result.status)) {
          state.jobs.delete(jobId);nativeBusy();updateSend();
          if (kind === 'knowledge') {
            if (state.chatId === chatId) {await loadChat(chatId);status('kb-status', result.result?.error?.message || '回答与出处已保存。', result.status === 'failed');}
            if (state.pendingAsk?.jobId === jobId) state.pendingAsk = null;
          } else {await refreshIssues();status('skill-issue-status', result.result?.error?.message || 'AI 处理已完成，请查看反馈记录。', result.status === 'failed');}
          persist();return;
        }
        if (kind === 'knowledge' && state.chatId === chatId) status('kb-status', '正在检索资料并回答，离开此页后任务仍会保留。');
      } catch (error) {status(kind === 'knowledge' ? 'kb-status' : 'skill-issue-status', error.message, true);}
      job.timer = setTimeout(tick, 1300);
    }
    tick();
  }
  async function ask(event) {
    event.preventDefault();if (busyKnowledge()) return;$('kb-send').disabled = true;
    const question = $('kb-question').value.trim();
    try {
      if (!question) throw new Error('请先写下问题。');
      if (!state.chatId) {
        if (!state.pendingChat) state.pendingChat = {title: question.slice(0, 60), key: key()};persist();
        const created = await api('chats', {title: state.pendingChat.title}, state.pendingChat.key);
        state.chatId = created.chat_id;state.pendingChat = null;await loadChats();
      }
      const body = {question, ...model()}, fingerprint = JSON.stringify([state.chatId, body]);
      if (!state.pendingAsk || state.pendingAsk.fingerprint !== fingerprint) state.pendingAsk = {fingerprint, key: key(), chatId: state.chatId};persist();
      const accepted = await api('chats/' + state.chatId + '/ask', body, state.pendingAsk.key);state.pendingAsk.jobId = accepted.job_id;
      $('kb-question').value = '';persist();await loadChat(state.chatId);watch(accepted.job_id, 'knowledge', state.chatId);
    } catch (error) {status('kb-status', error.message, true);}finally {updateSend();}
  }
  async function loadVersions() {
    const skill = $('version-skill').value, result = await api('skills/' + skill + '/versions');
    if (skill !== $('version-skill').value) return;clear($('skill-version-list'));
    for (const version of result.versions) {
      const row = node('div', 'skill-version'), p = version.preferences;
      row.append(node('strong', '', `版本 ${version.version}${version.version === result.active.version ? ' · 当前使用' : ''}`),
        node('p', '', `${PREF[p.detail]} · ${PREF[p.layout]} · ${PREF[p.tone]} · ${p.clarify_first ? '缺资料时先澄清' : '先回答有依据的部分'}`));
      if (version.version !== result.active.version) {
        const button = node('button', 'text-button', '恢复此版本');button.type = 'button';
        button.onclick = async () => {button.disabled = true;try {await api('skills/' + skill + '/rollback', {version: version.version, expected_version: result.active.version});await loadVersions();status('skill-issue-status', '已恢复所选偏好。历史回答保持原样。');}catch (error) {status('skill-issue-status', error.message, true);button.disabled = false;}};row.append(button);
      }
      $('skill-version-list').append(row);
    }
  }
  async function processIssue(issueId) {
    const accepted = await api('issues/' + issueId + '/process', model());watch(accepted.job_id, 'issue');await refreshIssues();
  }
  async function saveIssue(event, process) {
    event?.preventDefault();$('issue-save').disabled = $('issue-process').disabled = true;
    try {
      const body = {skill_id: $('issue-skill').value, title: $('issue-title').value, description: $('issue-description').value};
      const fingerprint = JSON.stringify(body);
      if (!state.pendingIssue || state.pendingIssue.fingerprint !== fingerprint) state.pendingIssue = {fingerprint, key: key()};persist();
      const saved = await api('issues', body, state.pendingIssue.key);
      if (process) await processIssue(saved.issue_id);
      $('issue-title').value = '';$('issue-description').value = '';state.pendingIssue = null;persist();await refreshIssues();
      status('skill-issue-status', process ? '问题已保存，AI 正在分析处理。' : '反馈已保存。可在记录中继续交给 AI 处理。');
    } catch (error) {status('skill-issue-status', error.message, true);}finally {$('issue-save').disabled = $('issue-process').disabled = false;}
  }
  async function refreshIssues() {
    const result = await api('issues');clear($('skill-issue-list'));
    if (!result.issues.length) $('skill-issue-list').append(node('p', 'small-note', '还没有反馈。可以记录遇到的问题或希望增加的功能。'));
    for (const issue of result.issues) {
      const row = node('article', 'skill-issue'), result = issue.result;
      row.append(node('span', 'soft-tag', `${issue.skill_id === 'liuyao' ? '六爻占问' : '知识库问答'} · ${ISSUE_STATUS[issue.status] || issue.status}`), node('h3', '', issue.title));
      const original = node('details');original.append(node('summary', '', '查看原始反馈'), node('p', '', issue.description));row.append(original);
      if (result) {
        row.append(node('p', '', result.summary || result.error?.message || '已处理。'));
        if (result.applied_skill) {const p = result.applied_skill.preferences;row.append(node('p', 'small-note', `已应用偏好版本 ${result.applied_skill.version}：${PREF[p.detail]}、${PREF[p.layout]}、${PREF[p.tone]}。可在版本列表回退。`));}
        if (result.acceptance?.length) {const details = node('details');details.append(node('summary', '', '验收要求'));const list = node('ul');result.acceptance.forEach(s => list.append(node('li', '', s)));details.append(list);row.append(details);}
      }
      const tools = node('div', 'skill-toolbar'), exportLink = node('a', 'text-button', '导出反馈 / 修复任务');exportLink.href = '/api/workbench/issues/' + issue.issue_id + '/export';exportLink.download = '技能反馈.json';tools.append(exportLink);
      if (!['processing', 'applied', 'reviewed'].includes(issue.status)) {const button = node('button', 'text-button', '交给 AI 处理');button.type = 'button';button.onclick = async () => {button.disabled = true;try {await processIssue(issue.issue_id);}catch (error) {status('skill-issue-status', error.message, true);button.disabled = false;}};tools.append(button);}
      row.append(tools);$('skill-issue-list').append(row);
    }
    await loadVersions();
  }
  function draft() {return {page: state.page, chatId: state.chatId, question: $('kb-question').value,
    issueSkill: $('issue-skill').value, issueTitle: $('issue-title').value, issueDescription: $('issue-description').value,
    pendingAsk: state.pendingAsk, pendingChat: state.pendingChat, pendingIssue: state.pendingIssue};}
  async function restoreDraft(value) {
    if (!value || typeof value !== 'object') return;
    state.chatId = typeof value.chatId === 'string' ? value.chatId : null;
    state.pendingAsk = value.pendingAsk || null;state.pendingChat = value.pendingChat || null;state.pendingIssue = value.pendingIssue || null;
    $('kb-question').value = value.question || '';$('issue-title').value = value.issueTitle || '';$('issue-description').value = value.issueDescription || '';
    if (['liuyao', 'knowledge'].includes(value.issueSkill)) $('issue-skill').value = value.issueSkill;
    page(value.page, false);await loadChats();if (state.chatId) await loadChat(state.chatId);
  }
  window.SkillWorkbench = {page, draft, restoreDraft, isBusy: () => state.jobs.size > 0};
  document.querySelectorAll('[data-skill-page]').forEach(button => button.onclick = () => page(button.dataset.skillPage));
  document.querySelectorAll('.skill-settings').forEach(button => button.onclick = () => $('settings-dialog').showModal());
  $('kb-import-form').addEventListener('submit', importDocument);
  $('kb-file').addEventListener('change', () => {const file = $('kb-file').files[0];if (file && !$('kb-document-title').value) $('kb-document-title').value = file.name.replace(/\.[^.]+$/, '');});
  $('kb-ask-form').addEventListener('submit', ask);
  $('kb-new-chat').onclick = () => {state.chatId = null;state.pendingChat = null;renderChat(null);$('kb-chat-select').value = '';updateSend();persist();};
  $('kb-chat-select').onchange = async () => {state.chatId = $('kb-chat-select').value || null;try {if (state.chatId) await loadChat(state.chatId);else renderChat(null);updateSend();persist();}catch (error) {status('kb-status', error.message, true);}};
  $('skill-issue-form').addEventListener('submit', event => saveIssue(event, false));$('issue-process').onclick = event => saveIssue(event, true);
  $('version-skill').onchange = () => loadVersions().catch(error => status('skill-issue-status', error.message, true));
  $('issues-refresh').onclick = () => refreshIssues().catch(error => status('skill-issue-status', error.message, true));
  const oldBack = window.MobileUI?.back;
  if (oldBack) window.MobileUI.back = () => {if (document.querySelector('dialog[open]')) return oldBack();if (state.page !== 'liuyao') {page('liuyao');return true;}return oldBack();};
  ['provider-select', 'model-select'].forEach(id => $(id).addEventListener('change', () => {$('kb-model-note').textContent = $('provider-select').selectedOptions[0]?.textContent || '使用模型设置中的选择';}));
  page('liuyao', false);$('kb-model-note').textContent = '使用模型设置中的选择';
  Promise.all([loadDocuments(), loadChats(), refreshIssues(), api('active')]).then(values => {
    for (const job of values[3].jobs) {
      if(job.kind==='assistant')continue;
      watch(job.job_id, job.kind, job.chat_id);
    }
  }).catch(error => status('kb-status', error.message, true));
})();
