import { state } from '../state.js';
import { showToast } from './toast.js';

export function initKeyboard() {
  document.addEventListener('keydown', (e) => {
    const isMac = navigator.platform.includes('Mac');
    const mod = isMac ? e.metaKey : e.ctrlKey;

    // Cmd/Ctrl + K — 搜索
    if (mod && e.key === 'k') {
      e.preventDefault();
      const searchInput = document.getElementById('sidebar-search');
      if (searchInput) {
        searchInput.focus();
        searchInput.select();
      }
    }

    // Cmd/Ctrl + N — 新对话
    if (mod && e.key === 'n') {
      e.preventDefault();
      const event = new CustomEvent('new-tab');
      document.dispatchEvent(event);
    }

    // Cmd/Ctrl + Shift + Delete — 清空对话
    if (mod && e.shiftKey && e.key === 'Delete') {
      e.preventDefault();
      const container = document.getElementById('messages');
      if (container) {
        container.innerHTML = '<div class="empty-state">' +
          '<div class="empty-state-icon">💬</div>' +
          '<div class="empty-state-title">开始一个新对话</div>' +
          '<div class="empty-state-hint">在下方输入消息，或从侧栏选择一个已有对话</div>' +
          '</div>';
      }
      state.set('currentMessages', []);
      showToast('对话已清空', 'info');
    }

    // ↑ (在 composer 为空时) — 编辑上一条用户消息
    if (e.key === 'ArrowUp' && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
      const input = document.getElementById('composer-input');
      if (input && input === document.activeElement && input.value === '') {
        const msgs = state.get('currentMessages') || [];
        const lastUser = [...msgs].reverse().find(m => m.role === 'user');
        if (lastUser && lastUser.content) {
          input.value = lastUser.content;
          input.dispatchEvent(new Event('input'));
          input.focus();
          input.setSelectionRange(input.value.length, input.value.length);
        }
      }
    }

    // Escape — 关闭设置 / 取消编辑
    if (e.key === 'Escape') {
      const dialog = document.querySelector('.settings-dialog');
      if (dialog) {
        dialog.querySelector('.settings-close')?.click();
      }
    }
  });
}
