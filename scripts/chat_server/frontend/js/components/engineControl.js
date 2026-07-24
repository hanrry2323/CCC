/** Engine 指示灯 + 手动启停（对话标题栏 / 看板工具栏共用） */

import { apiGet, apiPost } from '../api.js';
import { state } from '../state.js';

let _timer = null;
let _busy = false;
let _last = { running: false, allowed: false, mode: '?' };

function workspaceOf() {
  const map = state.get('projectWorkspaceMap') || {};
  const p = state.get('currentProject') || 'ccc';
  if (map[p]) return map[p];
  if (p === 'ccc') return 'CCC';
  return p;
}

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function engineControlHtml(idPrefix = 'eng') {
  return (
    `<div class="engine-control" id="${idPrefix}-engine-control" title="Engine 状态">` +
      `<span class="engine-led off" id="${idPrefix}-engine-led" aria-hidden="true"></span>` +
      `<span class="engine-label" id="${idPrefix}-engine-label">Engine</span>` +
      `<button type="button" class="engine-toggle-btn" id="${idPrefix}-engine-toggle" title="启动 / 停止 Engine">启动</button>` +
    `</div>`
  );
}

function paintHost(prefix, st) {
  const led = document.getElementById(prefix + '-engine-led');
  const label = document.getElementById(prefix + '-engine-label');
  const btn = document.getElementById(prefix + '-engine-toggle');
  if (!led || !btn) return;
  const running = !!st.engine_running;
  const allowed = !!st.engine_allowed;
  led.classList.toggle('on', running);
  led.classList.toggle('off', !running);
  if (label) {
    label.textContent = running ? 'Engine 已连接' : 'Engine 断开';
  }
  btn.disabled = _busy;
  btn.textContent = running ? '停止' : '启动';
  btn.title = running
    ? '停止 Engine（切到 ui）'
    : '启动 Engine（enabled + launchd）';
  btn.dataset.running = running ? '1' : '0';
  const wrap = document.getElementById(prefix + '-engine-control');
  if (wrap) {
    wrap.dataset.running = running ? '1' : '0';
    wrap.dataset.mode = st.mode || '';
    wrap.title =
      `Engine ${running ? '运行中' : '未运行'} · 控制面 ${st.mode || '?'}` +
      (allowed ? '' : ' · 控制面禁止自动跑');
  }
}

export async function refreshEngineControl() {
  const ws = workspaceOf();
  try {
    const st = await apiGet(
      '/api/runtime-status?workspace=' + encodeURIComponent(ws)
    );
    _last = {
      running: !!st.engine_running,
      allowed: !!st.engine_allowed,
      mode: st.mode || '?',
      git: st.git || {},
      counts: st.counts || {},
      raw: st,
    };
    paintHost('chat', st);
    paintHost('board', st);
    document.dispatchEvent(
      new CustomEvent('ccc-engine-status', { detail: _last })
    );
    return st;
  } catch (_) {
    paintHost('chat', { engine_running: false, engine_allowed: false, mode: '?' });
    paintHost('board', { engine_running: false, engine_allowed: false, mode: '?' });
    return null;
  }
}

async function toggleFrom(prefix) {
  if (_busy) return;
  const btn = document.getElementById(prefix + '-engine-toggle');
  const running = btn?.dataset.running === '1' || _last.running;
  _busy = true;
  if (btn) btn.disabled = true;
  try {
    if (running) {
      await apiPost('/api/engine/stop', {});
      window.showToast?.('Engine 已停止', 'info');
    } else {
      await apiPost('/api/engine/start', {});
      window.showToast?.('Engine 已启动', 'success');
    }
    await new Promise((r) => setTimeout(r, 600));
    await refreshEngineControl();
  } catch (err) {
    window.showToast?.(err.message || 'Engine 操作失败', 'error');
  } finally {
    _busy = false;
    await refreshEngineControl();
  }
}

export function mountEngineControlInTitlebar() {
  // 对话壳不塞 Engine 启停（运维噪音）；编排口看板自有入口
  if (
    typeof location !== 'undefined' &&
    (String(location.port || '') === '7788' ||
      window.__CCC_SHELL__ === 'dialogue')
  ) {
    return;
  }
  const titlebar = document.getElementById('titlebar');
  if (!titlebar || document.getElementById('chat-engine-control')) return;
  const settings = document.getElementById('settings-btn');
  const wrap = document.createElement('div');
  wrap.innerHTML = engineControlHtml('chat');
  const el = wrap.firstElementChild;
  if (settings) titlebar.insertBefore(el, settings);
  else titlebar.appendChild(el);
  el.querySelector('#chat-engine-toggle')?.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    toggleFrom('chat');
  });
}

export function mountEngineControlInBoard(toolbarActions) {
  if (!toolbarActions || document.getElementById('board-engine-control')) return;
  const wrap = document.createElement('div');
  wrap.innerHTML = engineControlHtml('board');
  const el = wrap.firstElementChild;
  toolbarActions.appendChild(el);
  el.querySelector('#board-engine-toggle')?.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    toggleFrom('board');
  });
}

export function initEngineControl() {
  mountEngineControlInTitlebar();
  refreshEngineControl().catch(() => {});
  if (_timer) clearInterval(_timer);
  _timer = setInterval(() => refreshEngineControl().catch(() => {}), 15000);
  document.addEventListener('project-change', () => {
    refreshEngineControl().catch(() => {});
  });
  document.addEventListener('ccc-task-dispatched', () => {
    refreshEngineControl().catch(() => {});
  });
}

export function getLastEngineStatus() {
  return _last;
}
