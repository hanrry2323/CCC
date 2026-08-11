/**
 * boardPanel.js — T40 三栏右栏：任务卡流（Linear 风格卡片）。
 * T56: 改接 cardApi + TaskCard* 统一数据层及组件层。
 *
 * 数据走 GET /cards?project=&state=&page=
 * 卡片：ID + 标题 + 状态徽章 + 执行体 + 打回次数 + 更新时间，点击展开详情。
 * 自动打开：首次进入对话视图且 localStorage 标记未关闭时打开（T40）。
 */
import { state } from '../state.js';
import { getCards, getBoardTask, apiGet } from '../api.js';
import { STATE_TONE, escapeHtml, fmtTaskCopy } from './taskCard.js';
import { TaskCardList } from './taskCardList.js';
import { renderTaskCardDetail } from './taskCardDetail.js';

// 契约 §2 五态（与新栈 models.STATES 对齐；旧 backlog/planned/... 已退役）
const STATES = ['待分派', '执行中', '机审', '已回写', '打回', '已关闭'];

const PANEL_KEY = 'ccc_board_panel_open';
const DETAIL_KEY = 'ccc_board_panel_detail';

let pollTimer = null;
let trackedTask = null;
let lastDetailId = null;
let cardListInstance = null;
let filterMode = 'linked';

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
    panel.innerHTML = `
      <div class="board-panel-header">
        <span class="board-panel-title">任务卡流</span>
        <span class="board-panel-ready" id="board-panel-ready" title="待合入（机审通过可合入）"></span>
        <div class="board-panel-actions">
          <a class="artifact-btn" id="board-full-link" href="#/board" title="完整看板">↗</a>
          <button type="button" class="artifact-btn" id="board-refresh" title="刷新">⟳</button>
          <button type="button" class="artifact-btn" id="board-close" title="收起">×</button>
        </div>
      </div>
      <div class="board-panel-body" id="board-panel-body">
        <div class="settings-loading"><div class="spinner"></div><span>加载中...</span></div>
      </div>`;
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
  cardListInstance = null;
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
  }, 5000);
}

function stopBoardAutoRefresh() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

/** Track a just-created task; column changes toast via board auto-refresh. */
export function trackDispatchedTask(taskId, workspace) {
  trackedTask = { id: taskId, workspace, lastCol: '待分派' };
}

function _toastTrackedTaskProgress(all) {
  if (!trackedTask) return;
  const hit = all.find((c) => c.id === trackedTask.id || c.card_id === trackedTask.id);
  const col = hit?.state || hit?.status;
  if (!col || col === trackedTask.lastCol) return;
  trackedTask.lastCol = col;
  window.showToast?.('任务 ' + trackedTask.id + ' → ' + col, 'info');
  if (col === '已关闭') {
    window.showToast?.('任务完成: ' + trackedTask.id, 'success');
    trackedTask = null;
  } else if (col === '打回') {
    window.showToast?.('任务被打回: ' + trackedTask.id, 'error');
    trackedTask = null;
  }
}

export async function refreshBoardPanel(opts = {}) {
  const body = document.getElementById('board-panel-body');
  if (!body) return;
  if (!opts.quiet) {
    if (!cardListInstance) {
      body.innerHTML = '<div class="settings-loading"><div class="spinner"></div><span>加载中...</span></div>';
    } else {
      cardListInstance.showLoading();
    }
  }
  const ws = workspaceOf();
  try {
    const res = await getCards({ project: ws === 'all' ? '' : ws, page_size: 1000 });
    const all = res.cards || [];
    try {
      const ready = await apiGet('/board/ready_for_merge');
      const el = document.getElementById('board-panel-ready');
      const n = (ready && ready.count) || 0;
      if (el) el.textContent = n ? `待合入 ${n}` : '';
    } catch (_) { /* 板务徽章可选 */ }
    try {
      const running = await apiGet('/tasks/running');
      const byId = new Map();
      for (const t of running.tasks || []) {
        if (t && t.work_id) byId.set(t.work_id, t);
      }
      for (const c of all) {
        const t = byId.get(c.id);
        if (!t) continue;
        if (t.dirty_files != null) c.dirty_files = t.dirty_files;
        if (t.lines_insert != null) c.lines_insert = t.lines_insert;
        if (t.lines_delete != null) c.lines_delete = t.lines_delete;
        if (t.branch_insert != null) c.branch_insert = t.branch_insert;
        if (t.branch_delete != null) c.branch_delete = t.branch_delete;
        if (t.elapsed_s != null) c.elapsed_s = t.elapsed_s;
        if (t.last_activity_at != null) c.last_activity_at = t.last_activity_at;
        if (t.log_bytes != null) c.log_bytes = t.log_bytes;
        if (t.tool_calls != null) c.tool_calls = t.tool_calls;
        if (t.shell_calls != null) c.shell_calls = t.shell_calls;
        if (t.metrics_live != null) c.metrics_live = t.metrics_live;
        else if (t.live != null) c.metrics_live = t.live;
      }
    } catch (_) { /* dirty 可选 */ }
    _toastTrackedTaskProgress(all);

    // Sort: 打回 > 执行中 > 机审 > 待分派 > 已回写 > 已关闭
    const order = { '打回': 0, '执行中': 1, '机审': 2, '待分派': 3, '已回写': 4, '已关闭': 5 };
    all.sort((a, b) => {
      const stateA = a.board_column || a.state || a.status || '待分派';
      const stateB = b.board_column || b.state || b.status || '待分派';
      const oa = order[stateA] ?? 9;
      const ob = order[stateB] ?? 9;
      if (oa !== ob) return oa - ob;
      return String(b.written_at || b.dispatched_at || '').localeCompare(String(a.written_at || a.dispatched_at || ''));
    });

    // Associated filter: current project unclosed cards OR current session associated cards
    const currentSessionId = state.get('currentSessionId');
    const filtered = all.filter(c => {
      if (filterMode === 'all') return true;
      const cardState = c.state || c.status;
      const isUnclosed = cardState !== '已关闭';
      const isCurrentProject = (ws === 'all' || (c.project || 'ccc') === ws);
      const isCurrentSession = currentSessionId && c.thread_id === currentSessionId;
      return (isCurrentProject && isUnclosed) || isCurrentSession;
    });

    // Calculate counts for each state
    const counts = { '待分派': 0, '执行中': 0, '机审': 0, '已回写': 0, '打回': 0, '已关闭': 0 };
    for (const c of filtered) {
      const st = c.board_column || c.state || c.status;
      if (counts[st] !== undefined) {
        counts[st]++;
      }
    }

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

    // Update body structure if it's the first render or workspace changed
    const wrapperId = 'board-card-list-wrapper';
    let listWrapper = document.getElementById(wrapperId);
    if (!listWrapper) {
      body.innerHTML = `
        <div class="board-ws">工作区: <strong>${escapeHtml(ws)}</strong></div>
        ${trackLine}
        <div class="board-stat-row">${countsHtml}</div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin: 4px 0 8px;">
          <div class="board-recent-title" style="margin: 0;">任务卡流</div>
          <div class="board-filter-toggle" style="display: flex; gap: 8px; font-size: 11px;">
            <button type="button" class="board-filter-btn" id="board-filter-linked" style="background: transparent; border: none; cursor: pointer; padding: 0 4px;">关联</button>
            <span style="color: var(--ccc-border-subtle)">|</span>
            <button type="button" class="board-filter-btn" id="board-filter-all" style="background: transparent; border: none; cursor: pointer; padding: 0 4px;">全部</button>
          </div>
        </div>
        <div id="${wrapperId}" style="flex: 1; min-height: 200px; display: flex; flex-direction: column; overflow: hidden; margin-bottom: 12px;"></div>
        <button type="button" class="btn-primary board-dispatch-btn" id="board-dispatch">下达任务</button>
      `;
      listWrapper = document.getElementById(wrapperId);

      document.getElementById('board-dispatch')?.addEventListener('click', () => {
        import('./taskDialog.js').then(m => m.openTaskDialog());
      });

      cardListInstance = new TaskCardList(listWrapper, {
        onCardClick: async (card, id) => {
          await toggleCardDetail(card, id);
        },
        onCopyClick: async (btn, id) => {
          const t = cardListInstance.items.find(x => x.id === id) || { id, title: '' };
          navigator.clipboard?.writeText(fmtTaskCopy(t, t.state || t.status)).then(() => {
            window.showToast?.('已复制任务块，可粘贴到对话', 'success');
          });
        }
      });
      // Enable virtual scrolling for the card stream
      cardListInstance.enableVirtualScroll(true);
    } else {
      // Just update track line and state stats if wrapper already exists
      const trackEl = body.querySelector('.board-track');
      if (trackedTask) {
        if (trackEl) {
          trackEl.innerHTML = `跟踪: <code>${escapeHtml(trackedTask.id)}</code> → ${escapeHtml(trackedTask.lastCol || '?')}`;
        } else {
          const wsEl = body.querySelector('.board-ws');
          if (wsEl) {
            wsEl.insertAdjacentHTML('afterend', `<div class="board-track">跟踪: <code>${escapeHtml(trackedTask.id)}</code> → ${escapeHtml(trackedTask.lastCol || '?')}</div>`);
          }
        }
      } else if (trackEl) {
        trackEl.remove();
      }

      const statRow = body.querySelector('.board-stat-row');
      if (statRow) {
        statRow.innerHTML = countsHtml;
      }
    }

    // Update filter buttons styling and bind handlers
    const btnLinked = body.querySelector('#board-filter-linked');
    const btnAll = body.querySelector('#board-filter-all');
    if (btnLinked && btnAll) {
      btnLinked.className = `board-filter-btn ${filterMode === 'linked' ? 'active' : ''}`;
      btnLinked.style.color = filterMode === 'linked' ? 'var(--ccc-text-accent)' : 'var(--ccc-text-muted)';
      btnLinked.style.fontWeight = filterMode === 'linked' ? 'bold' : 'normal';

      btnAll.className = `board-filter-btn ${filterMode === 'all' ? 'active' : ''}`;
      btnAll.style.color = filterMode === 'all' ? 'var(--ccc-text-accent)' : 'var(--ccc-text-muted)';
      btnAll.style.fontWeight = filterMode === 'all' ? 'bold' : 'normal';

      btnLinked.onclick = () => {
        if (filterMode === 'linked') return;
        filterMode = 'linked';
        refreshBoardPanel({ quiet: true });
      };
      btnAll.onclick = () => {
        if (filterMode === 'all') return;
        filterMode = 'all';
        refreshBoardPanel({ quiet: true });
        // Enters Kanban:
        const boardLink = document.getElementById('board-full-link');
        if (boardLink) {
          boardLink.href = '#/board?ws=' + encodeURIComponent(workspaceOf());
          boardLink.click();
        } else {
          location.hash = '#/board?ws=' + encodeURIComponent(workspaceOf());
        }
      };
    }

    const full = document.getElementById('board-full-link');
    if (full) full.href = '#/board?ws=' + encodeURIComponent(ws);

    // Update list elements inside TaskCardList
    cardListInstance.setItems(filtered);

  } catch (err) {
    if (!opts.quiet) {
      body.innerHTML = '<div class="board-empty">看板不可用: ' + escapeHtml(err.message || String(err)) + '</div>';
    }
    cardListInstance = null;
  }
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
    detail.innerHTML = renderTaskCardDetail(t);
    try { sessionStorage.setItem(DETAIL_KEY, taskId); } catch (_) {}
  } catch (err) {
    detail.innerHTML = '<div class="board-detail-error">详情不可用: ' + escapeHtml(err.message || String(err)) + '</div>';
  }
}
