/**
 * consolePage.js — 控制台（T30：新协议版）
 *
 * 数据源（全部走新服务端）：
 *   - 状态计数 KPI：GET /board/states → {状态: count}
 *   - 活动/异常任务：GET /board/snapshot?workspace=X → {columns: {状态: [tasks]}}
 *   - 运维告警数：GET /ops/summary → overview.alert_count
 *   - 项目列表：GET /board/summaries → {summaries: {项目: snapshot}}
 *
 * 旧字段（today_events / failures / risks / dashboard）服务端不暴露；
 *   对应区块改为占位提示「需 SSH / 桌面端查看」。
 *
 * 写操作（reopen / move / create）已禁用：服务端不暴露。
 */

import { apiGet } from '../api.js';

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
<div class="console-page hub-page">
  <div class="console-banner">
    控制台为简化看板；详细运维请用 <strong>桌面端</strong> 或 <a href="#/ops">运维页</a>。
  </div>
  <div class="console-bar">
    <h2>控制台</h2>
    <button type="button" class="hub-btn" id="console-ws">工作区: <span id="console-ws-label">全部</span></button>
    <a class="hub-btn" href="#/ops" id="console-ops-link">运维告警 <span class="badge" id="console-ops-n">0</span></a>
    <span style="flex:1"></span>
    <button type="button" class="hub-btn primary" id="console-to-board">打开看板</button>
  </div>
  <div class="console-kpi" id="console-kpi">
    <div class="console-kw"><div class="label">加载中…</div></div>
  </div>
  <div class="console-section">
    <h3>执行中 <span class="badge" id="console-active-n">0</span></h3>
    <div class="console-tasks" id="console-active"></div>
  </div>
  <div class="console-section">
    <h3>打回 <span class="badge" id="console-abn-n">0</span></h3>
    <div class="console-tasks" id="console-abn"></div>
  </div>
  <div class="console-section">
    <h3>最近失败 / 今日动态</h3>
    <div class="console-feed">
      <p class="ops-hint">旧 <code>/api/failures</code> / <code>/api/dashboard</code> 端点已下线。请用桌面端失败账本（<code>ccc-failure-report.py</code>）或 SSH 查 <code>~/.ccc/stats/failures.jsonl</code>。</p>
    </div>
  </div>
</div>`;
}

function renderKPI(counts) {
  const c = counts || {};
  const values = [
    { k: '待分派', label: '待分派', desc: '尚未执行' },
    { k: '执行中', label: '执行中', desc: '正在跑' },
    { k: '已回写', label: '已回写', desc: '待验收' },
    { k: '已关闭', label: '已关闭', desc: '已归档' },
    { k: '打回', label: '打回', desc: '需介入' },
  ];
  const box = _root.querySelector('#console-kpi');
  if (!box) return;
  box.innerHTML = values
    .map((item) => {
      const v = Number(c[item.k] || 0);
      return `<div class="console-kw"><div class="label">${esc(item.label)}</div><div class="big">${v}</div><div class="desc">${esc(item.desc)}</div></div>`;
    })
    .join('');
}

function renderTasks(elId, badgeId, tasks, opts = {}) {
  const el = _root.querySelector(elId);
  const nEl = _root.querySelector(badgeId);
  if (nEl) nEl.textContent = String(tasks.length);
  if (!el) return;
  if (!tasks.length) {
    el.innerHTML = '<div class="console-empty">' + (opts.empty || '无') + '</div>';
    return;
  }
  el.innerHTML = tasks
    .map(
      (t) => `<div class="console-tc" style="${opts.border ? 'border-left-color:' + opts.border : ''}">
        <div class="title">${opts.prefix || ''}${esc(t.title || t.id)}</div>
        <div class="id">${esc(t.id)} · ${esc(t.executor || '')} · ${esc(t.status || '')}</div>
      </div>`
    )
    .join('');
}

async function poll() {
  try {
    const wsQs = _ws === 'all' ? '' : ('?workspace=' + encodeURIComponent(_ws));
    const snap = await apiGet('/board/snapshot' + wsQs);
    const counts = snap.counts || {};
    const columns = snap.columns || {};
    renderKPI(counts);
    renderTasks('#console-active', '#console-active-n', columns['执行中'] || [], { empty: '当前无执行中任务' });
    renderTasks('#console-abn', '#console-abn-n', columns['打回'] || [], { border: '#c44', prefix: '⚠ ', empty: '无打回任务' });
  } catch (err) {
    const box = _root.querySelector('#console-kpi');
    if (box) box.innerHTML = `<div class="console-empty">加载失败: ${esc(err?.message || String(err))}</div>`;
  }
  // 运维告警数（来自 /ops/summary）
  try {
    const agg = await apiGet('/ops/summary');
    const badge = _root.querySelector('#console-ops-n');
    if (badge) {
      const alertCount = (agg.overview && agg.overview.alert_count) || 0;
      badge.textContent = String(alertCount);
    }
  } catch (_) { /* ops optional */ }
  const label = _root.querySelector('#console-ws-label');
  if (label) label.textContent = _ws === 'all' ? '全部' : _ws;
}

async function loadWorkspaceList() {
  try {
    const data = await apiGet('/board/summaries');
    const summaries = (data && data.summaries) || {};
    return ['all', ...Object.keys(summaries).sort()];
  } catch (_) {
    return ['all'];
  }
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
        const keys = await loadWorkspaceList();
        const idx = keys.indexOf(_ws);
        _ws = keys[(idx + 1) % keys.length];
        await poll();
      } catch (_) { /* ignore */ }
    });
  }
  await poll();
  if (!_timer) _timer = setInterval(() => poll().catch(() => {}), 15000);
}

export function unmountConsole() {
  if (_timer) {
    clearInterval(_timer);
    _timer = null;
  }
}
