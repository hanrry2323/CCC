import { state } from '../state.js';

export function initTitlebar() {
  const tabsEl = document.getElementById('tabs');
  const newBtn = document.getElementById('new-tab-btn');
  const settingsBtn = document.getElementById('settings-btn');
  const themeBtn = document.getElementById('theme-btn');

  // Init theme
  const saved = localStorage.getItem('ccc-chat-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const isDark = saved ? saved === 'dark' : prefersDark;
  document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  if (themeBtn) themeBtn.textContent = isDark ? '☀️' : '🌙';

  // Theme toggle
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('ccc-chat-theme', next);
      themeBtn.textContent = next === 'dark' ? '☀️' : '🌙';
    });
  }

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!localStorage.getItem('ccc-chat-theme')) {
      const isDark = e.matches;
      document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
      if (themeBtn) themeBtn.textContent = isDark ? '☀️' : '🌙';
    }
  });

  // Settings
  if (settingsBtn) {
    settingsBtn.addEventListener('click', () => {
      import('./settings.js').then(m => m.openSettings());
    });
  }

  // New tab
  if (newBtn) {
    newBtn.addEventListener('click', () => {
      const event = new CustomEvent('new-tab');
      document.dispatchEvent(event);
    });
  }

  // Tab click delegation
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
