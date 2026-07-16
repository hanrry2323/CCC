/** Composer 上方 runtime 状态条 + 对话旁失败可点重开（v0.42） */

import { apiGet, apiPost } from '../api.js';
import { state } from '../state.js';

let _timer = null;

function workspaceOf() {
  const map = state.get('projectWorkspaceMap') || {};
  const p = state.get('currentProject') || 'ccc';
  if (map[p]) return map[p];
  if (p === 'ccc') return 'CCC';
  return p;
}

function ensureDom() {
  const composer = document.getElementById('composer');
  if (!composer) return null;
  let bar = document.getElementById('runtime-status-bar');
  if (!bar) {
    bar = document.createElement('div');
    bar.id = 'runtime-status-bar';
    bar.className = 'runtime-status-bar';
    bar.hidden = true;
    composer.parentNode.insertBefore(bar, composer);
  }
  let fail = document.getElementById('chat-fail-strip');
  if (!fail) {
    fail = document.createElement('div');
    fail.id = 'chat-fail-strip';
    fail.className = 'chat-fail-strip';
    fail.hidden = true;
    composer.parentNode.insertBefore(fail, composer);
  }
  return { bar, fail };
}

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function reopen(tid) {
  const ws = workspaceOf();
  await apiPost('/api/tasks/reopen', { id: tid, workspace: ws, to: 'planned' });
  window.showToast?.('已重开 ' + tid, 'success');
  await refreshRuntimeStatus();
}

export async function refreshRuntimeStatus() {
  const dom = ensureDom();
  if (!dom) return;
  const ws = workspaceOf();
  try {
    const st = await apiGet(
      '/api/runtime-status?workspace=' + encodeURIComponent(ws)
    );
    const mode = st.mode || st.control?.mode || '?';
    const eng = st.engine_allowed ? 'Engine可跑' : 'Engine停';
    const wake = st.wake_pending ? 'wake待消费' : '无wake';
    const c = st.counts || {};
    dom.bar.hidden = false;
    dom.bar.innerHTML =
      `<span class="rs-mode">${esc(mode)}</span>` +
      `<span class="rs-sep">·</span>` +
      `<span>${esc(eng)}</span>` +
      `<span class="rs-sep">·</span>` +
      `<span>${esc(wake)}</span>` +
      `<span class="rs-sep">·</span>` +
      `<span>backlog ${esc(c.backlog ?? 0)}</span>` +
      `<span class="rs-sep">/</span>` +
      `<span>planned ${esc(c.planned ?? 0)}</span>` +
      `<span class="rs-ws">${esc(ws)}</span>`;
  } catch (_) {
    dom.bar.hidden = true;
  }

  try {
    const fr = await apiGet(
      '/api/failures?last=3&workspace=' + encodeURIComponent(ws)
    );
    const rows = (fr.failures || []).slice().reverse().slice(0, 3);
    if (!rows.length) {
      dom.fail.hidden = true;
      dom.fail.innerHTML = '';
      return;
    }
    dom.fail.hidden = false;
    dom.fail.innerHTML =
      '<div class="chat-fail-label">最近失败</div>' +
      rows
        .map(
          (f) =>
            `<div class="chat-fail-item">` +
            `<span class="chat-fail-meta"><b>${esc(f.task_id || '')}</b> · ${esc(f.role || '')} · ${esc((f.reason || '').slice(0, 80))}</span>` +
            (f.task_id
              ? `<button type="button" class="chat-fail-reopen" data-tid="${esc(f.task_id)}">重开</button>`
              : '') +
            `</div>`
        )
        .join('');
    dom.fail.querySelectorAll('.chat-fail-reopen').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const tid = btn.getAttribute('data-tid');
        if (!tid) return;
        btn.disabled = true;
        try {
          await reopen(tid);
        } catch (err) {
          window.showToast?.(err.message || '重开失败', 'error');
          btn.disabled = false;
        }
      });
    });
  } catch (_) {
    dom.fail.hidden = true;
  }
}

export function initRuntimeStatus() {
  ensureDom();
  refreshRuntimeStatus().catch(() => {});
  if (_timer) clearInterval(_timer);
  _timer = setInterval(() => refreshRuntimeStatus().catch(() => {}), 30000);
  document.addEventListener('project-change', () => {
    refreshRuntimeStatus().catch(() => {});
  });
  document.addEventListener('ccc-task-dispatched', () => {
    refreshRuntimeStatus().catch(() => {});
  });
}
