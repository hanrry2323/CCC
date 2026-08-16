/**
 * consolePage.js — 控制台（系统健康 + 配置中心 · ccc-plan-026）
 *
 * 定位：系统健康与平台配置中心，不再是「简化看板」。
 * 模块：系统总览 / 集群节点 / 服务网址(端口探索) / 中转站 / 后台任务进程 / 工程入口 / 设置。
 *
 * 数据源：
 *   /ops/summary      → 总览 + 节点
 *   /ops/ports        → 服务网址三态（lsof 全量发现）
 *   /ops/relay-stats  → 中转站状态
 *   /ops/hp-health    → HP 知识库节点探活
 *   /board/states、/board/ready_for_merge → 工程入口
 *   /tasks/running    → 后台任务进程（8s 轮询）
 *   /ops/concurrency  → 并发槽位
 *   /config           → 设置（只读）
 */

import { apiGet } from '../api.js';
import { esc, STATE_TONES } from '../ui.js';

let _root = null;
let _disposed = false;   // 2026-08-17 M3：卸载置位，异步回来不再写 DOM
let _timer = null;    // 系统/工程 15s
let _rtimer = null;   // 后台任务 8s

function pill(ok, label) {
  return `<span class="console-pill ${ok ? 'ok' : 'bad'}">${esc(label)}</span>`;
}

function html() {
  return `
<div class="console-page hub-page">
  <div class="console-bar">
    <h2>控制台</h2>
    <span class="console-sub">系统健康 · 配置中心</span>
    <span style="flex:1"></span>
    <button type="button" class="hub-btn" id="console-refresh">刷新</button>
  </div>

  <!-- ① 系统总览 -->
  <div id="console-overview" class="console-card console-overview"><div class="console-empty">加载中…</div></div>

  <!-- ② 主区 -->
  <div class="console-grid">
    <div class="console-left">
      <div class="console-card">
        <h4 class="console-card-title">集群节点 <span id="console-node-n" class="badge">0</span></h4>
        <div id="console-nodes"><div class="console-empty">加载中…</div></div>
      </div>
      <div class="console-card">
        <h4 class="console-card-title">服务网址（端口探索） <span id="console-port-n" class="badge">0</span></h4>
        <div id="console-ports"><div class="console-empty">加载中…</div></div>
      </div>
      <div class="console-card">
        <h4 class="console-card-title">中转站</h4>
        <div id="console-relay"><div class="console-empty">加载中…</div></div>
      </div>
      <div class="console-card">
        <h4 class="console-card-title">知识库健康 <span id="console-kb-n" class="badge">0</span></h4>
        <div id="console-kb"><div class="console-empty">加载中…</div></div>
      </div>
    </div>
    <div class="console-right">
      <div class="console-card">
        <h4 class="console-card-title">工程入口</h4>
        <div id="console-kpi" class="console-kpi"><div class="console-empty">加载中…</div></div>
        <div id="console-ready" class="console-ready"></div>
      </div>
      <div class="console-card">
        <h4 class="console-card-title">后台任务进程</h4>
        <div id="console-running" class="console-running"><div class="console-empty">当前无后台任务</div></div>
      </div>
    </div>
  </div>

  <!-- ③ 设置 -->
  <div class="console-card">
    <h4 class="console-card-title">设置（只读）</h4>
    <div id="console-settings" class="console-settings"><div class="console-empty">加载中…</div></div>
  </div>
</div>`;
}

/* ── ① 系统总览 ────────────────────────────── */

function renderOverview(summary, relay) {
  const el = _root.querySelector('#console-overview');
  if (!el) return;
  const severity = (summary && summary.severity) || '—';
  const sevCls = severity === 'green' ? 'ok' : severity === 'red' ? 'attn' : 'warn';
  const ov = (summary && summary.overview) || {};
  const machines = ov.machines || [];
  const total = machines.length;
  const reachable = machines.filter((m) => m.reachable).length;
  const services = ov.services || [];
  const svcRunning = services.filter((s) => s.running).length;
  const relayOk = !relay || relay.healthy !== false;
  el.innerHTML = `
    <div class="console-overview-row">
      <span class="console-sev ${sevCls}"><span class="console-dot"></span>${esc(severity === 'green' ? '系统健康' : severity === 'red' ? '系统异常' : '有注意项')}</span>
      <span class="console-overview-line">${esc((summary && summary.human_line) || '—')}</span>
      <span class="console-overview-chips">
        <span class="ops-chip">节点 ${reachable}/${total}</span>
        <span class="ops-chip">服务 ${svcRunning}/${services.length}</span>
        ${relay ? `<span class="ops-chip ${relayOk ? '' : 'alert'}">中转站 ${relayOk ? '正常' : '异常'}</span>` : ''}
      </span>
    </div>`;
}

/* ── ② 集群节点 ─────────────────────────────── */

function renderNodes(summary, hp) {
  const el = _root.querySelector('#console-nodes');
  if (!el) return;
  const machines = ((summary && summary.overview) || {}).machines || [];
  const nEl = _root.querySelector('#console-node-n');
  if (nEl) nEl.textContent = String(machines.length + (hp && hp.configured ? 1 : 0));
  const cards = machines.map((m) => `<div class="console-node ${m.reachable ? 'up' : 'down'}">
    <div class="console-node-head"><b>${esc(m.name || '')}</b>${pill(!!m.reachable, m.reachable ? '在线' : '不可达')}</div>
    <div class="console-node-meta">${esc(m.ip || '')} · ${esc(m.role || '')} · ${m.alive_ports || 0}/${m.port_count || 0} 端口</div>
  </div>`);
  if (hp && hp.configured) {
    cards.push(`<div class="console-node ${hp.reachable ? 'up' : 'down'}">
      <div class="console-node-head"><b>HP 知识库</b>${pill(!!hp.reachable, hp.reachable ? '在线' : '不可达')}</div>
      <div class="console-node-meta">${esc(hp.host || '')}:${esc(String(hp.port || ''))} · ${hp.latency_ms != null ? `${hp.latency_ms}ms` : ''}</div>
    </div>`);
  }
  el.innerHTML = cards.length ? cards.join('') : '<div class="console-empty">未配置集群节点</div>';
}

/* ── 服务网址（端口探索三态） ────────────────── */

function renderPorts(portsData) {
  const el = _root.querySelector('#console-ports');
  if (!el) return;
  const ports = (portsData && portsData.ports) || [];
  const nEl = _root.querySelector('#console-port-n');
  if (nEl) nEl.textContent = String(ports.length);
  const groups = {
    active_known: ports.filter((p) => p.status === 'active_known'),
    active_unknown: ports.filter((p) => p.status === 'active_unknown'),
    registered_stale: ports.filter((p) => p.status === 'registered_stale'),
  };
  const groupHTML = (list, label, tone) => list.length
    ? `<div class="console-port-group">
        <div class="console-port-group-h"><span class="console-dot ${tone}"></span>${label}<span class="badge">${list.length}</span></div>
        ${list.map((p) => `<a class="console-port-item" href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">
          <b>${esc(p.name || p.command || `端口 ${p.port}`)}</b><span>${p.port}</span><i>${p.status === 'active_unknown' ? `进程 ${esc(p.command || '')} ${esc(p.pid || '')} · 未识别` : p.status === 'registered_stale' ? '登记未运行' : '运行中'}</i>
        </a>`).join('')}
      </div>` : '';
  const gone = (portsData && portsData.gone_ports) || [];
  const goneHTML = gone.length
    ? `<div class="console-port-group"><div class="console-port-group-h"><span class="console-dot gone"></span>历史端口（今日已消失）<span class="badge">${gone.length}</span></div>
        <div class="console-gone-list">${gone.map((p) => `<span>${p}</span>`).join('')}</div></div>` : '';
  el.innerHTML = ports.length
    ? groupHTML(groups.active_known, '活跃服务', 'ok')
      + groupHTML(groups.active_unknown, '监听未识别（待确认）', 'warn')
      + groupHTML(groups.registered_stale, '登记未运行', 'gone')
      + goneHTML
    : '<div class="console-empty">无端口数据</div>';
}

/* ── 中转站 ─────────────────────────────────── */

function renderRelay(relay) {
  const el = _root.querySelector('#console-relay');
  if (!el) return;
  if (!relay) {
    el.innerHTML = '<div class="console-empty">中转站数据不可用</div>';
    return;
  }
  const t = relay.today || {};
  const d = relay.delta_10s || {};
  el.innerHTML = `
    <div class="console-relay-row">
      ${pill(relay.healthy !== false, relay.healthy !== false ? '正常' : '异常')}
      ${relay.alert ? `<span class="console-relay-alert">${esc(relay.alert)}</span>` : ''}
      <span class="console-relay-delta">近 10s <b>+${d.total || 0}</b></span>
    </div>
    <div class="console-relay-stats">
      <span class="console-relay-stat"><b>${t.total || 0}</b>今日总请求</span>
      <span class="console-relay-stat"><b>${t.code || 0}</b>code</span>
      <span class="console-relay-stat"><b>${t.flash || 0}</b>flash</span>
      <span class="console-relay-stat"><b>${t.pro || 0}</b>Pro</span>
    </div>`;
}

/* ── 知识库健康（P4）────────────────────── */

function renderKb(kb) {
  const el = _root.querySelector('#console-kb');
  const badge = _root.querySelector('#console-kb-n');
  if (!el) return;
  if (!kb || (!kb.ccc_kb && !kb.hp_kb)) {
    el.innerHTML = '<div class="console-empty">无数据</div>';
    if (badge) badge.textContent = '0';
    return;
  }
  const c = kb.ccc_kb || {};
  const h = kb.hp_kb || {};
  const cOk = !!c.ok;
  const hOk = h.configured ? !!h.reachable : false;
  const hLabel = !h.configured ? '未配置' : (hOk ? '在线' : '不可达');

  let hpMeta = h.configured ? `${h.host}:${h.port} · ${h.latency_ms}ms` : '—';
  if (hOk && h.documents != null) hpMeta += ` · ${h.documents} 文档`;
  let sync = '';
  if (hOk && h.ccc_sync) {
    const parts = Object.entries(h.ccc_sync).map(([name, p]) => {
      const ing = p.last_ingest ? ` @${String(p.last_ingest).slice(0, 10)}` : '';
      return `${name}:${p.docs}${ing}`;
    });
    if (parts.length) sync = `<div class="console-node-meta" style="padding-left:8px">同步 ${parts.join(' · ')}</div>`;
  }

  el.innerHTML = `
    <div class="console-node ${cOk ? 'up' : 'down'}">
      <div class="console-node-name">ccc-kb <span class="console-pill ${cOk ? 'ok' : 'bad'}">${cOk ? '就绪' : '异常'}</span></div>
      <div class="console-node-meta">本地 BM25 · ${c.documents ?? '—'} 文档${c.lag_days != null ? ` · 滞后 ${c.lag_days} 天` : ''}</div>
    </div>
    <div class="console-node ${hOk ? 'up' : 'down'}">
      <div class="console-node-name">hp-kb <span class="console-pill ${hOk ? 'ok' : 'bad'}">${hLabel}</span></div>
      <div class="console-node-meta">${hpMeta}</div>${sync}
    </div>`;
  if (badge) badge.textContent = (cOk ? 1 : 0) + (hOk ? 1 : 0);
}

/* ── 工程入口 ───────────────────────────────── */

function renderKPI(states) {
  const el = _root.querySelector('#console-kpi');
  if (!el) return;
  // P1 修复：/board/states 返回顶层五态 + columns（机审在 columns 里），无 counts 键
  const base = states || {};
  const columns = base.columns || {};
  const counts = (s) => base[s] != null ? base[s] : (columns[s] != null ? columns[s] : 0);
  const order = ['待分派', '执行中', '机审', '已回写', '打回'];
  const tones = STATE_TONES;
  const items = order.map((s) => `<a class="console-kpi-item" href="#/board" title="去看板 ${s}">
    <b style="color:${tones[s]}">${counts(s)}</b><span>${s}</span>
  </a>`).join('');
  el.innerHTML = items || '<div class="console-empty">无卡数据</div>';
}

function renderReady(merge) {
  const el = _root.querySelector('#console-ready');
  if (!el) return;
  const count = (merge && merge.count) || 0;
  const returned = 0;
  el.innerHTML = count
    ? `<a class="console-ready" href="#/board" title="待合入卡"><span>待合入</span><b>${count}</b> 去合入 →</a>`
    : '';
}

/* ── 后台任务进程（T53 契约保留） ────────────── */

function renderRunning(tasks, concurrency) {
  const el = _root.querySelector('#console-running');
  if (!el) return;
  const slots = (concurrency && concurrency.slots) || {};
  const head = slots.exec_max
    ? `<div class="console-running-head">执行槽 ${slots.exec_max} · 机审槽 ${slots.audit_max}</div>` : '';
  const list = (tasks && tasks.tasks) || [];
  if (!list.length) {
    el.innerHTML = head + '<div class="console-empty">当前无后台任务</div>';
    return;
  }
  el.innerHTML = head + list.slice(0, 10).map((t) => {
    // P1 修复：/tasks/running 字段为 work_id/board_column/metrics_live（此前读 id/phase/indeterminate 全空）
    const id = t.work_id || t.id || '';
    const kind = t.board_column || '';
    const running = t.metrics_live === true || t.indeterminate === true;
    const logTail = Array.isArray(t.log_tail) ? t.log_tail.join('\n') : (t.log_tail || '');
    return `
    <div class="console-task ${running ? 'running' : ''}">
      <div class="console-task-row">
        <b>${esc(id)}</b>
        <span class="ops-todo-type">${esc(kind)}</span>
        <span class="console-task-time">已用时 ${esc(t.elapsed_s != null ? t.elapsed_s + 's' : '—')}${t.last_activity_at ? ` · 最后活动 ${esc(t.last_activity_at)}` : ''}</span>
      </div>
      <div class="console-task-tail" title="日志尾">${esc(logTail.slice(-160))}</div>
      ${running ? '<div class="console-task-progress indeterminate"></div>' : ''}
    </div>`;
  }).join('');
}

/* ── 设置（只读） ───────────────────────────── */

function renderSettings(config, concurrency) {
  const el = _root.querySelector('#console-settings');
  if (!el) return;
  const slots = (concurrency && concurrency.slots) || {};
  const groups = [
    ['服务', config && config.ports ? [
      ['Web', config.ports.web || '—'],
      ['看板', config.ports.board || '—'],
      ['Engine', config.ports.engine || '—'],
      ['中转站', config.ports.relay || '—'],
    ] : []],
    ['模型', config && config.models ? config.models.map((m) => [m, '']) : []],
    ['并发', [
      ['执行槽', slots.exec_max || '—'],
      ['机审槽', slots.audit_max || '—'],
    ]],
    ['版本', config && config.version ? [['平台', config.version]] : []],
  ];
  el.innerHTML = groups.map(([title, rows]) => rows.length
    ? `<div class="console-settings-group"><h5>${esc(title)}</h5>${rows.map(([k, v]) => `<span>${esc(k)}</span><b>${esc(v)}</b>`).join('')}</div>`
    : '').join('') || '<div class="console-empty">配置不可用</div>';
}

/* ── 轮询 ───────────────────────────────────── */

async function pollSystem() {
  if (_disposed || !_root) return;
  const [summary, ports, relay, hp, kb, states, ready, config, concurrency] = await Promise.all([
    apiGet('/ops/summary').catch(() => null),
    apiGet('/ops/ports').catch(() => null),
    apiGet('/ops/relay-stats').catch(() => null),
    apiGet('/ops/hp-health').catch(() => null),
    apiGet('/ops/kb-health').catch(() => null),
    apiGet('/board/states').catch(() => null),
    apiGet('/board/ready_for_merge').catch(() => null),
    apiGet('/config').catch(() => null),
    apiGet('/ops/concurrency').catch(() => null),
  ]);
  if (_disposed || !_root) return; // 卸载后回来不再写 DOM
  renderOverview(summary, relay);
  renderNodes(summary, hp);
  renderPorts(ports);
  renderRelay(relay);
  renderKb(kb);
  renderKPI(states);
  renderReady(ready);
  renderSettings(config, concurrency);
}

async function pollRunning() {
  if (_disposed || !_root) return;
  const [tasks, concurrency] = await Promise.all([
    apiGet('/tasks/running').catch(() => null),
    apiGet('/ops/concurrency').catch(() => null),
  ]);
  if (_disposed || !_root) return; // 卸载后回来不再写 DOM
  renderRunning(tasks, concurrency);
}

export function mountConsole(el, ctx = {}) {
  _root = el;
  _disposed = false;
  el.innerHTML = html();
  el.querySelector('#console-refresh')?.addEventListener('click', async () => {
    const btn = el.querySelector('#console-refresh');
    btn.disabled = true;
    await Promise.all([pollSystem(), pollRunning()]);
    btn.disabled = false;
  });
  // M3 非阻塞：后台拉数据
  Promise.all([pollSystem(), pollRunning()]);
  _timer = setInterval(() => { if (!_disposed && document.visibilityState === 'visible') pollSystem(); }, 15000);
  _rtimer = setInterval(() => { if (!_disposed && document.visibilityState === 'visible') pollRunning(); }, 8000);
}

export function unmountConsole() {
  _disposed = true;
  if (_timer) {
    clearInterval(_timer);
    _timer = null;
  }
  if (_rtimer) {
    clearInterval(_rtimer);
    _rtimer = null;
  }
  _root = null;
}
