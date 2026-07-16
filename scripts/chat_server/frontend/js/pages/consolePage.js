/** Warm-style console (KPI) for CCC Hub (#/console) */

import { apiGet, apiPost } from '../api.js';

let _root = null;
let _timer = null;
let _ws = 'all';

function esc(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function html() {
  return `
<div class="console-page">
  <div class="console-bar">
    <h2>控制台</h2>
    <button type="button" class="hub-btn" id="console-ws">工作区: <span id="console-ws-label">全部</span></button>
    <span style="flex:1"></span>
    <button type="button" class="hub-btn primary" id="console-to-board">打开看板</button>
  </div>
  <div class="console-kpi" id="console-kpi">
    <div class="console-kw"><div class="label">加载中…</div></div>
  </div>
  <div class="console-section">
    <h3>进行中 <span class="badge" id="console-active-n">0</span></h3>
    <div class="console-tasks" id="console-active"></div>
  </div>
  <div class="console-section">
    <h3>需关注 <span class="badge" id="console-abn-n">0</span></h3>
    <div class="console-tasks" id="console-abn"></div>
  </div>
  <div class="console-section">
    <h3>最近失败 <span class="badge" id="console-fail-n">0</span></h3>
    <div class="console-feed" id="console-fail"></div>
  </div>
  <div class="console-section">
    <h3>今日动态 <span class="badge" id="console-ev-n">0</span></h3>
    <div class="console-feed" id="console-feed"></div>
  </div>
</div>`;
}

function renderKPI(d) {
  const kpi = d.kpi || {};
  const keys = [
    { k: 'in_progress', label: '开发中', desc: '正在跑的任务' },
    { k: 'testing', label: '测试/验收', desc: '等待审查/验收' },
    { k: 'abnormal', label: '异常', desc: '卡住需介入' },
    { k: 'released_today', label: '今日发布', desc: '已归档' },
  ];
  const box = _root.querySelector('#console-kpi');
  box.innerHTML = keys
    .map((item) => {
      const v = kpi[item.k] ?? d.counts?.[item.k] ?? 0;
      return `<div class="console-kw"><div class="label">${item.label}</div><div class="big">${esc(v)}</div><div class="desc">${item.desc}</div></div>`;
    })
    .join('');
}

function renderActive(tasks) {
  const el = _root.querySelector('#console-active');
  _root.querySelector('#console-active-n').textContent = String(tasks.length);
  if (!tasks.length) {
    el.innerHTML = '<div class="console-empty">当前没有进行中的任务</div>';
    return;
  }
  el.innerHTML = tasks
    .map(
      (t) => `<div class="console-tc">
      <div class="title">${esc(t.title || t.id)}</div>
      <div class="id">${esc(t.id)} · ${esc(t.workspace || '')} · ${esc(t.status || t.column || '')}</div>
    </div>`
    )
    .join('');
}

function renderAbn(tasks) {
  const el = _root.querySelector('#console-abn');
  _root.querySelector('#console-abn-n').textContent = String(tasks.length);
  if (!tasks.length) {
    el.innerHTML = '<div class="console-empty">没有异常任务</div>';
    return;
  }
  el.innerHTML = tasks
    .map(
      (t) => `<div class="console-tc" style="border-left-color:#c44">
      <div class="title">⚠ ${esc(t.title || t.id)}</div>
      <div class="id">${esc(t.id)}</div>
      <div style="font-size:12px;margin-top:8px;color:var(--ccc-text-secondary)">${esc(t.human_reason || t.reason || '卡住')}</div>
    </div>`
    )
    .join('');
}

function renderEvents(events) {
  const el = _root.querySelector('#console-feed');
  _root.querySelector('#console-ev-n').textContent = String(events.length);
  if (!events.length) {
    el.innerHTML = '<div class="console-empty">今天还没有动态</div>';
    return;
  }
  el.innerHTML = events
    .slice(0, 30)
    .map(
      (e) => `<div class="row">
      <span class="time">${esc(e.time || '')}</span>
      <span><b>${esc(e.task_title || e.task_id || '')}</b> ${esc(e.action_cn || e.to_column || '')}</span>
    </div>`
    )
    .join('');
}

function renderFailures(rows) {
  const el = _root.querySelector('#console-fail');
  const n = _root.querySelector('#console-fail-n');
  if (!el || !n) return;
  n.textContent = String(rows.length);
  if (!rows.length) {
    el.innerHTML = '<div class="console-empty">暂无失败账本记录</div>';
    return;
  }
  el.innerHTML = rows
    .slice()
    .reverse()
    .slice(0, 15)
    .map(
      (f) => `<div class="row console-fail-row" data-tid="${esc(f.task_id || '')}">
      <span class="time">${esc((f.ts || '').replace('T', ' ').slice(0, 16))}</span>
      <span><b>${esc(f.task_id || '')}</b> · ${esc(f.role || '')} · ${esc(f.reason || '')}</span>
      ${f.task_id ? '<button type="button" class="console-reopen-btn" data-tid="' + esc(f.task_id) + '">重开</button>' : ''}
    </div>`
    )
    .join('');
  el.querySelectorAll('.console-reopen-btn').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const tid = btn.getAttribute('data-tid');
      if (!tid) return;
      btn.disabled = true;
      try {
        const wsFail = _ws === 'all' ? 'CCC' : _ws;
        await apiPost('/api/tasks/reopen', { id: tid, workspace: wsFail, to: 'planned' });
        window.showToast?.('已重开 ' + tid + ' → planned', 'success');
        await poll();
      } catch (err) {
        window.showToast?.(err.message || '重开失败', 'error');
        btn.disabled = false;
      }
    });
  });
}

async function poll() {
  const r = await apiGet('/api/dashboard?workspace=' + encodeURIComponent(_ws));
  renderKPI(r);
  renderActive(r.active_tasks || []);
  renderAbn(r.abnormal_tasks || []);
  renderEvents(r.today_events || []);
  try {
    const wsFail = _ws === 'all' ? 'CCC' : _ws;
    const fr = await apiGet(
      '/api/failures?last=15&workspace=' + encodeURIComponent(wsFail)
    );
    renderFailures(fr.failures || []);
  } catch (_) {
    renderFailures([]);
  }
  const label = _root.querySelector('#console-ws-label');
  if (label) label.textContent = _ws === 'all' ? '全部' : _ws;
}

export async function mountConsole(el) {
  if (!_root) {
    _root = el;
    el.innerHTML = html();
    _root.querySelector('#console-to-board').addEventListener('click', () => {
      location.hash = '#/board';
    });
    _root.querySelector('#console-ws').addEventListener('click', async () => {
      try {
        const c = await apiGet('/api/config');
        const keys = ['all', ...Object.keys(c.workspaces || {})];
        const idx = keys.indexOf(_ws);
        _ws = keys[(idx + 1) % keys.length];
        await poll();
      } catch (_) {
        /* ignore */
      }
    });
  }
  await poll();
  if (!_timer) _timer = setInterval(() => poll().catch(() => {}), 5000);
}

export function unmountConsole() {
  if (_timer) {
    clearInterval(_timer);
    _timer = null;
  }
}
