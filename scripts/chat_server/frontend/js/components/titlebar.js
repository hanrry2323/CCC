import { getThemeScheme, applyTheme, toggleLightDark } from '../theme.js';
import { isTabStreaming } from '../streamRegistry.js';

export function initTitlebar() {
  const tabsEl = document.getElementById('tabs');
  const newBtn = document.getElementById('new-tab-btn');
  const settingsBtn = document.getElementById('settings-btn');
  const themeBtn = document.getElementById('theme-btn');
  const boardBtn = document.getElementById('board-btn');
  const taskBtn = document.getElementById('task-btn');

  applyTheme(getThemeScheme());

  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      toggleLightDark();
    });
  }

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    const scheme = getThemeScheme();
    if (scheme === 'system') applyTheme('system');
  });

  if (settingsBtn) {
    settingsBtn.addEventListener('click', () => {
      import('./settings.js').then((m) => m.openSettings());
    });
  }

  if (newBtn) {
    newBtn.addEventListener('click', () => {
      document.dispatchEvent(new CustomEvent('new-tab'));
    });
  }

  if (boardBtn) {
    boardBtn.addEventListener('click', () => {
      import('./boardPanel.js').then((m) => m.toggleBoardPanel());
    });
  }

  if (taskBtn) {
    taskBtn.addEventListener('click', () => {
      import('./taskDialog.js').then((m) => m.openTaskDialog());
    });
  }

  tabsEl.addEventListener('click', (e) => {
    const tab = e.target.closest('.titlebar-tab');
    if (!tab) return;
    if (e.target.closest('.close-btn')) {
      document.dispatchEvent(
        new CustomEvent('close-tab', { detail: { id: tab.dataset.tabId } })
      );
    } else {
      document.dispatchEvent(
        new CustomEvent('switch-tab', { detail: { id: tab.dataset.tabId } })
      );
    }
  });
}

export function renderTabs(tabs, activeId) {
  const tabsEl = document.getElementById('tabs');
  tabsEl.innerHTML = tabs
    .map((t) => {
      const isActive = t.id === activeId;
      const title = t.title || '新对话';
      const safeTitle = String(title)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
      const streaming = isTabStreaming(t.id);
      return (
        '<div class="titlebar-tab' +
        (isActive ? ' active' : '') +
        (streaming ? ' streaming' : '') +
        '" data-tab-id="' +
        t.id +
        '">' +
        (streaming
          ? '<span class="tab-stream-dot" title="生成中"></span>'
          : '') +
        '<span>' +
        safeTitle +
        '</span>' +
        (tabs.length > 1
          ? '<button class="close-btn" aria-label="关闭">×</button>'
          : '') +
        '</div>'
      );
    })
    .join('');
}
