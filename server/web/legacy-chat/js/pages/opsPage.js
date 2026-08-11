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
    <h3>待办清单 <span class="badge" id="loop-count">0</span></h3>
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
  el.innerHTML = `
    <div class="ops-dash">
      <div class="ops-dash-status ${sevCls}">
        <span class="ops-dash-dot"></span>
        <strong>${esc(healthLabel(severity))}</strong>
      </div>
      <div class="ops-dash-line">${esc(human)}</div>
      <div class="ops-dash-stats">
        <span class="ops-dash-stat">${total > 0 ? `${reachable}/${total} 节点在线` : '无节点配置'}</span>
        ${alerts > 0 ? `<span class="ops-dash-stat alert">${alerts} 项告警</span>` : '<span class="ops-dash-stat">无告警</span>'}
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
  if (!findings.length) {
    el.innerHTML = '<div class="ops-empty">没有待处理事项 🎉 集群一切正常</div>';
    return;
  }
  // 按风险等级排序（r1 高风险 → r2 风险 → r3 建议），同级按时间新→旧
  const order = { r1: 0, r2: 1, r3: 2 };
  findings.sort((a, b) => order[riskOf(a)] - order[riskOf(b)] || (b._ts || 0) - (a._ts || 0));
  el.innerHTML = findings
    .slice(0, 12)
    .map((f) => {
      const r = riskOf(f);
      const t = typeOf(f);
      const cmd = f._cmd || '';
      return `<div class="ops-todo-item ${r}">
        <span class="ops-priority ${r}">${riskLabel(r)}</span>
        <div class="ops-todo-body">
          <div class="ops-todo-title">${esc(summarizeFinding(f.title))}</div>
          <div class="ops-todo-meta">
            <span class="ops-todo-type">${esc(t)}</span>
            <span class="ops-todo-proj">${esc(f.project || '')}</span>
            <span class="ops-todo-time" title="${esc(f._ts ? new Date(f._ts * 1000).toLocaleString() : '')}">扫描于 ${agoText(f._ts)}</span>
            ${f.acting_on ? `<code>${esc(f.acting_on)}</code>` : ''}
          </div>
          ${cmd ? `<button type="button" class="hub-btn" data-cmd="${esc(cmd)}" title="复制转卡命令到 M1 执行">转卡</button>` : ''}
        </div>
      </div>`;
    })
    .join('');
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
