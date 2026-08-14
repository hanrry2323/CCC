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

import { apiGet, apiPost, getCards } from '../api.js';
import { TaskCardList } from '../components/taskCardList.js';
import { renderTaskCardDetail } from '../components/taskCardDetail.js';
import { fmtTaskCopy, renderTaskCard } from '../components/taskCard.js';

/** 看板列（2026-08-12 重排）：第一竖列待分派/打回 + 执行中/机审（上下分栏）+ 已回写；已关闭删除。 */
const FLOW_COLS = ['待分派', '打回', '执行中', '机审', '已回写'];
const PAIR_COLS = ['待分派', '打回'];
const RUN_COLS = ['执行中', '机审'];
const COLORS = {
  待分派: '#a39e93',
  执行中: '#c47a2c',
  机审: '#8b6cc1',
  已回写: '#3d9a5f',
  打回: '#c44',
};

let _root = null;
let _timer = null;
let _allCards = [];
let _ws = 'all';
let _wsNames = [];
let _indicatorBusy = false;
let _nameMap = {};
let _readyForMergeInfo = null;
let _collapsedCols = {};                  // 全部列默认展开（老板 2026-08-12：已关闭不折叠）
let _colOpen = {};                       // 列体折叠（头部按钮）
let _dense = false;                      // 卡片密度
let _searchQ = '';
let _colCardIds = { '执行中': [], '机审': [] }; // 上栏可见卡 id（运行流对应）
let _es = null;                          // /tasks/stream SSE 连接
let _esSig = '';                         // 当前 SSE 订阅签名（ids 未变复用连接）
let _runColSig = {};                     // 执行中/机审列渲染签名（消闪烁）
let _streamCache = {};                   // work_id → 最近中文行（卡片重建时恢复，刷新不冲掉）

// T58 state（2026-08 视图收拢：只保留看板）
let _colLists = {};
let _kanbanPageSizes = {};

function esc(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
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
  return 'all';
}

function html() {
  return `
<div class="board-page hub-page" style="display: flex; flex-direction: column; height: 100%; overflow: hidden;">
  <div class="board-toolbar" style="flex-shrink: 0; padding-bottom: 5px;">
    <h2>看板</h2>
    <div class="board-toolbar-actions">
      <button type="button" class="hub-btn" id="board-refresh" title="刷新">刷新</button>
    </div>
    <div class="board-ws-btns" id="board-ws-btns" role="group" aria-label="项目"></div>
    <input type="search" id="board-search" placeholder="搜索卡…" style="padding:5px 10px;border:1px solid var(--ccc-border-subtle);border-radius:999px;background:#fff;font-size:12px;width:150px;outline:none;">
    <button type="button" class="hub-btn" id="board-density" title="切换卡片密度">${_dense ? '舒适' : '紧凑'}</button>
    <span class="st" id="board-st">·</span>
  </div>

  <div id="board-backlog-alert-banner" style="display:none; flex-shrink: 0; margin: 0 10px 10px 10px; padding: 10px; background: var(--ccc-bg-layer); border: 1px solid #ffccc7; border-radius: var(--ccc-radius-sm); color: #ff4d4f; font-size: 12px; font-weight: 500; align-items: center; justify-content: space-between; animation: board-live-pulse 1.6s ease-in-out infinite;">
    <span id="board-backlog-alert-msg" style="flex: 1; margin-right: 10px;"></span>
    <button type="button" class="hub-btn" id="board-backlog-alert-btn" style="background:#ff4d4f; color:#fff; border:none; padding:4px 8px; font-size:11px; cursor:pointer; border-radius: 3px;">去收卡</button>
  </div>

  <div class="board-main" style="flex: 1; overflow: hidden; display: flex; flex-direction: column;">
    <div class="board-layout" id="board-layout" style="flex: 1; overflow: hidden; display: flex; flex-direction: column;">
      <div class="board-loading" style="display: flex; align-items: center; justify-content: center; height: 100%; color: var(--ccc-text-muted); font-size: 12px;">加载看板中…</div>
    </div>
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
      <button type="button" class="hub-btn" id="board-rd" style="display:none">重新分派</button>
      <button type="button" class="hub-btn" id="board-fp" style="display:none">标误报</button>
      <button type="button" class="hub-btn" id="board-audit" style="display:none">机审</button>
      <button type="button" class="hub-btn" id="board-void" style="display:none">作废</button>
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
    if (_searchQ) {
      const q = _searchQ.trim().toLowerCase();
      const hit = (c.title || '').toLowerCase().includes(q) || (c.id || '').toLowerCase().includes(q) || (c.project || '').toLowerCase().includes(q);
      if (!hit) return false;
    }
    return true;
  });
}

function renderBoard() {
  const host = _root.querySelector('#board-layout');
  if (!host) return;

  const alertBanner = _root.querySelector('#board-backlog-alert-banner');
  if (alertBanner) {
    if (_readyForMergeInfo && _readyForMergeInfo.backlog_alert && _readyForMergeInfo.warning) {
      const msgEl = _root.querySelector('#board-backlog-alert-msg');
      if (msgEl) msgEl.textContent = _readyForMergeInfo.warning;
      alertBanner.style.display = 'flex';
    } else {
      alertBanner.style.display = 'none';
    }
  }

  const filteredCards = getFilteredCards();

  if (!host.querySelector('#board-flow')) {
    host.innerHTML = `
      <div class="board-flow-cols" id="board-flow">
        <!-- 第一竖列：待分派 / 打回 上下各 50% -->
        <div class="board-col-pair">
          ${PAIR_COLS.map(col => `
            <div class="board-half-col" data-col="${esc(col)}">
              <div class="board-col-h">
                <span><span class="board-dot" style="background:${COLORS[col]}"></span>${esc(col)}</span>
                <span class="ct" id="ct-${col}">0</span>
                <button type="button" class="board-col-fold" data-fold-col="${esc(col)}" title="折叠/展开该列">${_colOpen[col] ? '−' : '+'}</button>
              </div>
              <div class="board-col-body" id="col-list-${col}" style="display: ${_colOpen[col] ? 'none' : 'flex'};"></div>
            </div>`).join('')}
        </div>
        <!-- 执行中 / 机审：完整独立栏，卡片下方跟该卡运行信息流 -->
        ${RUN_COLS.map(col => `
          <div class="board-col run-col" data-col="${esc(col)}">
            <div class="board-col-h">
              <span><span class="board-dot" style="background:${COLORS[col]}"></span>${esc(col)}</span>
              <span class="ct" id="ct-${col}">0</span>
              <button type="button" class="board-col-fold" data-fold-col="${esc(col)}" title="折叠/展开该列">${_colOpen[col] ? '−' : '+'}</button>
            </div>
            <div class="board-col-body" id="col-list-${col}" style="display: ${_colOpen[col] ? 'none' : 'flex'};"></div>
          </div>`).join('')}
        <!-- 已回写（待合入） -->
        <div class="board-col" data-col="已回写">
          <div class="board-col-h">
            <span><span class="board-dot" style="background:${COLORS['已回写']}"></span>已回写</span>
            <span class="ct" id="ct-已回写">0</span>
            <button type="button" class="board-col-fold" data-fold-col="已回写" title="折叠/展开该列">${_colOpen['已回写'] ? '−' : '+'}</button>
          </div>
          <div class="board-col-body" id="col-list-已回写" style="display: ${_colOpen['已回写'] ? 'none' : 'flex'};"></div>
        </div>
      </div>
    `;

    _colLists = {};
    for (const col of FLOW_COLS) {
      if (RUN_COLS.includes(col)) continue; // 这两列手动渲染（卡片+运行块）
      const colEl = host.querySelector(`#col-list-${col}`);
      if (colEl) {
        _colLists[col] = new TaskCardList(colEl, {
          itemHeight: _dense ? 92 : 118,
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
    host.querySelectorAll('[data-fold-col]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const col = btn.dataset.foldCol;
        _colOpen[col] = !_colOpen[col];
        renderBoard();
      });
    });
  }

  for (const col of FLOW_COLS) {
    let stateCards = filteredCards.filter(c => {
      const colKey = c.board_column || c.state || c.status || '待分派';
      return colKey === col;
    });
    const countEl = _root.querySelector(`#ct-${col}`);
    if (countEl) countEl.textContent = stateCards.length;

    if (_collapsedCols[col]) {
      continue;
    }

    if (RUN_COLS.includes(col)) {
      _kanbanPageSizes[col] = 3; // 老板 2026-08-12：这两列最多显示 3 张卡，下栏留给信息流
    } else if (!_kanbanPageSizes[col]) {
      _kanbanPageSizes[col] = 30;
    }

    const visibleCards = stateCards.slice(0, _kanbanPageSizes[col]);
    if (RUN_COLS.includes(col)) {
      _colCardIds[col] = visibleCards.map((c) => c.id).filter(Boolean);
      renderRunCol(col, visibleCards);
      continue;
    }

    if (_colLists[col]) {
      _colLists[col].setItems(visibleCards);
    }

    const paginationEl = _root.querySelector(`#col-list-${col} .task-card-list-pagination`);
    if (paginationEl) {
      if (stateCards.length > visibleCards.length && col !== '执行中' && col !== '机审') {
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
          renderBoard();
        });
      } else {
        paginationEl.innerHTML = '';
      }
    }
  }

  updateSummary();
}

function updateSummary() {
  const el = _root.querySelector('#board-st');
  if (!el) return;
  // 人审调整动作统一化：作废卡（终态）与已关闭一样不计入活跃总数
  const total = getFilteredCards().filter((c) => !['已关闭', '作废'].includes(c.board_column || c.state)).length;
  const wsDisplay = _ws === 'all' ? '全部' : (_nameMap[_ws] || _ws);
  el.textContent = wsDisplay + ` · 共 ${total} 张`;
}

/* ── 卡内实时日志流（SSE · 3 行瀑布 · 统一 5 秒刷新）── */

function _streamIds() {
  return [...new Set([...(_colCardIds['执行中'] || []), ...(_colCardIds['机审'] || [])])];
}

function _connectStream() {
  if (!_root) return;
  const ids = _streamIds();
  const sig = ids.join(',');
  if (_es && _esSig === sig) return; // ids 未变：复用连接，不重建（消闪烁/重置）
  if (_es) {
    _es.close();
    _es = null;
  }
  if (!ids.length) return;
  _esSig = sig;
  _es = new EventSource('/tasks/stream?ids=' + encodeURIComponent(ids.join(',')));
  const fillStream = (box, lines) => {
    if (!box) return;
    box.innerHTML = lines.length
      ? lines.map((l) => `<div class="board-stream-line">${esc(l)}</div>`).join('')
      : '<div class="board-card-stream-empty">（暂无日志）</div>';
  };
  _es.addEventListener('snapshot', (e) => {
    try {
      const d = JSON.parse(e.data);
      const box = _root.querySelector(`.board-card-stream[data-stream-id="${CSS.escape(d.work_id)}"] .board-card-stream-lines`);
      const lines = Array.isArray(d.lines) ? d.lines : [];
      _streamCache[d.work_id] = lines.slice(-5);
      fillStream(box, _streamCache[d.work_id]);
    } catch (err) { /* 忽略坏事件 */ }
  });
  _es.addEventListener('log', (e) => {
    try {
      const d = JSON.parse(e.data);
      const box = _root.querySelector(`.board-card-stream[data-stream-id="${CSS.escape(d.work_id)}"] .board-card-stream-lines`);
      if (!box || !d.line) return;
      _streamCache[d.work_id] = [...(_streamCache[d.work_id] || []), d.line].slice(-5);
      const empty = box.querySelector('.board-card-stream-empty');
      if (empty) empty.remove();
      const div = document.createElement('div');
      div.className = 'board-stream-line';
      div.textContent = d.line;
      box.appendChild(div);
      while (box.children.length > 5) box.removeChild(box.firstChild); // 硬性 5 行
    } catch (err) { /* 忽略坏事件 */ }
  });
  _es.onerror = () => {
    if (!_root || !_es) return;
    _root.querySelectorAll('.board-card-stream-lines').forEach((box) => {
      if (!box.querySelector('.board-stream-line')) {
        box.innerHTML = '<div class="board-card-stream-empty">连接中断，重连中…</div>';
      }
    });
  };
}

function renderRunCol(col, cards) {
  const el = _root.querySelector(`#col-list-${col}`);
  if (!el) return;
  const sig = cards.map((c) => [c.id, c.board_column || c.state, c.tool_calls, c.audit_runs, c.audit_status || ''].join(':')).join('|');
  if (sig === _runColSig[col]) return; // 数据未变不重建（消闪烁）
  _runColSig[col] = sig;
  el.innerHTML = cards.length
    ? cards.map((c) => renderTaskCard(c, { stream: true })).join('')
    : '<div class="board-empty">暂无任务</div>';
  // 恢复缓存的中文行：刷新重建后没有新中文输出时，保持显示旧信息（老板 2026-08-12）
  for (const c of cards) {
    const box = el.querySelector(`.board-card-stream[data-stream-id="${CSS.escape(c.id)}"] .board-card-stream-lines`);
    const cached = _streamCache[c.id];
    if (box && cached && cached.length) {
      box.innerHTML = cached.map((l) => `<div class="board-stream-line">${esc(l)}</div>`).join('');
    }
  }
  el.querySelectorAll('.board-task-card').forEach((card) => {
    card.addEventListener('click', (e) => {
      if (e.target.closest('.card-copy-btn')) return;
      showDetail(card.dataset.id);
    });
  });
  el.querySelectorAll('.card-copy-btn').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const id = btn.dataset.id;
      const t = _allCards.find((x) => x.id === id) || { id, title: '' };
      const ok = await copyTextToClipboard(fmtTaskCopy(t, col));
      if (ok) window.showToast?.('已复制任务块，可粘贴到对话', 'success');
      else window.showToast?.('复制失败', 'error');
    });
  });
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
    localStorage.removeItem('ccc_hub_last_project');
  } catch (_) {}
  loadBoard();
}

async function loadConfig() {
  const [data, projData] = await Promise.all([
    apiGet('/board/summaries'),
    apiGet('/projects').catch(() => ({ projects: [] }))
  ]);
  const summaries = (data && data.summaries) || {};
  const projects = (projData && projData.projects) || [];

  _nameMap = {};
  for (const p of projects) {
    if (p.prefix) {
      _nameMap[p.prefix] = p.name;
    }
  }

  const btns = _root.querySelector('#board-ws-btns');
  btns.innerHTML = '';
  _wsNames = Object.keys(summaries).sort();
  const want = preferredWorkspace();
  if (want && summaries[want]) _ws = want;
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
    b.textContent = _nameMap[n] || n;
    b.setAttribute('aria-pressed', n === _ws ? 'true' : 'false');
    btns.appendChild(b);
  }
}

function mergeDirtyFromRunning(cards, runningTasks) {
  const byId = new Map();
  for (const t of runningTasks || []) {
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
  return cards;
}

async function loadBoard() {
  try {
    const project = _ws === 'all' ? '' : _ws;
    const [r, running, ready] = await Promise.all([
      getCards({ project, page_size: 1000 }),
      apiGet('/tasks/running').catch(() => ({ tasks: [] })),
      apiGet('/board/ready_for_merge').catch(() => ({ count: 0 })),
    ]);
    _allCards = mergeDirtyFromRunning(r.cards || [], running.tasks || []);
    _readyForMergeInfo = ready;

    renderBoard();
    refreshAllWsIndicators().catch(() => {});
    _connectStream(); // 5s 刷新统一在这里重建 SSE（上栏卡变化自动跟随）
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
    const rdBtn = _root.querySelector('#board-rd');
    if (rdBtn) {
      const base = String(r.status || r.state || '').split('（')[0].trim();
      rdBtn.style.display = base === '打回' ? 'inline-block' : 'none';
      rdBtn.disabled = false;
    }
    // 人审调整动作统一化：卡作废（终态）——待分派/执行中/已回写/打回 可作废
    const voidBtn = _root.querySelector('#board-void');
    if (voidBtn) {
      const base = String(r.status || r.state || '').split('（')[0].trim();
      voidBtn.style.display = ['待分派', '执行中', '已回写', '打回'].includes(base) ? 'inline-block' : 'none';
      voidBtn.disabled = false;
    }
    // 手动机审节点（流程开发阶段）：已回写（机审列）卡可手动转发去机审
    const auditBtn = _root.querySelector('#board-audit');
    if (auditBtn) {
      const base = String(r.status || r.state || '').split('（')[0].trim();
      auditBtn.style.display = base === '已回写' ? 'inline-block' : 'none';
      auditBtn.disabled = false;
    }
    // 机审命中率台账：打回卡可标「误报」（回填 hit=False）
    const fpBtn = _root.querySelector('#board-fp');
    if (fpBtn) {
      const base = String(r.status || r.state || '').split('（')[0].trim();
      fpBtn.style.display = base === '打回' ? 'inline-block' : 'none';
      fpBtn.disabled = false;
    }
    _root.querySelector('#board-dm').classList.add('open');
  } catch (err) {
    window.showToast?.(err && err.message ? err.message : '加载详情失败', 'error');
  }
}

function bind() {
  const searchEl = _root.querySelector('#board-search');
  if (searchEl) {
    let deb = null;
    searchEl.addEventListener('input', () => {
      clearTimeout(deb);
      deb = setTimeout(() => {
        _searchQ = searchEl.value;
        renderBoard();
      }, 250);
    });
  }
  _root.querySelector('#board-density')?.addEventListener('click', () => {
    _dense = !_dense;
    const btn = _root.querySelector('#board-density');
    if (btn) btn.textContent = _dense ? '舒适' : '紧凑';
    _colLists = {};
    renderBoard();
  });
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

  _root.querySelector('#board-rd').addEventListener('click', async () => {
    const id = _root.querySelector('#board-did').textContent.trim();
    const btn = _root.querySelector('#board-rd');
    if (!id || !btn) return;
    btn.disabled = true;
    try {
      const r = await apiPost('/tasks/' + encodeURIComponent(id) + '/transition', { status: '待分派' });
      window.showToast?.((r && r.id ? `${r.id} 已重新分派 → 待分派（重试计数归零）` : '已重新分派'), 'success');
      _root.querySelector('#board-dm').classList.remove('open');
      await loadBoard();
    } catch (err) {
      window.showToast?.(err && err.message ? err.message : '重新分派失败', 'error');
    } finally {
      btn.disabled = false;
    }
  });

  _root.querySelector('#board-dclose').addEventListener('click', () => {
    _root.querySelector('#board-dm').classList.remove('open');
  });

  // 人审调整动作统一化：卡作废（终态，须附原因）
  _root.querySelector('#board-void').addEventListener('click', async () => {
    const id = _root.querySelector('#board-did').textContent.trim();
    const btn = _root.querySelector('#board-void');
    if (!id || !btn) return;
    const reason = window.prompt('作废原因（必填，终态不可逆）：', '');
    if (reason === null || !reason.trim()) return;
    if (!window.confirm(`确定作废 ${id}？终态不可逆。`)) return;
    btn.disabled = true;
    try {
      const r = await apiPost('/tasks/' + encodeURIComponent(id) + '/transition', { status: '作废', reason: reason.trim() });
      window.showToast?.((r && r.id ? `${r.id} 已作废（${reason.trim()}）` : '已作废'), 'success');
      _root.querySelector('#board-dm').classList.remove('open');
      await loadBoard();
    } catch (err) {
      window.showToast?.(err && err.message ? err.message : '作废失败', 'error');
    } finally {
      btn.disabled = false;
    }
  });

  // 机审命中率台账：老板标打回为误报（hit=False）
  _root.querySelector('#board-fp').addEventListener('click', async () => {
    const id = _root.querySelector('#board-did').textContent.trim();
    const btn = _root.querySelector('#board-fp');
    if (!id || !btn) return;
    if (!window.confirm(`确定将 ${id} 的机审打回标为「误报」？将回填命中率台账为未命中。`)) return;
    btn.disabled = true;
    try {
      await apiPost('/tasks/' + encodeURIComponent(id) + '/false-positive', {});
      window.showToast?.(`${id} 已标误报（台账未命中）`, 'success');
      _root.querySelector('#board-dm').classList.remove('open');
      await loadBoard();
    } catch (err) {
      window.showToast?.(err && err.message ? err.message : '标记失败', 'error');
    } finally {
      btn.disabled = false;
    }
  });

  // 手动机审节点：老板手动把卡转发去机审（流程开发阶段）
  _root.querySelector('#board-audit').addEventListener('click', async () => {
    const id = _root.querySelector('#board-did').textContent.trim();
    const btn = _root.querySelector('#board-audit');
    if (!id || !btn) return;
    const severity = window.prompt('机审 severity（留空=v4自动判定；重=fresh独立agent零上下文）：轻/中/重', '');
    if (severity !== null && severity !== '' && !['轻', '中', '重'].includes(severity)) {
      window.showToast?.('severity 须为 轻/中/重', 'error');
      return;
    }
    btn.disabled = true;
    btn.textContent = '机审中…';
    try {
      const body = severity ? { severity } : {};
      const r = await apiPost('/tasks/' + encodeURIComponent(id) + '/audit', body);
      if (r && r.skipped) {
        window.showToast?.((r.id || id) + ' 已有机审通过证据（force 可强制重审）', 'info');
      } else if (r && r.conclusion) {
        window.showToast?.(`${r.id || id} 机审${r.conclusion}` + (r.problems && r.problems.length ? '：' + r.problems[0] : ''), r.conclusion === '通过' ? 'success' : 'warning');
      } else {
        window.showToast?.(r && r.error ? r.error : '机审完成', 'info');
      }
      _root.querySelector('#board-dm').classList.remove('open');
      await loadBoard();
    } catch (err) {
      window.showToast?.(err && err.message ? err.message : '机审失败', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = '机审';
    }
  });

  const alertBtn = _root.querySelector('#board-backlog-alert-btn');
  if (alertBtn) {
    alertBtn.addEventListener('click', () => {
      location.hash = '#/console';
    });
  }

}

export async function mountBoard(el) {
  const want = preferredWorkspace();

  if (_root) {
    if (want && want !== _ws) {
      _ws = want;
      syncWsButtons();
    }
    await loadBoard();
    if (!_timer) _timer = setInterval(() => loadBoard().catch(() => {}), 5000);
    _connectStream();
    return;
  }
  _root = el;
  if (want) _ws = want;
  el.innerHTML = html();
  bind();
  await loadConfig();
  await loadBoard();
  _timer = setInterval(() => loadBoard().catch(() => {}), 5000);
  _connectStream();
}

export function unmountBoard() {
  if (_timer) {
    clearInterval(_timer);
    _timer = null;
  }
  if (_es) {
    _es.close();
    _es = null;
  }
  _colLists = {};
  _root = null;
}
