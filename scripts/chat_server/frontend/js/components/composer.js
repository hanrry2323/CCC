import { state } from '../state.js';
import { sendMessage, removeTyping, updateComposerState, runBaselineAlign } from './message.js';
import { cancelStream } from '../api.js';
import { fileToAttachment, renderAttachmentChips, clearAttachments, getPendingAttachments } from './attachments.js';
import { handleSlashInput, hideSlashMenu } from './slash.js';
import { initComposerActionDock } from './fixedActions.js';
import { isCurrentTabStreaming, syncStreamingFlagForActiveTab } from '../streamRegistry.js';

export function initComposer() {
  const input = document.getElementById('composer-input');
  const sendBtn = document.getElementById('send-btn');
  const cancelBtn = document.getElementById('cancel-btn');
  const attachBtn = document.getElementById('attach-btn');
  const fileInput = document.getElementById('file-input');

  initComposerActionDock({
    onBaseline: () => runBaselineAlign(),
    onPrompt: (prompt, opts) => sendMessage(prompt, [], opts || {}),
    onSlash: (slash) => import('./slash.js').then((m) => m.tryExecuteSlash(slash)),
    onTransfer: () =>
      import('./dispatchCard.js').then((m) => m.openTransferFromLatest()),
  });

  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 200) + 'px';
    sendBtn.disabled = (!input.value.trim() && !getPendingAttachments().length) || isCurrentTabStreaming();
    handleSlashInput(input);
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      hideSlashMenu();
      return;
    }
    // IME 组字中（中文输入法选词回车）不得发送；仅确认候选
    if (e.key === 'Enter' && !e.shiftKey) {
      if (e.isComposing || e.keyCode === 229) return;
      const menu = document.getElementById('slash-menu');
      if (menu && menu.classList.contains('open')) return;
      e.preventDefault();
      doSend();
    }
  });

  sendBtn.addEventListener('click', doSend);

  cancelBtn.addEventListener('click', () => {
    cancelStream(state.get('activeTabId'));
    syncStreamingFlagForActiveTab();
    removeTyping(state.get('activeTabId'));
    updateComposerState();
  });

  const modelSelect = document.getElementById('model-select');
  if (modelSelect) {
    modelSelect.value = state.get('model') || 'flash';
    modelSelect.addEventListener('change', () => {
      state.set('model', modelSelect.value);
    });
  }

  const projectSelect = document.getElementById('project-select');
  if (projectSelect) {
    projectSelect.addEventListener('change', () => {
      state.set('currentProject', projectSelect.value);
      document.getElementById('project-display').textContent =
        projectSelect.options[projectSelect.selectedIndex]?.text || projectSelect.value;
      document.dispatchEvent(new CustomEvent('project-change'));
    });
  }

  if (attachBtn && fileInput) {
    attachBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', async () => {
      for (const file of fileInput.files || []) {
        try {
          await fileToAttachment(file);
        } catch (err) {
          window.showToast?.(err.message || '附件失败', 'error');
        }
      }
      fileInput.value = '';
      renderAttachmentChips();
      sendBtn.disabled = (!input.value.trim() && !getPendingAttachments().length) || isCurrentTabStreaming();
    });
  }

  // Drag & drop / paste images
  const composer = document.getElementById('composer');
  composer?.addEventListener('dragover', (e) => {
    e.preventDefault();
    composer.classList.add('drag-over');
  });
  composer?.addEventListener('dragleave', () => composer.classList.remove('drag-over'));
  composer?.addEventListener('drop', async (e) => {
    e.preventDefault();
    composer.classList.remove('drag-over');
    for (const file of e.dataTransfer?.files || []) {
      try {
        await fileToAttachment(file);
      } catch (err) {
        window.showToast?.(err.message || '附件失败', 'error');
      }
    }
    renderAttachmentChips();
    sendBtn.disabled = (!input.value.trim() && !getPendingAttachments().length) || isCurrentTabStreaming();
  });

  input.addEventListener('paste', async (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    let handled = false;
    for (const item of items) {
      if (item.kind === 'file') {
        const file = item.getAsFile();
        if (!file) continue;
        handled = true;
        try {
          await fileToAttachment(file);
        } catch (err) {
          window.showToast?.(err.message || '粘贴附件失败', 'error');
        }
      }
    }
    if (handled) {
      renderAttachmentChips();
      sendBtn.disabled = (!input.value.trim() && !getPendingAttachments().length) || isCurrentTabStreaming();
    }
  });
}

export function setProjectActive(projectId, displayName) {
  state.set('currentProject', projectId);
  try {
    localStorage.setItem('ccc_hub_last_project', projectId);
  } catch (_) {
    /* ignore */
  }
  const sel = document.getElementById('project-select');
  if (sel) sel.value = projectId;
  const display = document.getElementById('project-display');
  if (display) display.textContent = displayName || projectId;
  document.querySelectorAll('#sidebar-project-btns .board-ws-btn').forEach((b) => {
    const on = b.dataset.projectId === projectId;
    b.classList.toggle('active', on);
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
  });
  document.dispatchEvent(new CustomEvent('project-change'));
}

export function setupProjectSelect(projects) {
  const sel = document.getElementById('project-select');
  const btnsHost = document.getElementById('sidebar-project-btns');
  let last = null;
  try {
    last = localStorage.getItem('ccc_hub_last_project');
  } catch (_) {
    last = null;
  }
  const preferred =
    state.get('currentProject') || last || state.get('defaultProject');
  const pickDefault = () => {
    if (
      preferred &&
      projects.some(
        (p) =>
          p.id === preferred &&
          p.role !== 'orch' &&
          p.engine_eligible !== false
      )
    ) {
      return preferred;
    }
    const app = projects.find(
      (p) => p.role !== 'orch' && p.engine_eligible !== false
    );
    if (app) return app.id;
    if (preferred && projects.some((p) => p.id === preferred)) return preferred;
    return projects[0]?.id;
  };
  let activeId = pickDefault();
  let activeName = activeId;

  if (sel) {
    sel.innerHTML = '';
    for (const p of projects) {
      const opt = document.createElement('option');
      opt.value = p.id;
      const tag =
        p.role === 'orch' || p.engine_eligible === false ? ' · 编排' : '';
      opt.textContent = (p.name || p.id) + tag;
      if (p.id === activeId) opt.selected = true;
      sel.appendChild(opt);
    }
    if (activeId) sel.value = activeId;
    const cur = projects.find((p) => p.id === sel.value);
    activeId = sel.value;
    activeName = cur?.name || sel.value;
  }

  if (btnsHost) {
    btnsHost.innerHTML = '';
    for (const p of projects) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'board-ws-btn' + (p.id === activeId ? ' active' : '');
      b.dataset.projectId = p.id;
      b.dataset.workspace = p.workspace || p.id;
      b.dataset.role = p.role || 'app';
      b.innerHTML =
        '<span class="board-ws-label"></span><span class="board-ws-live" hidden aria-hidden="true"></span>';
      b.querySelector('.board-ws-label').textContent =
        (p.workspace || p.name || p.id) +
        (p.role === 'orch' ? ' ◆' : '');
      b.title =
        (p.name || p.id) +
        (p.role === 'orch' ? '（编排仓·不可下达）' : '') +
        (p.path ? ' · ' + p.path : '');
      b.setAttribute('aria-pressed', p.id === activeId ? 'true' : 'false');
      b.addEventListener('click', () => {
        if (state.get('currentProject') === p.id) return;
        setProjectActive(p.id, p.name || p.workspace || p.id);
      });
      btnsHost.appendChild(b);
    }
    syncProjectLiveDots();
  }

  const display = document.getElementById('project-display');
  if (display) display.textContent = activeName || activeId;
  if (activeId && activeId !== state.get('currentProject')) {
    state.set('currentProject', activeId);
  }
}

function syncProjectLiveDots() {
  import('../streamRegistry.js').then((m) => {
    const live = new Set(m.streamingProjectIds());
    document.querySelectorAll('#sidebar-project-btns .board-ws-btn').forEach((b) => {
      const on = live.has(b.dataset.projectId);
      const dot = b.querySelector('.board-ws-live');
      if (dot) dot.hidden = !on;
      b.classList.toggle('has-live', on);
    });
  });
}

// Keep live dots in sync
if (typeof document !== 'undefined') {
  document.addEventListener('ccc-streams-changed', () => syncProjectLiveDots());
}

function doSend() {
  const input = document.getElementById('composer-input');
  const text = input.value.trim();
  const attachments = getPendingAttachments();
  if ((!text && !attachments.length) || isCurrentTabStreaming()) return;
  if (text.startsWith('/')) {
    import('./slash.js').then(m => {
      if (m.tryExecuteSlash(text)) {
        input.value = '';
        input.style.height = 'auto';
        document.getElementById('send-btn').disabled = true;
      } else {
        reallySend(text, attachments);
      }
    });
    return;
  }
  reallySend(text, attachments);
}

function reallySend(text, attachments) {
  const input = document.getElementById('composer-input');
  input.value = '';
  input.style.height = 'auto';
  document.getElementById('send-btn').disabled = true;
  hideSlashMenu();
  const payload = attachments.slice();
  clearAttachments();
  renderAttachmentChips();
  sendMessage(text || '（见附件）', payload);
}
