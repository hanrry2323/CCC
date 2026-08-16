/**
 * opsPage.js — 运维页（职责重构 2026-08-12）
 *
 * 运维理念（老板 2026-08-12）：运维 = 项目工程化运维——
 * 项目健康 / diff 审查 / 螺旋循环 / 代码健康监控。
 * 系统健康（节点/服务/管道）是控制台职责，本页只留入口提示。
 *
 * 数据源：
 *   /board/roadmap → 项目业务线路（项目健康）
 *   /board/ready_for_merge → diff 审查队列（待合入）
 *   /cards → 打回卡 / 各状态计数（螺旋循环）
 *   /loop/findings → 代码健康发现（按项目聚合）
 */

import { apiGet, apiPost } from '../api.js';
import { esc, setHtml } from '../ui.js';

let _root = null;
let _timer = null;
let _disposed = false;   // 2026-08-17 M3：卸载置位，异步回来不再写 DOM

function agoText(ts) {
  const sec = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (sec < 60) return '刚刚';
  if (sec < 3600) return `${Math.floor(sec / 60)} 分钟前`;
  if (sec < 86400) return `${Math.floor(sec / 3600)} 小时前`;
  return `${Math.floor(sec / 86400)} 天前`;
}

function html() {
  return `
<div class="ops-page hub-page">
  <div class="ops-bar">
    <h2>运维</h2>
    <span class="ops-sub">项目工程化运维 · diff 审查 · 螺旋循环 · 代码健康</span>
    <span style="flex:1"></span>
    <button type="button" class="hub-btn" id="ops-refresh">刷新</button>
  </div>

  <!-- ① 项目健康 -->
  <div class="ops-section">
    <h3>项目健康 <span class="ops-scan-at" id="ops-scan-at"></span></h3>
    <div id="ops-projects" class="ops-projects-grid"><div class="ops-empty">加载中…</div></div>
  </div>

  <!-- 人审闸门（033 三大人审节点对齐：出卡 / 合入 / 验收） -->
  <div class="ops-section">
    <h3>人审闸门 <span class="ops-scan-at">出卡（已确定→待排期→转卡）→ 合入批准 → 验收拍板 · 老板动作待办</span></h3>
    <div class="ops-todo-grid">
      <div class="ops-card ops-block">
        <h4 class="ops-block-title">① 未排期草案 <span class="badge" id="ops-gate1-count">0</span></h4>
        <div id="ops-gate-drafts"><div class="ops-empty">加载中…</div></div>
      </div>
      <div class="ops-card ops-block">
        <h4 class="ops-block-title">② 出卡待办 <span class="badge" id="ops-gate2-count">0</span></h4>
        <div id="ops-gate-plans"><div class="ops-empty">加载中…</div></div>
      </div>
      <div class="ops-card ops-block">
        <h4 class="ops-block-title">③ 待合入批准 <span class="badge" id="ops-gate3-count">0</span></h4>
        <div id="ops-gate-merge"><div class="ops-empty">加载中…</div></div>
      </div>
      <div class="ops-card ops-block">
        <h4 class="ops-block-title">④ 待验收拍板 <span class="badge" id="ops-gate4-count">0</span></h4>
        <div id="ops-gate-accept"><div class="ops-empty">加载中…</div></div>
      </div>
    </div>
  </div>

  <!-- ② 工程化待办（主区） -->
  <div class="ops-section">
    <h3>工程化待办 <span class="badge" id="ops-todo-count">0</span></h3>
    <div class="ops-todo-grid">
      <div class="ops-card ops-block">
        <h4 class="ops-block-title">diff 审查 <span class="badge" id="ops-review-count">0</span></h4>
        <div id="ops-review"><div class="ops-empty">加载中…</div></div>
      </div>
      <div class="ops-card ops-block">
        <h4 class="ops-block-title">代码健康发现 <span class="badge" id="ops-find-count">0</span></h4>
        <div id="ops-findings"><div class="ops-empty">加载中…</div></div>
      </div>
    </div>
  </div>

  <!-- ③ 螺旋循环 -->
  <div class="ops-section">
    <h3>螺旋循环 <span class="ops-scan-at">发现 → 转卡 → 执行 → 机审 → 合入</span></h3>
    <div id="ops-loop-progress" class="ops-card"><div class="ops-empty">加载中…</div></div>
  </div>

  <!-- 失败原因聚合（第三步 · 挂账 2026-08-08） -->
  <div class="ops-section">
    <h3>失败原因 <span class="ops-scan-at">打回 / 机审不通过 / 执行失败 · 最近 30 条</span></h3>
    <div id="ops-failures" class="ops-card"><div class="ops-empty">加载中…</div></div>
  </div>

  <div class="ops-sys-note">系统健康（节点 / 服务 / 管道 / 中转站）属控制台职责 → <a href="#/console">去控制台</a></div>
</div>`;
}

/* ── ① 项目健康 ─────────────────────────────── */

function projectStats(detail) {
  // P1#15：项目健康迁移到 per-project 新模型（/roadmap/{proj}，里程碑级）。
  // 此前用聚合旧模型 /board/roadmap/{proj}（读 docs/roadmap.md 业务线路段）→ 双解析器双真值
  const miles = (detail && detail.milestones) || [];
  const total = miles.length;
  const done = miles.filter((m) => m.status === '已完成').length;
  const doing = miles.filter((m) => m.status === '进行中').length;
  const risk = miles.filter((m) => m.status === '草案').length;
  return { total, done, doing, risk };
}

function renderProjects(roadmaps, details, cards, loopData, mergeData) {
  const el = _root.querySelector('#ops-projects');
  if (!el) return;
  const returnedBy = {};
  const reviewBy = {};
  for (const c of cards || []) {
    const col = c.board_column || c.state;
    const proj = c.project || '其他';
    if (col === '打回') returnedBy[proj] = (returnedBy[proj] || 0) + 1;
  }
  // 待合入计数源与 diff 审查区强一致（ready_for_merge）
  for (const c of ((mergeData && mergeData.cards) || [])) {
    const proj = c.project || '其他';
    reviewBy[proj] = (reviewBy[proj] || 0) + 1;
  }
  const findingsBy = {};
  const latestFindings = ((loopData && loopData.loop_reports && loopData.loop_reports[0] && loopData.loop_reports[0].findings) || []);
  for (const f of latestFindings) {
    const proj = f.project || '其他';
    findingsBy[proj] = (findingsBy[proj] || 0) + 1;
  }
  if (!roadmaps.length) {
    setHtml(el, '<div class="ops-empty">无业务线路数据（roadmap.md 未配置）</div>');
    return;
  }
  const cardsHtml = [];
  for (const rm of roadmaps) {
    const proj = rm.project || '未知';
    const detail = (details || {})[proj];
    if (!detail) continue; // 单项目无 roadmap.md（404）时跳过，不整页空白
    const st = projectStats(detail);
    const pct = st.total ? Math.round((st.done / st.total) * 100) : 0;
    const issues = (reviewBy[proj] || 0) + (returnedBy[proj] || 0) + (findingsBy[proj] || 0);
    cardsHtml.push(`<div class="ops-proj-card ${st.risk ? 'risk' : st.total && st.done === st.total ? 'done' : 'active'}">
      <div class="ops-proj-head"><b>${esc(proj)}</b><span>${st.total} 里程碑</span></div>
      <div class="ops-proj-bar"><div class="ops-proj-fill" style="width:${pct}%"></div></div>
      <div class="ops-proj-stats">
        <span>完成 ${st.done}</span><span>进行中 ${st.doing}</span>
        ${st.risk ? `<span class="ops-proj-risk">未启动 ${st.risk}</span>` : ''}
        ${issues ? `<span class="ops-proj-risk">待处理 ${issues}</span>` : ''}
      </div>
    </div>`);
  }
  setHtml(el, cardsHtml.length ? cardsHtml.join('') : '<div class="ops-empty">项目均无业务线路数据</div>');
}

/* ── 人审闸门（第三步）─────────────────────── */

const APPROVED_PREFIXES = ['老板确认方案', '老板确认转卡', '老板合入批准', '老板验收拍板'];

function approvalStage(a) {
  if (!a) return '';
  const s = String(a);
  for (const p of APPROVED_PREFIXES) {
    if (s.startsWith(p)) return p;
  }
  return '已批准';
}

function renderHumanGates(roadmaps, plansData, merge) {
  const draftsEl = _root.querySelector('#ops-gate-drafts');
  const plansEl = _root.querySelector('#ops-gate-plans');
  const mergeEl = _root.querySelector('#ops-gate-merge');
  const acceptEl = _root.querySelector('#ops-gate-accept');
  if (!draftsEl || !plansEl || !mergeEl || !acceptEl) return;

  // ① 未排期草案 = 线路图草案池（按项目分组；标签统一「未排期」，033）
  const draftGroups = {};
  for (const rm of roadmaps || []) {
    const drafts = (rm.drafts || []).filter(Boolean);
    if (drafts.length) draftGroups[rm.project] = drafts;
  }
  const draftN = Object.values(draftGroups).flat().length;
  const g1cnt = _root.querySelector('#ops-gate1-count');
  if (g1cnt) g1cnt.textContent = String(draftN);
  setHtml(draftsEl, draftN
    ? Object.entries(draftGroups).map(([proj, items]) => `
      <div class="ops-subgroup">
        <h5>${esc(proj)}（${items.length}）</h5>
        ${items.slice(0, 8).map((t) => `
          <div class="ops-review-item">
            <span class="ops-todo-type pending">未排期</span>
            <span class="ops-review-title">${esc(typeof t === 'string' ? t : (t && t.title || ''))}</span>
            <a class="ops-goto-board" href="#/plans" title="去计划页确认">去处理 →</a>
          </div>`).join('')}
      </div>`).join('')
    : '<div class="ops-empty">草案池空 🎉 无需确认</div>');

  // ② 出卡待办（033）：已确定（待老板确认→待排期）+ 待排期（待转卡）
  const plans = (plansData && plansData.plans) || [];
  const determined = plans.filter((p) => p.status === '已确定');
  const confirmed = plans.filter((p) => p.status === '待排期');
  const g2cnt = _root.querySelector('#ops-gate2-count');
  if (g2cnt) g2cnt.textContent = String(determined.length + confirmed.length);
  setHtml(plansEl, (determined.length || confirmed.length)
    ? [
        ...determined.slice(0, 5).map((p) => `
          <div class="ops-review-item">
            <span class="ops-todo-type pending">已确定</span>
            <span class="ops-review-id">${esc(p.id || '')}</span>
            <span class="ops-review-title">${esc(p.title || '')}</span>
            <span class="ops-review-proj">${esc(p.project || '')}</span>
            <a class="ops-goto-board" href="#/plans" title="去计划页确认到待排期">去处理 →</a>
          </div>`),
        ...confirmed.slice(0, 5).map((p) => `
          <div class="ops-review-item">
            <span class="ops-todo-type pending">待转卡·待排期</span>
            <span class="ops-review-id">${esc(p.id || '')}</span>
            <span class="ops-review-title">${esc(p.title || '')}</span>
            <span class="ops-review-proj">${esc(p.project || '')}</span>
            <a class="ops-goto-board" href="#/plans" title="去计划页转卡">去处理 →</a>
          </div>`),
      ].join('')
    : '<div class="ops-empty">无出卡待办 🎉</div>');

  // ③ 待合入批准 = ready_for_merge
  const mergeCards = ((merge && merge.cards) || []).filter((c) => !String(c.approval || '').includes('合入批准'));
  const g3cnt = _root.querySelector('#ops-gate3-count');
  if (g3cnt) g3cnt.textContent = String(mergeCards.length);
  setHtml(mergeEl, mergeCards.length
    ? mergeCards.slice(0, 10).map((c) => `
      <div class="ops-review-item">
        <span class="ops-todo-type pending">待合入</span>
        <span class="ops-review-id">${esc(c.id || '')}</span>
        <span class="ops-review-title">${esc(c.title || c.intent || '')}</span>
        <span class="ops-review-proj">${esc(c.project || '')}</span>
        <a class="ops-goto-board" href="#/board" title="去看板合入批准">去处理 →</a>
      </div>`).join('')
    : '<div class="ops-empty">无待合入卡 🎉</div>');

  // ④ 待验收拍板（033 新增）：待验收方案（卡全关待老板/验收席拍板）
  const awaitingAccept = plans.filter((p) => p.status === '待验收');
  const g4cnt = _root.querySelector('#ops-gate4-count');
  if (g4cnt) g4cnt.textContent = String(awaitingAccept.length);
  setHtml(acceptEl, awaitingAccept.length
    ? awaitingAccept.slice(0, 10).map((p) => `
      <div class="ops-review-item">
        <span class="ops-todo-type pending">待拍板</span>
        <span class="ops-review-id">${esc(p.id || '')}</span>
        <span class="ops-review-title">${esc(p.title || '')}</span>
        <span class="ops-review-proj">${esc(p.project || '')}</span>
        <a class="ops-goto-board" href="#/plans" title="去计划页验收拍板">去处理 →</a>
      </div>`).join('')
    : '<div class="ops-empty">无待验收方案 🎉</div>');
}

/* ── ② diff 审查 + 代码健康发现 ──────────────── */

function renderReview(mergeData, cards) {
  const el = _root.querySelector('#ops-review');
  const cnt = _root.querySelector('#ops-review-count');
  if (!el) return;
  const mergeCards = (mergeData && mergeData.cards) || [];
  const returned = (cards || []).filter((c) => (c.board_column || c.state) === '打回');
  const auditing = (cards || []).filter((c) => (c.board_column || c.state) === '机审');
  const total = mergeCards.length + returned.length;
  if (cnt) cnt.textContent = String(total);
  const item = (c, tag) => `<div class="ops-review-item">
    <span class="ops-review-id">${esc(c.id || '')}</span>
    <span class="ops-review-title">${esc(c.title || c.intent || '')}</span>
    <span class="ops-review-proj">${esc(c.project || '')}</span>
    ${tag}
    <a class="ops-goto-board" href="#/board" title="去看板处理">去处理 →</a>
  </div>`;
  const htmlParts = [];
  htmlParts.push(`<div class="ops-subgroup"><h5>待合入审查（${mergeCards.length}）</h5>${mergeCards.length ? mergeCards.slice(0, 12).map((c) => item(c, '<span class="ops-todo-type">待合入</span>')).join('') : '<div class="ops-empty">无待合入</div>'}</div>`);
  const returnedItem = (c) => `<div class="ops-review-item">
    <span class="ops-review-id">${esc(c.id || '')}</span>
    <span class="ops-review-title">${esc(c.title || c.intent || '')}</span>
    <span class="ops-review-proj">${esc(c.project || '')}</span>
    <span class="ops-todo-type returned">打回</span>
    ${c.reason ? `<span class="ops-review-reason" title="${esc(c.reason)}">${esc(String(c.reason).slice(0, 30))}${String(c.reason).length > 30 ? '…' : ''}</span>` : ''}
    <a class="ops-goto-board" href="#/board" title="去看板处理">去处理 →</a>
  </div>`;
  htmlParts.push(`<div class="ops-subgroup"><h5>打回待处理（${returned.length}）</h5>${returned.length ? returned.slice(0, 12).map(returnedItem).join('') : '<div class="ops-empty">无打回卡</div>'}</div>`);
  const auditWait = (c) => {
    if (!c.written_at || c.written_at === '未知') return '';
    const d = Math.floor((Date.now() / 1000 - new Date(c.written_at).getTime() / 1000) / 86400);
    return `· 最老等待 ${d < 1 ? '1 天内' : `${d} 天`}`;
  };
  const oldestAudit = auditing.length
    ? auditWait(auditing.reduce((a, b) => ((a.written_at || '') < (b.written_at || '') ? a : b)))
    : '';
  htmlParts.push(`<div class="ops-subgroup"><h5>机审中（${auditing.length}${oldestAudit}）</h5>${auditing.length ? auditing.slice(0, 8).map((c) => `<div class="ops-review-item">
      <span class="ops-review-id">${esc(c.id || '')}</span>
      <span class="ops-review-title">${esc(c.title || c.intent || '')}</span>
      <span class="ops-review-proj">${esc(c.project || '')}</span>
      <span class="ops-todo-type">机审中</span>
    </div>`).join('') : '<div class="ops-empty">无机审中</div>'}</div>`);
  setHtml(el, htmlParts.length
    ? htmlParts.join('')
    : '<div class="ops-empty">无待审查项 🎉</div>');
}

/* 本会话已留档的 finding 标题（sessionStorage 持久化，防重复处理） */
function _loadAdopted() {
  try {
    return new Set(JSON.parse(sessionStorage.getItem('ops-adopted') || '[]'));
  } catch (e) {
    return new Set();
  }
}

function renderFindings(loopData) {
  const el = _root.querySelector('#ops-findings');
  const cnt = _root.querySelector('#ops-find-count');
  if (!el) return;
  const reports = (loopData && loopData.loop_reports) || [];
  const latest = reports[0] || {};
  const reportName = latest.name || '';
  const findings = (latest.findings || []).map((f, i) => ({
    ...f,
    _ts: f.ts || latest.mtime || 0,
    _cmd: (latest.commands || [])[i] || '',
    _report: reportName,
  }));
  if (cnt) cnt.textContent = String(findings.length);
  const scanEl = _root.querySelector('#ops-scan-at');
  if (scanEl) scanEl.textContent = latest.mtime ? `上次巡检 ${agoText(latest.mtime)}` : '';
  if (!findings.length) {
    setHtml(el, '<div class="ops-empty">代码健康无发现 🎉 项目治理干净</div>');
    return;
  }
  const adopted = _loadAdopted();
  const byProj = {};
  for (const f of findings) {
    (byProj[f.project || '其他'] = byProj[f.project || '其他'] || []).push(f);
  }
  const typeLabel = {
    missing_section: '缺段落', drift: '状态漂移', broken_link: '关联断裂', missing_four_questions: '维护区缺失',
    consistency: '一致性', tech: '技术债', scan: '巡查',
  };
  const adoptBtn = (f) => {
    const done = adopted.has(f.title || '');
    return `<button type="button" class="hub-btn ops-act ${done ? 'adopted' : 'adopt'}" data-find="${esc(f.title || '')}" data-report="${esc(f._report)}" title="标记已处理（/loop/adopt 留档）" ${done ? 'disabled' : ''}>${done ? '已留档 ✓' : '已处理'}</button>`;
  };
  setHtml(el, Object.entries(byProj).map(([proj, items]) => `
    <div class="ops-subgroup">
      <h5>${esc(proj)}（${items.length}）</h5>
      ${items.slice(0, 10).map((f) => `
        <div class="ops-review-item">
          <span class="ops-todo-type">${esc(typeLabel[f.type] || '巡查')}</span>
          <span class="ops-review-title">${esc(f.human_title || f.title || '')}</span>
          <span class="ops-review-time">${agoText(f._ts)}</span>
          ${f._cmd ? `<button type="button" class="hub-btn ops-act" data-cmd="${esc(f._cmd)}" title="复制转卡命令">转卡</button>` : ''}
          ${adoptBtn(f)}
        </div>`).join('')}
    </div>`).join(''));
  el.querySelectorAll('button[data-cmd]').forEach((btn) => {
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
  el.querySelectorAll('button.adopt').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const find = btn.getAttribute('data-find') || '';
      const report = btn.getAttribute('data-report') || '';
      if (!find || !report) return;
      btn.disabled = true;
      btn.textContent = '留档中…';
      try {
        await apiPost('/loop/adopt', { report, finding: find, decision: 'adopt', reason: 'ops 页已处理' });
        btn.textContent = '已留档 ✓';
        btn.classList.add('adopted');
        const s = _loadAdopted();
        s.add(find);
        sessionStorage.setItem('ops-adopted', JSON.stringify([...s]));
      } catch (e) {
        btn.textContent = '留档失败';
        btn.disabled = false;
      }
    });
  });
}

/* ── ③ 螺旋循环 ─────────────────────────────── */

/** 本周新增发现数：最新报告 findings 中，title 未在更早报告出现过的（区分存量/增量）。 */
function newFindingsCount(loopData) {
  const reports = (loopData && loopData.loop_reports) || [];
  const latest = reports[0];
  if (!latest || !latest.findings || !latest.findings.length) return 0;
  const fresh = new Set(latest.findings.map((f) => f.title));
  for (const r of reports.slice(1)) {
    for (const f of (r.findings || [])) fresh.delete(f.title);
  }
  return fresh.size;
}

function renderFailures(failuresData) {
  const el = _root.querySelector('#ops-failures');
  if (!el) return;
  const data = failuresData || {};
  const failures = data.failures || [];
  const top = data.top_reasons || [];
  const stageLabel = { run: '执行失败', audit: '机审不通过' };
  const phaseLabel = (p) => stageLabel[p] || '打回';
  setHtml(el, `
    <div class="ops-subgroup">
      <h5>原因 Top（共 ${data.total_fail_events || 0} 条失败事件）</h5>
      ${top.length ? top.slice(0, 5).map((r) => `
        <div class="ops-review-item">
          <span class="ops-todo-type returned">×${r.count}</span>
          <span class="ops-review-title" title="${esc(r.reason)}">${esc(r.reason)}</span>
        </div>`).join('') : '<div class="ops-empty">无失败事件 🎉</div>'}
    </div>
    <div class="ops-subgroup">
      <h5>最近失败（${failures.length}）</h5>
      ${failures.length ? failures.slice(0, 10).map((f) => `
        <div class="ops-review-item">
          <span class="ops-review-id">${esc(f.card_id || '')}</span>
          <span class="ops-todo-type returned">${esc(phaseLabel(f.phase))}</span>
          <span class="ops-review-title" title="${esc(f.problem)}">${esc(String(f.problem || '').slice(0, 40))}${String(f.problem || '').length > 40 ? '…' : ''}</span>
        </div>`).join('') : '<div class="ops-empty">无最近失败 🎉</div>'}
    </div>`);
}

function renderLoopProgress(loopData, cards, mergeData) {
  const el = _root.querySelector('#ops-loop-progress');
  if (!el) return;
  const findingsN = newFindingsCount(loopData);
  const col = (name) => (cards || []).filter((c) => (c.board_column || c.state) === name).length;
  const segs = [
    [findingsN, '发现'],
    [col('待分派'), '转卡'],
    [col('执行中'), '执行'],
    [col('机审'), '机审'],
    [((mergeData && mergeData.count) || 0), '合入'],
  ];
  setHtml(el, `<div class="ops-loop-progress">
    ${segs.map(([n, label], i) => `
      <span class="ops-loop-seg ${n ? 'on' : ''}">
        <b>${n}</b>${label}
        ${i < segs.length - 1 ? '<i>→</i>' : ''}
      </span>`).join('')}
  </div>`);
}

/* ── poll ────────────────────────────────────── */

async function poll() {
  if (_disposed || !_root) return;
  const [roadmapsData, loop, merge, cardsData, plansConfirmed, failuresData] = await Promise.all([
    apiGet('/board/roadmap').catch(() => null),
    apiGet('/loop/findings').catch(() => null),
    apiGet('/board/ready_for_merge').catch(() => null),
    apiGet('/cards?page_size=500').catch(() => null),
    apiGet('/plans/list?status=待排期').catch(() => null),
    apiGet('/ops/failures').catch(() => null),
  ]);
  if (_disposed || !_root) return; // 卸载后回来不再写 DOM
  const cards = (cardsData && cardsData.cards) || [];
  const roadmaps = (roadmapsData && roadmapsData.roadmaps) || [];
  const details = {};
  if (roadmaps.length) {
    // P1#15：详情改用 /roadmap/{proj}（per-project 新模型），与 roadmapPage 同真值；
    // M2 缓存：/roadmap/{proj} TTL 20s（见 api.js CACHEABLE_PREFIXES），消 N+1 重复拉
    const dets = await Promise.all(roadmaps.map((rm) =>
      apiGet(`/roadmap/${encodeURIComponent(rm.project)}`).catch(() => null)));
    if (_disposed || !_root) return;
    roadmaps.forEach((rm, i) => {
      if (dets[i] && !dets[i].error) details[rm.project] = dets[i];
    });
  }
  renderHumanGates(roadmaps, plansConfirmed, merge);
  renderProjects(roadmaps, details, cards, loop, merge);
  renderReview(merge, cards);
  renderFindings(loop);
  renderLoopProgress(loop, cards, merge);
  renderFailures(failuresData);
  if (_disposed || !_root) return;
  const cnt = _root.querySelector('#ops-todo-count');
  if (cnt) {
    const reviewN = ((merge && merge.cards) || []).length + cards.filter((c) => (c.board_column || c.state) === '打回').length;
    const auditN = cards.filter((c) => (c.board_column || c.state) === '机审').length;
    const findN = newFindingsCount(loop);
    cnt.textContent = String(reviewN + auditN + findN);
  }
}

export function mountOps(el, ctx = {}) {
  _root = el;
  _disposed = false;
  el.innerHTML = html();
  el.querySelector('#ops-refresh')?.addEventListener('click', async () => {
    const btn = el.querySelector('#ops-refresh');
    btn.disabled = true;
    await poll();
    btn.disabled = false;
  });
  // M3 非阻塞：同步渲染骨架 → 后台拉数据
  poll();
  // M4 降频：15s → 30s（M2 缓存已让数据快，降频降服务器负载）
  _timer = setInterval(() => {
    if (!_disposed && document.visibilityState === 'visible') poll();
  }, 30000);
}

export function unmountOps() {
  _disposed = true;
  if (_timer) {
    clearInterval(_timer);
    _timer = null;
  }
  _root = null;
}
