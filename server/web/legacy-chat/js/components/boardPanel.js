/**
 * boardPanel.js — T40 三栏右栏：任务卡流（Linear 风格卡片）。
 *
 * 数据走 /board/snapshot?workspace=X → {columns: {状态: [BoardTask]}, counts, workspace}
 * 卡片：ID + 标题 + 状态徽章 + 执行体 + 打回次数 + 更新时间，点击展开详情。
 * 自动打开：首次进入对话视图且 localStorage 标记未关闭时打开（T40）。
 */
import { state } from '../state.js';
import { loadBoard, getBoardTask } from '../api.js';
import { escapeHtml } from '../utils.js';

// 契约 §2 五态（与新栈 models.STATES 对齐；旧 backlog/planned/... 已退役）
const STATES = ['待分派', '执行中', '已回写', '已关闭', '打回'];

// 状态色板（与桌面 CCCTheme 对齐；css/variables.css 已定义同名 CSS 变量）
const STATE_TONE = {
  '待分派': 'pending',
  '执行中': 'running',
  '已回写': 'written',
  '已关闭': 'closed',
  '打回': 'returned',
};

const PANEL_KEY = 'ccc_board_panel_open';
const DETAIL_KEY = 'ccc_board_panel_detail';

let pollTimer = null;
let trackedTask = null;
let lastDetailId = null;

export function workspaceOf() {
  const map = state.get('projectWorkspaceMap') || {};
  const p = state.get('currentProject') || 'ccc';
  if (map[p]) return map[p];
  // T44：默认「CCC 平台」无真实任务卡 → 卡流按全部工作区拉取（与看板页一致）
  if (p === 'ccc') return 'all';
  return p;
}

export function toggleBoardPanel() {
  const panel = document.getElementById('board-panel');
  if (panel?.classList.contains('open')) {
    closeBoardPanel();
  } else {
    openBoardPanel();
  }
}

export async function openBoardPanel() {
  let panel = document.getElementById('board-panel');
  if (!panel) {
    panel = document.createElement('aside');
    panel.id = 'board-panel';
    panel.innerHTML =
      '<div class="board-panel-header">' +
        '<span class="board-panel-title">任务卡流</span>' +
        '<div class="board-panel-actions">' +
          '<a class="artifact-btn" id="board-full-link" href="#/board" title="完整看板">↗</a>' +
          '<button type="button" class="artifact-btn" id="board-refresh" title="刷新">⟳</button>' +
          '<button type="button" class="artifact-btn" id="board-close" title="收起">×</button>' +
        '</div>' +
      '</div>' +
      '<div class="board-panel-body" id="board-panel-body">' +
        '<div class="settings-loading"><div class="spinner"></div><span>加载中...</span></div>' +
      '</div>';
    document.getElementById('layout')?.appendChild(panel);
    const boardLink = document.getElementById('board-full-link');
    if (boardLink) {
      boardLink.addEventListener('click', () => {
        boardLink.href = '#/board?ws=' + encodeURIComponent(workspaceOf());
        closeBoardPanel();
      });
    }
    document.getElementById('board-close')?.addEventListener('click', closeBoardPanel);
    document.getElementById('board-refresh')?.addEventListener('click', () => refreshBoardPanel());
  }
  panel.classList.add('open');
  document.getElementById('layout')?.classList.add('with-board');
  try { localStorage.setItem(PANEL_KEY, '1'); } catch (_) {}
  await refreshBoardPanel();
  startBoardAutoRefresh();
}

export function closeBoardPanel() {
  stopBoardAutoRefresh();
  document.getElementById('board-panel')?.classList.remove('open');
  document.getElementById('layout')?.classList.remove('with-board');
  try { localStorage.setItem(PANEL_KEY, '0'); } catch (_) {}
}

/** 首次进入对话视图时自动打开右栏（用户曾手动关闭则不强制）。 */
export function maybeAutoOpen() {
  try {
    const v = localStorage.getItem(PANEL_KEY);
    // 默认打开；用户点关闭后记 0
    if (v === '0') return;
  } catch (_) {}
  const panel = document.getElementById('board-panel');
  if (!panel?.classList.contains('open')) {
    openBoardPanel();
  }
}

function startBoardAutoRefresh() {
  stopBoardAutoRefresh();
  pollTimer = setInterval(() => {
    if (document.getElementById('board-panel')?.classList.contains('open')) {
      refreshBoardPanel({ quiet: true });
    }
  }, 8000);
}

function stopBoardAutoRefresh() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

/** Track a just-created task and toast on column changes / terminal. */
export function trackDispatchedTask(taskId, workspace) {
  trackedTask = { id: taskId, workspace, lastCol: '待分派' };
  import('../api.js').then(({ pollTaskUntil }) => {
    pollTaskUntil(taskId, workspace, {
      intervalMs: 4000,
      timeoutMs: 45 * 60 * 1000,
      onTick: (snap, col) => {
        if (!col || col === trackedTask?.lastCol) return;
        trackedTask.lastCol = col;
        window.showToast?.('任务 ' + taskId + ' → ' + col, 'info');
        refreshBoardPanel({ quiet: true });
      },
    }).then((final) => {
      const col = final?._column || final?.status;
      if (col === '已关闭') {
        window.showToast?.('任务完成: ' + taskId, 'success');
      } else if (col === '打回') {
        window.showToast?.('任务被打回: ' + taskId, 'error');
      }
      trackedTask = null;
      refreshBoardPanel({ quiet: true });
    });
  });
}

export async function refreshBoardPanel(opts = {}) {
  const body = document.getElementById('board-panel-body');
  if (!body) return;
  if (!opts.quiet) {
    body.innerHTML = '<div class="settings-loading"><div class="spinner"></div><span>加载中...</span></div>';
  }
  const ws = workspaceOf();
  try {
    const data = await loadBoard(ws);
    const board = data.columns || data.board || {};
    const counts = data.counts || {};
    // 收集所有任务并附状态列
    let all = [];
    for (const st of STATES) {
      const arr = board[st] || [];
      if (counts[st] == null) counts[st] = Array.isArray(arr) ? arr.length : 0;
      if (Array.isArray(arr)) {
        for (const t of arr) all.push({ ...t, state: st });
      }
    }
    // 排序：打回 > 执行中 > 待分派 > 已回写 > 已关闭；同状态按更新时间倒序
    const order = { '打回': 0, '执行中': 1, '待分派': 2, '已回写': 3, '已关闭': 4 };
    all.sort((a, b) => {
      const oa = order[a.state] ?? 9;
      const ob = order[b.state] ?? 9;
      if (oa !== ob) return oa - ob;
      return String(b.written_at || b.dispatched_at || '').localeCompare(String(a.written_at || a.dispatched_at || ''));
    });

    const trackLine = trackedTask
      ? '<div class="board-track">跟踪: <code>' + escapeHtml(trackedTask.id) + '</code> → ' +
        escapeHtml(trackedTask.lastCol || '?') + '</div>'
      : '';

    const countsHtml = STATES.map(c =>
      '<button type="button" class="board-stat-chip state-' + STATE_TONE[c] + '" data-state="' + escapeHtml(c) + '">' +
        '<span class="board-stat-n">' + (counts[c] || 0) + '</span>' +
        '<span class="board-stat-l">' + escapeHtml(c) + '</span>' +
      '</button>'
    ).join('');

    body.innerHTML =
      '<div class="board-ws">工作区: <strong>' + escapeHtml(ws) + '</strong></div>' +
      trackLine +
      '<div class="board-stat-row">' + countsHtml + '</div>' +
      '<div class="board-recent-title">任务卡流</div>' +
      '<div class="board-card-list" id="board-card-list">' +
        (all.length
          ? all.map(renderCard).join('')
          : '<div class="board-empty">暂无任务</div>') +
      '</div>' +
      '<button type="button" class="btn-primary board-dispatch-btn" id="board-dispatch">下达任务</button>';

    const full = document.getElementById('board-full-link');
    if (full) full.href = '#/board?ws=' + encodeURIComponent(ws);

    document.getElementById('board-dispatch')?.addEventListener('click', () => {
      import('./taskDialog.js').then(m => m.openTaskDialog());
    });

    // 卡片点击：展开/收起详情
    document.querySelectorAll('#board-card-list .board-task-card').forEach(card => {
      card.addEventListener('click', (ev) => {
        if (ev.target.closest('.board-card-copy')) return;
        const id = card.dataset.id;
        toggleCardDetail(card, id);
      });
    });
    // 复制按钮
    document.querySelectorAll('#board-card-list .board-card-copy').forEach(btn => {
      btn.addEventListener('click', (ev) => {
        ev.stopPropagation();
        const id = btn.dataset.id;
        if (id) {
          navigator.clipboard?.writeText(id).then(() => {
            window.showToast?.('已复制任务 ID: ' + id, 'info');
          });
        }
      });
    });
  } catch (err) {
    if (!opts.quiet) {
      body.innerHTML = '<div class="board-empty">看板不可用: ' + escapeHtml(err.message || String(err)) + '</div>';
    }
  }
}

function renderCard(t) {
  const tone = STATE_TONE[t.state] || 'pending';
  const reject = Number(t.reject_count || 0);
  const rejectBadge = reject > 0
    ? '<span class="board-card-badge badge-reject" title="打回次数">↩ ' + reject + '</span>'
    : '';
  const executor = t.executor && t.executor !== '未知'
    ? '<span class="board-card-badge badge-exec" title="执行体">@' + escapeHtml(t.executor) + '</span>'
    : '';
  const updated = t.written_at && t.written_at !== '未知'
    ? t.written_at
    : (t.dispatched_at && t.dispatched_at !== '未知' ? t.dispatched_at : '');
  const updatedHtml = updated
    ? '<span class="board-card-time" title="更新时间">' + escapeHtml(updated) + '</span>'
    : '';
  return (
    '<div class="board-task-card state-' + tone + '" data-id="' + escapeHtml(t.id) + '">' +
      '<div class="board-card-row">' +
        '<span class="board-card-id">' + escapeHtml(t.id) + '</span>' +
        '<span class="board-card-state state-' + tone + '">' + escapeHtml(t.state) + '</span>' +
      '</div>' +
      '<div class="board-card-title">' + escapeHtml(t.title || t.id) + '</div>' +
      '<div class="board-card-meta">' +
        executor +
        rejectBadge +
        updatedHtml +
        '<button type="button" class="board-card-copy" data-id="' + escapeHtml(t.id) + '" title="复制 ID" aria-label="复制 ID">⧉</button>' +
      '</div>' +
      '<div class="board-card-detail" hidden></div>' +
    '</div>'
  );
}

async function toggleCardDetail(card, taskId) {
  const detail = card.querySelector('.board-card-detail');
  if (!detail) return;
  if (!detail.hasAttribute('hidden')) {
    detail.setAttribute('hidden', '');
    try { sessionStorage.removeItem(DETAIL_KEY); } catch (_) {}
    return;
  }
  // 展开详情：先放 loading，再拉详情
  detail.innerHTML = '<div class="board-detail-loading"><div class="spinner"></div></div>';
  detail.removeAttribute('hidden');
  try {
    const t = await getBoardTask(taskId);
    detail.innerHTML = renderDetail(t);
    try { sessionStorage.setItem(DETAIL_KEY, taskId); } catch (_) {}
  } catch (err) {
    detail.innerHTML = '<div class="board-detail-error">详情不可用: ' + escapeHtml(err.message || String(err)) + '</div>';
  }
}

function renderDetail(t) {
  const phases = Array.isArray(t.phases) ? t.phases : [];
  const events = Array.isArray(t.events) ? t.events : [];
  // T45：状态流转说明（契约 §2 五态），让卡片点击不只展示静态详情
  const flowHtml =
    '<div class="board-detail-section"><div class="board-detail-h">状态流转</div>' +
    '<div class="board-detail-flow">待分派 → 执行中 → 已回写 → 已关闭；打回 → 待分派（附问题清单）</div></div>';
  const phasesHtml = phases.length
    ? '<div class="board-detail-section"><div class="board-detail-h">阶段</div>' +
      phases.map(p =>
        '<div class="board-detail-phase">' +
          '<span class="phase-name">' + escapeHtml(p.name || '') + '</span>' +
          '<span class="phase-status st-' + (p.status || 'unknown') + '">' + escapeHtml(p.status || '—') + '</span>' +
          (p.commit ? '<code class="phase-commit">' + escapeHtml(p.commit) + '</code>' : '') +
        '</div>'
      ).join('') + '</div>'
    : '';
  const eventsHtml = events.length
    ? '<div class="board-detail-section"><div class="board-detail-h">时间线</div>' +
      events.map(ev =>
        '<div class="board-detail-event">' +
          '<span class="ev-ts">' + escapeHtml(ev.ts || '') + '</span>' +
          '<span class="ev-role">@' + escapeHtml(ev.role || 'system') + '</span>' +
          '<span class="ev-msg">' + escapeHtml(ev.message || '') + '</span>' +
        '</div>'
      ).join('') + '</div>'
    : '';
  const note = t.note ? '<div class="board-detail-note">' + escapeHtml(t.note) + '</div>' : '';
  const acceptance = t.acceptance ? '<div class="board-detail-section"><div class="board-detail-h">验收</div><div class="board-detail-acc">' + escapeHtml(t.acceptance) + '</div></div>' : '';
  return (
    flowHtml +
    note +
    acceptance +
    phasesHtml +
    eventsHtml
  );
}
