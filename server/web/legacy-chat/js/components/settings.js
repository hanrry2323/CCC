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

  const hub = localStorage.getItem('ccc_hub_base') || hubBase() || '';
  const agent = localStorage.getItem('ccc_agent_base') || agentBase() || '';
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
    '<option value="light">浅色</option>' +
    '<option value="dark">深色</option>' +
    '<option value="system">跟随系统</option>' +
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
    '<div class="settings-group-title">连接</div>' +
    '<div class="settings-row settings-row-col">' +
    '<span class="settings-label">服务端地址（2017 单端 :7788；同源留空走相对路径）</span>' +
    '<input class="settings-input" id="settings-hub-base" placeholder="http://192.168.3.116:7788" value="' +
    _esc(hub) +
    '"/>' +
    '</div>' +
    '<div class="settings-row settings-row-col">' +
    '<span class="settings-label">对话 Agent 地址（同源留空；跨机填 2017 :7788）</span>' +
    '<input class="settings-input" id="settings-agent-base" placeholder="http://192.168.3.116:7788" value="' +
    _esc(agent) +
    '"/>' +
    '</div>' +
    '<div class="settings-row settings-row-col">' +
    '<span class="settings-label">workspace 路径映射（JSON：项目 id → 本机路径；由用户填写，服务端不臆造）</span>' +
    '<textarea class="settings-textarea" id="settings-workspace-map" rows="4" placeholder=\'{"ccc":"/path/to/CCC"}\'>' +
    _esc(mapText) +
    '</textarea>' +
    '</div>' +
    '<div class="settings-row">' +
    '<button type="button" class="btn-primary" id="settings-ports-save">保存连接设置</button>' +
    '<span class="settings-row-value" id="settings-ports-hint" style="margin-left:8px"></span>' +
    '</div>' +
    (isDialogueShell()
      ? '<p style="font-size:12px;opacity:.7;margin:8px 0 0">当前为对话壳；HTTP 直连 2017 单端 :7788（对话/看板/运维/线路图四视图统一入口）。</p>'
      : '<p style="font-size:12px;opacity:.7;margin:8px 0 0">当前为编排壳；聊天请开 2017 :7788。</p>') +
    '</div>' +
    '<div class="settings-group">' +
    '<div class="settings-group-title">关于</div>' +
    '<div class="settings-row">' +
    '<span class="settings-label">版本</span>' +
    '<span class="settings-row-value">CCC v0.70.0（2017 单端 :7788）</span>' +
    '</div>' +
    '</div>' +
    '</div>' +
    '</div>';

  // 2026-08-24 修复：异步续跑前校验对话框仍在（快速关开后 getElementById 返回
  // null 会抛未捕获 TypeError；重开则旧闭包向新对话框重复绑监听）
  const themeSelect = document.getElementById('settings-theme');
  if (themeSelect) {
    themeSelect.value = getThemeScheme();
    themeSelect.addEventListener('change', () => {
      setThemeScheme(themeSelect.value);
    });
  }

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
    // ccc-plan-045 P1.5：composer 已随对话栈拆除，直接落 state + 隐藏 select
    state.set('currentProject', projSelect.value);
    const hidden = document.getElementById('project-select');
    if (hidden) hidden.value = projSelect.value;
    const disp = document.getElementById('project-display');
    if (disp) disp.textContent = name;
    document.dispatchEvent(new CustomEvent('project-change'));
  });

  document.getElementById('settings-ports-save')?.addEventListener('click', () => {
    const hint = document.getElementById('settings-ports-hint');
    const hubVal = (
      document.getElementById('settings-hub-base')?.value || ''
    ).trim();
    const agentVal = (
      document.getElementById('settings-agent-base')?.value || ''
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
    // 2026-08-24 修复：连接地址零校验 + 空值无法清除。现在：
    // ① URL 构造校验（防 htp:/ 打错字母后全站请求跟着坏）；② 显式清空=恢复同源。
    if (hubVal) {
      if (!/^https?:\/\//i.test(hubVal) || (() => { try { new URL(hubVal); return false; } catch (_) { return true; } })()) {
        if (hint) hint.textContent = '连接地址无效（须 http(s):// 完整 URL）';
        return;
      }
      localStorage.setItem('ccc_hub_base', hubVal.replace(/\/$/, ''));
      window.__CCC_HUB_BASE__ = hubVal.replace(/\/$/, '');
    } else {
      localStorage.removeItem('ccc_hub_base');
      delete window.__CCC_HUB_BASE__;
    }
    if (agentVal) {
      localStorage.setItem('ccc_agent_base', agentVal.replace(/\/$/, ''));
      window.__CCC_AGENT_BASE__ = agentVal.replace(/\/$/, '');
    }
    if (hint) hint.textContent = '已保存';
    window.showToast?.('连接设置已保存', 'ok');
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
