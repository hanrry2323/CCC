/**
 * boardPanel.js — T40 三栏右栏：任务卡流（Linear 风格卡片）。
 * T56: 改接 cardApi + TaskCard* 统一数据层及组件层。
 *
 * 数据走 GET /cards?project=&state=&page=
 * 卡片：ID + 标题 + 状态徽章 + 执行体 + 打回次数 + 更新时间，点击展开详情。
 * 自动打开：首次进入对话视图且 localStorage 标记未关闭时打开（T40）。
 */
import { state } from '../state.js';
import { getCards, getBoardTask } from '../api.js';
import { STATE_TONE, escapeHtml, fmtTaskCopy } from './taskCard.js';
import { TaskCardList } from './taskCardList.js';
import { renderTaskCardDetail } from './taskCardDetail.js';

// 契约 §2 五态（与新栈 models.STATES 对齐；旧 backlog/planned/... 已退役）
const STATES = ['待分派', '执行中', '已回写', '已关闭', '打回'];

const PANEL_KEY = 'ccc_board_panel_open';
const DETAIL_KEY = 'ccc_board_panel_detail';

let pollTimer = null;
let trackedTask = null;
let lastDetailId = null;
let cardListInstance = null;

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
  if (!opts.quiet && !cardListInstance) {
    body.innerHTML = '<div class="settings-loading"><div class="spinner"></div><span>加载中...</span></div>';
  }
  const ws = workspaceOf();
  try {
    const res = await getCards({ project: ws === 'all' ? '' : ws, page_size: 1000 });
    const all = res.cards || [];

    // Calculate counts for each state
    const counts = { '待分派': 0, '执行中': 0, '已回写': 0, '已关闭': 0, '打回': 0 };
    for (const c of all) {
      const st = c.state || c.status;
      if (counts[st] !== undefined) {
        counts[st]++;
      }
    }

    // Sort: 打回 > 执行中 > 待分派 > 已回写 > 已关闭; same state sorted by update time desc
    const order = { '打回': 0, '执行中': 1, '待分派': 2, '已回写': 3, '已关闭': 4 };
    all.sort((a, b) => {
      const stateA = a.state || a.status || '待分派';
      const stateB = b.state || b.status || '待分派';
      const oa = order[stateA] ?? 9;
      const ob = order[stateB] ?? 9;
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

    // Update body structure if it's the first render or workspace changed
    const wrapperId = 'board-card-list-wrapper';
    let listWrapper = document.getElementById(wrapperId);
    if (!listWrapper) {
      body.innerHTML = `
        <div class="board-ws">工作区: <strong>${escapeHtml(ws)}</strong></div>
        ${trackLine}
        <div class="board-stat-row">${countsHtml}</div>
        <div class="board-recent-title">任务卡流</div>
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

    const full = document.getElementById('board-full-link');
    if (full) full.href = '#/board?ws=' + encodeURIComponent(ws);

    // Update list elements inside TaskCardList
    cardListInstance.setItems(all);

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
