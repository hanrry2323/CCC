import { state } from '../state.js';
import { loadProjects } from '../api.js';
import { getThemeScheme, setThemeScheme } from '../theme.js';
import { hubBase, agentBase, isDialogueShell } from '../ports.js';

function _esc(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/"/g, '&quot;');
}

export async function openSettings() {
  document.querySelector('.settings-sheet')?.remove();
  document.querySelector('.dialog-overlay')?.remove();

  const overlay = document.createElement('div');
  overlay.className = 'dialog-overlay';
  overlay.addEventListener('click', closeSettings);
  document.body.appendChild(overlay);

  const dialog = document.createElement('div');
  dialog.className = 'settings-sheet';
  dialog.innerHTML =
    '<div class="settings-panel"><div class="settings-loading"><div class="spinner"></div><span>加载中...</span></div></div>';
  document.body.appendChild(dialog);

  let projects = [];
  try {
    projects = await loadProjects();
  } catch (_) {
    projects = [];
  }

  const tok = localStorage.getItem('ccc_agent_token') || '';
  const hub = localStorage.getItem('ccc_hub_base') || hubBase() || 'http://192.168.3.116:7777';
  const agent = localStorage.getItem('ccc_agent_base') || agentBase() || 'http://192.168.3.140:7788';
  let mapText = '';
  try {
    mapText = localStorage.getItem('ccc_local_workspace_map') || '{}';
    JSON.parse(mapText);
  } catch (_) {
    mapText = '{}';
  }

  dialog.innerHTML =
    '<div class="settings-panel">' +
    '<div class="settings-header">' +
    '<span class="settings-title">' +
    '<svg class="settings-title-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
    '<circle cx="12" cy="12" r="3"/>' +
    '<path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72 1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>' +
    '</svg>' +
    '设置' +
    '</span>' +
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
    '<div class="settings-group-title">双口连接</div>' +
    '<div class="settings-row settings-row-col">' +
    '<span class="settings-label">Hub 编排口（Basic Auth）</span>' +
    '<input class="settings-input" id="settings-hub-base" placeholder="http://192.168.3.116:7777" value="' +
    _esc(hub) +
    '"/>' +
    '</div>' +
    '<div class="settings-row settings-row-col">' +
    '<span class="settings-label">Agent 对话口</span>' +
    '<input class="settings-input" id="settings-agent-base" placeholder="http://192.168.3.140:7788" value="' +
    _esc(agent) +
    '"/>' +
    '</div>' +
    '<div class="settings-row settings-row-col">' +
    '<span class="settings-label">Agent Token（~/.ccc/agent-token，勿写进 URL）</span>' +
    '<input class="settings-input" id="settings-agent-token" type="password" autocomplete="off" placeholder="Bearer 密钥" value="' +
    _esc(tok) +
    '"/>' +
    '</div>' +
    '<div class="settings-row settings-row-col">' +
    '<span class="settings-label">本机路径 map（JSON：project_id → M1 绝对路径）</span>' +
    '<textarea class="settings-textarea" id="settings-workspace-map" rows="4" placeholder=\'{"ccc-demo":"/Users/apple/program/apps/ccc-demo"}\'>' +
    _esc(mapText) +
    '</textarea>' +
    '</div>' +
    '<div class="settings-row">' +
    '<button type="button" class="settings-select" id="settings-ports-save" style="cursor:pointer">保存双口设置</button>' +
    '<span class="settings-row-value" id="settings-ports-hint" style="margin-left:8px"></span>' +
    '</div>' +
    (isDialogueShell()
      ? '<p style="font-size:12px;opacity:.7;margin:8px 0 0">当前为 M1 对话壳；聊走本机 sidecar，下达走 Hub。</p>'
      : '<p style="font-size:12px;opacity:.7;margin:8px 0 0">当前为 Hub 编排壳；聊天请开 M1 :7788。</p>') +
    '</div>' +
    '<div class="settings-group">' +
    '<div class="settings-group-title">关于</div>' +
    '<div class="settings-row">' +
    '<span class="settings-label">版本</span>' +
    '<span class="settings-row-value">CCC 双口壳</span>' +
    '</div>' +
    '</div>' +
    '</div>' +
    '</div>';

  const themeSelect = document.getElementById('settings-theme');
  themeSelect.value = getThemeScheme();
  themeSelect.addEventListener('change', () => {
    setThemeScheme(themeSelect.value);
  });

  const projSelect = document.getElementById('settings-project');
  for (const p of projects) {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = p.name;
    if (p.id === state.get('currentProject')) opt.selected = true;
    projSelect.appendChild(opt);
  }
  if (!projects.length) {
    const opt = document.createElement('option');
    opt.value = state.get('currentProject') || 'ccc';
    opt.textContent = opt.value;
    projSelect.appendChild(opt);
  }
  projSelect.addEventListener('change', () => {
    const name =
      projSelect.options[projSelect.selectedIndex]?.text || projSelect.value;
    import('./composer.js').then((m) => {
      if (m.setProjectActive) m.setProjectActive(projSelect.value, name);
      else {
        state.set('currentProject', projSelect.value);
        const hidden = document.getElementById('project-select');
        if (hidden) hidden.value = projSelect.value;
        const disp = document.getElementById('project-display');
        if (disp) disp.textContent = name;
        document.dispatchEvent(new CustomEvent('project-change'));
      }
    });
  });

  document.getElementById('settings-ports-save')?.addEventListener('click', () => {
    const hint = document.getElementById('settings-ports-hint');
    const hubVal = (
      document.getElementById('settings-hub-base')?.value || ''
    ).trim();
    const agentVal = (
      document.getElementById('settings-agent-base')?.value || ''
    ).trim();
    const tokVal = (
      document.getElementById('settings-agent-token')?.value || ''
    ).trim();
    const mapRaw =
      document.getElementById('settings-workspace-map')?.value || '{}';
    try {
      const parsed = JSON.parse(mapRaw);
      if (typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('map 须为对象');
      }
      localStorage.setItem('ccc_local_workspace_map', JSON.stringify(parsed));
      window.__CCC_WORKSPACE_MAP__ = {
        ...(window.__CCC_WORKSPACE_MAP__ || {}),
        ...parsed,
      };
    } catch (e) {
      if (hint) hint.textContent = 'map JSON 无效: ' + e.message;
      return;
    }
    if (hubVal) {
      localStorage.setItem('ccc_hub_base', hubVal.replace(/\/$/, ''));
      window.__CCC_HUB_BASE__ = hubVal.replace(/\/$/, '');
    }
    if (agentVal) {
      localStorage.setItem('ccc_agent_base', agentVal.replace(/\/$/, ''));
      window.__CCC_AGENT_BASE__ = agentVal.replace(/\/$/, '');
    }
    if (tokVal) localStorage.setItem('ccc_agent_token', tokVal);
    else localStorage.removeItem('ccc_agent_token');
    if (hint) hint.textContent = '已保存';
    window.showToast?.('双口设置已保存', 'ok');
  });

  document
    .getElementById('settings-close-btn')
    ?.addEventListener('click', closeSettings);

  const escHandler = (e) => {
    if (e.key === 'Escape') {
      closeSettings();
      document.removeEventListener('keydown', escHandler);
    }
  };
  document.addEventListener('keydown', escHandler);
}

function closeSettings() {
  document.querySelector('.settings-sheet')?.remove();
  document.querySelector('.dialog-overlay')?.remove();
}
