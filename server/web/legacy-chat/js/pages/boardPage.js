/**
 * boardPage.js — 看板页（T30：新协议版）
 * T56: 改接 cardApi + TaskCard* 统一数据层及组件层。
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
import { fmtTaskCopy } from '../components/taskCard.js';

/** 契约 §2 五态（与 server/board/models.py STATES 对齐）。 */
const FLOW_COLS = ['待分派', '执行中', '已回写', '已关闭', '打回'];
const COLORS = {
  待分派: '#a39e93',
  执行中: '#c47a2c',
  已回写: '#3d9a5f',
  已关闭: '#5a7a9a',
  打回: '#c44',
};

let _root = null;
let _timer = null;
let _state = { columns: {}, counts: {} };
let _ws = 'all';
let _wsNames = [];
let _indicatorBusy = false;
let _filterQ = '';
let _filterDebounce = null;
let _colLists = {}; // Map of state -> TaskCardList instance

function esc(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function matchesKeyword(t, q) {
  if (!q) return true;
  const hay = [t.id, t.title, t.executor, t.status, t.note].filter(Boolean).join(' ');
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

function html() {
  return `
<div class="board-page hub-page">
  <div class="orch-hint">看板 · 走新服务端协议（/board/snapshot）。2017 单端 :7788 四视图。</div>
  <div class="board-toolbar">
    <h2>看板</h2>
    <div class="board-toolbar-actions">
      <button type="button" class="hub-btn" id="board-refresh" title="刷新">刷新</button>
      <span class="board-write-hint" title="写操作请用桌面端">读视图 · 写操作请用桌面端</span>
    </div>
    <div class="board-ws-btns" id="board-ws-btns" role="group" aria-label="项目"></div>
    <span class="st" id="board-st">·</span>
  </div>
  <div class="board-toolbar-filters">
    <input type="search" id="board-filter-q" class="board-filter-input" placeholder="筛选关键词（标题/ID/执行体）" aria-label="筛选关键词">
  </div>
  <div class="board-main">
    <div class="board-layout" id="board-layout">
      <div class="board-flow-cols" id="board-flow" style="display: grid; grid-auto-columns: minmax(220px, 1fr); grid-auto-flow: column; gap: 10px; height: 100%; overflow-x: auto; padding: 10px 0;"></div>
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
      <button type="button" class="hub-btn" id="board-dclose">关闭</button>
    </div>
  </div>
</div>`;
}

function _viewTasks(col) {
  let tasks = _state.columns[col] || [];
  if (_filterQ) tasks = tasks.filter((t) => matchesKeyword(t, _filterQ));
  return tasks;
}

function renderCols() {
  const host = _root.querySelector('#board-flow');
  if (!host) return;

  if (host.innerHTML === '') {
    // Build initial column frames
    host.innerHTML = FLOW_COLS.map(col => `
      <div class="board-col" style="display: flex; flex-direction: column; background: var(--ccc-bg-layer); border: 1px solid var(--ccc-border-subtle); border-radius: var(--ccc-radius-sm); overflow: hidden; height: 100%;">
        <div class="board-col-h">
          <span><span class="board-dot" style="background:${COLORS[col]}"></span>${esc(col)}</span>
          <span class="ct" id="ct-${col}">0</span>
        </div>
        <div class="board-col-body" id="col-list-${col}" style="display: flex; flex-direction: column; overflow: hidden; flex: 1; min-height: 200px; padding: 6px; gap: 4px;"></div>
      </div>
    `).join('');

    // Instantiate TaskCardList for each column
    for (const col of FLOW_COLS) {
      const colEl = _root.querySelector(`#col-list-${col}`);
      if (colEl) {
        _colLists[col] = new TaskCardList(colEl, {
          onCardClick: (card, id) => {
            showDetail(id);
          },
          onCopyClick: async (btn, id) => {
            const t = (_state.columns[col] || []).find((x) => x.id === id) || { id, title: '' };
            const ok = await copyTextToClipboard(fmtTaskCopy(t, col));
            if (ok) {
              window.showToast?.('已复制任务块，可粘贴到对话', 'success');
            } else {
              window.showToast?.('复制失败：请长按选中后手动复制', 'error');
            }
          }
        });
        // Enable virtual scrolling for extremely large lists
        _colLists[col].enableVirtualScroll(true);
      }
    }
  }

  // Update items in each column list
  for (const col of FLOW_COLS) {
    const tasks = _viewTasks(col);
    const countEl = _root.querySelector(`#ct-${col}`);
    if (countEl) countEl.textContent = tasks.length;

    if (_colLists[col]) {
      _colLists[col].setItems(tasks);
    }
  }

  updateSummary();
}

function updateSummary() {
  const el = _root.querySelector('#board-st');
  if (!el) return;
  const counts = _state.counts || {};
  const total = FLOW_COLS.reduce((s, c) => s + Number(counts[c] || 0), 0);
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
  // 全部项目按钮
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

async function loadBoard() {
  try {
    const project = _ws === 'all' ? '' : _ws;
    const r = await getCards({ project, page_size: 1000 });
    const cards = r.cards || [];

    // Build columns & counts map
    const columns = { '待分派': [], '执行中': [], '已回写': [], '已关闭': [], '打回': [] };
    const counts = { '待分派': 0, '执行中': 0, '已回写': 0, '已关闭': 0, '打回': 0 };

    for (const c of cards) {
      const st = c.state || c.status || '待分派';
      if (columns[st] !== undefined) {
        columns[st].push(c);
        counts[st]++;
      }
    }

    _state = { columns, counts };
    renderCols();
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
    qInput.addEventListener('input', () => {
      clearTimeout(_filterDebounce);
      _filterDebounce = setTimeout(() => {
        _filterQ = qInput.value.trim();
        renderCols();
      }, 150);
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
    if (!_timer) _timer = setInterval(() => loadBoard().catch(() => {}), 15000);
    return;
  }
  _root = el;
  if (want) _ws = want;
  el.innerHTML = html();
  bind();
  await loadConfig();
  await loadBoard();
  _timer = setInterval(() => loadBoard().catch(() => {}), 15000);
}

export function unmountBoard() {
  if (_timer) {
    clearInterval(_timer);
    _timer = null;
  }
  _colLists = {};
}
