/** Hub Ops page — cluster / ports / diff / daily-review / risks */

import { apiGet, apiPost } from '../api.js';

let _root = null;
let _timer = null;

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

function html() {
  return `
<div class="ops-page">
  <div class="ops-bar">
    <h2>运维</h2>
    <span class="ops-sub">集群 · 端口 · Diff · 日审 · 知识库</span>
    <span style="flex:1"></span>
    <a class="hub-btn" href="#/console">控制台</a>
    <button type="button" class="hub-btn" id="ops-refresh">刷新</button>
  </div>

  <div class="ops-section">
    <h3>A. 集群总览 <span class="badge" id="ops-alert-n">0</span></h3>
    <div class="ops-machines" id="ops-machines"></div>
  </div>

  <div class="ops-section">
    <h3>B. 端口与服务
      <button type="button" class="hub-btn" id="ops-copy-ports" style="margin-left:8px">复制端口表</button>
    </h3>
    <p class="ops-hint">SSOT：<code id="ops-infra-path">.ccc/infrastructure.md</code>（勿在 UI 硬编码端口）</p>
    <div id="ops-ports"></div>
  </div>

  <div class="ops-grid-2">
    <div class="ops-section">
      <h3>C. 本机资源</h3>
      <div id="ops-resources" class="ops-card"></div>
    </div>
    <div class="ops-section">
      <h3>H. 生产/部署视角</h3>
      <div id="ops-deploy" class="ops-card"></div>
    </div>
  </div>

  <div class="ops-section">
    <h3>D. Diff 与工作区</h3>
    <div id="ops-workspaces"></div>
  </div>

  <div class="ops-section">
    <h3>E. 日审报告
      <button type="button" class="hub-btn" id="ops-run-dry">再跑一次</button>
      <button type="button" class="hub-btn primary" id="ops-run-apply">应用建卡</button>
    </h3>
    <div id="ops-daily" class="ops-card"></div>
  </div>

  <div class="ops-grid-2">
    <div class="ops-section">
      <h3>F. 风险与建议 <span class="badge" id="ops-risk-n">0</span></h3>
      <div id="ops-risks"></div>
    </div>
    <div class="ops-section">
      <h3>G. 知识库健康</h3>
      <div id="ops-kb"></div>
    </div>
  </div>

  <div class="ops-grid-2">
    <div class="ops-section">
      <h3>I. 文档债</h3>
      <div id="ops-docs"></div>
    </div>
    <div class="ops-section">
      <h3>J. Ops 队列表 <span class="badge" id="ops-auto-n">0</span></h3>
      <div id="ops-auto"></div>
    </div>
  </div>

  <div class="ops-section">
    <h3>质量日摘要
      <button type="button" class="hub-btn" id="ops-quality-refresh">刷新</button>
    </h3>
    <div id="ops-quality"></div>
  </div>
</div>`;
}

function renderMachines(d) {
  const el = _root.querySelector('#ops-machines');
  const n = _root.querySelector('#ops-alert-n');
  if (n) n.textContent = String(d.alert_count ?? 0);
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

function renderResources(d) {
  const el = _root.querySelector('#ops-resources');
  const load = d.load || {};
  const mem = d.memory || {};
  const disk = d.disk || {};
  el.innerHTML = `
    <div><b>${esc(d.host || '本机')}</b></div>
    <div class="ops-kv">Load ${esc(load['1']?.toFixed?.(2) ?? load['1'] ?? '—')} / ${esc(load['5']?.toFixed?.(2) ?? '—')} / ${esc(load['15']?.toFixed?.(2) ?? '—')}</div>
    <div class="ops-kv">内存 ${esc(mem.used_pct != null ? mem.used_pct + '%' : '—')} · ${esc(fmtBytes(mem.used_bytes))} / ${esc(fmtBytes(mem.total_bytes))}</div>
    <div class="ops-kv">磁盘 ${esc(disk.used_pct != null ? disk.used_pct + '%' : '—')} · 可用 ${esc(fmtBytes(disk.free_bytes))}</div>`;
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
    <th>仓</th><th>分支</th><th>dirty</th><th>ahead</th><th>behind</th><th>摘要</th>
  </tr></thead><tbody>${rows
    .map((w) => {
      const sample = (w.dirty_sample || []).slice(0, 3).map(esc).join('<br>') || '—';
      return `<tr>
        <td><b>${esc(w.id)}</b><div class="muted mono small">${esc(w.path)}</div></td>
        <td class="mono">${esc(w.branch || '—')}</td>
        <td>${esc(w.dirty ?? '—')}</td>
        <td>${esc(w.ahead ?? 0)}</td>
        <td>${esc(w.behind ?? 0)}</td>
        <td class="mono small">${sample}</td>
      </tr>`;
    })
    .join('')}</tbody></table>`;
}

function renderDaily(d) {
  const el = _root.querySelector('#ops-daily');
  const latest = d.latest;
  if (!latest) {
    el.innerHTML = '<div class="ops-empty">尚无 daily-review 报告</div>';
    return;
  }
  const body = (d.latest_body || '').slice(0, 6000);
  el.innerHTML = `
    <div class="ops-kv"><b>${esc(latest.name)}</b> · ${esc(latest.workspace)} · ${esc(latest.mtime)}</div>
    <div class="muted mono small">${esc(latest.path)}</div>
    <pre class="ops-pre">${esc(body)}</pre>`;
}

function renderRisks(d) {
  const el = _root.querySelector('#ops-risks');
  const n = _root.querySelector('#ops-risk-n');
  if (n) n.textContent = String(d.count ?? 0);
  const risks = d.risks || [];
  if (!risks.length) {
    el.innerHTML = '<div class="ops-empty">当前无聚合风险</div>';
    return;
  }
  el.innerHTML = risks
    .map((r) => {
      const sev = esc(r.severity || 'info');
      return `<div class="ops-risk sev-${sev}">
        <div class="title">${esc(r.title)}</div>
        <div class="meta">${esc(r.source)} · ${sev}${r.workspace ? ' · ' + esc(r.workspace) : ''}</div>
        <div class="detail">${esc(r.detail || '')}</div>
        ${
          r.title && !String(r.id || '').startsWith('engine')
            ? `<button type="button" class="hub-btn ops-adopt-btn" data-title="${esc(r.title)}" data-detail="${esc(r.detail || '')}" data-ws="${esc(r.workspace || 'CCC')}">采纳为任务</button>`
            : ''
        }
      </div>`;
    })
    .join('');
  el.querySelectorAll('.ops-adopt-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        await apiPost('/api/ops/adopt', {
          workspace: btn.dataset.ws || 'CCC',
          title: btn.dataset.title || 'ops suggestion',
          description: btn.dataset.detail || '',
          tags: ['ops-auto', 'from-risk'],
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
    .map(
      (f) => `<div class="ops-risk sev-${esc(f.severity || 'low')}">
      <div class="title">${esc(f.title)}</div>
      <div class="detail">${esc(f.suggestion || '')}</div>
      <button type="button" class="hub-btn ops-adopt-btn" data-title="${esc('文档: ' + (f.title || ''))}" data-detail="${esc(f.suggestion || '')}" data-ws="${esc(f.workspace || 'CCC')}">采纳为任务</button>
    </div>`
    )
    .join('');
  el.querySelectorAll('.ops-adopt-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        await apiPost('/api/ops/adopt', {
          workspace: btn.dataset.ws || 'CCC',
          title: btn.dataset.title,
          description: btn.dataset.detail || '',
          tags: ['ops-auto', 'docs'],
        });
        window.showToast?.('已入队', 'success');
        await poll();
      } catch (e) {
        window.showToast?.(e.message || '失败', 'error');
        btn.disabled = false;
      }
    });
  });
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

function renderQuality(d) {
  const el = _root.querySelector('#ops-quality');
  const rows = d.workspaces || [];
  el.innerHTML =
    `<p class="ops-hint">${esc(d.note || '')}</p>` +
    (rows
      .map((w) => {
        const commits = (w.commit_sample || []).map(esc).join('<br>') || '—';
        return `<div class="ops-card" style="margin-bottom:8px">
        <b>${esc(w.workspace)}</b> · 24h commits ${esc(w.commits_24h)} · released ${esc(w.released_total)}
        <div class="mono small">${commits}</div>
        <button type="button" class="hub-btn ops-adopt-btn" data-title="${esc('质量跟进: ' + w.workspace)}" data-detail="${esc((w.commit_sample || []).join('\\n'))}" data-ws="${esc(w.workspace)}">建议入队打磨</button>
      </div>`;
      })
      .join('') || '<div class="ops-empty">无摘要</div>');
  el.querySelectorAll('.ops-adopt-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        await apiPost('/api/ops/adopt', {
          workspace: btn.dataset.ws || 'CCC',
          title: btn.dataset.title,
          description: btn.dataset.detail || '',
          tags: ['ops-auto', 'quality'],
        });
        window.showToast?.('已入队打磨任务', 'success');
        await poll();
      } catch (e) {
        window.showToast?.(e.message || '失败', 'error');
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
  // Phase 3.2: 11 次 GET → 单次聚合端点 /api/ops/summary
  const agg = await _safeGet('/api/ops/summary', null);
  if (!agg) return;

  // overview + ports 单独渲染（含交互按钮）
  renderMachines(agg.overview || { machines: [], alert_count: 0 });
  renderPorts(agg.ports || { groups: [] });

  renderResources(agg.resources || {});
  renderWorkspaces(agg.workspaces || { workspaces: [] });
  renderDaily(agg.daily || {});
  renderRisks(agg.risks || { count: 0, risks: [] });
  renderKb(agg.kb || { services: [] });
  renderDeploy(agg.deploy || { targets: [] });
  renderDocs(agg.docs || { findings: [] });
  renderAuto(agg.auto || { tasks: [] });
  renderQuality(agg.quality || { workspaces: [] });
}

async function runReview(apply) {
  try {
    const r = await apiPost('/api/ops/daily-review/run', { workspace: 'CCC', apply });
    if (r.ok) {
      window.showToast?.(apply ? '已 apply（见 spawn）' : 'dry-run 完成', 'success');
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
    _root.querySelector('#ops-copy-ports').addEventListener('click', () => {
      const t = _root._portsCopyText || '';
      navigator.clipboard?.writeText(t).then(
        () => window.showToast?.('已复制端口表', 'success'),
        () => window.showToast?.('复制失败', 'error')
      );
    });
    _root.querySelector('#ops-run-dry').addEventListener('click', () => runReview(false));
    _root.querySelector('#ops-run-apply').addEventListener('click', () => {
      if (confirm('确认对 CCC workspace 执行日审 --apply（可建 ops-auto 卡）？')) {
        runReview(true);
      }
    });
    _root.querySelector('#ops-quality-refresh')?.addEventListener('click', async () => {
      try {
        renderQuality(await apiGet('/api/ops/quality'));
      } catch (_) {
        /* ignore */
      }
    });
  }
  await poll();
  // Phase 3.2: polling 20s → 30s（聚合端点 + DOM diff 已降负载）
  if (!_timer) _timer = setInterval(() => poll().catch(() => {}), 30000);
}

export function unmountOps() {
  if (_timer) {
    clearInterval(_timer);
    _timer = null;
  }
}
