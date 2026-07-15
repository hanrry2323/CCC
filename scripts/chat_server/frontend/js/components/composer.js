import { state } from '../state.js';
import { sendMessage, removeTyping } from './message.js';

export function initComposer() {
  const input = document.getElementById('composer-input');
  const sendBtn = document.getElementById('send-btn');
  const cancelBtn = document.getElementById('cancel-btn');

  // Auto-resize
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 200) + 'px';
    sendBtn.disabled = !input.value.trim() || state.get('streaming');
  });

  // Enter to send
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      doSend();
    }
  });

  sendBtn.addEventListener('click', doSend);
  cancelBtn.addEventListener('click', () => {
    removeTyping();
    state.set('streaming', false);
    sendBtn.style.display = 'flex';
    cancelBtn.style.display = 'none';
    sendBtn.disabled = !input.value.trim();
  });

  // Model select
  const modelSelect = document.getElementById('model-select');
  if (modelSelect) {
    modelSelect.addEventListener('change', () => {
      state.set('model', modelSelect.value);
    });
  }

  // Project select
  const projectSelect = document.getElementById('project-select');
  if (projectSelect) {
    projectSelect.addEventListener('change', () => {
      state.set('currentProject', projectSelect.value);
      const event = new CustomEvent('project-change');
      document.dispatchEvent(event);
    });
  }
}

export function setupProjectSelect(projects) {
  const sel = document.getElementById('project-select');
  if (!sel) return;
  sel.innerHTML = '';
  for (const p of projects) {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = p.name;
    if (p.id === state.get('currentProject')) opt.selected = true;
    sel.appendChild(opt);
  }
}

function doSend() {
  const input = document.getElementById('composer-input');
  const text = input.value.trim();
  if (!text || state.get('streaming')) return;
  input.value = '';
  input.style.height = 'auto';
  document.getElementById('send-btn').disabled = true;
  sendMessage(text);
}
