/**
 * dshPage.js — DSH 巡回审查报告页（#/dsh · 结论优先）
 *
 * 设计理念（老板 2026-08-15 定）：读重点、读结论，不读全文。
 *   ① 顶部核心结论摘要：红灯/黄旗/蓝旗计数 + 重点面 + 处置汇总 + 报告信息
 *   ② 发现清单：按严重度降序（红旗在顶），低置信度折叠，证据默认折叠
 *   ③ 原始报告：可折叠，不默认展示（含覆盖度自评/读了哪些/推断项）
 *
 * 数据源：GET /ops/dsh-findings（DSH 审计报告 6 列契约）。
 * 人审留档：POST /loop/adopt（source=dsh），复用 ops 页 sessionStorage 模式。
 */

import { apiGet, apiPost } from '../api.js';
import { esc } from '../ui.js';

let _root = null;
let _timer = null;

function agoText(ts) {
  const sec = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (sec < 60) return '刚刚';
  if (sec < 3600) return `${Math.floor(sec / 60)} 分钟前`;
  if (sec < 86400) return `${Math.floor(sec / 3600)} 小时前`;
  return `${Math.floor(sec / 86400)} 天前`;
}

/** 置信度 → pill 类 + 排序权重（高→红旗在最上）。 */
const CONF_META = {
  '高': { cls: 'conf-high', sev: '红旗', order: 0 },
  '中': { cls: 'conf-mid', sev: '黄旗', order: 1 },
  '低': { cls: 'conf-low', sev: '蓝旗', order: 2 },
};

/** 建议处置 → badge 类。 */
const ACTION_CLS = { '改': 'act-fix', '删': 'act-del', '留': 'act-keep' };

function html() {
  return `
<div class="dsh-page hub-page">
  <div class="dsh-bar">
    <h2>DSH 巡检</h2>
    <span class="dsh-sub">DeepSeek Harness 巡回审查 · 只读取证 · 深度巡检</span>
    <span class="dsh-last" id="dsh-last"></span>
    <span style="flex:1"></span>
    <button type="button" class="hub-btn" id="dsh-refresh">刷新</button>
  </div>

  <!-- ① 核心结论摘要（读重点） -->
  <div class="dsh-section dsh-summary" id="dsh-summary">
    <div class="dsh-empty">加载中…</div>
  </div>

  <!-- ② 发现清单（按严重度降序，结论优先） -->
  <div class="dsh-section">
    <h3>发现 <span class="badge" id="dsh-count">0</span> <span class="dsh-scan-at">高/中置信度展示 · 证据默认折叠</span></h3>
    <div id="dsh-findings"><div class="dsh-empty">加载中…</div></div>
  </div>

  <!-- ③ 原始报告（可折叠，不默认展示） -->
  <div class="dsh-section">
    <details class="dsh-raw">
      <summary>完整报告原文（含覆盖度自评 / 读了哪些 / 推断项）</summary>
      <pre id="dsh-raw-content" class="dsh-raw-content"></pre>
    </details>
  </div>
</div>`;
}

function _loadAdopted() {
  try {
    return new Set(JSON.parse(sessionStorage.getItem('dsh-adopted') || '[]'));
  } catch (e) {
    return new Set();
  }
}

/** ① 渲染结论摘要：严重度分布 + 重点面 + 处置汇总 + 报告信息。 */
function renderSummary(findings, report) {
  const el = _root.querySelector('#dsh-summary');
  if (!el) return;
  if (!findings.length) {
    el.innerHTML = '<div class="dsh-empty">DSH 暂无巡检报告 🎉 去麦克2017 跑一单看看</div>';
    return;
  }
  const bySev = { '红旗': 0, '黄旗': 0, '蓝旗': 0 };
  const byAction = { '改': 0, '删': 0, '留': 0 };
  const byFace = {};
  for (const f of findings) {
    const sev = f.severity || CONF_META[f.confidence]?.sev || '蓝旗';
    bySev[sev] = (bySev[sev] || 0) + 1;
    byAction[f.action] = (byAction[f.action] || 0) + 1;
    const face = f.face || '其他';
    byFace[face] = (byFace[face] || 0) + 1;
  }
  const topFaces = Object.entries(byFace).sort((a, b) => b[1] - a[1]).slice(0, 3);
  const stamp = report.mtime ? agoText(report.mtime) : '';
  el.innerHTML = `
    <div class="dsh-summary-cards">
      <div class="dsh-sum-card">
        <b class="dsh-sum-red">${bySev['红旗']}</b><span>红旗</span>
      </div>
      <div class="dsh-sum-card">
        <b class="dsh-sum-yellow">${bySev['黄旗']}</b><span>黄旗</span>
      </div>
      <div class="dsh-sum-card">
        <b class="dsh-sum-blue">${bySev['蓝旗']}</b><span>蓝旗</span>
      </div>
      <div class="dsh-sum-card">
        <b>${findings.length}</b><span>发现总数</span>
      </div>
    </div>
    <div class="dsh-sum-line">
      <span>重点面：</span>
      ${topFaces.length ? topFaces.map(([face, n]) => `<code class="dsh-face">${esc(face)} ×${n}</code>`).join(' ') : '<span>—</span>'}
      <span class="dsh-sum-sep">·</span>
      <span>处置：</span>
      <span class="dsh-act-sum">改 ×${byAction['改'] || 0}</span>
      <span class="dsh-act-sum del">删 ×${byAction['删'] || 0}</span>
      <span class="dsh-act-sum keep">留 ×${byAction['留'] || 0}</span>
    </div>
    <div class="dsh-sum-meta">最新报告 <code>${esc(report.name || '')}</code> · ${findings.length} 条发现 · ${stamp}</div>
  `;
}

/** ② 渲染发现清单：按严重度降序，低置信度折叠，证据默认折叠。 */
function renderFindings(findings, report) {
  const el = _root.querySelector('#dsh-findings');
  const cnt = _root.querySelector('#dsh-count');
  if (!el) return;
  if (cnt) cnt.textContent = String(findings.length);
  if (!findings.length) {
    el.innerHTML = '<div class="dsh-empty">无发现 —— DSH 巡检干净</div>';
    return;
  }
  const adopted = _loadAdopted();
  const reportName = report.name || '';
  // 排序：红旗(0) > 黄旗(1) > 蓝旗(2)；同权重按位置稳定
  const sorted = findings
    .map((f, i) => ({ ...f, _i: i }))
    .sort((a, b) => {
      const oa = CONF_META[a.confidence]?.order ?? 3;
      const ob = CONF_META[b.confidence]?.order ?? 3;
      return oa - ob || a._i - b._i;
    });
  // 高/中置信度展开；低置信度折叠进 details
  const main = sorted.filter((f) => CONF_META[f.confidence]?.order <= 1);
  const low = sorted.filter((f) => CONF_META[f.confidence]?.order >= 2);
  const findingHtml = (f) => {
    const meta = CONF_META[f.confidence] || { cls: 'conf-low', sev: '蓝旗' };
    const actCls = ACTION_CLS[f.action] || '';
    const key = `${f.face}|${f.location}`;
    const done = adopted.has(key);
    const evHtml = f.evidence
      ? `<details class="dsh-evidence"><summary>证据</summary><pre>${esc(f.evidence)}</pre></details>`
      : '';
    const cmd = (f.action === '改' || f.action === '删')
      ? `scripts/new-card.sh --title "修复：${f.location}" --related "dsh: ${reportName}"`
      : '';
    return `
      <div class="dsh-review-item">
        <span class="dsh-pill ${meta.cls}" title="置信度 ${esc(f.confidence)}">${esc(f.confidence)}</span>
        <span class="dsh-act-badge ${actCls}">${esc(f.action || '—')}</span>
        <code class="dsh-loc">${esc(f.location)}</code>
        <span class="dsh-title">${esc(f.phenomenon)}</span>
        ${evHtml}
        ${cmd ? `<button type="button" class="hub-btn dsh-act-copy" data-cmd="${esc(cmd)}" title="复制转卡命令">转卡</button>` : ''}
        <button type="button" class="hub-btn dsh-act-adopt ${done ? 'adopted' : ''}" data-key="${esc(key)}" data-report="${esc(reportName)}" title="标记已处理（/loop/adopt 留档，source=dsh）" ${done ? 'disabled' : ''}>${done ? '已留档 ✓' : '已处理'}</button>
      </div>`;
  };
  let htmlOut = main.map(findingHtml).join('');
  if (low.length) {
    htmlOut += `<details class="dsh-low-group"><summary>低置信度（${low.length}）—— 已折叠</summary>${low.map(findingHtml).join('')}</details>`;
  }
  el.innerHTML = htmlOut || '<div class="dsh-empty">无高/中置信度发现</div>';
  bindButtons(el);
}

function bindButtons(el) {
  el.querySelectorAll('button.dsh-act-copy').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const cmd = btn.getAttribute('data-cmd') || '';
      try {
        await navigator.clipboard.writeText(cmd);
        btn.textContent = '已复制 ✓';
        setTimeout(() => { btn.textContent = '转卡'; }, 1500);
      } catch (e) {
        btn.textContent = '复制失败';
      }
    });
  });
  el.querySelectorAll('button.dsh-act-adopt').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const key = btn.getAttribute('data-key') || '';
      const report = btn.getAttribute('data-report') || '';
      if (!key || !report) return;
      btn.disabled = true;
      btn.textContent = '留档中…';
      try {
        await apiPost('/loop/adopt', { report, finding: key, decision: 'adopt', reason: 'dsh 页已处理', source: 'dsh' });
        btn.textContent = '已留档 ✓';
        btn.classList.add('adopted');
        const s = _loadAdopted();
        s.add(key);
        sessionStorage.setItem('dsh-adopted', JSON.stringify([...s]));
      } catch (e) {
        btn.textContent = '留档失败';
        btn.disabled = false;
      }
    });
  });
}

async function poll() {
  try {
    const data = await apiGet('/ops/dsh-findings');
    const reports = (data && data.dsh_reports) || [];
    const latest = reports[0] || {};
    const findings = (latest.findings || []).map((f) => ({ ...f, _ts: f.ts || latest.mtime || 0 }));
    const lastEl = _root.querySelector('#dsh-last');
    if (lastEl) lastEl.textContent = reports.length
      ? `${reports.length} 份报告 · 最新 ${agoText(latest.mtime || 0)}`
      : '';
    renderSummary(findings, latest);
    renderFindings(findings, latest);
    const rawEl = _root.querySelector('#dsh-raw-content');
    if (rawEl) {
      const text = await (await fetch(latest.path || '')).text().catch(() => '');
      rawEl.textContent = text || '（无原文）';
    }
  } catch (e) {
    const el = _root.querySelector('#dsh-summary');
    if (el) el.innerHTML = '<div class="dsh-empty">加载失败：' + esc(String(e)) + '</div>';
  }
}

export function mountDsh(el) {
  _root = el;
  _root.innerHTML = html();
  const refresh = _root.querySelector('#dsh-refresh');
  if (refresh) refresh.addEventListener('click', poll);
  poll();
  _timer = setInterval(poll, 30000); // DSH 低频，30s 轮询
}

export function unmountDsh() {
  if (_timer) { clearInterval(_timer); _timer = null; }
  _root = null;
}
