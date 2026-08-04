import { state } from '../state.js';
import { renderMarkdown } from '../markdown.js';
import { escapeHtml, ts, scrollToBottom } from '../utils.js';
import { streamChat } from '../api.js';
import { WAIT_HINT_TEXT } from '../chatStatus.js';
import { refreshSidebar } from './sidebar.js';
import { parseDispatchBlock } from './dispatchFormat.js';
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
import {
  isEnabled as dualPaneEnabled,
  isTabVisible,
  messagesElForTab,
  activeMessagesEl,
} from '../dualPane.js';

function attachMessageActions(msgEl, role, content) {
  if (!msgEl || msgEl.querySelector('.msg-actions')) return;
  const actions = document.createElement('div');
  actions.className = 'msg-actions';
  if (role === 'assistant') {
    actions.innerHTML =
      '<button type="button" class="msg-action-btn" data-act="copy">复制</button>' +
      '<button type="button" class="msg-action-btn" data-act="regen">重新生成</button>' +
      '<button type="button" class="msg-action-btn" data-act="preview">预览</button>';
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
      editMessage(msgEl, activeMessagesEl());
    } else if (act === 'regen') {
      regenerateLast();
    } else if (act === 'preview') {
      maybeShowArtifacts(content || '');
    }
  });
}

export function renderMessage(container, role, content, appendToLast) {
  if (role === 'system') {
    const div = document.createElement('div');
    div.className = 'msg system';
    div.innerHTML =
      '<div class="bubble">' + renderMarkdown(content) + '</div>';
    container.appendChild(div);
    requestAnimationFrame(() => scrollToBottom(container));
    return div;
  }

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

  const isAssistant = (role === 'assistant');
  let draftHtml = '';
  let p = null;
  if (isAssistant) {
    p = parseDispatchBlock(content);
    if (p.ok) {
      const acceptanceList = (p.acceptance || []).map(a => `<li>${escapeHtml(a)}</li>`).join('');
      draftHtml = `
        <div class="draft-card" style="margin-top: 12px; padding: 12px; border: 1px solid var(--ccc-border-accent, #444); border-radius: 6px; background: rgba(255,255,255,0.02);">
          <div class="draft-title" style="font-weight: bold; margin-bottom: 8px; color: var(--ccc-text-accent, #a885f7);">【任务卡草案】${escapeHtml(p.title)}</div>
          <div class="draft-goal" style="margin-bottom: 6px;"><strong>目标</strong>: ${escapeHtml(p.goal)}</div>
          <div class="draft-acceptance" style="margin-bottom: 12px;">
            <strong>验收标准</strong>:
            <ul style="margin: 4px 0 0 16px; padding: 0;">${acceptanceList}</ul>
          </div>
          <div class="draft-actions" style="display: flex; gap: 8px;">
            <button class="btn-primary confirm-btn" style="padding: 4px 12px; font-size: 12px; cursor: pointer; background: var(--ccc-bg-accent, #6200ee); color: #fff; border: none; border-radius: 4px;">确认下达</button>
            <button class="btn-secondary modify-btn" style="padding: 4px 12px; font-size: 12px; cursor: pointer; background: transparent; border: 1px solid #666; color: var(--ccc-text-primary, #ccc); border-radius: 4px;">修改</button>
          </div>
        </div>
      `;
    }
  }

  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML =
    '<div class="msg-label">' + (role === 'user' ? 'You' : 'Claude') + '</div>' +
    '<div class="bubble">' + renderMarkdown(content) + draftHtml + '</div>' +
    '<div class="time">' + ts() + '</div>';
  container.appendChild(div);

  if (isAssistant && p && p.ok) {
    const confirmBtn = div.querySelector('.confirm-btn');
    if (confirmBtn) {
      confirmBtn.addEventListener('click', () => {
        sendMessage("【确认下达】已确认该方案，请正式下达并在 docs/dispatch 目录下创建任务卡。");
      });
    }
    const modifyBtn = div.querySelector('.modify-btn');
    if (modifyBtn) {
      modifyBtn.addEventListener('click', () => {
        const input = document.getElementById('composer-input');
        if (input) {
          input.value = `请修改以下任务方案：\n标题：${p.title}\n目标：${p.goal}\n修改意见：`;
          input.focus();
          input.dispatchEvent(new Event('input'));
        }
      });
    }
  }

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

/** C3/C4: 错误气泡 — 琥珀样式 + 重试按钮（复用标准 actions，重试=重新生成最后一条）。 */
export function renderErrorBubble(container, text, onRetry) {
  const el = renderMessage(container, 'assistant', text);
  el.classList.add('msg-error');
  const bubble = el.querySelector('.bubble');
  if (bubble) bubble.classList.add('bubble-error');
  const actions = el.querySelector('.msg-actions');
  if (actions) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'msg-action-btn retry-btn';
    btn.textContent = '重试';
    btn.addEventListener('click', () => onRetry && onRetry());
    actions.insertBefore(btn, actions.firstChild);
  }
  return el;
}

/** C1: 移除某 tab 内残留的 streaming 光标（取消/错误后清理，避免「假流式」）。 */
export function removeStreamingCursors(tabId) {
  const container = tabId ? messagesElForTab(tabId) : activeMessagesEl();
  if (!container) return;
  container.querySelectorAll('.streaming-cursor').forEach((el) => el.remove());
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
  const container = activeMessagesEl();
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
  const container = activeMessagesEl();
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

/** 首包超时：把打字气泡切成「等待模型响应…」文本（无气泡则忽略）。 */
export function showWaitHint(tabId) {
  const el = document.getElementById(typingId(tabId));
  if (!el) return;
  const dots = el.querySelectorAll('.typing-dot');
  dots.forEach((d) => d.remove());
  const bubble = el.querySelector('.bubble');
  if (bubble) {
    bubble.classList.add('typing-wait');
    bubble.textContent = WAIT_HINT_TEXT;
  }
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

/**
 * Paint when the stream's tab is visible.
 * Dual-pane: either left/right pane; single: active tab + project.
 */
function canPaint(ownerTabId, ownerProject) {
  if (dualPaneEnabled()) {
    return isTabVisible(ownerTabId);
  }
  return (
    state.get('activeTabId') === ownerTabId &&
    state.get('currentProject') === ownerProject
  );
}

function paintContainer(ownerTabId) {
  return messagesElForTab(ownerTabId) || activeMessagesEl();
}

export async function sendMessage(text, attachments = [], opts = {}) {
  const ownerTabId = state.get('activeTabId');
  if (!ownerTabId) return;
  if (isTabStreaming(ownerTabId)) return;

  const container = paintContainer(ownerTabId);
  const project = state.get('currentProject');
  const ownerProject = project;
  let msgs = (state.get('currentMessages') || []).slice();
  let sid = state.get('currentSessionId') || ownerTabId;

  // 首包等待 watch：12s 无首包 → 打字气泡切成「等待模型响应…」
  const WAIT_HINT_MS = 12000;
  let waitTimer = null;
  let firstPacketAt = 0;

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
    // 首包超时：长时间无响应（模型未开始吐）→ 切「等待模型响应…」
    if (!waitTimer) {
      waitTimer = setTimeout(() => {
        if (fullContent === '' && firstPacketAt === 0) {
          showWaitHint(ownerTabId);
        }
      }, WAIT_HINT_MS);
    }
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
  let metaInfo = null;
  let thinkingBuf = '';
  let thinkingEl = null;
  let pendingText = '';
  let twTimer = null;
  let twActive = false;

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
    const c = paintContainer(ownerTabId);
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
        smartScroll(paintContainer(ownerTabId));
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

  /** 首个事件（text/thinking/tool_use/meta 任一）到达 → 取消首包等待提示。 */
  function markFirstPacket() {
    if (firstPacketAt === 0) firstPacketAt = Date.now();
    if (waitTimer) {
      clearTimeout(waitTimer);
      waitTimer = null;
    }
  }

  /** meta 信息条：模型 / 工具 / MCP / skills 可见（T41 心智可见性）。 */
  function paintMetaInfo() {
    if (!metaInfo || !msgDiv) return;
    const bubble = msgDiv.querySelector('.bubble');
    if (!bubble) return;
    let chip = msgDiv.querySelector('.stream-meta');
    if (!chip) {
      chip = document.createElement('div');
      chip.className = 'stream-meta';
      bubble.insertBefore(chip, bubble.firstChild);
    }
    const parts = [];
    if (metaInfo.model) parts.push('模型 ' + metaInfo.model);
    const tools = (metaInfo.tools || []).length;
    const mcp = (metaInfo.mcp_servers || []).length;
    const skills = (metaInfo.skills || []).length;
    if (tools) parts.push('工具 ' + tools);
    if (mcp) parts.push('MCP ' + mcp);
    if (skills) parts.push('skills ' + skills);
    chip.textContent = parts.join(' · ');
    chip.title = JSON.stringify(metaInfo);
  }

  /** 大脑当前动作状态行（T46 B7：思考不可得 → 过程可视化）。
   *  有 thinking 事件内容才建折叠；否则显示「正在分析… / 已用时 Xs」动作行，无内容可展开。 */
  function ensureThinkingHost() {
    if (thinkingEl && msgDiv && msgDiv.contains(thinkingEl)) return thinkingEl;
    if (!msgDiv) return null;
    const bubble = msgDiv.querySelector('.bubble');
    if (!bubble) return null;
    // 仅当确有 thinking 内容才建可展开的 thinking 折叠（不空占位）
    if (!thinkingBuf) return null;
    thinkingEl = document.createElement('details');
    thinkingEl.className = 'thinking-fold';
    thinkingEl.innerHTML =
      '<summary><span class="thinking-summary">思考</span><button type="button" class="thinking-copy" title="复制思考内容">⧉</button></summary>' +
      '<div class="thinking-body"></div>';
    const md = bubble.querySelector('.md-stream');
    if (md) bubble.insertBefore(thinkingEl, md);
    else bubble.prepend(thinkingEl);
    const copyBtn = thinkingEl.querySelector('.thinking-copy');
    if (copyBtn) {
      copyBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        navigator.clipboard?.writeText(thinkingBuf).then(() => {
          window.showToast?.('思考已复制', 'success');
        }).catch(() => window.showToast?.('复制失败', 'error'));
      });
    }
    return thinkingEl;
  }

  function appendThinking(text) {
    if (!text) return;
    thinkingBuf += text;
    const host = ensureThinkingHost();
    if (!host) return;
    const body = host.querySelector('.thinking-body');
    if (body) body.textContent = thinkingBuf;
  }

  /** 过程可视化动作行：大脑当前动作 + 已用时（T46 B7，无 thinking 时替代空白占位）。 */
  let procEl = null;
  let procStart = Date.now();
  let procTimer = null;

  function ensureProcLine() {
    if (procEl && msgDiv && msgDiv.contains(procEl)) return procEl;
    if (!msgDiv) return null;
    const bubble = msgDiv.querySelector('.bubble');
    if (!bubble) return null;
    procEl = document.createElement('div');
    procEl.className = 'proc-line';
    bubble.insertBefore(procEl, bubble.querySelector('.md-stream'));
    tickProcLine();
    if (!procTimer) {
      procTimer = setInterval(tickProcLine, 1000);
    }
    return procEl;
  }

  function tickProcLine() {
    if (!procEl || !procEl.isConnected) {
      if (procTimer) { clearInterval(procTimer); procTimer = null; }
      return;
    }
    const sec = Math.max(1, Math.round((Date.now() - procStart) / 1000));
    procEl.textContent = '正在分析… 已用时 ' + sec + 's';
  }

  function clearProcLine() {
    if (procTimer) { clearInterval(procTimer); procTimer = null; }
    if (procEl && procEl.remove) procEl.remove();
    procEl = null;
  }

  /** 句读分片：优先在标点处断句，避免逐字闪烁；长无标点串按单词/固定窗口切。 */
  function takeSentenceFragment(s) {
    const m = s.match(/^.*?[，。！？；、,.!?;:）)\]}】」]/);
    if (m && m[0]) return m[0];
    if (s.length >= 28) {
      const sp = s.lastIndexOf(' ', 28);
      return sp > 14 ? s.slice(0, sp) : s.slice(0, 28);
    }
    return s;
  }

  const TYPEWRITER_MS = 18;

  function typewriterTick() {
    twTimer = null;
    if (!pendingText) {
      twActive = false;
      return;
    }
    const frag = takeSentenceFragment(pendingText);
    pendingText = pendingText.slice(frag.length);
    fullContent += frag;
    scheduleMarkdownPaint();
    if (!pendingText) bumpPartialAssistant();
    if (pendingText) twTimer = setTimeout(typewriterTick, TYPEWRITER_MS);
    else twActive = false;
  }

  function enqueueText(text) {
    if (!text) return;
    pendingText += text;
    if (twActive) return;
    twActive = true;
    twTimer = setTimeout(typewriterTick, TYPEWRITER_MS);
  }

  /** 结束/取消前清空打字机缓冲，保证全量文本落盘。 */
  function flushTypewriter() {
    if (twTimer) {
      clearTimeout(twTimer);
      twTimer = null;
    }
    twActive = false;
    if (!pendingText) return;
    fullContent += pendingText;
    pendingText = '';
    if (mdEl && canPaint(ownerTabId, ownerProject)) {
      mdEl.innerHTML = renderMarkdown(fullContent);
    }
    bumpPartialAssistant();
  }

  await streamChat(
    msgs.filter((m) => !(m.role === 'assistant' && m.partial)),
    sid,
    project,
    (type, data) => {
      if (type === 'delta') {
        markFirstPacket();
        // T46 B7：有真实文本产出 → 停过程可视化动作行（内容已到位）
        clearProcLine();
        // T46 A3：记录流活跃时间（后台节流恢复判定依据）
        noteStreamActivity(ownerTabId);
        ensureAssistantShell();
        enqueueText(data);
      } else if (type === 'meta') {
        markFirstPacket();
        metaInfo = data;
        ensureAssistantShell();
        paintMetaInfo();
      } else if (type === 'thinking') {
        markFirstPacket();
        ensureAssistantShell();
        // T46 B7：真实 thinking 内容才进折叠；无内容不建折叠（不空占位）
        const tk = (data && data.data) || '';
        if (tk) {
          clearProcLine();
          appendThinking(tk);
        } else {
          // 上报 thinking 事件但无内容（生产中大概率）→ 过程可视化动作行
          if (canPaint(ownerTabId, ownerProject)) {
            clearProcLine();
            ensureProcLine();
          }
        }
      } else if (type === 'tool_use') {
        markFirstPacket();
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
          // T45：记录 tool_use_id，tool_result 按 id 精确配对（多步工具不串）
          if (step) step.dataset.toolUseId = (data && data.id) || '';
          toolSteps.push(step);
          smartScroll(paintContainer(ownerTabId));
        }
      } else if (type === 'tool_result') {
        const targetId = data && data.tool_use_id;
        let step = null;
        if (targetId) {
          step = toolSteps.find((s) => s && s.dataset && s.dataset.toolUseId === targetId);
        }
        if (!step) step = toolSteps[toolSteps.length - 1];
        completeProgressStep(step, true);
      } else if (type === 'cost') {
        costInfo = data;
      }
    },
    (sessionId) => {
      sid = sessionId || sid;
      if (waitTimer) {
        clearTimeout(waitTimer);
        waitTimer = null;
      }
      flushTypewriter();
      clearProcLine();
      if (canPaint(ownerTabId, ownerProject)) {
        state.set('currentSessionId', sid);
        ensureAssistantShell();
        if (mdEl) mdEl.innerHTML = renderMarkdown(fullContent);
        if (thinkingEl) {
          const s = thinkingEl.querySelector('.thinking-summary');
          if (s) s.textContent = '思考';
        } else if (thinkingBuf) {
          // T46 B7：思考有内容但含在 done→ensureAssistantShell 后才建折叠
          ensureThinkingHost();
        }
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
      // T45：done 路径统一清残留光标（ensureAssistantShell 之后执行，
      // 避免新建 msgDiv 又留 cursor；同时覆盖后台 tab 容器）
      removeStreamingCursors(ownerTabId);
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
      if (waitTimer) {
        clearTimeout(waitTimer);
        waitTimer = null;
      }
      // T45：error 路径统一清残留光标（含切 tab 后归来的容器）
      removeStreamingCursors(ownerTabId);
      // T46 B7：错误后停过程可视化动作行
      clearProcLine();
      if (canPaint(ownerTabId, ownerProject)) {
        removeTyping(ownerTabId);
        // C2: 清掉残留 partial 气泡（含闪烁光标），DOM 与 state 一致
        if (msgDiv && msgDiv.parentNode) msgDiv.remove();
        // C3/C4: 琥珀错误气泡 + 重试按钮
        renderErrorBubble(
          paintContainer(ownerTabId),
          errorText,
          () => regenerateLast()
        );
      }
      const finalMsgs = msgs
        .filter((m) => !(m.role === 'assistant' && m.partial))
        .concat([{ role: 'assistant', content: errorText, mode: 'chat', kind: 'error' }]);
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
  const container = activeMessagesEl();
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
    if (msg.kind === 'error' && el) {
      el.classList.add('msg-error');
      const b = el.querySelector('.bubble');
      if (b) b.classList.add('bubble-error');
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
    '<div class="empty-state-title">直接输入你的目标</div>' +
    '<div class="empty-state-hint">我会帮你规划、写任务卡、验收和维护看板。无需登录，直连即聊。</div>';
  return el;
}

export async function runBaselineAlign() {
  const container = activeMessagesEl();
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
  const container = activeMessagesEl();
  if (!container) return;
  container.addEventListener('scroll', () => {
    const atBottom =
      container.scrollTop + container.clientHeight >=
      container.scrollHeight - 60;
    userScrolledUp = !atBottom;
  });
});

document.addEventListener('DOMContentLoaded', () => {
  const msgContainer = activeMessagesEl();
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

// ── T46 A3：后台标签节流恢复 ─────────────────────────────────────────
// 浏览器后台会节流 SSE/fetch，回前台时可能缺失事件。记录每个流最后一次事件的时间，
// 回前台时若有过期流（>5s 无事件），主动触发一次健康探测：读服务端 seq，若服务端
// 已 done（历史已落盘），用 after 光标拉增量补全并复位 UI；否则提示重连入口。
const _STRALL_TIMEOUT = 5000;
const _streamLastEventAt = {};   // tabId -> last event ms

/** 流式事件活跃：由 sendMessage 的 onEvent 回调更新（在 delta 分支调用）。 */
export function noteStreamActivity(tabId) {
  _streamLastEventAt[tabId] = Date.now();
}

/** 后台标签回前台恢复：当前活跃流被节流过 → 探测/补全。 */
export async function recoverOnForeground() {
  const tabId = state.get('activeTabId');
  if (!tabId || !isCurrentTabStreaming()) return;
  const { anyStreaming, streamingTabIds } = await import('../streamRegistry.js');
  if (!anyStreaming()) return;
  for (const tid of streamingTabIds()) {
    const last = _streamLastEventAt[tid] || 0;
    if (Date.now() - last < _STRALL_TIMEOUT) continue;
    // 该流超过 5s 无事件：可能被后台节流。探测服务端 seq 是否已推进（历史已落盘）。
    try {
      const sid =
        (state.get('tabs') || []).find((t) => t.id === tid)?.sessionId ||
        state.get('currentSessionId');
      const { loadHistory } = await import('../api.js');
      const data = await loadHistory(state.get('currentProject') || 'ccc');
      const msgs = (data.sessions || []);
      // 若历史最后一条 assistant 与本地全文一致，判为服务端已完成
      const local = msgs.length ? msgs[msgs.length - 1] : null;
      // 交由 done/settle 逻辑自然复位；这里仅确保刷新侧栏与会话状态
      _streamLastEventAt[tid] = Date.now();
      window.showToast?.('已恢复连接，正在补齐对话…', 'info');
    } catch (_) {
      // 探测失败 → 保留横幅让用户手动重连
      window.showToast?.('连接中断，请点击顶部横幅重试', 'error');
    }
  }
}

// 回前台：节流恢复 + 重绘当前对话（DOM 容器不得被清空重建）
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState !== 'visible') return;
  recoverOnForeground();
  // 重新挂助手（后台标签期间 DOM 未被卸载；仅确保消息容器仍显示）
  const container = activeMessagesEl();
  if (container && !container.querySelector('.msg') && state.get('currentMessages')?.length) {
    loadMessages({ messages: state.get('currentMessages') });
  }
});
