/** Hub Ops page — logistics-first IA (Engine front / Ops logistics) */

import { apiGet, apiPost } from '../api.js';

let _root = null;
let _timer = null;
let _lastAgg = null;

const FOLD_KEY = 'ccc.ops.fold';

function esc(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function fmtBytes(n) {
  if (n == null || Number.isNaN(n)) return '—';
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  let v = Number(n);
  let i = 0;
  while (v >= 1024 && i < u.length - 1) {
    v /= 1024;
    i += 1;
  }
  return v.toFixed(i ? 1 : 0) + ' ' + u[i];
}

function pill(ok, label) {
  const cls = ok ? 'ops-pill ok' : 'ops-pill bad';
  return `<span class="${cls}">${esc(label)}</span>`;
}

function foldOpen(id, defaultOpen = false) {
  try {
    const raw = localStorage.getItem(FOLD_KEY);
    if (!raw) return defaultOpen;
    const m = JSON.parse(raw);
    if (m && typeof m[id] === 'boolean') return m[id];
  } catch (_) {
    /* ignore */
  }
  return defaultOpen;
}

function persistFold(el) {
  const id = el?.dataset?.fold;
  if (!id) return;
  try {
    const raw = localStorage.getItem(FOLD_KEY);
    const m = raw ? JSON.parse(raw) : {};
    m[id] = !!el.open;
    localStorage.setItem(FOLD_KEY, JSON.stringify(m));
  } catch (_) {
    /* ignore */
  }
}

function html() {
  const f = (id, def = false) => (foldOpen(id, def) ? ' open' : '');
  return `
<div class="ops-page">
  <div class="ops-bar">
    <h2>运维</h2>
    <span class="ops-sub">后勤态势 · 供弹 · 红灯</span>
    <span style="flex:1"></span>
    <a class="hub-btn" href="#/console">控制台</a>
    <button type="button" class="hub-btn" id="ops-refresh">刷新</button>
  </div>

  <div class="ops-section">
    <h3>状态</h3>
    <div id="ops-status" class="ops-card ops-status-bar"></div>
  </div>

  <div class="ops-section">
    <h3>后勤供弹</h3>
    <div id="ops-logistics" class="ops-card"></div>
  </div>

  <div class="ops-section">
    <h3>需关注 <span class="badge" id="ops-alert-n">0</span></h3>
    <div id="ops-alerts"></div>
  </div>

  <details class="ops-fold" data-fold="fleet"${f('fleet')}>
    <summary>舰队详情 · 机器 / 端口 / 资源 / 部署</summary>
    <div class="ops-fold-body">
      <div class="ops-section">
        <h3>集群</h3>
        <div class="ops-machines" id="ops-machines"></div>
      </div>
      <div class="ops-section">
        <h3>端口与服务
          <button type="button" class="hub-btn" id="ops-copy-ports" style="margin-left:8px">复制端口表</button>
        </h3>
        <p class="ops-hint">SSOT：<code id="ops-infra-path">.ccc/infrastructure.md</code></p>
        <div id="ops-ports"></div>
      </div>
      <div class="ops-grid-2">
        <div class="ops-section">
          <h3>本机资源</h3>
          <div id="ops-resources" class="ops-card"></div>
        </div>
        <div class="ops-section">
          <h3>生产/部署</h3>
          <div id="ops-deploy" class="ops-card"></div>
        </div>
      </div>
      <div class="ops-section">
        <h3>工作区 Diff</h3>
        <div id="ops-workspaces"></div>
      </div>
      <div class="ops-section">
        <h3>知识库</h3>
        <div id="ops-kb"></div>
      </div>
    </div>
  </details>

  <details class="ops-fold" data-fold="reports"${f('reports')}>
    <summary>报告与债 · 日审 / 文档 / 质量 / 心智</summary>
    <div class="ops-fold-body">
      <div class="ops-section">
        <h3>日审报告</h3>
        <div id="ops-daily" class="ops-card"></div>
      </div>
      <div class="ops-section">
        <h3>项目心智 L1（只读）</h3>
        <p class="ops-hint">权威在 2017 <code>.ccc/agent-mind/</code></p>
        <div id="ops-minds" class="ops-card"></div>
      </div>
      <div class="ops-grid-2">
        <div class="ops-section">
          <h3>文档债</h3>
          <div id="ops-docs"></div>
        </div>
        <div class="ops-section">
          <h3>质量日摘要</h3>
          <div id="ops-quality"></div>
        </div>
      </div>
      <div class="ops-section">
        <h3>其它风险 <span class="badge" id="ops-risk-n">0</span></h3>
        <div id="ops-risks-low"></div>
      </div>
    </div>
  </details>

  <div class="ops-section">
    <h3>弹药队列 <span class="badge" id="ops-auto-n">0</span></h3>
    <p class="ops-hint">只读 · ops-auto / daily-review backlog（业务仓）</p>
    <div id="ops-auto"></div>
  </div>

  <details class="ops-fold" data-fold="actions"${f('actions')}>
    <summary>例外动作 · 日审 / 手动采纳</summary>
    <div class="ops-fold-body">
      <div class="ops-section">
        <h3>日审（业务仓 all-apps）</h3>
        <p class="ops-hint">默认 dry-run；apply 仅 C/E/F。禁 CCC orch。</p>
        <button type="button" class="hub-btn" id="ops-run-dry">dry-run</button>
        <button type="button" class="hub-btn" id="ops-run-apply">apply 建卡</button>
      </div>
      <div class="ops-section">
        <h3>可采纳项（有业务仓 workspace）</h3>
        <div id="ops-adoptables"></div>
      </div>
    </div>
  </details>
</div>`;
}

function renderStatus(agg) {
  const el = _root.querySelector('#ops-status');
  if (!el) return;
  const risks = (agg.risks && agg.risks.risks) || [];
  const engineDown = risks.some((r) => r.id === 'engine-down');
  const control = agg.control || {};
  const mode = control.mode || '—';
  const modeOk = mode === 'enabled';
  const inventOff = control.invent_hard_disabled !== false;
  const hubOk = control.hub_port_7777 !== false;
  const engineOk =
    control.engine_running === true || (!engineDown && control.engine_running !== false);
  const sum = (agg.resources_history && agg.resources_history.summary) || {};
  const verdict = sum.verdict || '—';
  const plist = (agg.logistics && agg.logistics.plist) || {};
  const loaded = !!plist.any_loaded;
  const applyAmmo = !!plist.any_apply_ammo;
  const high = Number(agg.risks?.high ?? risks.filter((r) => r.severity === 'high').length);
  const headline = (agg.logistics && agg.logistics.headline) || '';
  const needs = !!(agg.logistics && agg.logistics.needs_attention);
  const ready = agg.ready_to_dispatch || {};
  const readyOk = !!ready.ok;
  const readyLine = ready.reason || (readyOk ? '可下达' : '暂缓下达');

  el.innerHTML = `
    <div class="ops-kv ${readyOk ? 'ops-ok' : 'ops-attn'}" style="margin-bottom:8px;font-weight:600">${esc(readyLine)}</div>
    <div class="ops-status-row">
      ${pill(engineOk, engineOk ? 'Engine 在跑' : 'Engine 停')}
      ${pill(modeOk, `mode ${esc(mode)}`)}
      ${pill(inventOff, inventOff ? 'invent 关' : 'invent 开?')}
      ${pill(hubOk, hubOk ? 'Hub :7777' : 'Hub 未听')}
      ${pill(verdict !== 'saturated', `并行 ${esc(verdict)}`)}
      ${pill(loaded, loaded ? (applyAmmo ? 'plist apply' : 'plist dry') : 'plist 未启用')}
      ${pill(high === 0, high ? `红灯 ${high}` : '无红灯')}
    </div>
    <div class="ops-kv ${needs ? 'ops-attn' : ''}">${esc(headline || '—')}</div>
    <p class="ops-hint">定时供弹：<code>bash scripts/install-ops-plist.sh install --enable --apply-ammo</code>（界面不代启；无自造任务入口）</p>`;
}

function renderMachines(d) {
  const el = _root.querySelector('#ops-machines');
  const machines = d.machines || [];
  if (!machines.length) {
    el.innerHTML = '<div class="ops-empty">未解析到机器清单</div>';
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

function renderPorts(d) {
  const el = _root.querySelector('#ops-ports');
  const pathEl = _root.querySelector('#ops-infra-path');
  if (pathEl && d.infra_path) pathEl.textContent = d.infra_path;
  const groups = d.groups || [];
  if (!groups.length) {
    el.innerHTML = '<div class="ops-empty">无端口数据</div>';
    return;
  }
  el.innerHTML = groups
    .map((g) => {
      const rows = (g.ports || [])
        .map(
          (p) => `<tr>
          <td class="mono">${esc(p.port)}</td>
          <td>${esc(p.name)}</td>
          <td>${esc(p.machine || '')}</td>
          <td>${pill(!!p.alive, p.alive ? p.label || 'OK' : 'down')}</td>
        </tr>`
        )
        .join('');
      return `<div class="ops-port-group"><h4>${esc(g.group)}</h4>
        <table class="ops-table"><thead><tr><th>端口</th><th>服务</th><th>机器</th><th>状态</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="4">—</td></tr>'}</tbody></table></div>`;
    })
    .join('');
  _root._portsCopyText = groups
    .flatMap((g) =>
      (g.ports || []).map((p) => `${p.port}\t${p.name}\t${p.machine || ''}\t${p.alive ? 'up' : 'down'}`)
    )
    .join('\n');
}

function renderResources(d, history) {
  const el = _root.querySelector('#ops-resources');
  const load = d.load || {};
  const mem = d.memory || {};
  const disk = d.disk || {};
  const sum = (history && history.summary) || {};
  const sparks = (history && history.sparklines) || {};
  const verdict = sum.verdict
    ? `<div class="ops-kv">并行容量 <b>${esc(sum.verdict)}</b> · ${esc(sum.reason || '')}</div>`
    : '';
  const curve =
    sparks.load_ratio || sparks.mem_pct
      ? `<div class="ops-kv mono small">load ${esc(sparks.load_ratio || '—')}<br>mem&nbsp; ${esc(sparks.mem_pct || '—')}</div>`
      : '<div class="ops-kv muted small">曲线：Engine 采样中 → ~/.ccc/stats/host-resources.jsonl</div>';
  el.innerHTML = `
    <div><b>${esc(d.host || '本机')}</b> · ncpu ${esc(d.ncpu ?? '—')}</div>
    <div class="ops-kv">Load ${esc(load['1']?.toFixed?.(2) ?? load['1'] ?? '—')} / ${esc(load['5']?.toFixed?.(2) ?? '—')} / ${esc(load['15']?.toFixed?.(2) ?? '—')} · ratio ${esc(d.load_ratio ?? '—')}</div>
    <div class="ops-kv">内存 ${esc(mem.used_pct != null ? mem.used_pct + '%' : '—')} · ${esc(fmtBytes(mem.used_bytes))} / ${esc(fmtBytes(mem.total_bytes))}</div>
    <div class="ops-kv">磁盘 ${esc(disk.used_pct != null ? disk.used_pct + '%' : '—')} · 可用 ${esc(fmtBytes(disk.free_bytes))}</div>
    ${curve}
    ${verdict}`;
}

function renderDeploy(d) {
  const el = _root.querySelector('#ops-deploy');
  const dev = d.dev || {};
  const targets = d.targets || [];
  el.innerHTML =
    `<div class="ops-kv"><b>开发</b> ${esc(dev.name)} ${esc(dev.ip || '')} · ${esc(dev.role || '')}</div>` +
    targets
      .map((t) => {
        const checks = (t.checks || [])
          .map((c) => pill(!!c.alive, `${c.label || c.port}:${c.alive ? 'up' : 'down'}`))
          .join(' ');
        return `<div class="ops-deploy-row">
          <div><b>${esc(t.name)}</b> ${esc(t.ip || '')} · ${esc(t.role)} ${pill(!!t.reachable, t.reachable ? '可达' : '不可达')}</div>
          <div class="muted">${esc(t.notes || '')}</div>
          <div>${checks || '—'}</div>
        </div>`;
      })
      .join('');
}

function renderWorkspaces(d) {
  const el = _root.querySelector('#ops-workspaces');
  const rows = d.workspaces || [];
  if (!rows.length) {
    el.innerHTML = '<div class="ops-empty">无注册工作区</div>';
    return;
  }
  el.innerHTML = `<table class="ops-table"><thead><tr>
    <th>仓</th><th>分支</th><th>dirty</th><th>planned</th><th>doing</th><th>test</th><th>abn</th><th>摘要</th>
  </tr></thead><tbody>${rows
    .map((w) => {
      const sample = (w.dirty_sample || []).slice(0, 3).map(esc).join('<br>') || '—';
      return `<tr>
        <td><b>${esc(w.id || w.workspace)}</b><div class="muted mono small">${esc(w.path)}</div></td>
        <td class="mono">${esc(w.branch || '—')}</td>
        <td>${esc(w.dirty ?? '—')}</td>
        <td>${esc(w.planned ?? 0)}</td>
        <td>${esc(w.in_progress ?? 0)}</td>
        <td>${esc(w.testing ?? 0)}</td>
        <td>${esc(w.abnormal ?? 0)}</td>
        <td class="mono small">${sample}</td>
      </tr>`;
    })
    .join('')}</tbody></table>`;
}

function renderLogistics(d) {
  const el = _root.querySelector('#ops-logistics');
  if (!el) return;
  if (!d || d.error) {
    el.innerHTML = `<p class="ops-hint">${esc(d?.error || '无后勤心跳')}</p>`;
    return;
  }
  const plist = d.plist || {};
  const agents = plist.agents || [];
  const ammo = d.ammo_workspaces || [];
  const daily = d.daily_today || [];
  const chips = ammo.length
    ? `<div class="ops-chips">${ammo
        .map((a) => `<span class="ops-chip">${esc(a.workspace)}</span>`)
        .join('')}</div>`
    : '<div class="ops-kv muted">无 engine-eligible 弹药仓</div>';
  const agentRows = agents
    .map(
      (a) =>
        `<div class="ops-kv">${pill(!!a.loaded, a.loaded ? 'loaded' : 'off')}
        <code>${esc(a.label)}</code>
        ${a.apply_ammo ? 'apply-ammo' : 'dry-run'}</div>`
    )
    .join('');
  const dailyRows = daily.length
    ? `<table class="ops-table"><thead><tr><th>仓</th><th>decision</th><th>mtime</th></tr></thead><tbody>${daily
        .map(
          (x) =>
            `<tr><td>${esc(x.workspace)}</td><td class="mono">${esc(x.decision || '—')}</td><td class="mono small">${esc(x.mtime || '')}</td></tr>`
        )
        .join('')}</tbody></table>`
    : '<div class="ops-kv muted">今日尚无日审报告</div>';
  el.innerHTML = `
    <div class="ops-kv ${d.needs_attention ? 'ops-attn' : ''}"><b>${esc(d.headline || '后勤')}</b></div>
    <div class="ops-kv">弹药仓 ${esc(String(ammo.length))} · ops-auto ${esc(String(d.ops_auto_backlog ?? 0))} · spawn提示 ${esc(String(d.spawn_hint_today ?? 0))}</div>
    ${chips}
    <p class="ops-hint">CCC orch 不在供弹名单（Engine 不消费）</p>
    ${agentRows || '<div class="ops-kv muted">无 ops plist 文件</div>'}
    ${dailyRows}
    <p class="ops-hint">${esc(d.note || '')}</p>`;
}

function bindAdopt(rootEl, tags) {
  rootEl?.querySelectorAll('.ops-adopt-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        await apiPost('/api/ops/adopt', {
          workspace: btn.dataset.ws,
          title: btn.dataset.title || 'ops suggestion',
          description: btn.dataset.detail || '',
          tags,
        });
        window.showToast?.('已入队 backlog（ops-auto）', 'success');
        await poll();
      } catch (e) {
        window.showToast?.(e.message || '建卡失败', 'error');
        btn.disabled = false;
      }
    });
  });
}

function riskCard(r, { adopt = false } = {}) {
  const sev = esc(r.severity || 'info');
  const ws = (r.workspace || '').trim();
  const canAdopt =
    adopt &&
    ws &&
    ws.toUpperCase() !== 'CCC' &&
    r.title &&
    !String(r.id || '').startsWith('engine');
  return `<div class="ops-risk sev-${sev}">
    <div class="title">${esc(r.title)}</div>
    <div class="meta">${esc(r.source)} · ${sev}${ws ? ' · ' + esc(ws) : ''}</div>
    <div class="detail">${esc(r.detail || '')}</div>
    ${
      canAdopt
        ? `<button type="button" class="hub-btn ops-adopt-btn" data-title="${esc(r.title)}" data-detail="${esc(r.detail || '')}" data-ws="${esc(ws)}">采纳为任务</button>`
        : ''
    }
  </div>`;
}

function renderAlerts(agg) {
  const el = _root.querySelector('#ops-alerts');
  const nEl = _root.querySelector('#ops-alert-n');
  const risks = (agg.risks && agg.risks.risks) || [];
  const high = risks.filter((r) => String(r.severity || '').toLowerCase() === 'high');
  const down = (agg.overview && agg.overview.down_ports) || [];
  const criticalDown = down.filter((p) => [7775, 7777].includes(Number(p.port)));
  if (nEl) nEl.textContent = String(high.length + criticalDown.length);

  let htmlOut = '';
  if (high.length) {
    htmlOut += high.map((r) => riskCard(r, { adopt: false })).join('');
  }
  if (criticalDown.length) {
    htmlOut += criticalDown
      .map(
        (p) => `<div class="ops-risk sev-high">
        <div class="title">关键端口 ${esc(p.port)} 未响应 (${esc(p.name || '')})</div>
        <div class="meta">ports · high</div>
        <div class="detail">${esc(p.label || p.host || '')}</div>
      </div>`
      )
      .join('');
  }
  if (!htmlOut) {
    htmlOut = '<div class="ops-empty">当前无红灯</div>';
  }
  el.innerHTML = htmlOut;
}

function renderRisksLow(d) {
  const el = _root.querySelector('#ops-risks-low');
  const n = _root.querySelector('#ops-risk-n');
  const risks = (d.risks || []).filter((r) => String(r.severity || '').toLowerCase() !== 'high');
  if (n) n.textContent = String(risks.length);
  if (!risks.length) {
    el.innerHTML = '<div class="ops-empty">无 medium/low 风险</div>';
    return;
  }
  el.innerHTML = risks.map((r) => riskCard(r, { adopt: false })).join('');
}

function renderDaily(d) {
  const el = document.getElementById('ops-daily');
  if (!el) return;
  if (!d || d.error) {
    el.innerHTML = `<p class="ops-hint">${esc(d?.error || '无数据')}</p>`;
    return;
  }
  const items = d.items || d.reviews || [];
  if (!items.length) {
    el.innerHTML = '<p class="ops-hint">暂无日审报告</p>';
    return;
  }
  el.innerHTML = `<ul>${items
    .slice(0, 8)
    .map(
      (x) =>
        `<li><code>${esc(x.workspace || x.path || '')}</code> ${esc(x.title || x.name || x.as_of || '')}</li>`
    )
    .join('')}</ul>`;
}

function renderMinds(d) {
  const el = document.getElementById('ops-minds');
  if (!el) return;
  if (!d || d.ok === false) {
    el.innerHTML = `<p class="ops-hint">${esc(d?.error || '心智摘要不可用')}</p>`;
    return;
  }
  const items = d.items || [];
  if (!items.length) {
    el.innerHTML = '<p class="ops-hint">无业务仓心智摘要</p>';
    return;
  }
  el.innerHTML = `<table class="ops-table"><thead><tr>
    <th>项目</th><th>as_of</th><th>看板</th><th>日报</th><th>约束数</th>
  </tr></thead><tbody>${items
    .map((x) => {
      if (x.error) {
        return `<tr><td>${esc(x.project_id)}</td><td colspan="4">${esc(x.error)}</td></tr>`;
      }
      return `<tr>
      <td><code>${esc(x.project_id)}</code></td>
      <td>${esc(x.as_of || '')}</td>
      <td>${esc((x.board_summary || '').slice(0, 80))}</td>
      <td>${esc((x.daily || x.weekly || '—').toString().slice(0, 60))}</td>
      <td>${esc(String(x.constraints_n ?? 0))}</td>
    </tr>`;
    })
    .join('')}</tbody></table>`;
}

function renderKb(d) {
  const el = _root.querySelector('#ops-kb');
  const svcs = d.services || [];
  el.innerHTML =
    (svcs
      .map(
        (s) => `<div class="ops-kv">${pill(!!s.alive, s.alive ? 'up' : 'down')}
        <b>${esc(s.name)}</b> :${esc(s.port)}
        <a href="${esc(s.deep_link)}" target="_blank" rel="noopener">打开</a>
      </div>`
      )
      .join('') || '<div class="ops-empty">无 KB 探针</div>') +
    `<p class="ops-hint">${esc(d.note || '')}</p>`;
}

function renderDocs(d) {
  const el = _root.querySelector('#ops-docs');
  const findings = d.findings || [];
  if (!findings.length) {
    el.innerHTML = '<div class="ops-empty">未发现文档债提示</div>';
    return;
  }
  el.innerHTML = findings
    .map((f) => {
      const ws = (f.workspace || '').trim();
      return `<div class="ops-risk sev-${esc(f.severity || 'low')}">
      <div class="title">${esc(f.title)}</div>
      <div class="detail">${esc(f.suggestion || '')}${ws ? ' · ' + esc(ws) : ''}</div>
    </div>`;
    })
    .join('');
}

function renderQuality(d) {
  const el = _root.querySelector('#ops-quality');
  const rows = d.workspaces || [];
  el.innerHTML =
    `<p class="ops-hint">${esc(d.note || '')}</p>` +
    (rows
      .map((w) => {
        const ws = (w.workspace || '').trim();
        const commits = (w.commit_sample || []).map(esc).join('<br>') || '—';
        return `<div class="ops-card" style="margin-bottom:8px">
        <b>${esc(ws)}</b> · 24h commits ${esc(w.commits_24h)} · released ${esc(w.released_total)}
        <div class="mono small">${commits}</div>
      </div>`;
      })
      .join('') || '<div class="ops-empty">无摘要</div>');
}

function renderAuto(d) {
  const el = _root.querySelector('#ops-auto');
  const n = _root.querySelector('#ops-auto-n');
  const tasks = d.tasks || [];
  if (n) n.textContent = String(tasks.length);
  if (!tasks.length) {
    el.innerHTML = '<div class="ops-empty">暂无 ops-auto 卡</div>';
    return;
  }
  el.innerHTML = tasks
    .slice(0, 20)
    .map(
      (t) => `<div class="ops-auto-row">
      <div class="title">${esc(t.title || t.id)}</div>
      <div class="meta mono">${esc(t.id)} · ${esc(t.workspace)} · ${esc(t.origin)} · ${(t.tags || []).map(esc).join(', ')}</div>
    </div>`
    )
    .join('');
}

function renderAdoptables(agg) {
  const el = _root.querySelector('#ops-adoptables');
  if (!el) return;
  const risks = ((agg.risks && agg.risks.risks) || []).filter((r) => {
    const ws = (r.workspace || '').trim();
    return (
      ws &&
      ws.toUpperCase() !== 'CCC' &&
      r.title &&
      !String(r.id || '').startsWith('engine')
    );
  });
  const findings = ((agg.docs && agg.docs.findings) || []).filter((f) => {
    const ws = (f.workspace || '').trim();
    return ws && ws.toUpperCase() !== 'CCC';
  });
  const quality = ((agg.quality && agg.quality.workspaces) || []).filter((w) => {
    const ws = (w.workspace || '').trim();
    return ws && ws.toUpperCase() !== 'CCC';
  });

  let htmlOut = '';
  if (risks.length) {
    htmlOut += '<h4 class="ops-subh">来自风险</h4>';
    htmlOut += risks
      .slice(0, 8)
      .map((r) => riskCard(r, { adopt: true }))
      .join('');
  }
  if (findings.length) {
    htmlOut += '<h4 class="ops-subh">来自文档债</h4>';
    htmlOut += findings
      .slice(0, 8)
      .map((f) => {
        const ws = (f.workspace || '').trim();
        return `<div class="ops-risk sev-${esc(f.severity || 'low')}">
        <div class="title">${esc(f.title)}</div>
        <div class="detail">${esc(f.suggestion || '')}</div>
        <button type="button" class="hub-btn ops-adopt-btn" data-title="${esc('文档: ' + (f.title || ''))}" data-detail="${esc(f.suggestion || '')}" data-ws="${esc(ws)}" data-tags="docs">采纳为任务</button>
      </div>`;
      })
      .join('');
  }
  if (quality.length) {
    htmlOut += '<h4 class="ops-subh">来自质量摘要</h4>';
    htmlOut += quality
      .slice(0, 6)
      .map((w) => {
        const ws = (w.workspace || '').trim();
        return `<div class="ops-card" style="margin-bottom:8px">
        <b>${esc(ws)}</b> · 24h ${esc(w.commits_24h)}
        <button type="button" class="hub-btn ops-adopt-btn" data-title="${esc('质量跟进: ' + ws)}" data-detail="${esc((w.commit_sample || []).join('\\n'))}" data-ws="${esc(ws)}" data-tags="quality">建议入队打磨</button>
      </div>`;
      })
      .join('');
  }
  if (!htmlOut) {
    htmlOut = '<div class="ops-empty">无可采纳业务仓项（减负：日常靠定时供弹）</div>';
  }
  el.innerHTML = htmlOut;
  el.querySelectorAll('.ops-adopt-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      const tagExtra = btn.dataset.tags || 'from-risk';
      try {
        await apiPost('/api/ops/adopt', {
          workspace: btn.dataset.ws,
          title: btn.dataset.title || 'ops suggestion',
          description: btn.dataset.detail || '',
          tags: ['ops-auto', tagExtra],
        });
        window.showToast?.('已入队 backlog（ops-auto）', 'success');
        await poll();
      } catch (e) {
        window.showToast?.(e.message || '建卡失败', 'error');
        btn.disabled = false;
      }
    });
  });
}

async function _safeGet(path, fallback) {
  try {
    return await apiGet(path);
  } catch (e) {
    console.warn('ops fetch failed', path, e);
    return fallback;
  }
}

async function poll() {
  const agg = await _safeGet('/api/ops/summary', null);
  if (!agg) return;
  _lastAgg = agg;

  renderStatus(agg);
  renderLogistics(agg.logistics || {});
  renderAlerts(agg);

  renderMachines(agg.overview || { machines: [], alert_count: 0 });
  renderPorts(agg.ports || { groups: [] });
  renderResources(agg.resources || {}, agg.resources_history || null);
  renderDeploy(agg.deploy || { targets: [] });
  renderWorkspaces(agg.workspaces || { workspaces: [] });
  renderKb(agg.kb || { services: [] });

  renderDaily(agg.daily || {});
  renderMinds(agg.agent_minds || {});
  renderDocs(agg.docs || { findings: [] });
  renderQuality(agg.quality || { workspaces: [] });
  renderRisksLow(agg.risks || { count: 0, risks: [] });

  renderAuto(agg.auto || { tasks: [] });
  renderAdoptables(agg);
}

async function runReview(apply) {
  try {
    const r = await apiPost('/api/ops/daily-review/run', { all_apps: true, apply });
    if (r.ok) {
      window.showToast?.(apply ? '已 apply（业务仓 C/E/F）' : 'dry-run 完成（all apps）', 'success');
    } else {
      window.showToast?.(r.error || '日审失败', 'error');
    }
    await poll();
  } catch (e) {
    window.showToast?.(e.message || '日审失败', 'error');
  }
}

export async function mountOps(el) {
  if (!_root) {
    _root = el;
    el.innerHTML = html();
    _root.querySelector('#ops-refresh').addEventListener('click', () => poll().catch(() => {}));
    _root.querySelector('#ops-copy-ports')?.addEventListener('click', () => {
      const t = _root._portsCopyText || '';
      navigator.clipboard?.writeText(t).then(
        () => window.showToast?.('已复制端口表', 'success'),
        () => window.showToast?.('复制失败', 'error')
      );
    });
    _root.querySelector('#ops-run-dry')?.addEventListener('click', () => runReview(false));
    _root.querySelector('#ops-run-apply')?.addEventListener('click', () => {
      if (confirm('确认对已登记业务仓执行日审 --apply（仅 C/E/F 可建 ops-auto；禁 orch）？')) {
        runReview(true);
      }
    });
    _root.querySelectorAll('details.ops-fold').forEach((d) => {
      d.addEventListener('toggle', () => persistFold(d));
    });
  }
  await poll();
  if (!_timer) _timer = setInterval(() => poll().catch(() => {}), 30000);
}

export function unmountOps() {
  if (_timer) {
    clearInterval(_timer);
    _timer = null;
  }
}
