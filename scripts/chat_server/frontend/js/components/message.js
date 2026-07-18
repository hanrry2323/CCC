import { state } from '../state.js';
import { renderMarkdown } from '../markdown.js';
import { escapeHtml, ts, scrollToBottom } from '../utils.js';
import { streamChat } from '../api.js';
import { refreshSidebar } from './sidebar.js';
import {
  createProgressRail,
  appendProgressStep,
  completeProgressStep,
  finishProgressRail,
} from './toolCall.js';
import { maybeShowArtifacts } from './artifacts.js';
import {
  beginStream,
  endStream,
  isCurrentTabStreaming,
  isTabStreaming,
  anyStreaming,
  syncStreamingFlagForActiveTab,
} from '../streamRegistry.js';

function attachMessageActions(msgEl, role, content) {
  if (!msgEl || msgEl.querySelector('.msg-actions')) return;
  const actions = document.createElement('div');
  actions.className = 'msg-actions';
  if (role === 'assistant') {
    actions.innerHTML =
      '<button type="button" class="msg-action-btn" data-act="copy">复制</button>' +
      '<button type="button" class="msg-action-btn" data-act="regen">重新生成</button>' +
      '<button type="button" class="msg-action-btn" data-act="preview">预览</button>' +
      '<button type="button" class="msg-action-btn" data-act="task">转任务</button>';
  } else {
    actions.innerHTML =
      '<button type="button" class="msg-action-btn" data-act="copy">复制</button>' +
      '<button type="button" class="msg-action-btn" data-act="edit">编辑</button>';
  }
  msgEl.appendChild(actions);
  actions.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-act]');
    if (!btn) return;
    const act = btn.dataset.act;
    if (act === 'copy') {
      navigator.clipboard.writeText(content || '').then(() => {
        window.showToast?.('已复制', 'success');
      }).catch(() => window.showToast?.('复制失败', 'error'));
    } else if (act === 'edit') {
      editMessage(msgEl, document.getElementById('messages'));
    } else if (act === 'regen') {
      regenerateLast();
    } else if (act === 'preview') {
      maybeShowArtifacts(content || '');
    } else if (act === 'task') {
      import('./dispatchCard.js').then((m) => m.openTransferFromMessage(content || ''));
    }
  });
}

export function renderMessage(container, role, content, appendToLast) {
  const lastMsg = container.lastElementChild;
  if (appendToLast && lastMsg && lastMsg.classList.contains(role) && role === 'assistant') {
    const bubble = lastMsg.querySelector('.bubble');
    if (bubble) {
      const divider = document.createElement('hr');
      bubble.appendChild(divider);
      const fragment = document.createElement('span');
      fragment.innerHTML = renderMarkdown(content);
      bubble.appendChild(fragment);
      const timeEl = lastMsg.querySelector('.time');
      if (timeEl) timeEl.textContent = ts();
      return lastMsg;
    }
  }

  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML =
    '<div class="msg-label">' + (role === 'user' ? 'You' : 'Claude') + '</div>' +
    '<div class="bubble">' + renderMarkdown(content) + '</div>' +
    '<div class="time">' + ts() + '</div>';
  container.appendChild(div);
  attachMessageActions(div, role, content);
  requestAnimationFrame(() => scrollToBottom(container));

  if (role === 'user') {
    div.style.cursor = 'pointer';
    div.title = '双击编辑';
    div.addEventListener('dblclick', function (e) {
      if (e.target.closest('.edit-textarea, .edit-actions, button, .copy-btn, .msg-actions')) return;
      editMessage(this, container);
    });
  }
  return div;
}

function editMessage(msgEl, container) {
  if (isCurrentTabStreaming()) {
    window.showToast?.('生成中不可编辑，请先取消或等完成', 'error');
    return;
  }
  const bubble = msgEl.querySelector('.bubble');
  if (!bubble) return;
  const currentText = bubble.textContent || '';
  const safeText = escapeHtml(currentText).replace(/'/g, "\\'");
  bubble.innerHTML =
    '<div class="edit-area">' +
    '<textarea class="edit-textarea">' +
    safeText +
    '</textarea>' +
    '<div class="edit-actions">' +
    '<button class="edit-save" onclick="window.saveEdit(this)">保存并重发</button>' +
    '<button class="edit-cancel" onclick="window.cancelEdit(this)">取消</button>' +
    '</div></div>';
  const ta = bubble.querySelector('.edit-textarea');
  ta.dataset.original = currentText;
  ta.focus();
  ta.setSelectionRange(ta.value.length, ta.value.length);
}

window.saveEdit = function (btn) {
  if (isCurrentTabStreaming()) {
    window.showToast?.('生成中不可重发', 'error');
    return;
  }
  const area = btn.closest('.edit-area');
  const ta = area.querySelector('.edit-textarea');
  const newText = ta.value.trim();
  const orig = ta.dataset.original || '';
  if (!newText || newText === orig) {
    doCancelEdit(area, orig);
    return;
  }

  const msgEl = btn.closest('.msg');
  if (!msgEl) return;
  const container = document.getElementById('messages');
  let next = msgEl.nextElementSibling;
  while (next) {
    const n = next.nextElementSibling;
    if (next.classList.contains('msg') && !next.classList.contains('typing')) {
      next.remove();
    }
    next = n;
  }

  const bubble = msgEl.querySelector('.bubble');
  if (bubble) bubble.innerHTML = renderMarkdown(newText);

  let msgs = state.get('currentMessages') || [];
  const userNodes = [...container.querySelectorAll('.msg.user')];
  const userIndex = userNodes.indexOf(msgEl);
  let seen = -1;
  let cut = 0;
  for (let i = 0; i < msgs.length; i++) {
    if (msgs[i].role === 'user') {
      seen++;
      if (seen === userIndex) {
        cut = i;
        break;
      }
    }
  }
  state.set('currentMessages', msgs.slice(0, cut));
  msgEl.remove();
  sendMessage(newText);
};

window.cancelEdit = function (btn) {
  const area = btn.closest('.edit-area');
  const ta = area?.querySelector('.edit-textarea');
  const orig = ta ? ta.dataset.original || '' : '';
  doCancelEdit(area, orig);
};

function doCancelEdit(area, orig) {
  if (!area) return;
  const bubble = area.closest('.bubble');
  if (bubble) bubble.innerHTML = renderMarkdown(orig || '');
}

function regenerateLast() {
  if (isCurrentTabStreaming()) return;
  let msgs = state.get('currentMessages') || [];
  while (msgs.length && msgs[msgs.length - 1].role === 'assistant') {
    msgs = msgs.slice(0, -1);
  }
  const lastUser = [...msgs].reverse().find((m) => m.role === 'user');
  if (!lastUser) {
    window.showToast?.('没有可重新生成的用户消息', 'error');
    return;
  }
  state.set('currentMessages', msgs.slice(0, msgs.indexOf(lastUser)));
  const container = document.getElementById('messages');
  const nodes = [...container.querySelectorAll('.msg')];
  let lastUserEl = null;
  for (const n of nodes) {
    if (n.classList.contains('user')) lastUserEl = n;
  }
  if (lastUserEl) {
    let sib = lastUserEl.nextElementSibling;
    while (sib) {
      const n = sib.nextElementSibling;
      sib.remove();
      sib = n;
    }
    lastUserEl.remove();
  }
  sendMessage(lastUser.content);
}

function typingId(tabId) {
  return 'typing-' + (tabId || 'x');
}

export function showTyping(container, tabId) {
  removeTyping(tabId);
  const el = document.createElement('div');
  el.className = 'msg assistant';
  el.id = typingId(tabId);
  el.innerHTML =
    '<div class="msg-label">Claude</div><div class="bubble typing-bubble">' +
    '<span class="typing-dot"></span>' +
    '<span class="typing-dot"></span>' +
    '<span class="typing-dot"></span></div>';
  container.appendChild(el);
  scrollToBottom(container);
  return el;
}

export function removeTyping(tabId) {
  const el =
    document.getElementById(typingId(tabId)) ||
    document.getElementById('typing-indicator');
  if (el) el.remove();
}

function setStreamingIndicator() {
  const el = document.getElementById('streaming-indicator');
  if (!el) return;
  el.classList.toggle('active', anyStreaming());
  const label = el.querySelector('span:not(.dot)');
  if (label) {
    const count = state.get('streamingCount') || 0;
    const max = state.get('maxLiveStreams') || 4;
    if (count > 0) {
      label.textContent =
        count > 1
          ? `生成中 (${count}/${max})…`
          : `生成中 (1/${max})…`;
    } else {
      label.textContent = '生成中...';
    }
  }
}

function persistTabMessages(tabId, msgs, sessionId, projectId) {
  const tabs = state.get('tabs') || [];
  const tab = tabs.find((t) => t.id === tabId);
  if (!tab) return;
  if (sessionId) tab.sessionId = sessionId;
  if (projectId) tab.projectId = projectId;
  tab.messages = msgs.slice();
  const firstUser = msgs.find((m) => m.role === 'user');
  if (firstUser && (!tab.title || tab.title === '新对话')) {
    const raw = firstUser.uiLabel
      ? firstUser.uiLabel
      : String(firstUser.content || '');
    tab.title = raw.slice(0, 28) || '对话';
  }
  state.set('tabs', tabs);
  const project = state.get('currentProject') || 'ccc';
  const visible = tabs.filter((t) => (t.projectId || 'ccc') === project);
  import('./titlebar.js').then((m) =>
    m.renderTabs(visible, state.get('activeTabId'))
  );
}

/** Paint only when this stream still owns the visible tab AND project. */
function canPaint(ownerTabId, ownerProject) {
  return (
    state.get('activeTabId') === ownerTabId &&
    state.get('currentProject') === ownerProject
  );
}

export async function sendMessage(text, attachments = [], opts = {}) {
  const ownerTabId = state.get('activeTabId');
  if (!ownerTabId) return;
  if (isTabStreaming(ownerTabId)) return;

  const container = document.getElementById('messages');
  const project = state.get('currentProject');
  const ownerProject = project;
  let msgs = (state.get('currentMessages') || []).slice();
  let sid = state.get('currentSessionId') || ownerTabId;

  // Reserve stream slot before mutating UI (max concurrent)
  const abort = beginStream(ownerTabId, sid, { projectId: ownerProject });
  if (!abort) {
    const max = state.get('maxLiveStreams') || 4;
    window.showToast?.(
      '已满 ' + max + ' 路并发，请等待或取消一路后再发',
      'error'
    );
    return;
  }

  const empty = container?.querySelector('.empty-state');
  if (empty) empty.remove();

  const uiLabel = (opts && opts.uiLabel) || '';
  const displayText = uiLabel ? '【' + uiLabel + '】' : text;

  msgs.push({
    role: 'user',
    content: text,
    mode: 'chat',
    uiLabel: uiLabel || undefined,
  });
  if (canPaint(ownerTabId, ownerProject) && container) {
    const userEl = renderMessage(container, 'user', displayText);
    if (uiLabel && userEl) {
      userEl.classList.add('msg-qa');
      const bubble = userEl.querySelector('.bubble');
      if (bubble) {
        bubble.classList.add('qa-user-pill');
        bubble.title = text.slice(0, 500) + (text.length > 500 ? '…' : '');
      }
    }
    showTyping(container, ownerTabId);
  }

  persistTabMessages(ownerTabId, msgs, sid, ownerProject);

  let fullContent = '';
  let toolSteps = [];
  let progressRail = null;
  let costInfo = null;
  let msgDiv = null;
  let mdEl = null;
  let toolsHost = null;
  let cursorEl = null;
  let rafPending = false;

  syncStreamingFlagForActiveTab();
  setStreamingIndicator();
  updateComposerState();

  const wireAttachments = (attachments || []).map((a) => ({
    name: a.name,
    content_base64: a.content_base64,
    type: a.type,
  }));

  function ensureAssistantShell() {
    if (!canPaint(ownerTabId, ownerProject)) return;
    const c = document.getElementById('messages');
    if (!c) return;
    if (msgDiv && c.contains(msgDiv)) return;
    removeTyping(ownerTabId);
    msgDiv = document.createElement('div');
    msgDiv.className = 'msg assistant';
    msgDiv.dataset.streamTab = ownerTabId;
    msgDiv.innerHTML =
      '<div class="msg-label">Claude</div>' +
      '<div class="bubble">' +
      '<div class="md-stream"></div>' +
      '<div class="tools-host"></div>' +
      '<span class="streaming-cursor"></span>' +
      '</div>' +
      '<div class="time">' +
      ts() +
      '</div>';
    c.appendChild(msgDiv);
    mdEl = msgDiv.querySelector('.md-stream');
    toolsHost = msgDiv.querySelector('.tools-host');
    cursorEl = msgDiv.querySelector('.streaming-cursor');
    if (fullContent && mdEl) mdEl.innerHTML = renderMarkdown(fullContent);
  }

  function scheduleMarkdownPaint() {
    if (!canPaint(ownerTabId, ownerProject)) return;
    if (rafPending || !mdEl) return;
    rafPending = true;
    requestAnimationFrame(() => {
      rafPending = false;
      if (mdEl && canPaint(ownerTabId, ownerProject)) {
        mdEl.innerHTML = renderMarkdown(fullContent);
        if (fullContent.trim().length > 40 && progressRail) {
          finishProgressRail(progressRail, { hide: true });
        }
        smartScroll(document.getElementById('messages'));
      }
    });
  }

  function bumpPartialAssistant() {
    const base = msgs.filter((m) => !(m.role === 'assistant' && m.partial));
    const next = base.slice();
    if (fullContent) {
      next.push({
        role: 'assistant',
        content: fullContent,
        mode: 'chat',
        partial: true,
      });
    }
    persistTabMessages(ownerTabId, next, sid, ownerProject);
    if (canPaint(ownerTabId, ownerProject)) {
      state.set('currentMessages', next);
    }
  }

  await streamChat(
    msgs.filter((m) => !(m.role === 'assistant' && m.partial)),
    sid,
    project,
    (type, data) => {
      if (type === 'delta') {
        ensureAssistantShell();
        fullContent += data;
        scheduleMarkdownPaint();
        bumpPartialAssistant();
      } else if (type === 'tool_use') {
        ensureAssistantShell();
        if (canPaint(ownerTabId, ownerProject)) {
          if (!progressRail && toolsHost) {
            progressRail = createProgressRail();
            toolsHost.appendChild(progressRail);
          }
          const step = appendProgressStep(progressRail, {
            name: data.name,
            input: data.input,
          });
          toolSteps.push(step);
          smartScroll(document.getElementById('messages'));
        }
      } else if (type === 'tool_result') {
        if (toolSteps.length) {
          completeProgressStep(toolSteps[toolSteps.length - 1], true);
        }
      } else if (type === 'cost') {
        costInfo = data;
      }
    },
    (sessionId) => {
      sid = sessionId || sid;
      if (canPaint(ownerTabId, ownerProject)) {
        state.set('currentSessionId', sid);
        ensureAssistantShell();
        if (mdEl) mdEl.innerHTML = renderMarkdown(fullContent);
        if (cursorEl) cursorEl.remove();
        if (progressRail) finishProgressRail(progressRail, { hide: true });
        if (costInfo && msgDiv) {
          const costEl = document.createElement('div');
          costEl.className = 'cost-info';
          costEl.textContent =
            'Tokens: ' +
            (costInfo.tokens || 0) +
            ' · $' +
            (costInfo.usd || 0).toFixed(4);
          msgDiv.appendChild(costEl);
        }
        if (msgDiv) attachMessageActions(msgDiv, 'assistant', fullContent);
        maybeShowArtifacts(fullContent);
        removeTyping(ownerTabId);
      }
      import('./dispatchFormat.js').then((m) => {
        const p = m.parseDispatchBlock(fullContent);
        if (p.ok && canPaint(ownerTabId, ownerProject)) {
          window.showToast?.(
            '定稿已就绪：点消息「转任务」或工具条「转任务」核实后下达',
            'success'
          );
        }
      });
      const finalMsgs = msgs
        .filter((m) => !(m.role === 'assistant' && m.partial))
        .concat(
          fullContent
            ? [{ role: 'assistant', content: fullContent, mode: 'chat' }]
            : []
        );
      msgs = finalMsgs;
      persistTabMessages(ownerTabId, finalMsgs, sid, ownerProject);
      if (canPaint(ownerTabId, ownerProject)) {
        state.set('currentMessages', finalMsgs);
      }
      endStream(ownerTabId);
      syncStreamingFlagForActiveTab();
      setStreamingIndicator();
      updateComposerState();
      if (state.get('currentProject') === ownerProject) {
        refreshSidebar();
      }
      import('./runtimeStatus.js')
        .then((m) => m.refreshRuntimeStatus?.())
        .catch(() => {});
    },
    (errorText) => {
      if (canPaint(ownerTabId, ownerProject)) {
        removeTyping(ownerTabId);
        renderMessage(
          document.getElementById('messages'),
          'assistant',
          errorText
        );
      }
      const finalMsgs = msgs
        .filter((m) => !(m.role === 'assistant' && m.partial))
        .concat([{ role: 'assistant', content: errorText, mode: 'chat' }]);
      persistTabMessages(ownerTabId, finalMsgs, sid, ownerProject);
      if (canPaint(ownerTabId, ownerProject)) {
        state.set('currentMessages', finalMsgs);
      }
      endStream(ownerTabId);
      syncStreamingFlagForActiveTab();
      setStreamingIndicator();
      updateComposerState();
    },
    wireAttachments,
    { abortController: abort }
  );
}

function syncActiveTab() {
  const tabs = state.get('tabs') || [];
  const activeId = state.get('activeTabId');
  const tab = tabs.find((t) => t.id === activeId);
  if (!tab) return;
  tab.sessionId = state.get('currentSessionId');
  tab.messages = state.get('currentMessages') || [];
  const msgs = tab.messages;
  const firstUser = msgs.find((m) => m.role === 'user');
  if (firstUser && (!tab.title || tab.title === '新对话')) {
    tab.title =
      String(firstUser.uiLabel || firstUser.content || '').slice(0, 28) ||
      '对话';
    import('./titlebar.js').then((m) => m.renderTabs(tabs, activeId));
  }
  state.set('tabs', tabs);
}

let userScrolledUp = false;

function smartScroll(container) {
  if (!container || userScrolledUp) return;
  requestAnimationFrame(() => scrollToBottom(container));
}

export function loadMessages(data) {
  const container = document.getElementById('messages');
  container.innerHTML = '';
  const msgs = data.messages || [];
  if (msgs.length === 0) {
    container.appendChild(createEmptyState());
  }
  state.set('currentMessages', msgs);
  for (const msg of msgs) {
    const label = msg.uiLabel;
    const show =
      label && msg.role === 'user' ? '【' + label + '】' : msg.content;
    const el = renderMessage(container, msg.role, show);
    if (label && msg.role === 'user' && el) {
      el.classList.add('msg-qa');
      const bubble = el.querySelector('.bubble');
      if (bubble) {
        bubble.classList.add('qa-user-pill');
        bubble.title = String(msg.content || '').slice(0, 500);
      }
    }
    if (msg.partial && msg.role === 'assistant' && el) {
      el.classList.add('msg-partial');
    }
  }
  if (data.reply && !msgs.some((m) => m.role === 'assistant')) {
    renderMessage(container, 'assistant', data.reply);
    msgs.push({ role: 'assistant', content: data.reply, mode: 'chat' });
    state.set('currentMessages', msgs);
  }
  syncActiveTab();
}

export function updateComposerState() {
  const sendBtn = document.getElementById('send-btn');
  const cancelBtn = document.getElementById('cancel-btn');
  const streaming = isCurrentTabStreaming();
  const input = document.getElementById('composer-input');
  if (sendBtn) {
    sendBtn.style.display = streaming ? 'none' : 'flex';
    if (!streaming) {
      sendBtn.disabled = !(input?.value.trim());
    }
  }
  if (cancelBtn) cancelBtn.style.display = streaming ? 'flex' : 'none';
  setStreamingIndicator();
}

export function setupCancel() {
  // Cancel handled in composer.js
}

export function createEmptyState() {
  const el = document.createElement('div');
  el.className = 'empty-state';
  el.innerHTML =
    '<div class="empty-brand">CCC</div>' +
    '<div class="empty-state-title">今天想做什么？</div>' +
    '<div class="empty-state-hint">标准投递：聊方案 → <b>定稿方案</b> → 消息上 <b>转任务</b> → 改标题 → <b>下达并开工</b></div>';
  return el;
}

export async function runBaselineAlign() {
  const container = document.getElementById('messages');
  if (!container || isCurrentTabStreaming()) return;
  const empty = container.querySelector('.empty-state');
  if (empty) empty.remove();
  try {
    const { fetchProjectBaseline } = await import('../api.js');
    const data = await fetchProjectBaseline(state.get('currentProject'));
    const bl = data.baseline || {};
    const card = document.createElement('div');
    card.className = 'msg assistant';
    const risks = (bl.risks || [])
      .map((r) => '<li>' + escapeHtml(r) + '</li>')
      .join('');
    card.innerHTML =
      '<div class="msg-label">基线快照</div>' +
      '<div class="bubble baseline-card">' +
      '<p>' +
      escapeHtml(bl.summary || '') +
      '</p>' +
      (risks ? '<ul>' + risks + '</ul>' : '') +
      '<p class="baseline-hint">接着由 Claude 解读结构与下一步…</p>' +
      '</div>' +
      '<div class="time">' +
      ts() +
      '</div>';
    container.appendChild(card);
    smartScroll(container);
    const prompt = data.prompt || '请对齐当前项目基线并说明结构与风险。';
    await sendMessage(prompt, [], { uiLabel: '对齐基线' });
  } catch (err) {
    window.showToast?.(err.message || '基线采集失败', 'error');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('messages');
  if (!container) return;
  container.addEventListener('scroll', () => {
    const atBottom =
      container.scrollTop + container.clientHeight >=
      container.scrollHeight - 60;
    userScrolledUp = !atBottom;
  });
});

document.addEventListener('DOMContentLoaded', () => {
  const msgContainer = document.getElementById('messages');
  const titlebar = document.getElementById('titlebar');
  if (!msgContainer || !titlebar) return;
  msgContainer.addEventListener('scroll', () => {
    titlebar.classList.toggle('scrolled', msgContainer.scrollTop > 10);
  });
});

document.addEventListener('ccc-streams-changed', () => {
  updateComposerState();
  const tabs = state.get('tabs') || [];
  import('./titlebar.js').then((m) =>
    m.renderTabs(tabs, state.get('activeTabId'))
  );
});
