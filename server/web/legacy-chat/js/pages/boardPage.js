/**
 * boardPage.js — 看板页（T30：新协议版）
 * T58: 列表默认 + 视图切换 + 分组视图。
 *
 * 数据源（全部走新服务端）：
 *   - 列表/搜索：GET /cards?project=&state=&page=
 *   - 多项目指标：GET /board/summaries?workspaces=a,b,c
 *   - 卡详情：GET /tasks/{id}（不含 events；events 字段为 []）
 *
 * 状态命名：契约 §2 五态（中文）：待分派 / 执行中 / 已回写 / 已关闭 / 打回。
 */

import { apiGet, getCards } from '../api.js';
import { TaskCardList } from '../components/taskCardList.js';
import { renderTaskCardDetail } from '../components/taskCardDetail.js';
import { fmtTaskCopy, renderTaskCard } from '../components/taskCard.js';

/** 看板列：五态派生，增加「机审」（已回写且无机审通过）。 */
const FLOW_COLS = ['待分派', '执行中', '机审', '已回写', '打回', '已关闭'];
const COLORS = {
  待分派: '#a39e93',
  执行中: '#c47a2c',
  机审: '#8b6cc1',
  已回写: '#3d9a5f',
  打回: '#c44',
  已关闭: '#5a7a9a',
};
const CLOSED_COL_LIMIT = 10;

let _root = null;
let _timer = null;
let _allCards = [];
let _ws = 'all';
let _wsNames = [];
let _indicatorBusy = false;

// T58 state
let _activeView = 'list'; // 'list' | 'kanban' | 'group-project' | 'group-executor'
let _filterProj = 'all';
let _filterState = 'all';
let _filterExec = 'all';
let _filterQ = '';
let _filterDebounce = null;
let _listCurrentPage = 1;
let _listCardList = null;
let _colLists = {};
let _kanbanPageSizes = {};
const _collapsedGroups = new Set();

function esc(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function matchesKeyword(t, q) {
  if (!q) return true;
  const hay = [t.id, t.title, t.executor, t.status, t.state, t.note].filter(Boolean).join(' ');
  return hay.toLowerCase().indexOf(q.toLowerCase()) >= 0;
}

async function copyTextToClipboard(text) {
  const payload = String(text || '');
  if (!payload) return false;
  try {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      await navigator.clipboard.writeText(payload);
      return true;
    }
  } catch (_) { /* fall through */ }
  try {
    const ta = document.createElement('textarea');
    ta.value = payload;
    ta.setAttribute('readonly', '');
    ta.style.cssText =
      'position:fixed;top:0;left:0;width:1px;height:1px;padding:0;border:0;opacity:0;';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, payload.length);
    const ok = document.execCommand('copy');
    ta.remove();
    return !!ok;
  } catch (_) {
    return false;
  }
}

function wsFromHash() {
  const raw = (location.hash || '').replace(/^#\/?/, '');
  const qi = raw.indexOf('?');
  if (qi < 0) return '';
  try {
    return (new URLSearchParams(raw.slice(qi + 1)).get('ws') || '').trim();
  } catch (_) {
    return '';
  }
}

function preferredWorkspace() {
  const fromHash = wsFromHash();
  if (fromHash) return fromHash;
  try {
    const cur = localStorage.getItem('ccc_hub_last_project');
    if (cur) return cur;
  } catch (_) {}
  return 'all';
}

function getPreferredView() {
  try {
    return localStorage.getItem('ccc_board_view') || 'list';
  } catch (_) {
    return 'list';
  }
}

function setPreferredView(view) {
  _activeView = view;
  try {
    localStorage.setItem('ccc_board_view', view);
  } catch (_) {}
}

function html() {
  return `
<div class="board-page hub-page" style="display: flex; flex-direction: column; height: 100%; overflow: hidden;">
  <div class="orch-hint">看板 · 走新服务端协议（/board/snapshot）。2017 单端 :7788 四视图。</div>

  <div class="board-toolbar" style="flex-shrink: 0; padding-bottom: 5px;">
    <h2>看板</h2>
    <div class="board-toolbar-actions">
      <button type="button" class="hub-btn" id="board-refresh" title="刷新">刷新</button>
      <span class="board-write-hint" title="写操作走任务卡 / Engine">读视图 · 写操作走任务卡 / Engine</span>
    </div>
    <div class="board-ws-btns" id="board-ws-btns" role="group" aria-label="项目"></div>
    <span class="st" id="board-st">·</span>
  </div>

  <div class="board-toolbar-filters" style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap; padding: 10px; background: var(--ccc-bg-layer); border-bottom: 1px solid var(--ccc-border-subtle); flex-shrink: 0; border-radius: var(--ccc-radius-sm); margin-bottom: 5px;">
    <div class="filter-group" style="display: flex; align-items: center; gap: 6px;">
      <label for="board-filter-proj" style="font-size: 11px; color: var(--ccc-text-muted);">项目:</label>
      <select id="board-filter-proj" class="hub-select" style="padding: 2px 6px; font-size: 12px; border-radius: 3px; border: 1px solid var(--ccc-border-subtle); background: var(--ccc-bg-base); color: var(--ccc-text-base);">
        <option value="all">全部</option>
      </select>
    </div>

    <div class="filter-group" style="display: flex; align-items: center; gap: 6px;">
      <label for="board-filter-state" style="font-size: 11px; color: var(--ccc-text-muted);">状态:</label>
      <select id="board-filter-state" class="hub-select" style="padding: 2px 6px; font-size: 12px; border-radius: 3px; border: 1px solid var(--ccc-border-subtle); background: var(--ccc-bg-base); color: var(--ccc-text-base);">
        <option value="all">全部</option>
        <option value="待分派">待分派</option>
        <option value="执行中">执行中</option>
        <option value="机审">机审</option>
        <option value="已回写">已回写</option>
        <option value="打回">打回</option>
        <option value="已关闭">已关闭</option>
      </select>
    </div>

    <div class="filter-group" style="display: flex; align-items: center; gap: 6px;">
      <label for="board-filter-exec" style="font-size: 11px; color: var(--ccc-text-muted);">执行体:</label>
      <select id="board-filter-exec" class="hub-select" style="padding: 2px 6px; font-size: 12px; border-radius: 3px; border: 1px solid var(--ccc-border-subtle); background: var(--ccc-bg-base); color: var(--ccc-text-base);">
        <option value="all">全部</option>
      </select>
    </div>

    <div class="filter-group" style="display: flex; align-items: center; gap: 6px; flex: 1; min-width: 150px;">
      <input type="search" id="board-filter-q" class="board-filter-input" placeholder="筛选关键词（标题/ID/执行体）" aria-label="筛选关键词" style="width: 100%;">
    </div>

    <div class="view-switcher" style="display: flex; gap: 2px; background: var(--ccc-bg-base); padding: 2px; border: 1px solid var(--ccc-border-subtle); border-radius: var(--ccc-radius-sm);">
      <button type="button" class="hub-btn view-switch-btn" data-view="list">列表</button>
      <button type="button" class="hub-btn view-switch-btn" data-view="kanban">看板</button>
      <button type="button" class="hub-btn view-switch-btn" data-view="group-project">项目分组</button>
      <button type="button" class="hub-btn view-switch-btn" data-view="group-executor">执行体分组</button>
    </div>
  </div>

  <div class="board-main" style="flex: 1; overflow: hidden; display: flex; flex-direction: column;">
    <div class="board-layout" id="board-layout" style="flex: 1; overflow: hidden; display: flex; flex-direction: column;"></div>
  </div>
</div>

<div class="board-modal" id="board-dm">
  <div class="box" style="width:520px">
    <h2 id="board-dti">任务详情</h2>
    <div style="font-size:12px;line-height:1.6;max-height:60vh;overflow:auto">
      <div id="board-did" style="font-family:var(--ccc-font-mono);font-size:11px;color:var(--ccc-text-muted)"></div>
      <div id="board-dtt" style="font-weight:500;padding:6px 0"></div>
      <div id="board-dmt" style="padding:6px 0;border-top:1px solid var(--ccc-border-subtle);font-size:11px"></div>
      <div id="board-dde" style="white-space:pre-wrap;border-top:1px solid var(--ccc-border-subtle);padding-top:6px;display:none;"></div>
      <div id="board-dacc" style="border-top:none;padding-top:6px;margin-top:6px"></div>
    </div>
    <div class="btns" style="margin-top:10px">
      <button type="button" class="hub-btn" id="board-dclose">关闭</button>
    </div>
  </div>
</div>`;
}

function getFilteredCards() {
  return _allCards.filter(c => {
    // 1. Primary workspace filter (from top buttons)
    if (_ws !== 'all' && c.project !== _ws) {
      return false;
    }
    // 2. Project filter from dropdown
    if (_filterProj !== 'all' && c.project !== _filterProj) {
      return false;
    }
    // 3. State filter
    const cardState = c.state || c.status || '待分派';
    if (_filterState !== 'all' && cardState !== _filterState) {
      return false;
    }
    // 4. Executor filter
    if (_filterExec !== 'all' && c.executor !== _filterExec) {
      return false;
    }
    // 5. Keyword search filter
    if (_filterQ && !matchesKeyword(c, _filterQ)) {
      return false;
    }
    return true;
  });
}

function populateFilterOptions() {
  if (!_root) return;

  // 1. Project select dropdown
  const projSelect = _root.querySelector('#board-filter-proj');
  if (projSelect) {
    const selectedVal = _filterProj;
    const projects = new Set();
    for (const c of _allCards) {
      if (c.project) projects.add(c.project);
    }
    const sortedProj = Array.from(projects).sort();

    let htmlOpts = '<option value="all">全部</option>';
    for (const p of sortedProj) {
      htmlOpts += `<option value="${esc(p)}">${esc(p)}</option>`;
    }
    projSelect.innerHTML = htmlOpts;
    projSelect.value = selectedVal;
    if (selectedVal !== 'all' && !projects.has(selectedVal)) {
      _filterProj = 'all';
      projSelect.value = 'all';
    }
  }

  // 2. Executor select dropdown
  const execSelect = _root.querySelector('#board-filter-exec');
  if (execSelect) {
    const selectedVal = _filterExec;
    const executors = new Set();
    for (const c of _allCards) {
      if (c.executor && c.executor !== '未知') {
        executors.add(c.executor);
      }
    }
    const sortedExec = Array.from(executors).sort();

    let htmlOpts = '<option value="all">全部</option>';
    for (const e of sortedExec) {
      htmlOpts += `<option value="${esc(e)}">${esc(e)}</option>`;
    }
    execSelect.innerHTML = htmlOpts;
    execSelect.value = selectedVal;
    if (selectedVal !== 'all' && !executors.has(selectedVal)) {
      _filterExec = 'all';
      execSelect.value = 'all';
    }
  }
}

function renderActiveView() {
  const host = _root.querySelector('#board-layout');
  if (!host) return;

  const filteredCards = getFilteredCards();

  // Sync active view switch button
  _root.querySelectorAll('.view-switch-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === _activeView);
  });

  if (_activeView === 'list') {
    // Clear other view-specific items from colLists
    _colLists = {};

    if (!host.querySelector('#board-list-container')) {
      host.innerHTML = `<div class="board-list-density" id="board-list-container" style="display: flex; flex-direction: column; height: 100%; overflow: hidden;"></div>`;

      const listContainer = host.querySelector('#board-list-container');
      _listCardList = new TaskCardList(listContainer, {
        itemHeight: 36, // compact high density rows
        pageSize: 50,
        onCardClick: (card, id) => showDetail(id),
        onCopyClick: async (btn, id) => {
          const t = _allCards.find(x => x.id === id) || { id, title: '' };
          const ok = await copyTextToClipboard(fmtTaskCopy(t, t.state || t.status));
          if (ok) {
            window.showToast?.('已复制任务块，可粘贴到对话', 'success');
          } else {
            window.showToast?.('复制失败：请长按选中后手动复制', 'error');
          }
        }
      });
      _listCardList.enableVirtualScroll(true);
    }

    const totalPages = Math.ceil(filteredCards.length / 50);
    if (_listCurrentPage > totalPages) _listCurrentPage = Math.max(1, totalPages);

    const startIndex = (_listCurrentPage - 1) * 50;
    const pageCards = filteredCards.slice(startIndex, startIndex + 50);

    _listCardList.setItems(pageCards);
    _listCardList.setupPagination({
      currentPage: _listCurrentPage,
      totalPages,
      onPageChange: (p) => {
        _listCurrentPage = p;
        renderActiveView();
      }
    });

  } else if (_activeView === 'kanban') {
    _listCardList = null;

    if (!host.querySelector('#board-flow')) {
      host.innerHTML = `
        <div class="board-flow-cols" id="board-flow" style="display: grid; grid-auto-columns: minmax(278px, 1fr); grid-auto-flow: column; gap: 12px; height: 100%; overflow-x: auto; padding: 10px 0;">
          ${FLOW_COLS.map(col => `
            <div class="board-col" style="display: flex; flex-direction: column; background: var(--ccc-bg-layer); border: 1px solid var(--ccc-border-subtle); border-radius: var(--ccc-radius-sm); overflow: hidden; height: 100%; min-width: 278px;">
              <div class="board-col-h">
                <span><span class="board-dot" style="background:${COLORS[col]}"></span>${esc(col)}${col === '已关闭' ? '<span class="board-col-cap" title="只显示最近关闭的卡">·近10</span>' : ''}</span>
                <span class="ct" id="ct-${col}">0</span>
              </div>
              <div class="board-col-body" id="col-list-${col}" style="display: flex; flex-direction: column; overflow: hidden; flex: 1; min-height: 200px; padding: 8px; gap: 6px;"></div>
            </div>
          `).join('')}
        </div>
      `;

      _colLists = {};
      for (const col of FLOW_COLS) {
        const colEl = host.querySelector(`#col-list-${col}`);
        if (colEl) {
          _colLists[col] = new TaskCardList(colEl, {
            itemHeight: 118,
            onCardClick: (card, id) => showDetail(id),
            onCopyClick: async (btn, id) => {
              const t = _allCards.find(x => x.id === id) || { id, title: '' };
              const ok = await copyTextToClipboard(fmtTaskCopy(t, col));
              if (ok) {
                window.showToast?.('已复制任务块，可粘贴到对话', 'success');
              } else {
                window.showToast?.('复制失败：请长按选中后手动复制', 'error');
              }
            }
          });
          _colLists[col].enableVirtualScroll(true);
        }
      }
    } else {
      const flow = host.querySelector('#board-flow');
      if (flow) {
        flow.style.gridAutoColumns = 'minmax(278px, 1fr)';
        flow.style.gap = '12px';
      }
      host.querySelectorAll('.board-col').forEach((el) => {
        el.style.minWidth = '278px';
      });
      host.querySelectorAll('.board-col-body').forEach((el) => {
        el.style.padding = '8px';
        el.style.gap = '6px';
      });
      for (const col of FLOW_COLS) {
        if (_colLists[col]) _colLists[col].itemHeight = 118;
      }
    }

    for (const col of FLOW_COLS) {
      let stateCards = filteredCards.filter(c => {
        const colKey = c.board_column || c.state || c.status || '待分派';
        return colKey === col;
      });
      if (col === '已关闭') {
        stateCards = stateCards
          .slice()
          .sort((a, b) => String(b.written_at || b.closed_at || b.dispatched_at || '')
            .localeCompare(String(a.written_at || a.closed_at || a.dispatched_at || '')))
          .slice(0, CLOSED_COL_LIMIT);
      }

      const countEl = _root.querySelector(`#ct-${col}`);
      if (countEl) countEl.textContent = stateCards.length;

      if (!_kanbanPageSizes[col]) {
        _kanbanPageSizes[col] = 30;
      }

      const visibleCards = stateCards.slice(0, _kanbanPageSizes[col]);

      if (_colLists[col]) {
        _colLists[col].setItems(visibleCards);
      }

      const paginationEl = _root.querySelector(`#col-list-${col} .task-card-list-pagination`);
      if (paginationEl) {
        if (stateCards.length > visibleCards.length) {
          paginationEl.innerHTML = `
            <div style="display: flex; justify-content: center; padding: 6px;">
              <button type="button" class="hub-btn load-more-btn" style="width: 100%; font-size: 11px; padding: 4px 8px; cursor: pointer; border: 1px solid var(--ccc-border-subtle); background: var(--ccc-bg-layer); color: var(--ccc-text-base); border-radius: 3px;">
                加载更多 (${stateCards.length - visibleCards.length})
              </button>
            </div>
          `;
          paginationEl.querySelector('.load-more-btn').addEventListener('click', (ev) => {
            ev.preventDefault();
            _kanbanPageSizes[col] += 30;
            renderActiveView();
          });
        } else {
          paginationEl.innerHTML = '';
        }
      }
    }

  } else if (_activeView === 'group-project' || _activeView === 'group-executor') {
    _listCardList = null;
    _colLists = {};

    if (!host.querySelector('.board-grouped-container')) {
      host.innerHTML = `<div class="board-grouped-container" style="flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; padding: 10px 0;"></div>`;
    }

    const groupBy = _activeView === 'group-project' ? 'project' : 'executor';
    const grouped = {};
    for (const card of filteredCards) {
      const key = groupBy === 'project'
        ? (card.project || '未知')
        : (card.executor && card.executor !== '未知' ? card.executor : '未分配');
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(card);
    }

    const groupContainer = host.querySelector('.board-grouped-container');
    if (Object.keys(grouped).length === 0) {
      groupContainer.innerHTML = '<div class="board-empty">暂无分组任务</div>';
      return;
    }

    groupContainer.innerHTML = Object.entries(grouped).map(([key, groupCards]) => {
      const isCollapsed = _collapsedGroups.has(key);
      const toggleIcon = isCollapsed ? '▶' : '▼';
      const cardsHtml = isCollapsed ? '' : groupCards.map(renderTaskCard).join('');
      return `
        <div class="board-group" data-group-key="${esc(key)}" style="border: 1px solid var(--ccc-border-subtle); border-radius: var(--ccc-radius-sm); background: var(--ccc-bg-layer); overflow: hidden; margin-bottom: 4px;">
          <div class="board-group-header" style="display: flex; align-items: center; padding: 8px 12px; background: var(--ccc-bg-base); cursor: pointer; user-select: none;">
            <span class="board-group-toggle" style="margin-right: 8px; font-family: monospace; font-size: 11px; color: var(--ccc-text-muted);">${toggleIcon}</span>
            <span style="font-weight: 600; font-size: 12px; color: var(--ccc-text-base);">${esc(key)}</span>
            <span class="board-group-count" style="margin-left: 8px; font-size: 10px; color: var(--ccc-text-muted); background: var(--ccc-border-subtle); padding: 1px 6px; border-radius: 10px;">${groupCards.length}</span>
          </div>
          <div class="board-group-body" style="display: ${isCollapsed ? 'none' : 'flex'}; flex-direction: column; gap: 4px; padding: 8px;" ${isCollapsed ? 'hidden' : ''}>
            ${cardsHtml}
          </div>
        </div>
      `;
    }).join('');

    groupContainer.querySelectorAll('.board-group').forEach(groupEl => {
      const key = groupEl.dataset.groupKey;
      const header = groupEl.querySelector('.board-group-header');
      header.addEventListener('click', (ev) => {
        ev.preventDefault();
        if (_collapsedGroups.has(key)) {
          _collapsedGroups.delete(key);
        } else {
          _collapsedGroups.add(key);
        }
        renderActiveView();
      });

      const body = groupEl.querySelector('.board-group-body');
      if (body) {
        body.addEventListener('click', (ev) => {
          const card = ev.target.closest('.board-task-card');
          if (!card) return;
          if (ev.target.closest('.board-card-copy') || ev.target.closest('.card-copy-btn')) {
            ev.stopPropagation();
            ev.preventDefault();
            const id = card.dataset.id;
            const t = _allCards.find(x => x.id === id) || { id, title: '' };
            copyTextToClipboard(fmtTaskCopy(t, t.state || t.status)).then(ok => {
              if (ok) window.showToast?.('已复制任务块，可粘贴到对话', 'success');
            });
            return;
          }
          const id = card.dataset.id;
          showDetail(id);
        });
      }
    });
  }

  updateSummary();
}

function updateSummary() {
  const el = _root.querySelector('#board-st');
  if (!el) return;
  const total = getFilteredCards().length;
  el.textContent = _ws + ` · 共 ${total} 张`;
}

function classifyWsStatus(payload) {
  const counts = payload.counts || {};
  const reject = Number(counts['打回'] || 0);
  const doing = Number(counts['执行中'] || 0);
  if (reject > 0) {
    return { mode: 'alert', title: `需人工介入 · 异常 ${reject} 张` };
  }
  if (doing > 0) {
    return { mode: 'running', title: `执行中 · ${doing} 张` };
  }
  return { mode: 'idle', title: '' };
}

function applyWsIndicator(btn, { mode, title }) {
  btn.classList.remove('ws-running', 'ws-alert');
  if (mode === 'running') btn.classList.add('ws-running');
  if (mode === 'alert') btn.classList.add('ws-alert');
  if (title) btn.title = title;
  else btn.removeAttribute('title');
  btn.setAttribute('data-ws-status', mode);
}

async function refreshAllWsIndicators() {
  if (!_root || _indicatorBusy || !_wsNames.length) return;
  _indicatorBusy = true;
  try {
    const agg = await apiGet(
      '/board/summaries?workspaces=' +
        encodeURIComponent(_wsNames.join(','))
    ).catch(() => null);
    const summaries = (agg && agg.summaries) || {};
    for (const name of _wsNames) {
      const r = summaries[name];
      const btn = [..._root.querySelectorAll('.board-ws-btn')].find(
        (el) => el.dataset.ws === name
      );
      if (btn) {
        if (!r || r.error) {
          applyWsIndicator(btn, { mode: 'idle', title: r?.error || '' });
        } else {
          applyWsIndicator(btn, classifyWsStatus(r));
        }
      }
    }
  } finally {
    _indicatorBusy = false;
  }
}

function syncWsButtons() {
  if (!_root) return;
  _root.querySelectorAll('.board-ws-btn').forEach((b) => {
    const on = b.dataset.ws === _ws;
    b.classList.toggle('active', on);
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
  });
}

function setActiveWorkspace(name) {
  if (!name || name === _ws) return;
  _ws = name;
  syncWsButtons();
  try {
    const next = '#/board?ws=' + encodeURIComponent(_ws);
    if (location.hash !== next) location.hash = next;
    localStorage.setItem('ccc_hub_last_project', _ws);
  } catch (_) {}
  _listCurrentPage = 1;
  loadBoard();
}

async function loadConfig() {
  const data = await apiGet('/board/summaries');
  const summaries = (data && data.summaries) || {};
  const btns = _root.querySelector('#board-ws-btns');
  btns.innerHTML = '';
  _wsNames = Object.keys(summaries).sort();
  const want = preferredWorkspace();
  if (want && summaries[want]) _ws = want;
  else if (_wsNames.length) _ws = _wsNames[0];
  else _ws = 'all';

  const allBtn = document.createElement('button');
  allBtn.type = 'button';
  allBtn.className = 'board-ws-btn' + (_ws === 'all' ? ' active' : '');
  allBtn.dataset.ws = 'all';
  allBtn.textContent = '全部';
  allBtn.setAttribute('aria-pressed', _ws === 'all' ? 'true' : 'false');
  btns.appendChild(allBtn);

  for (const n of _wsNames) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'board-ws-btn' + (n === _ws ? ' active' : '');
    b.dataset.ws = n;
    b.textContent = n;
    b.setAttribute('aria-pressed', n === _ws ? 'true' : 'false');
    btns.appendChild(b);
  }
}

async function mergeDirtyFromRunning(cards) {
  try {
    const data = await apiGet('/tasks/running');
    const byId = new Map();
    for (const t of data.tasks || []) {
      if (t && t.work_id) byId.set(t.work_id, t);
    }
    for (const c of cards) {
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
  } catch (_) { /* 徽章可选；失败不挡看板 */ }
  return cards;
}

async function loadBoard() {
  try {
    const project = _ws === 'all' ? '' : _ws;
    const r = await getCards({ project, page_size: 1000 });
    _allCards = await mergeDirtyFromRunning(r.cards || []);

    populateFilterOptions();
    renderActiveView();
    refreshAllWsIndicators().catch(() => {});
  } catch (err) {
    window.showToast?.(err && err.message ? err.message : '加载看板失败', 'error');
  }
}

async function showDetail(id) {
  try {
    const r = await apiGet('/tasks/' + encodeURIComponent(id));
    _root.querySelector('#board-dti').textContent = '任务: ' + (r.id || id);
    _root.querySelector('#board-did').textContent = r.id || id;
    _root.querySelector('#board-dtt').textContent = r.title || '(无标题)';
    const meta = [
      `状态: ${esc(r.status || '—')}`,
      r.executor ? `执行体: ${esc(r.executor)}` : '',
      r.card_kind ? `类型: ${esc(r.card_kind)}` : '',
      r.parent_id ? `父卡: ${esc(r.parent_id)}` : '',
    ].filter(Boolean).join(' · ');
    _root.querySelector('#board-dmt').innerHTML = meta;

    const accEl = _root.querySelector('#board-dacc');
    if (accEl) {
      accEl.innerHTML = renderTaskCardDetail(r);
    }
    _root.querySelector('#board-dm').classList.add('open');
  } catch (err) {
    window.showToast?.(err && err.message ? err.message : '加载详情失败', 'error');
  }
}

function bind() {
  _root.querySelector('#board-ws-btns').addEventListener('click', (e) => {
    const btn = e.target.closest('.board-ws-btn');
    if (!btn) return;
    setActiveWorkspace(btn.dataset.ws);
  });

  _root.querySelector('#board-refresh').addEventListener('click', async () => {
    const btn = _root.querySelector('#board-refresh');
    if (btn) btn.disabled = true;
    await loadBoard();
    if (btn) btn.disabled = false;
  });

  _root.querySelector('#board-dclose').addEventListener('click', () => {
    _root.querySelector('#board-dm').classList.remove('open');
  });

  const qInput = _root.querySelector('#board-filter-q');
  if (qInput) {
    qInput.value = _filterQ;
    qInput.addEventListener('input', () => {
      clearTimeout(_filterDebounce);
      _filterDebounce = setTimeout(() => {
        _filterQ = qInput.value.trim();
        _listCurrentPage = 1;
        renderActiveView();
      }, 150);
    });
  }

  const projSelect = _root.querySelector('#board-filter-proj');
  if (projSelect) {
    projSelect.addEventListener('change', () => {
      _filterProj = projSelect.value;
      _listCurrentPage = 1;
      renderActiveView();
    });
  }

  const stateSelect = _root.querySelector('#board-filter-state');
  if (stateSelect) {
    stateSelect.addEventListener('change', () => {
      _filterState = stateSelect.value;
      _listCurrentPage = 1;
      renderActiveView();
    });
  }

  const execSelect = _root.querySelector('#board-filter-exec');
  if (execSelect) {
    execSelect.addEventListener('change', () => {
      _filterExec = execSelect.value;
      _listCurrentPage = 1;
      renderActiveView();
    });
  }

  _root.querySelector('.board-toolbar-filters').addEventListener('click', (ev) => {
    const switchBtn = ev.target.closest('.view-switch-btn');
    if (!switchBtn) return;
    ev.preventDefault();
    const targetView = switchBtn.dataset.view;
    if (targetView && targetView !== _activeView) {
      setPreferredView(targetView);
      renderActiveView();
    }
  });
}

export async function mountBoard(el) {
  const want = preferredWorkspace();
  _activeView = getPreferredView();

  if (_root) {
    if (want && want !== _ws) {
      _ws = want;
      syncWsButtons();
    }
    await loadBoard();
    if (!_timer) _timer = setInterval(() => loadBoard().catch(() => {}), 5000);
    return;
  }
  _root = el;
  if (want) _ws = want;
  el.innerHTML = html();
  bind();
  await loadConfig();
  await loadBoard();
  _timer = setInterval(() => loadBoard().catch(() => {}), 5000);
}

export function unmountBoard() {
  if (_timer) {
    clearInterval(_timer);
    _timer = null;
  }
  _colLists = {};
  _listCardList = null;
  _root = null;
}
