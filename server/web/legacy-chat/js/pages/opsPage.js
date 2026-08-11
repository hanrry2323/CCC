/**
 * opsPage.js — 运维页（用户化重构 2026-08-11）
 *
 * 三层架构（数据源：/ops/summary + /loop/findings，纯前端不改后端）：
 *   ① 健康仪表盘：severity + human_line → 一句话结论 + 色块
 *   ② 待办清单：findings → 优先级(P1/P2/P3) + 人话摘要 + 操作按钮
 *   ③ 技术详情：节点/端口/证据/命令 → 折叠，运维人员才展开
 *
 * 设计原则：用户看「哪坏了、要紧不、要不要修」，Agent 细节折叠在后面。
 */

import { apiGet, apiPost } from '../api.js';

let _root = null;
let _timer = null;
let _loopData = null;
let _showAll = false;

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
  <div class="ops-bar">
    <h2>运维</h2>
    <span class="ops-sub">集群健康 · 待办 · 详情</span>
    <span style="flex:1"></span>
    <button type="button" class="hub-btn" id="ops-refresh">刷新</button>
  </div>

  <!-- ① 健康仪表盘 -->
  <div class="ops-section">
    <div id="ops-status" class="ops-card ops-status-bar"></div>
  </div>

  <!-- ② 待办清单 -->
  <div class="ops-section">
    <h3>待办清单 <span class="badge" id="loop-count">0</span> <span class="ops-scan-at" id="loop-scan-at"></span></h3>
    <div id="ops-loop" class="ops-card"><div class="ops-empty">加载中…</div></div>
  </div>

  <!-- ③ 技术详情（折叠） -->
  <div class="ops-section">
    <details class="ops-fold">
      <summary>技术详情（节点 / 端口 / 原始命令）</summary>
      <div id="ops-detail" class="ops-detail-body">
        <div id="ops-machines" class="ops-card"></div>
      </div>
    </details>
  </div>
</div>`;
}

/* ── ① 健康仪表盘 ─────────────────────────────── */

function healthLabel(severity) {
  if (severity === 'green') return '健康';
  if (severity === 'amber') return '有注意项';
  if (severity === 'red') return '有问题';
  return '未知';
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
  const alerts = overview.alert_count || 0;
  const services = overview.services || [];
  const svcRunning = services.filter((s) => s.running).length;
  const pipe = agg.pipeline || {};
  const pipeOk = pipe.git_sync_ok !== false && !(pipe.probe_skips || 0) && !(pipe.none_skips || 0);
  const clusterCls = reachable === total ? 'ok' : reachable === 0 ? 'attn' : 'warn';
  const svcCls = svcRunning === services.length ? 'ok' : 'attn';
  el.innerHTML = `
    <div class="ops-dash">
      <div class="ops-dash-status ${sevCls}">
        <span class="ops-dash-dot"></span>
        <strong>${esc(healthLabel(severity))}</strong>
      </div>
      <div class="ops-dash-line">${esc(human)}</div>
      <div class="ops-dash-grid">
        <div class="ops-dash-card ${clusterCls}">
          <span class="ops-dash-card-label">集群</span>
          <strong>${total > 0 ? `${reachable}/${total} 节点在线` : '无节点配置'}</strong>
          <span class="ops-dash-card-note">${alerts > 0 ? `${alerts} 项告警` : '无告警'}</span>
        </div>
        <div class="ops-dash-card ${svcCls}">
          <span class="ops-dash-card-label">服务</span>
          <strong>${services.length ? `${svcRunning}/${services.length} 运行` : '未配置服务'}</strong>
          <span class="ops-dash-card-note">${services.length ? 'pgrep 进程检测' : 'CLUSTER_SERVICES 未配置'}</span>
        </div>
        <div class="ops-dash-card ${pipeOk ? 'ok' : 'warn'}">
          <span class="ops-dash-card-label">管道</span>
          <strong>${pipe.git_sync_ok === false ? 'git sync 失败' : '引擎管道正常'}</strong>
          <span class="ops-dash-card-note">${(pipe.probe_skips || 0) ? `探活跳过 ${pipe.probe_skips}` : ''}${(pipe.probe_skips || 0) && (pipe.none_skips || 0) ? ' · ' : ''}${(pipe.none_skips || 0) ? `未派发绑定 ${pipe.none_skips}` : ''}</span>
        </div>
      </div>
    </div>`;
}

/* ── ② 待办清单 ───────────────────────────────── */

/** 权重 → 优先级（D2 映射：≥4=P1红, 2-3=P2橙, <2=P3蓝） */
function priorityOf(weightStr) {
  const w = parseFloat(weightStr);
  if (isNaN(w)) return 'p3';
  if (w >= 4) return 'p1';
  if (w >= 2) return 'p2';
  return 'p3';
}

/** 后台 severity → 用户风险标签（双维标签之「风险等级」） */
function riskOf(f) {
  const sev = f.severity || '';
  if (sev === '红旗') return 'r1';
  if (sev === '黄旗') return 'r2';
  if (sev === '蓝旗') return 'r3';
  // 无 severity 时用 weight 兜底
  return priorityOf(f.weight);
}

function riskLabel(r) {
  return { r1: '高风险', r2: '风险', r3: '建议' }[r] || '建议';
}

/** 后台 type 或标题 → 用户巡查类型标签（双维标签之「类型」） */
function typeOf(f) {
  const t = f.type || '';
  if (t) {
    return (
      {
        missing_section: '缺失项',
        drift: '状态漂移',
        broken_link: '关联断裂',
        missing_four_questions: '维护区缺失',
      }[t] || '巡查项'
    );
  }
  // 无 type 时从标题推导
  const title = f.title || '';
  if (title.includes('状态漂移') || title.includes('已交付')) return '状态漂移';
  if (title.includes('缺席') || title.includes('缺少')) return '缺失项';
  if (title.includes('关联了不存在') || title.includes('未全部关闭')) return '关联断裂';
  if (title.includes('维护区')) return '维护区缺失';
  return '巡查项';
}

/** 把技术化长标题归纳成用户能看懂的一句话 */
function summarizeFinding(title) {
  if (!title) return '';
  let t = String(title);
  t = t.replace(/^任务卡\s*([a-z0-9]+)\s*状态漂移：/, '$1 状态漂移：');
  t = t.replace(/roadmap\.md\s*标注/, '标注');
  t = t.replace(/看板\/卡文件实际状态/, '实际');
  t = t.replace(/项目\s*([a-z0-9]+)\s*缺席 roadmap\.md 的业务线路段落/, '$1 项目缺少路线图段落');
  t = t.replace(/方案\s*([a-z0-9\-]+)\s*已完成但关联卡未关闭/, '$1 方案已完成但卡未关');
  t = t.replace(/卡\s*([a-z0-9]+)\s*缺维护区四问/, '$1 卡缺维护区填写');
  if (t.length > 40) t = t.slice(0, 40) + '…';
  return t;
}

function renderLoop(loopData) {
  const el = _root.querySelector('#ops-loop');
  const nEl = _root.querySelector('#loop-count');
  if (!el) return;
  _loopData = loopData;
  const reports = loopData?.loop_reports || [];
  // 只取最新一份报告（每份是"当时全量扫描"，最新代表当前真实状态；旧报告是过期快照，避免残留误报）
  const latest = reports[0] || {};
  const _cmds = latest.commands || [];
  const findings = (latest.findings || []).map((f, i) => ({
    ...f,
    _report: latest.name,
    _ts: f.ts || latest.mtime || 0,
    _cmd: _cmds[i] || '',
  }));
  if (nEl) nEl.textContent = String(findings.length);
  const scanEl = _root.querySelector('#loop-scan-at');
  if (scanEl) {
    scanEl.textContent = latest.mtime ? `上次扫描 ${agoText(latest.mtime)}` : '';
  }
  if (!findings.length) {
    el.innerHTML = '<div class="ops-empty">没有待处理事项 🎉 集群一切正常</div>';
    return;
  }
  // 按风险等级排序（r1 高风险 → r2 风险 → r3 建议），同级按时间新→旧
  const order = { r1: 0, r2: 1, r3: 2 };
  findings.sort((a, b) => order[riskOf(a)] - order[riskOf(b)] || (b._ts || 0) - (a._ts || 0));
  const shown = _showAll ? findings : findings.slice(0, 12);
  el.innerHTML = shown
    .map((f) => {
      const r = riskOf(f);
      const t = typeOf(f);
      const cmd = f._cmd || '';
      return `<div class="ops-todo-item ${r}">
        <span class="ops-priority ${r}">${riskLabel(r)}</span>
        <div class="ops-todo-body">
          <div class="ops-todo-title">${esc(f.human_title || summarizeFinding(f.title))}</div>
          <div class="ops-todo-meta">
            <span class="ops-todo-type">${esc(t)}</span>
            <span class="ops-todo-proj">${esc(f.project || '')}</span>
            <span class="ops-todo-time" title="${esc(f._ts ? new Date(f._ts * 1000).toLocaleString() : '')}">扫描于 ${agoText(f._ts)}</span>
            ${f.acting_on ? `<code>${esc(f.acting_on)}</code>` : ''}
          </div>
          ${cmd ? `<button type="button" class="hub-btn" data-cmd="${esc(cmd)}" title="复制转卡命令到 M1 执行">转卡</button>` : ''}
          <span class="ops-todo-actions">
            <button type="button" class="hub-btn ops-act" data-adopt="${esc(f.title)}" data-decision="adopt" title="采纳为真问题，留档">采纳</button>
            <button type="button" class="hub-btn ops-act" data-adopt="${esc(f.title)}" data-decision="reject" title="标记已处理/忽略，留档">已处理</button>
          </span>
        </div>
      </div>`;
    })
    .join('')
    + (findings.length > 12 ? `<button type="button" class="hub-btn" id="ops-todo-more">${_showAll ? '收起' : `展开全部（${findings.length} 条）`}</button>` : '');
  // 绑定「转卡」按钮：点击复制命令 + 提示
  el.querySelectorAll('button[data-cmd]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const cmd = btn.getAttribute('data-cmd');
      try {
        navigator.clipboard.writeText(cmd);
        btn.textContent = '已复制 ✓';
        setTimeout(() => { btn.textContent = '转卡'; }, 1500);
      } catch (e) {
        btn.textContent = '复制失败';
      }
    });
  });
  // 「采纳/已处理」→ POST /loop/adopt 留档（只记录，不自动出卡/不隐藏条目）
  el.querySelectorAll('button[data-adopt]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const report = _loopData?.loop_reports?.[0]?.name || '';
      const finding = btn.getAttribute('data-adopt') || '';
      const decision = btn.getAttribute('data-decision') || 'reject';
      btn.disabled = true;
      try {
        await apiPost('/loop/adopt', {
          report,
          finding,
          decision,
          reason: '运维页人工操作',
        });
        btn.textContent = '已留档 ✓';
        setTimeout(() => { btn.textContent = decision === 'adopt' ? '采纳' : '已处理'; btn.disabled = false; }, 1500);
      } catch (e) {
        btn.textContent = '留档失败';
        btn.disabled = false;
      }
    });
  });
  const moreBtn = el.querySelector('#ops-todo-more');
  if (moreBtn) {
    moreBtn.addEventListener('click', () => {
      _showAll = !_showAll;
      if (_loopData) renderLoop(_loopData);
    });
  }
}

/** 时间戳 → 「X 分钟/小时前」 */
function agoText(ts) {
  const sec = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (sec < 60) return '刚刚';
  if (sec < 3600) return `${Math.floor(sec / 60)} 分钟前`;
  if (sec < 86400) return `${Math.floor(sec / 3600)} 小时前`;
  return `${Math.floor(sec / 86400)} 天前`;
}

/* ── ③ 技术详情（折叠） ────────────────────────── */

function renderMachines(agg) {
  const el = _root.querySelector('#ops-machines');
  if (!el) return;
  const overview = agg.overview || {};
  const machines = overview.machines || [];
  if (!machines.length) {
    el.innerHTML = '<div class="ops-empty">未配置集群节点</div>';
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
      el.innerHTML = `<div class="ops-empty">待办清单加载失败: ${esc(err?.message || String(err))}</div>`;
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
