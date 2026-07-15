import { state } from '../state.js';
import { renderMarkdown } from '../markdown.js';
import { escapeHtml, ts, scrollToBottom, generateId } from '../utils.js';
import { streamChat, cancelStream } from '../api.js';
import { refreshSidebar } from './sidebar.js';
import { createToolCard, updateToolCardStatus, setToolResult, createThinkingIndicator } from './toolCall.js';

let fullContent = '';
let toolCards = [];
let costInfo = null;
let toolIdCounter = 0;

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
  div.innerHTML = '<div class="bubble">' + renderMarkdown(content) + '</div>' +
    '<div class="time">' + ts() + '</div>';
  container.appendChild(div);
  requestAnimationFrame(() => scrollToBottom(container));

  if (role === 'user') {
    div.style.cursor = 'pointer';
    div.title = '双击编辑';
    div.addEventListener('dblclick', function (e) {
      if (e.target.closest('.edit-textarea, .edit-actions, button, .copy-btn')) return;
      editMessage(this, container);
    });
  }
  return div;
}

function editMessage(msgEl, container) {
  const bubble = msgEl.querySelector('.bubble');
  if (!bubble) return;
  const currentText = bubble.textContent || '';
  const safeText = escapeHtml(currentText).replace(/'/g, "\\'");
  bubble.innerHTML = '<div class="edit-area">' +
    '<textarea class="edit-textarea">' + safeText + '</textarea>' +
    '<div class="edit-actions">' +
    '<button class="edit-save" onclick="window.saveEdit(this)">保存</button>' +
    '<button class="edit-cancel" onclick="window.cancelEdit(this)">取消</button>' +
    '</div></div>';
  const ta = bubble.querySelector('.edit-textarea');
  ta.dataset.original = currentText;
  ta.focus();
  ta.setSelectionRange(ta.value.length, ta.value.length);
}

window.saveEdit = function (btn) {
  const area = btn.closest('.edit-area');
  const ta = area.querySelector('.edit-textarea');
  const newText = ta.value.trim();
  const orig = ta.dataset.original || '';
  if (!newText || newText === orig) { doCancelEdit(area, orig); return; }

  const msgEl = btn.closest('.msg');
  if (!msgEl) return;
  const container = document.getElementById('messages');
  const siblings = [];
  let next = msgEl.nextElementSibling;
  while (next) {
    if (next.classList.contains('msg') && !next.classList.contains('typing')) {
      siblings.push(next);
    }
    next = next.nextElementSibling;
  }
  siblings.forEach(s => s.remove());

  const bubble = msgEl.querySelector('.bubble');
  if (bubble) bubble.innerHTML = renderMarkdown(newText);

  let msgs = state.get('currentMessages') || [];
  const idx = msgs.findIndex(m => m.role === 'user');
  if (idx !== -1) {
    msgs = msgs.slice(0, idx + 1);
    msgs[idx].content = newText;
  }
  state.set('currentMessages', msgs);

  const input = document.getElementById('composer-input');
  if (input) {
    input.value = newText;
    input.dispatchEvent(new Event('input'));
  }
  document.getElementById('send-btn')?.click();
};

window.cancelEdit = function (btn) {
  const area = btn.closest('.edit-area');
  const ta = area?.querySelector('.edit-textarea');
  const orig = ta ? (ta.dataset.original || '') : '';
  doCancelEdit(area, orig);
};

function doCancelEdit(area, orig) {
  if (!area) return;
  const bubble = area.closest('.bubble');
  if (bubble) bubble.innerHTML = renderMarkdown(orig || '');
}

export function showTyping(container) {
  removeTyping();
  const el = document.createElement('div');
  el.className = 'msg assistant';
  el.id = 'typing-indicator';
  el.innerHTML = '<div class="bubble" style="display:flex;gap:4px;padding:14px 18px">' +
    '<span class="typing-dot"></span>' +
    '<span class="typing-dot"></span>' +
    '<span class="typing-dot"></span></div>';
  container.appendChild(el);
  scrollToBottom(container);
  return el;
}

export function removeTyping() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
}

function setStreamingIndicator(active) {
  const el = document.getElementById('streaming-indicator');
  if (el) el.classList.toggle('active', active);
}

export async function sendMessage(text) {
  const container = document.getElementById('messages');
  const project = state.get('currentProject');
  let msgs = state.get('currentMessages') || [];

  if (state.get('streaming')) return;

  const empty = container.querySelector('.empty-state');
  if (empty) empty.remove();

  msgs.push({ role: 'user', content: text, mode: 'chat' });
  renderMessage(container, 'user', text);

  showTyping(container);

  const sid = state.get('currentSessionId');
  fullContent = '';
  toolCards = [];
  costInfo = null;
  toolIdCounter = 0;
  state.set('streaming', true);
  setStreamingIndicator(true);
  updateComposerState();

  let msgDiv = null;
  let bubble = null;

  await streamChat(
    msgs,
    sid,
    project,
    (type, data) => {
      if (type === 'delta') {
        if (!msgDiv) {
          removeTyping();
          msgDiv = document.createElement('div');
          msgDiv.className = 'msg assistant';
          msgDiv.innerHTML = '<div class="bubble"></div><div class="time">' + ts() + '</div>';
          container.appendChild(msgDiv);
          bubble = msgDiv.querySelector('.bubble');
        }
        fullContent += data;
        if (bubble) {
          bubble.innerHTML = renderMarkdown(fullContent);
          toolCards.forEach(c => {
            if (!c.parentNode) bubble.appendChild(c);
          });
          // Add streaming cursor
          const cursor = document.createElement('span');
          cursor.className = 'streaming-cursor';
          bubble.appendChild(cursor);
        }
        smartScroll(container);
      } else if (type === 'tool_use') {
        removeTyping();
        if (!msgDiv) {
          msgDiv = document.createElement('div');
          msgDiv.className = 'msg assistant';
          msgDiv.innerHTML = '<div class="bubble"></div><div class="time">' + ts() + '</div>';
          container.appendChild(msgDiv);
          bubble = msgDiv.querySelector('.bubble');
        }
        const toolId = 'tool-' + (++toolIdCounter);
        const card = createToolCard({ id: toolId, name: data.name, input: data.input });
        toolCards.push(card);
        if (bubble) {
          bubble.appendChild(card);
          updateToolCardStatus(card, 'running');
        }
        smartScroll(container);
      } else if (type === 'tool_result') {
        if (toolCards.length) {
          const last = toolCards[toolCards.length - 1];
          setToolResult(last, data.content);
          updateToolCardStatus(last, 'completed', data);
        }
      } else if (type === 'cost') {
        costInfo = data;
      }
    },
    (sessionId) => {
      state.set('currentSessionId', sessionId);
      if (costInfo && msgDiv) {
        const costEl = document.createElement('div');
        costEl.className = 'cost-info';
        costEl.textContent = 'Tokens: ' + (costInfo.tokens || 0) + ' · $' + (costInfo.usd || 0).toFixed(4);
        msgDiv.appendChild(costEl);
      }
      msgs.push({ role: 'assistant', content: fullContent, mode: 'chat' });
      state.set('currentMessages', msgs);
      state.set('streaming', false);
      setStreamingIndicator(false);
      updateComposerState();
      refreshSidebar();
    },
    (errorText) => {
      removeTyping();
      renderMessage(container, 'assistant', errorText);
      msgs.push({ role: 'assistant', content: errorText, mode: 'chat' });
      state.set('currentMessages', msgs);
      state.set('streaming', false);
      setStreamingIndicator(false);
      updateComposerState();
    }
  );
}

let userScrolledUp = false;

function smartScroll(container) {
  if (userScrolledUp) return;
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
    renderMessage(container, msg.role, msg.content);
  }
  if (data.reply && !msgs.some(m => m.role === 'assistant')) {
    renderMessage(container, 'assistant', data.reply);
    msgs.push({ role: 'assistant', content: data.reply, mode: 'chat' });
    state.set('currentMessages', msgs);
  }
}

function updateComposerState() {
  const sendBtn = document.getElementById('send-btn');
  const cancelBtn = document.getElementById('cancel-btn');
  const streaming = state.get('streaming');
  if (sendBtn) sendBtn.style.display = streaming ? 'none' : 'flex';
  if (cancelBtn) cancelBtn.style.display = streaming ? 'flex' : 'none';
}

export function setupCancel() {
  document.getElementById('cancel-btn')?.addEventListener('click', () => {
    cancelStream();
    state.set('streaming', false);
    setStreamingIndicator(false);
    updateComposerState();
    removeTyping();
  });
}

export function createEmptyState() {
  const el = document.createElement('div');
  el.className = 'empty-state';
  el.innerHTML =
    '<svg viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg">' +
      '<rect x="8" y="12" width="56" height="48" rx="10" stroke="currentColor" stroke-width="1.5" fill="none"/>' +
      '<path d="M24 30h24M24 38h16M24 46h12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>' +
      '<circle cx="54" cy="18" r="10" fill="currentColor" opacity="0.15"/>' +
      '<path d="M52 18h4M54 16v4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>' +
    '</svg>' +
    '<div class="empty-state-title">开始一个新对话</div>' +
    '<div class="empty-state-hint">在下方输入消息，或从侧栏选择一个已有对话</div>' +
    '<div class="empty-state-actions">' +
      '<button class="empty-state-btn" onclick="document.getElementById(\'composer-input\')?.focus()">开始输入</button>' +
      '<button class="empty-state-btn" onclick="document.querySelector(\'#sidebar-toggle\')?.click()">查看历史</button>' +
    '</div>';
  return el;
}

// Smart scroll: track if user manually scrolled up
document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('messages');
  if (!container) return;
  container.addEventListener('scroll', () => {
    const atBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 60;
    userScrolledUp = !atBottom;
  });
});

// Titlebar shadow on scroll
document.addEventListener('DOMContentLoaded', () => {
  const msgContainer = document.getElementById('messages');
  const titlebar = document.getElementById('titlebar');
  if (!msgContainer || !titlebar) return;
  msgContainer.addEventListener('scroll', () => {
    titlebar.classList.toggle('scrolled', msgContainer.scrollTop > 10);
  });
});
