import { state } from '../state.js';
import { showToast } from './toast.js';

export function initKeyboard() {
  document.addEventListener('keydown', (e) => {
    const isMac = navigator.platform.includes('Mac');
    const mod = isMac ? e.metaKey : e.ctrlKey;

    if (mod && e.key === 'k') {
      e.preventDefault();
      const searchInput = document.getElementById('sidebar-search');
      if (searchInput) {
        searchInput.focus();
        searchInput.select();
      }
    }

    if (mod && e.key === 'n') {
      e.preventDefault();
      const event = new CustomEvent('new-tab');
      document.dispatchEvent(event);
    }

    if (mod && e.shiftKey && e.key === 'Delete') {
      e.preventDefault();
      const container = document.getElementById('messages');
      if (container) {
        import('./message.js').then(m => {
          container.innerHTML = '';
          container.appendChild(m.createEmptyState());
        });
      }
      state.set('currentMessages', []);
      showToast('对话已清空', 'info');
    }

    // / — focus composer
    if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey) {
      const input = document.getElementById('composer-input');
      if (input && document.activeElement !== input) {
        e.preventDefault();
        input.focus();
      }
    }

    // ⌘ + [1-9] — switch tabs
    if (mod && e.key >= '1' && e.key <= '9') {
      e.preventDefault();
      const idx = parseInt(e.key) - 1;
      const tabs = state.get('tabs') || [];
      if (tabs[idx]) {
        const event = new CustomEvent('switch-tab', { detail: { id: tabs[idx].id } });
        document.dispatchEvent(event);
      }
    }

    // ↑ (empty composer) — edit last user message
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

    // Escape — close settings / panels / slash
    if (e.key === 'Escape') {
      const dialog = document.querySelector('.settings-sheet');
      if (dialog) {
        dialog.querySelector('.settings-close')?.click();
        return;
      }
      import('./slash.js').then(m => m.hideSlashMenu());
      import('./boardPanel.js').then(m => m.closeBoardPanel());
      import('./artifacts.js').then(m => m.closeArtifactPanel());
    }
  });
}
