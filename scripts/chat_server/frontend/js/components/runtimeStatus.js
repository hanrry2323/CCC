/** Composer 上方：队列摘要 + 工作区改动提示（不含「最近失败」） */

import { apiGet } from '../api.js';
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
  // 移除旧「最近失败」条
  document.getElementById('chat-fail-strip')?.remove();

  let bar = document.getElementById('runtime-status-bar');
  if (!bar) {
    bar = document.createElement('div');
    bar.id = 'runtime-status-bar';
    bar.className = 'runtime-status-bar';
    bar.hidden = true;
    composer.parentNode.insertBefore(bar, composer);
  }
  let git = document.getElementById('git-dirty-strip');
  if (!git) {
    git = document.createElement('div');
    git.id = 'git-dirty-strip';
    git.className = 'git-dirty-strip';
    git.hidden = true;
    composer.parentNode.insertBefore(git, composer);
  }
  return { bar, git };
}

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
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
    const c = st.counts || {};
    const wake = st.wake_pending ? 'wake待消费' : '';
    dom.bar.hidden = false;
    dom.bar.innerHTML =
      `<span class="rs-mode">${esc(mode)}</span>` +
      `<span class="rs-sep">·</span>` +
      `<span>backlog ${esc(c.backlog ?? 0)}</span>` +
      `<span class="rs-sep">/</span>` +
      `<span>planned ${esc(c.planned ?? 0)}</span>` +
      (c.in_progress
        ? `<span class="rs-sep">/</span><span>跑 ${esc(c.in_progress)}</span>`
        : '') +
      (wake ? `<span class="rs-sep">·</span><span>${esc(wake)}</span>` : '') +
      `<span class="rs-ws">${esc(ws)}</span>`;

    const g = st.git || {};
    const dirty = Number(g.dirty || 0);
    const ahead = Number(g.ahead || 0);
    if (dirty > 0 || ahead > 0) {
      dom.git.hidden = false;
      const bits = [];
      if (dirty > 0) bits.push(`<b>${dirty}</b> 处改动`);
      if (ahead > 0) bits.push(`领先远端 ${ahead}`);
      if (g.branch) bits.push(esc(g.branch));
      dom.git.innerHTML =
        `<span class="git-dirty-icon" aria-hidden="true">✎</span>` +
        `<span class="git-dirty-text">工作区 · ${bits.join(' · ')}</span>` +
        `<span class="git-dirty-hint">建议 commit` +
        (ahead > 0 ? ' / push' : '') +
        `</span>`;
    } else {
      dom.git.hidden = true;
      dom.git.innerHTML = '';
    }
  } catch (_) {
    dom.bar.hidden = true;
    if (dom.git) dom.git.hidden = true;
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
  document.addEventListener('ccc-engine-status', () => {
    refreshRuntimeStatus().catch(() => {});
  });
}
