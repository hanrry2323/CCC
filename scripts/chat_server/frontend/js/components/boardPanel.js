import { state } from '../state.js';
import { loadBoard } from '../api.js';
import { escapeHtml } from '../utils.js';

const COLUMNS = [
  'backlog', 'planned', 'in_progress', 'testing', 'verified', 'released', 'abnormal',
];

function workspaceOf() {
  const p = state.get('currentProject') || 'ccc';
  if (p === 'ccc') return 'CCC';
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
        '<span>看板摘要</span>' +
        '<div class="board-panel-actions">' +
          '<a class="artifact-btn" id="board-full-link" href="http://127.0.0.1:7777" target="_blank" rel="noopener">完整看板</a>' +
          '<button type="button" class="artifact-btn" id="board-refresh">刷新</button>' +
          '<button type="button" class="artifact-btn" id="board-close">关闭</button>' +
        '</div>' +
      '</div>' +
      '<div class="board-panel-body" id="board-panel-body">' +
        '<div class="settings-loading"><div class="spinner"></div><span>加载中...</span></div>' +
      '</div>';
    document.getElementById('layout')?.appendChild(panel);
    document.getElementById('board-close')?.addEventListener('click', closeBoardPanel);
    document.getElementById('board-refresh')?.addEventListener('click', () => refreshBoardPanel());
  }
  panel.classList.add('open');
  document.getElementById('layout')?.classList.add('with-board');
  await refreshBoardPanel();
}

export function closeBoardPanel() {
  document.getElementById('board-panel')?.classList.remove('open');
  document.getElementById('layout')?.classList.remove('with-board');
}

export async function refreshBoardPanel() {
  const body = document.getElementById('board-panel-body');
  if (!body) return;
  body.innerHTML = '<div class="settings-loading"><div class="spinner"></div><span>加载中...</span></div>';
  const ws = workspaceOf();
  try {
    const data = await loadBoard(ws);
    const board = data.columns || data.board || data;
    const counts = data.counts || {};
    let recent = [];
    for (const col of COLUMNS) {
      const tasks = board[col] || [];
      if (counts[col] == null) counts[col] = Array.isArray(tasks) ? tasks.length : 0;
      if (Array.isArray(tasks)) {
        for (const t of tasks) {
          recent.push({ ...t, column: col });
        }
      }
    }
    recent.sort((a, b) => String(b.updated_at || b.created_at || '').localeCompare(String(a.updated_at || a.created_at || '')));
    recent = recent.slice(0, 8);

    body.innerHTML =
      '<div class="board-ws">工作区: <strong>' + escapeHtml(ws) + '</strong></div>' +
      '<div class="board-counts">' +
        COLUMNS.map(c =>
          '<div class="board-count-chip"><span class="board-count-n">' + counts[c] + '</span>' +
          '<span class="board-count-l">' + c + '</span></div>'
        ).join('') +
      '</div>' +
      '<div class="board-recent-title">最近任务</div>' +
      '<div class="board-recent">' +
        (recent.length
          ? recent.map(t =>
              '<div class="board-task-row">' +
                '<span class="board-task-col">' + escapeHtml(t.column) + '</span>' +
                '<span class="board-task-title">' + escapeHtml(t.title || t.id) + '</span>' +
              '</div>'
            ).join('')
          : '<div class="board-empty">暂无任务</div>') +
      '</div>' +
      '<button type="button" class="btn-primary board-dispatch-btn" id="board-dispatch">下达任务</button>';

    document.getElementById('board-dispatch')?.addEventListener('click', () => {
      import('./taskDialog.js').then(m => m.openTaskDialog());
    });
  } catch (err) {
    body.innerHTML = '<div class="board-empty">看板不可用: ' + escapeHtml(err.message || String(err)) + '</div>';
  }
}
