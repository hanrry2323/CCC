import { state } from '../state.js';
import { renderMarkdown } from '../markdown.js';
import { escapeHtml, ts, scrollToBottom } from '../utils.js';
import { streamChat } from '../api.js';
import { renderSidebar, refreshSidebar } from './sidebar.js';

let fullContent = '';
let toolCards = [];
let costInfo = null;

export function renderMessage(container, role, content) {
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML = '<div class="bubble">' + renderMarkdown(content) + '</div>' +
    '<div class="time">' + ts() + '</div>';
  container.appendChild(div);
  scrollToBottom(container);

  // Double-click edit on user messages
  if (role === 'user') {
    div.style.cursor = 'pointer';
    div.title = '双击编辑';
    div.addEventListener('dblclick', function () {
      if (event.target.closest('.edit-textarea, .edit-actions, button, .copy-btn')) return;
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

export async function sendMessage(text) {
  const container = document.getElementById('messages');
  const project = state.get('currentProject');
  let msgs = state.get('currentMessages') || [];

  if (state.get('streaming')) return;

  // Add user message
  msgs.push({ role: 'user', content: text, mode: 'chat' });
  renderMessage(container, 'user', text);

  // Show typing
  showTyping(container);

  const sid = state.get('currentSessionId');
  fullContent = '';
  toolCards = [];
  costInfo = null;
  state.set('streaming', true);
  updateComposerState();

  let msgDiv = null;
  let bubble = null;

  await streamChat(
    msgs,
    sid,
    project,
    // onEvent
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
        bubble.innerHTML = renderMarkdown(fullContent);
        toolCards.forEach(c => bubble.appendChild(c));
        scrollToBottom(container);
      } else if (type === 'tool_use') {
        const card = document.createElement('details');
        card.className = 'tool-card';
        card.open = false;
        card.innerHTML = '<summary>🛠 ' + escapeHtml(data.name || 'tool') + '</summary>' +
          '<pre>' + escapeHtml(JSON.stringify(data.input, null, 2)) + '</pre>';
        toolCards.push(card);
        if (bubble) bubble.appendChild(card);
      } else if (type === 'tool_result') {
        if (toolCards.length) {
          const last = toolCards[toolCards.length - 1];
          const pre = document.createElement('pre');
          pre.textContent = typeof data.content === 'string' ? data.content : JSON.stringify(data.content, null, 2);
          last.appendChild(pre);
        }
      } else if (type === 'cost') {
        costInfo = data;
      }
    },
    // onDone
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
      updateComposerState();
      refreshSidebar();
    },
    // onError
    (errorText) => {
      removeTyping();
      renderMessage(container, 'assistant', errorText);
      msgs.push({ role: 'assistant', content: errorText, mode: 'chat' });
      state.set('currentMessages', msgs);
      state.set('streaming', false);
      updateComposerState();
    }
  );
}

export function loadMessages(data) {
  const container = document.getElementById('messages');
  container.innerHTML = '';
  const msgs = data.messages || [];
  state.set('currentMessages', msgs);
  for (const msg of msgs) {
    renderMessage(container, msg.role, msg.content);
  }
  // If there's a reply but no assistant message
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
    import('../api.js').then(m => m.cancelStream());
    state.set('streaming', false);
    updateComposerState();
    removeTyping();
  });
}
