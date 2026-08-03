/**
 * boardPage.js — 看板页（T30：新协议版）
 *
 * 数据源（全部走新服务端）：
 *   - 项目列表：GET /board/summaries（无参 → 全部项目各自一个 snapshot）
 *   - 单项目看板：GET /board/snapshot?workspace=X
 *     返回 {columns: {状态: [BoardTask]}, counts: {...}, workspace}
 *   - 多项目指标：GET /board/summaries?workspaces=a,b,c
 *   - 卡详情：GET /tasks/{id}（不含 events；events 字段为 []）
 *
 * 写操作（移卡/建卡/清理）已禁用：服务端不暴露；请在桌面端或编排口操作。
 *
 * 状态命名：契约 §2 五态（中文）：待分派 / 执行中 / 已回写 / 已关闭 / 打回。
 */

import { apiGet } from '../api.js';
import { dialogueEntryUrl } from '../ports.js';

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

function fmtTaskCopy(t, col) {
  const lines = [
    '<<<CCC_TASK>>>',
    'id: ' + (t.id || ''),
    'workspace: ' + _ws,
    'column: ' + (col || t.status || ''),
    'kind: ' + (t.card_kind || 'work'),
    'title: ' + (t.title || ''),
  ];
  if (t.parent_id) lines.push('parent: ' + t.parent_id);
  if (t.split_status) lines.push('split_status: ' + t.split_status);
  if (t.note) lines.push('note: ' + t.note);
  if (Array.isArray(t.phases) && t.phases.length) {
    lines.push('phases: ' + t.phases.join(', '));
  }
  lines.push('<<<END_CCC_TASK>>>');
  lines.push('（请围绕上述任务与我讨论：现状、风险、下一步）');
  return lines.join('\n');
}

function copyBtnHtml() {
  return (
    '<button type="button" class="card-copy-btn" title="复制任务信息到对话" aria-label="复制任务">' +
    '<span class="card-copy-ico" aria-hidden="true">⧉</span>' +
    '<span class="card-copy-txt">复制</span>' +
    '</button>'
  );
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

async function copyCardTask(card) {
  if (!card) return;
  const id = card.dataset.id;
  const col = card.dataset.col;
  const t = (_state.columns[col] || []).find((x) => x.id === id) || { id, title: '' };
  const ok = await copyTextToClipboard(fmtTaskCopy(t, col));
  if (ok) {
    window.showToast?.('已复制任务块，可粘贴到对话', 'success');
    card.classList.add('just-copied');
    setTimeout(() => card.classList.remove('just-copied'), 600);
  } else {
    window.showToast?.('复制失败：请长按选中后手动复制', 'error');
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
  <div class="orch-hint">看板 · 走新服务端协议（/board/snapshot）。对话请开 <a href="${dialogueEntryUrl()}">M1 :7788</a></div>
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
      <div class="board-flow-cols" id="board-flow"></div>
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
      <div id="board-dde" style="white-space:pre-wrap;border-top:1px solid var(--ccc-border-subtle);padding-top:6px"></div>
      <div id="board-dacc" style="border-top:1px solid var(--ccc-border-subtle);padding-top:6px;margin-top:6px"></div>
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

function _buildFlowCol(col) {
  const tasks = _viewTasks(col);
  const d = document.createElement('div');
  d.className = 'board-col';
  const cards = tasks.length
    ? tasks
        .map((t) => {
          const border = COLORS[col] || '#a39e93';
          const exec = t.executor ? `<div class="parent-tag">执行体: ${esc(t.executor)}</div>` : '';
          const idLine = `<div class="id">${esc(t.id)}</div>`;
          const ti = `<div class="ti">${esc(t.title)}</div>`;
          return `<div class="board-card board-card-work" data-id="${esc(t.id)}" data-col="${esc(col)}" style="border-left-color:${border}">
            ${idLine}
            ${ti}
            ${exec}
            ${copyBtnHtml()}
          </div>`;
        })
        .join('')
    : '<div class="board-empty">—</div>';
  d.innerHTML = `<div class="board-col-h"><span><span class="board-dot" style="background:${COLORS[col]}"></span>${esc(col)}</span><span class="ct">${tasks.length}</span></div><div class="board-col-body">${cards}</div>`;
  return d;
}

function renderFlowCols() {
  const host = _root.querySelector('#board-flow');
  if (!host) return;
  const newSigs = {};
  for (const col of FLOW_COLS) {
    const tasks = _viewTasks(col);
    newSigs[col] = tasks.map((t) => t.id + ':' + (t.updated_at || '')).join('|');
  }
  const existingCols = host.querySelectorAll('.board-col');
  if (existingCols.length !== FLOW_COLS.length) {
    host.innerHTML = '';
    for (const col of FLOW_COLS) host.appendChild(_buildFlowCol(col));
    host.dataset.sigs = JSON.stringify(newSigs);
    return;
  }
  let prevSigs = {};
  try { prevSigs = JSON.parse(host.dataset.sigs || '{}'); } catch (_) {}
  for (let i = 0; i < FLOW_COLS.length; i++) {
    const col = FLOW_COLS[i];
    if (prevSigs[col] !== newSigs[col]) {
      const oldEl = existingCols[i];
      const oldBody = oldEl.querySelector('.board-col-body');
      const scrollTop = oldBody ? oldBody.scrollTop : 0;
      const newEl = _buildFlowCol(col);
      oldEl.replaceWith(newEl);
      const newBody = newEl.querySelector('.board-col-body');
      if (newBody && scrollTop) newBody.scrollTop = scrollTop;
    }
  }
  host.dataset.sigs = JSON.stringify(newSigs);
}

function updateSummary() {
  const el = _root.querySelector('#board-st');
  if (!el) return;
  const counts = _state.counts || {};
  const total = FLOW_COLS.reduce((s, c) => s + Number(counts[c] || 0), 0);
  el.textContent = _ws + ` · 共 ${total} 张`;
}

function renderCols() {
  renderFlowCols();
  updateSummary();
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
  // T30：项目列表来自 /board/summaries（无参 → 全部项目各自一个 snapshot）
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
  const qs = _ws === 'all' ? '' : ('?workspace=' + encodeURIComponent(_ws));
  try {
    const r = await apiGet('/board/snapshot' + qs);
    _state = r || { columns: {}, counts: {} };
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
    _root.querySelector('#board-dde').textContent = r.note || '(无描述)';
    const accEl = _root.querySelector('#board-dacc');
    if (r.acceptance) {
      accEl.innerHTML = '<h3 style="font-size:11px;color:var(--ccc-text-muted)">验收标准</h3><div style="white-space:pre-wrap;font-size:12px">' + esc(r.acceptance) + '</div>';
    } else {
      accEl.innerHTML = '';
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
  _root.querySelector('#board-layout').addEventListener('click', (e) => {
    const copyBtn = e.target.closest('.card-copy-btn');
    if (copyBtn) {
      e.stopPropagation();
      e.preventDefault();
      const card = copyBtn.closest('.board-card');
      copyCardTask(card);
      return;
    }
    const card = e.target.closest('.board-card');
    if (card) {
      showDetail(card.dataset.id);
    }
  });
  _root.querySelector('#board-layout').addEventListener(
    'pointerdown',
    (e) => {
      const copyBtn = e.target.closest('.card-copy-btn');
      if (!copyBtn) return;
      e.stopPropagation();
    },
    true
  );
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
}
