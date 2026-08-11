/**
 * opsPage.js — 运维页（T30：新协议版）
 *
 * 数据源：GET /ops/summary（唯一端点）
 *   返回：
 *     severity: "green" | "amber" | "red"
 *     human_line: "<一句话概览>"
 *     overview: { machines: [{name, ip, role, reachable, alive_ports, port_count}],
 *                 alert_count: N, down_ports: [...], generated_at }
 *   其余字段（risks/workspaces/daily/quality/docs/kb/deploy/ports/auto/...）旧 Hub
 *   大字段一律置空，本页不再渲染（避免误导）。
 *
 * 写操作（adopt/daily-review/run）已禁用：服务端不暴露。
 */

import { apiGet } from '../api.js';

let _root = null;
let _timer = null;

function esc(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function pill(ok, label) {
  const cls = ok ? 'ops-pill ok' : 'ops-pill bad';
  return `<span class="${cls}">${esc(label)}</span>`;
}

function html() {
  return `
<div class="ops-page hub-page">
  <div class="orch-hint">运维 · 走新服务端协议（/ops/summary）。2017 单端 :7788 四视图。</div>
  <div class="ops-bar">
    <h2>运维</h2>
    <span class="ops-sub">集群节点 + 服务概览</span>
    <span style="flex:1"></span>
    <button type="button" class="hub-btn" id="ops-refresh">刷新</button>
  </div>

  <div class="ops-section">
    <h3>状态</h3>
    <div id="ops-status" class="ops-card ops-status-bar"></div>
  </div>

  <div class="ops-section">
    <h3>集群节点 <span class="badge" id="ops-node-n">0</span></h3>
    <div id="ops-machines" class="ops-card"></div>
  </div>

  <div class="ops-section">
    <h3>Loop 巡查产出 <span class="badge" id="loop-count">0</span></h3>
    <div id="ops-loop" class="ops-card"><div class="ops-empty">加载中…</div></div>
  </div>

  <div class="ops-section">
    <h3>说明</h3>
    <div class="ops-card">
      <p class="ops-hint">本页只读 · 数据源 <code>/ops/summary</code> + <code>/loop/findings</code>。</p>
      <p class="ops-hint">Loop 巡查产出（后台 Observer 生成）：风险发现 + 建议转卡命令。人审闸门——采纳 = 复制命令在 M1 执行 new-card.sh 转卡（Loop 只审不投，绝不自动出卡）。</p>
      <p class="ops-hint">旧 Hub 大字段（risks / workspaces / daily / quality / docs / kb / deploy / ports / auto / relay 等）已下线；运维详情请用本页摘要、任务卡 / Engine，或 SSH 查 2017 日志。</p>
      <p class="ops-hint">写操作（adopt / daily-review / run）已禁用：服务端不暴露。</p>
    </div>
  </div>
</div>`;
}

function renderStatus(agg) {
  const el = _root.querySelector('#ops-status');
  if (!el) return;
  const severity = agg.severity || '—';
  const human = agg.human_line || '—';
  const sevCls = severity === 'green' ? 'ops-ok' : severity === 'red' ? 'ops-attn' : 'ops-warn';
  const overview = agg.overview || {};
  const machines = overview.machines || [];
  const total = machines.length;
  const reachable = machines.filter((m) => m.reachable).length;
  el.innerHTML = `
    <div class="ops-kv ${sevCls}" style="margin-bottom:8px;font-weight:600">
      <span class="ops-pill ${severity === 'green' ? 'ok' : severity === 'red' ? 'bad' : 'warn'}">${esc(severity)}</span>
      ${esc(human)}
    </div>
    <div class="ops-status-row">
      ${pill(reachable === total && total > 0, total > 0 ? `节点 ${reachable}/${total} 可达` : '无节点配置')}
      ${pill(severity !== 'red', severity === 'green' ? '绿' : severity === 'amber' ? '琥珀' : '红')}
    </div>`;
}

function renderMachines(agg) {
  const el = _root.querySelector('#ops-machines');
  const nEl = _root.querySelector('#ops-node-n');
  const overview = agg.overview || {};
  const machines = overview.machines || [];
  if (nEl) nEl.textContent = String(machines.length);
  if (!machines.length) {
    el.innerHTML = '<div class="ops-empty">未配置集群节点（CLUSTER_TARGETS env 为空）</div>';
    return;
  }
  el.innerHTML = machines
    .map(
      (m) => `<div class="ops-machine ${m.reachable ? 'up' : 'down'}">
      <div class="name">${esc(m.name)}</div>
      <div class="meta">${esc(m.ip)} · ${esc(m.role)}</div>
      <div class="status">${pill(!!m.reachable, m.reachable ? '在线' : '不可达')}
        <span class="muted">${esc(m.alive_ports || 0)}/${esc(m.port_count || 0)} 端口</span>
      </div>
    </div>`
    )
    .join('');
}

function renderLoop(loopData) {
  const el = _root.querySelector('#ops-loop');
  const nEl = _root.querySelector('#loop-count');
  if (!el) return;
  const reports = loopData?.loop_reports || [];
  if (nEl) nEl.textContent = String(reports.length);
  if (!reports.length) {
    el.innerHTML = '<div class="ops-empty">无 Loop 巡查报告（Observer 尚未产出）</div>';
    return;
  }
  el.innerHTML = reports
    .map((r) => {
      const findings = (r.findings || []).slice(0, 8);
      const commands = r.commands || [];
      const rows = findings
        .map(
          (f) => `<tr>
            <td>${esc(f.weight)}</td>
            <td>${esc(f.project)}</td>
            <td>${esc(f.title)}</td>
            <td><code>${esc(f.acting_on)}</code></td>
          </tr>`
        )
        .join('');
      const cmdBlocks = commands
        .slice(0, 3)
        .map((c) => `<pre class="ops-cmd">${esc(c)}</pre>`)
        .join('');
      return `<div class="ops-loop-report">
        <div class="ops-loop-head">
          <strong>${esc(r.name)}</strong>
          <span class="muted">${(r.findings || []).length} 发现 · ${commands.length} 建议命令</span>
        </div>
        ${rows ? `<table class="ops-table"><thead><tr><th>权重</th><th>项目</th><th>发现</th><th>对象</th></tr></thead><tbody>${rows}</tbody></table>` : '<div class="ops-empty">无表格发现</div>'}
        ${cmdBlocks}
      </div>`;
    })
    .join('');
}

async function poll() {
  try {
    const agg = await apiGet('/ops/summary');
    renderStatus(agg);
    renderMachines(agg);
  } catch (err) {
    const el = _root.querySelector('#ops-status');
    if (el) {
      el.innerHTML = `<div class="ops-kv ops-attn">运维采集失败: ${esc(err?.message || String(err))}</div>`;
    }
  }
  try {
    const loopData = await apiGet('/loop/findings');
    renderLoop(loopData);
  } catch (err) {
    const el = _root.querySelector('#ops-loop');
    if (el) {
      el.innerHTML = `<div class="ops-empty">Loop 巡查加载失败: ${esc(err?.message || String(err))}</div>`;
    }
  }
}

export async function mountOps(el) {
  _root = el;
  el.innerHTML = html();
  const refreshBtn = el.querySelector('#ops-refresh');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      refreshBtn.disabled = true;
      await poll();
      refreshBtn.disabled = false;
    });
  }
  await poll();
  _timer = setInterval(poll, 15000);
}

export function unmountOps() {
  if (_timer) {
    clearInterval(_timer);
    _timer = null;
  }
  _root = null;
}
