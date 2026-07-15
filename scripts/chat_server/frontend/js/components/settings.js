import { state } from '../state.js';
import { loadProjects } from '../api.js';
import { setupProjectSelect } from './composer.js';

export async function openSettings() {
  // Remove existing dialog if any
  document.querySelector('.settings-dialog')?.remove();
  document.querySelector('.dialog-overlay')?.remove();

  const overlay = document.createElement('div');
  overlay.className = 'dialog-overlay';
  overlay.addEventListener('click', closeSettings);
  document.body.appendChild(overlay);

  const projects = await loadProjects();

  const dialog = document.createElement('div');
  dialog.className = 'settings-dialog';
  dialog.innerHTML =
    '<div class="settings-panel">' +
    '<div class="settings-header">' +
    '<span class="settings-title">设置</span>' +
    '<button class="settings-close" id="settings-close-btn">×</button>' +
    '</div>' +
    '<div class="settings-body">' +
    '<div class="settings-group">' +
    '<div class="settings-group-title">外观</div>' +
    '<div class="settings-row">' +
    '<span class="settings-label">主题</span>' +
    '<select class="settings-select" id="settings-theme">' +
    '<option value="system">跟随系统</option>' +
    '<option value="light">浅色</option>' +
    '<option value="dark">深色</option>' +
    '</select>' +
    '</div>' +
    '</div>' +
    '<div class="settings-group">' +
    '<div class="settings-group-title">项目</div>' +
    '<div class="settings-row">' +
    '<span class="settings-label">当前项目</span>' +
    '<select class="settings-select" id="settings-project"></select>' +
    '</div>' +
    '</div>' +
    '<div class="settings-group">' +
    '<div class="settings-group-title">关于</div>' +
    '<div class="settings-row">' +
    '<span class="settings-label">版本</span>' +
    '<span style="font-size:13px;color:var(--ccc-text-muted)">CCC Chat v2</span>' +
    '</div>' +
    '</div>' +
    '</div>' +
    '</div>';

  document.body.appendChild(dialog);

  // Theme select
  const themeSelect = document.getElementById('settings-theme');
  const savedScheme = localStorage.getItem('opencode-color-scheme') || 'system';
  themeSelect.value = savedScheme;
  themeSelect.addEventListener('change', () => {
    const val = themeSelect.value;
    localStorage.setItem('opencode-color-scheme', val);
    applyTheme(val);
  });

  // Project select
  const projSelect = document.getElementById('settings-project');
  for (const p of projects) {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = p.name;
    if (p.id === state.get('currentProject')) opt.selected = true;
    projSelect.appendChild(opt);
  }
  projSelect.addEventListener('change', () => {
    state.set('currentProject', projSelect.value);
    document.getElementById('project-select').value = projSelect.value;
    const event = new CustomEvent('project-change');
    document.dispatchEvent(event);
  });

  document.getElementById('settings-close-btn')?.addEventListener('click', closeSettings);

  // Close on Escape
  const escHandler = (e) => {
    if (e.key === 'Escape') { closeSettings(); document.removeEventListener('keydown', escHandler); }
  };
  document.addEventListener('keydown', escHandler);
}

function closeSettings() {
  document.querySelector('.settings-dialog')?.remove();
  document.querySelector('.dialog-overlay')?.remove();
}

function applyTheme(scheme) {
  const isDark = scheme === 'dark' || (scheme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  const themeBtn = document.getElementById('theme-btn');
  if (themeBtn) themeBtn.textContent = isDark ? '☀️' : '🌙';
}
