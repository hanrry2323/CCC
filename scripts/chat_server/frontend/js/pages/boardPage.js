/** Warm-style kanban page for CCC Hub (#/board) */

import { apiGet, apiPost } from '../api.js';

const LABELS = {
  backlog: '待办',
  planned: '已计划',
  in_progress: '开发中',
  testing: '测试中',
  verified: '已验证',
  released: '已发布',
  abnormal: '异常',
};
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
  backlog: 'planned',
  planned: 'in_progress',
  in_progress: 'testing',
  testing: 'verified',
  verified: 'released',
};
const PREV = {
  planned: 'backlog',
  in_progress: 'planned',
  testing: 'in_progress',
  verified: 'testing',
  released: 'verified',
};

let _root = null;
let _timer = null;
let _state = { columns: {}, counts: {} };
let _ws = 'CCC';

function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function html() {
  return `
<div class="board-page">
  <div class="board-toolbar">
    <h2>看板</h2>
    <select id="board-ws"></select>
    <button type="button" class="primary" id="board-new">+ 新建</button>
    <span class="st" id="board-st">·</span>
  </div>
  <div class="board-roles" id="board-roles"></div>
  <div class="board-main">
    <div class="board-cols" id="board-cols"></div>
    <div class="board-side">
      <div class="board-tl" id="board-tl"><h3>活动</h3></div>
      <div class="board-logs" id="board-logs"><h3>日志</h3></div>
    </div>
  </div>
</div>
<div class="board-modal" id="board-mo">
  <div class="box">
    <h2>新建任务</h2>
    <label>ID</label><input id="board-fid" placeholder="task-id">
    <label>标题</label><input id="board-fti" placeholder="一句话描述">
    <label>描述</label><textarea id="board-fde" placeholder="详情"></textarea>
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
  const sel = _root.querySelector('#board-ws');
  const fs = _root.querySelector('#board-fws');
  sel.innerHTML = '';
  fs.innerHTML = '';
  const spaces = c.workspaces || { CCC: '.' };
  for (const n of Object.keys(spaces)) {
    const o = document.createElement('option');
    o.value = n;
    o.textContent = n;
    sel.appendChild(o);
    const o2 = document.createElement('option');
    o2.value = n;
    o2.textContent = n;
    fs.appendChild(o2);
  }
  if (spaces[_ws]) sel.value = _ws;
  else _ws = sel.value || 'CCC';
}

async function loadBoard() {
  _ws = _root.querySelector('#board-ws').value || 'CCC';
  const r = await apiGet('/api/board?workspace=' + encodeURIComponent(_ws));
  _state = r;
  const total = Object.values(r.counts || {}).reduce((a, b) => a + b, 0);
  _root.querySelector('#board-st').textContent = _ws + ' · ' + total + ' 个';
  renderCols();
  loadRoles();
  loadTL();
  loadLogs();
}

function renderCols() {
  const bb = _root.querySelector('#board-cols');
  const cols = Object.keys(_state.columns || {});
  bb.innerHTML = '';
  for (const col of cols) {
    const tasks = _state.columns[col] || [];
    const d = document.createElement('div');
    d.className = 'board-col';
    const cards = tasks.length
      ? tasks
          .map((t) => {
            const pv = PREV[col] || '';
            const nx = NEXT[col] || '';
            const rn = col === 'in_progress' ? ' running' : '';
            return `<div class="board-card${rn}" data-id="${esc(t.id)}" data-col="${col}" data-prev="${pv}" data-next="${nx}" style="border-left-color:${COLORS[col] || '#a39e93'}">
              <div class="id">${esc(t.id)}</div>
              <div class="ti">${esc(t.title)}</div>
              <div class="ac">
                ${pv ? '<button type="button" class="mv-prev">←</button>' : ''}
                ${nx ? '<button type="button" class="mv-next">→</button>' : ''}
              </div>
            </div>`;
          })
          .join('')
      : '<div style="text-align:center;color:var(--ccc-text-faint);font-size:11px;padding:16px">—</div>';
    d.innerHTML = `<div class="board-col-h"><span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${COLORS[col] || '#a39e93'};margin-right:6px"></span>${LABELS[col] || col}</span><span class="ct">${tasks.length}</span></div><div class="board-col-body">${cards}</div>`;
    bb.appendChild(d);
  }
}

async function loadRoles() {
  try {
    const r = await apiGet('/api/roles');
    const b = _root.querySelector('#board-roles');
    if (!r || !r.roles) {
      b.innerHTML = '';
      return;
    }
    b.innerHTML = r.roles
      .map((role) => {
        const s = role.status || 'idle';
        const tm = role.last_run ? role.last_run.slice(11, 19) : '--:--:--';
        return `<div class="board-role"><span class="dot ${esc(s)}"></span>${esc((role.role || '').toUpperCase())}<span style="margin-left:auto;font-family:var(--ccc-font-mono);font-size:10px;color:var(--ccc-text-muted)">${tm}</span></div>`;
      })
      .join('');
  } catch (_) {
    /* roles optional */
  }
}

async function loadTL() {
  try {
    const r = await apiGet('/api/timeline?workspace=' + encodeURIComponent(_ws));
    const b = _root.querySelector('#board-tl');
    const events = (r && r.events) || [];
    b.innerHTML =
      '<h3>活动</h3>' +
      events
        .slice(0, 20)
        .map((e) => {
          if (e.type === 'role_run') {
            const ok = e.exit_code === '0';
            return `<div class="board-ev"><span class="t">${(e.time || '').slice(11, 19)}</span><span>${ok ? '✓' : '✗'} ${(e.role || '').toUpperCase()}</span></div>`;
          }
          return `<div class="board-ev"><span class="t">${(e.time || '').slice(11, 19)}</span><span>→ ${esc(e.task_id || '')}</span></div>`;
        })
        .join('');
  } catch (_) {
    /* optional */
  }
}

async function loadLogs() {
  try {
    const r = await apiGet('/api/logs?workspace=' + encodeURIComponent(_ws));
    const b = _root.querySelector('#board-logs');
    const logs = (r && r.logs) || [];
    b.innerHTML =
      '<h3>日志</h3>' +
      logs
        .slice(0, 25)
        .map(
          (l) =>
            `<div class="board-lg"><span class="t">${(l.mtime || '').slice(11, 19)}</span><span>${esc((l.role || '').toUpperCase())} · ${l.exit_code || '?'}</span></div>`
        )
        .join('');
  } catch (_) {
    /* optional */
  }
}

async function moveTask(id, from, to) {
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
  _root.querySelector('#board-dmt').innerHTML =
    `<span style="color:var(--ccc-text-muted)">状态:</span> ${esc(st)}`;
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
  _root.querySelector('#board-ws').addEventListener('change', () => loadBoard());
  _root.querySelector('#board-new').addEventListener('click', () => {
    _root.querySelector('#board-fid').value = 'task-' + Math.floor(Date.now() / 1000);
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
  _root.querySelector('#board-mk').addEventListener('click', async () => {
    const id = _root.querySelector('#board-fid').value.trim();
    const title = _root.querySelector('#board-fti').value.trim();
    const description = _root.querySelector('#board-fde').value.trim();
    const workspace = _root.querySelector('#board-fws').value;
    if (!id || !title) {
      window.showToast?.('ID 和标题必填', 'error');
      return;
    }
    await apiPost('/api/tasks', { id, title, description, workspace, status: 'backlog' });
    _root.querySelector('#board-mo').classList.remove('open');
    await loadBoard();
  });
  _root.querySelector('#board-cols').addEventListener('click', (e) => {
    const btn = e.target.closest('.mv-prev, .mv-next');
    const card = e.target.closest('.board-card');
    if (!card) return;
    if (btn) {
      e.stopPropagation();
      const target = btn.classList.contains('mv-prev') ? card.dataset.prev : card.dataset.next;
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
