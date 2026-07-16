import { state } from '../state.js';
import { sendMessage, removeTyping, updateComposerState } from './message.js';
import { cancelStream } from '../api.js';
import { fileToAttachment, renderAttachmentChips, clearAttachments, getPendingAttachments } from './attachments.js';
import { handleSlashInput, hideSlashMenu } from './slash.js';

export function initComposer() {
  const input = document.getElementById('composer-input');
  const sendBtn = document.getElementById('send-btn');
  const cancelBtn = document.getElementById('cancel-btn');
  const attachBtn = document.getElementById('attach-btn');
  const fileInput = document.getElementById('file-input');

  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 200) + 'px';
    sendBtn.disabled = (!input.value.trim() && !getPendingAttachments().length) || state.get('streaming');
    handleSlashInput(input);
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      hideSlashMenu();
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      const menu = document.getElementById('slash-menu');
      if (menu && menu.classList.contains('open')) return;
      e.preventDefault();
      doSend();
    }
  });

  sendBtn.addEventListener('click', doSend);

  cancelBtn.addEventListener('click', () => {
    cancelStream();
    state.set('streaming', false);
    removeTyping();
    updateComposerState();
    document.getElementById('streaming-indicator')?.classList.remove('active');
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
      sendBtn.disabled = (!input.value.trim() && !getPendingAttachments().length) || state.get('streaming');
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
    sendBtn.disabled = (!input.value.trim() && !getPendingAttachments().length) || state.get('streaming');
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
      sendBtn.disabled = (!input.value.trim() && !getPendingAttachments().length) || state.get('streaming');
    }
  });
}

export function setupProjectSelect(projects) {
  const sel = document.getElementById('project-select');
  const sidebarSel = document.getElementById('sidebar-project-select');
  for (const target of [sel, sidebarSel]) {
    if (!target) continue;
    const prev = target.value || state.get('currentProject');
    target.innerHTML = '';
    for (const p of projects) {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.name;
      if (p.id === prev) opt.selected = true;
      target.appendChild(opt);
    }
  }
  if (sidebarSel) {
    sidebarSel.addEventListener('change', () => {
      state.set('currentProject', sidebarSel.value);
      if (sel) sel.value = sidebarSel.value;
      document.getElementById('project-display').textContent =
        sidebarSel.options[sidebarSel.selectedIndex]?.text || sidebarSel.value;
      document.dispatchEvent(new CustomEvent('project-change'));
    });
  }
  const display = document.getElementById('project-display');
  if (display && sel) {
    display.textContent = sel.options[sel.selectedIndex]?.text || state.get('currentProject');
  }
}

function doSend() {
  const input = document.getElementById('composer-input');
  const text = input.value.trim();
  const attachments = getPendingAttachments();
  if ((!text && !attachments.length) || state.get('streaming')) return;
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
