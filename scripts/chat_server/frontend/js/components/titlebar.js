import { state } from '../state.js';

export function initTitlebar() {
  const tabsEl = document.getElementById('tabs');
  const newBtn = document.getElementById('new-tab-btn');
  const settingsBtn = document.getElementById('settings-btn');
  const themeBtn = document.getElementById('theme-btn');

  const saved = localStorage.getItem('opencode-color-scheme') || 'system';
  applyTheme(saved);

  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const currentScheme = localStorage.getItem('opencode-color-scheme') || 'system';
      const next = currentScheme === 'dark' ? 'light' : 'dark';
      localStorage.setItem('opencode-color-scheme', next);
      applyTheme(next);
    });
  }

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    const scheme = localStorage.getItem('opencode-color-scheme');
    if (!scheme || scheme === 'system') {
      applyTheme('system');
    }
  });

  if (settingsBtn) {
    settingsBtn.addEventListener('click', () => {
      import('./settings.js').then(m => m.openSettings());
    });
  }

  if (newBtn) {
    newBtn.addEventListener('click', () => {
      const event = new CustomEvent('new-tab');
      document.dispatchEvent(event);
    });
  }

  tabsEl.addEventListener('click', (e) => {
    const tab = e.target.closest('.titlebar-tab');
    if (!tab) return;
    if (e.target.closest('.close-btn')) {
      const event = new CustomEvent('close-tab', { detail: { id: tab.dataset.tabId } });
      document.dispatchEvent(event);
    } else {
      const event = new CustomEvent('switch-tab', { detail: { id: tab.dataset.tabId } });
      document.dispatchEvent(event);
    }
  });
}

export function renderTabs(tabs, activeId) {
  const tabsEl = document.getElementById('tabs');
  tabsEl.innerHTML = tabs.map(t => {
    const isActive = t.id === activeId;
    const title = t.title || '新对话';
    const safeTitle = String(title).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    return '<div class="titlebar-tab' + (isActive ? ' active' : '') + '" data-tab-id="' + t.id + '">' +
      '<span>' + safeTitle + '</span>' +
      (tabs.length > 1 ? '<button class="close-btn">×</button>' : '') +
      '</div>';
  }).join('');
}

function applyTheme(scheme) {
  const isDark = scheme === 'dark' || (scheme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
}
