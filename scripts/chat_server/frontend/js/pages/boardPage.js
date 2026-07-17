/** Warm-style kanban — epic 待办 sticky 左列 + 流转列；无活动/日志侧栏 */

import { apiGet, apiPost } from '../api.js';
import { epicLifecycleLabel, normalizeEpicSplitStatus } from '../epicLifecycle.js';

export { epicLifecycleLabel, normalizeEpicSplitStatus };

const LABELS = {
  backlog: '待办',
  planned: '已计划',
  in_progress: '开发中',
  testing: '测试/验收',
  verified: '已验证',
  released: '已发布',
  abnormal: '异常',
};
const FLOW_COLS = [
  'planned',
  'in_progress',
  'testing',
  'verified',
  'released',
  'abnormal',
];
const COLORS = {
  backlog: '#a39e93',
  planned: '#c96442',
  in_progress: '#c47a2c',
  testing: '#b86b3a',
  verified: '#3d9a5f',
  released: '#5a7a9a',
  abnormal: '#c44',
};
const NEXT = {
  planned: 'in_progress',
  in_progress: 'testing',
  testing: 'verified',
  verified: 'released',
};
const PREV = {
  planned: '',
  in_progress: 'planned',
  testing: 'in_progress',
  verified: 'testing',
  released: 'verified',
};

let _root = null;
let _timer = null;
let _state = { columns: {}, counts: {} };
let _ws = 'CCC';
let _showHidden = false;
let _wsNames = [];
let _indicatorBusy = false;

function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function taskHue(group, depth) {
  if (!group || group.length !== 1) return null;
  const code = group.charCodeAt(0);
  if (code < 65 || code > 90) return null;
  const hue = ((code - 65) * 360) / 26;
  const lightness = (depth || 0) <= 0 ? 48 : 62;
  return `hsl(${hue.toFixed(1)}, 58%, ${lightness}%)`;
}

/** Epic 五态中文标签 — 实现见 epicLifecycle.js */

function epicChip(ss) {
  const st = normalizeEpicSplitStatus(ss);
  return `<span class="epic-chip epic-chip-${st}">${epicLifecycleLabel(st)}</span>`;
}

function epicGroupBadge(group) {
  if (!group) return '';
  return `<span class="epic-group-badge" title="批次 ${esc(group)}">${esc(group)}</span>`;
}

function epicProgress(t) {
  const kids = t.child_ids || [];
  if (!kids.length) return '';
  const relSet = new Set((_state.columns.released || []).map((x) => x.id));
  const n = kids.filter((id) => relSet.has(id)).length;
  const pct = Math.round((n / kids.length) * 100);
  return `<div class="epic-prog">
    <div class="epic-prog-bar"><i style="width:${pct}%"></i></div>
    <span>${n}/${kids.length} 已发布</span>
  </div>`;
}

function borderFor(t, col) {
  const ss = t.split_status || 'pending';
  if (col === 'backlog') {
    if (ss === 'pending' || !t.color_group) return '#9a958c';
    if (ss === 'failed' || ss === 'blocked') return '#c45c4a';
  }
  const depth = t.color_depth != null ? t.color_depth : col === 'backlog' ? 0 : 1;
  const hsl = taskHue(t.color_group, depth);
  return hsl || COLORS[col] || '#a39e93';
}

function renderEpicCol() {
  const host = _root.querySelector('#board-epic');
  let tasks = _state.columns.backlog || [];
  if (!_showHidden) tasks = tasks.filter((t) => !t.ui_hidden);
  const cards = tasks.length
    ? tasks
        .map((t) => {
          const ss = normalizeEpicSplitStatus(t.split_status || 'pending');
          const border = borderFor({ ...t, split_status: ss }, 'backlog');
          const done = ss === 'done' ? ' epic-done' : '';
          return `<div class="board-card board-card-epic epic-st-${esc(ss)}${done}" data-id="${esc(t.id)}" data-col="backlog" style="border-left-color:${border}">
            <div class="epic-card-top">
              <div class="id">${esc(t.id)}</div>
              ${epicGroupBadge(t.color_group)}
            </div>
            <div class="ti">${esc(t.title)}</div>
            <div class="epic-meta">${epicChip(ss)}</div>
            ${epicProgress(t)}
          </div>`;
        })
        .join('')
    : '<div class="board-empty">暂无大卡</div>';
  host.innerHTML = `<div class="board-col board-col-epic"><div class="board-col-h"><span><span class="board-dot" style="background:${COLORS.backlog}"></span>待办 · 大卡</span><span class="ct">${tasks.length}</span></div><div class="board-col-body">${cards}</div></div>`;
}

function renderFlowCols() {
  const host = _root.querySelector('#board-flow');
  host.innerHTML = '';
  for (const col of FLOW_COLS) {
    let tasks = (_state.columns[col] || []).filter(
      (t) => (t.card_kind || 'work') !== 'epic'
    );
    const d = document.createElement('div');
    d.className = 'board-col';
    const cards = tasks.length
      ? tasks
          .map((t) => {
            const pv = PREV[col] || '';
            const nx = NEXT[col] || '';
            const rn = col === 'in_progress' ? ' running' : '';
            const border = borderFor(t, col);
            const hue = taskHue(t.color_group, 1);
            const dot = hue
              ? `<span class="work-group-dot" style="background:${hue}"></span>`
              : '';
            const parent = t.parent_id
              ? `<div class="parent-tag">${dot}↩ ${esc(t.parent_id)}</div>`
              : '';
            return `<div class="board-card board-card-work${rn}" data-id="${esc(t.id)}" data-col="${col}" data-prev="${pv}" data-next="${nx}" style="border-left-color:${border}">
              <div class="id">${esc(t.id)}</div>
              <div class="ti">${esc(t.title)}</div>
              ${parent}
              <div class="ac">
                ${pv ? '<button type="button" class="mv-prev">←</button>' : ''}
                ${nx ? '<button type="button" class="mv-next">→</button>' : ''}
              </div>
            </div>`;
          })
          .join('')
      : '<div class="board-empty">—</div>';
    d.innerHTML = `<div class="board-col-h"><span><span class="board-dot" style="background:${COLORS[col]}"></span>${LABELS[col]}</span><span class="ct">${tasks.length}</span></div><div class="board-col-body">${cards}</div>`;
    host.appendChild(d);
  }
}

function html() {
  return `
<div class="board-page">
  <div class="board-toolbar">
    <h2>看板</h2>
    <div class="board-toolbar-actions">
      <button type="button" class="primary" id="board-new">+ 新建大卡</button>
      <button type="button" id="board-clean-done" title="隐藏已完成大卡">清理已完成</button>
      <label class="board-toggle"><input type="checkbox" id="board-show-hidden"> 显示已隐藏</label>
    </div>
    <div class="board-ws-btns" id="board-ws-btns" role="group" aria-label="项目"></div>
    <span class="st" id="board-st">·</span>
  </div>
  <div class="board-main">
    <div class="board-layout" id="board-layout">
      <div class="board-epic-col" id="board-epic"></div>
      <div class="board-flow-cols" id="board-flow"></div>
    </div>
  </div>
</div>
<div class="board-modal" id="board-mo">
  <div class="box">
    <h2>新建大卡（待办）</h2>
    <label>ID</label><input id="board-fid" placeholder="epic-id">
    <label>标题</label><input id="board-fti" placeholder="一句话意图">
    <label>描述</label><textarea id="board-fde" placeholder="方案要点 / 给 Claude 拆分的上下文"></textarea>
    <label>看板</label><select id="board-fws"></select>
    <div class="btns">
      <button type="button" id="board-cancel">取消</button>
      <button type="button" class="primary" id="board-mk">创建</button>
    </div>
  </div>
</div>
<div class="board-modal" id="board-dm">
  <div class="box" style="width:520px">
    <h2 id="board-dti">任务详情</h2>
    <div style="font-size:12px;line-height:1.6;max-height:60vh;overflow:auto">
      <div id="board-did" style="font-family:var(--ccc-font-mono);font-size:11px;color:var(--ccc-text-muted)"></div>
      <div id="board-dtt" style="font-weight:500;padding:6px 0"></div>
      <div id="board-dde" style="white-space:pre-wrap;border-top:1px solid var(--ccc-border-subtle);padding-top:6px"></div>
      <div id="board-dmt" style="padding:6px 0;border-top:1px solid var(--ccc-border-subtle);font-size:11px"></div>
      <div id="board-devs"><h3 style="font-size:11px;color:var(--ccc-text-muted)">活动流</h3></div>
    </div>
    <div class="btns" style="margin-top:10px"><button type="button" id="board-dclose">关闭</button></div>
  </div>
</div>`;
}

async function loadConfig() {
  const c = await apiGet('/api/config');
  const btns = _root.querySelector('#board-ws-btns');
  const fs = _root.querySelector('#board-fws');
  btns.innerHTML = '';
  fs.innerHTML = '';
  const spaces = c.workspaces || { CCC: '.' };
  _wsNames = Object.keys(spaces);
  if (!spaces[_ws] && _wsNames.length) _ws = _wsNames[0];
  for (const n of _wsNames) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'board-ws-btn' + (n === _ws ? ' active' : '');
    b.dataset.ws = n;
    b.textContent = n;
    b.setAttribute('aria-pressed', n === _ws ? 'true' : 'false');
    btns.appendChild(b);
    const o2 = document.createElement('option');
    o2.value = n;
    o2.textContent = n;
    fs.appendChild(o2);
  }
}

function setActiveWorkspace(name) {
  if (!name || name === _ws) return;
  _ws = name;
  _root.querySelectorAll('.board-ws-btn').forEach((b) => {
    const on = b.dataset.ws === _ws;
    b.classList.toggle('active', on);
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
  });
  loadBoard();
}

/** 看板指示态：alert（需人工）> running（开发中）> idle */
function classifyWsStatus(payload) {
  const counts = payload.counts || {};
  const abnormal = Number(counts.abnormal || 0);
  const inProg = Number(counts.in_progress || 0);
  const backlog = (payload.columns && payload.columns.backlog) || [];
  const epicFailed = backlog.some((t) => {
    const kind = t.card_kind || 'epic';
    const ss = normalizeEpicSplitStatus(t.split_status || 'pending');
    return kind === 'epic' && ss === 'failed';
  });
  if (abnormal > 0 || epicFailed) {
    const bits = [];
    if (abnormal > 0) bits.push(`异常 ${abnormal}`);
    if (epicFailed) bits.push('大卡失败');
    return { mode: 'alert', title: '需人工介入 · ' + bits.join(' · ') };
  }
  if (inProg > 0) {
    return { mode: 'running', title: `开发中 · ${inProg} 个任务` };
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
    const results = await Promise.all(
      _wsNames.map(async (name) => {
        try {
          const r = await apiGet(
            '/api/board?workspace=' +
              encodeURIComponent(name) +
              '&fields=summary&include_hidden=1'
          );
          return { name, status: classifyWsStatus(r) };
        } catch (_) {
          return { name, status: { mode: 'idle', title: '' } };
        }
      })
    );
    for (const { name, status } of results) {
      const btn = [..._root.querySelectorAll('.board-ws-btn')].find(
        (el) => el.dataset.ws === name
      );
      if (btn) applyWsIndicator(btn, status);
    }
  } finally {
    _indicatorBusy = false;
  }
}

function updateSummary() {
  const epics = (_state.columns.backlog || []).filter((t) => !t.ui_hidden);
  let flow = 0;
  for (const c of ['planned', 'in_progress', 'testing', 'verified']) {
    flow += (_state.columns[c] || []).length;
  }
  _root.querySelector('#board-st').textContent =
    _ws + ` · 待办 ${epics.length} · 流转中 ${flow}`;
}

function renderCols() {
  renderEpicCol();
  renderFlowCols();
  updateSummary();
}

async function loadBoard() {
  const q =
    '/api/board?workspace=' +
    encodeURIComponent(_ws) +
    (_showHidden ? '&include_hidden=1' : '');
  const r = await apiGet(q);
  _state = r;
  renderCols();
  refreshAllWsIndicators().catch(() => {});
}

async function moveTask(id, from, to) {
  if (from === 'backlog') {
    window.showToast?.('待办大卡不可移入流转列', 'error');
    return;
  }
  await apiPost('/api/tasks/move', { id, from, to, workspace: _ws });
  await loadBoard();
}

async function showDetail(id) {
  const r = await apiGet(
    `/api/tasks/${encodeURIComponent(id)}/events?workspace=${encodeURIComponent(_ws)}`
  );
  _root.querySelector('#board-dti').textContent = '任务: ' + r.id;
  _root.querySelector('#board-did').textContent = r.id;
  _root.querySelector('#board-dtt').textContent = r.title || '(无标题)';
  _root.querySelector('#board-dde').textContent = r.description || '(无描述)';
  const st = LABELS[r._column] || r._column || '?';
  const meta = [
    `状态: ${esc(st)}`,
    r.card_kind ? `类型: ${esc(r.card_kind)}` : '',
    r.split_status ? `拆分: ${esc(r.split_status)}` : '',
    r.parent_id ? `父卡: ${esc(r.parent_id)}` : '',
  ]
    .filter(Boolean)
    .join(' · ');
  _root.querySelector('#board-dmt').innerHTML = meta;
  const evBox = _root.querySelector('#board-devs');
  if (r.events && r.events.length) {
    evBox.innerHTML =
      '<h3 style="font-size:11px;color:var(--ccc-text-muted)">活动流</h3>' +
      r.events
        .map(
          (e) =>
            `<div class="board-ev"><span class="t">${(e.timestamp || '').slice(11, 19)}</span><span>${esc(e.from || '?')} → ${esc(e.to || '?')}</span></div>`
        )
        .join('');
  } else {
    evBox.innerHTML =
      '<h3 style="font-size:11px;color:var(--ccc-text-muted)">活动流</h3><div style="color:var(--ccc-text-faint);font-size:11px">无记录</div>';
  }
  _root.querySelector('#board-dm').classList.add('open');
}

function bind() {
  _root.querySelector('#board-ws-btns').addEventListener('click', (e) => {
    const btn = e.target.closest('.board-ws-btn');
    if (!btn) return;
    setActiveWorkspace(btn.dataset.ws);
  });
  _root.querySelector('#board-new').addEventListener('click', () => {
    _root.querySelector('#board-fid').value = 'epic-' + Math.floor(Date.now() / 1000);
    _root.querySelector('#board-fti').value = '';
    _root.querySelector('#board-fde').value = '';
    _root.querySelector('#board-fws').value = _ws;
    _root.querySelector('#board-mo').classList.add('open');
  });
  _root.querySelector('#board-cancel').addEventListener('click', () => {
    _root.querySelector('#board-mo').classList.remove('open');
  });
  _root.querySelector('#board-dclose').addEventListener('click', () => {
    _root.querySelector('#board-dm').classList.remove('open');
  });
  _root.querySelector('#board-show-hidden').addEventListener('change', (e) => {
    _showHidden = !!e.target.checked;
    loadBoard();
  });
  _root.querySelector('#board-clean-done').addEventListener('click', async () => {
    try {
      await apiPost('/api/tasks/hide-completed-epics', { workspace: _ws });
      window.showToast?.('已隐藏完成大卡', 'ok');
      await loadBoard();
    } catch (err) {
      window.showToast?.('清理失败', 'error');
    }
  });
  _root.querySelector('#board-mk').addEventListener('click', async () => {
    const id = _root.querySelector('#board-fid').value.trim();
    const title = _root.querySelector('#board-fti').value.trim();
    const description = _root.querySelector('#board-fde').value.trim();
    const workspace = _root.querySelector('#board-fws').value;
    if (!id || !title) {
      window.showToast?.('ID 和标题必填', 'error');
      return;
    }
    await apiPost('/api/tasks', {
      id,
      title,
      description,
      workspace,
      status: 'backlog',
      card_kind: 'epic',
      split_status: 'pending',
    });
    _root.querySelector('#board-mo').classList.remove('open');
    await loadBoard();
  });
  _root.querySelector('#board-layout').addEventListener('click', (e) => {
    const btn = e.target.closest('.mv-prev, .mv-next');
    const card = e.target.closest('.board-card');
    if (!card) return;
    if (btn) {
      e.stopPropagation();
      const target = btn.classList.contains('mv-prev')
        ? card.dataset.prev
        : card.dataset.next;
      if (target) moveTask(card.dataset.id, card.dataset.col, target);
    } else {
      showDetail(card.dataset.id);
    }
  });
}

export async function mountBoard(el) {
  if (_root) {
    await loadBoard();
    if (!_timer) _timer = setInterval(() => loadBoard().catch(() => {}), 5000);
    return;
  }
  _root = el;
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
}
