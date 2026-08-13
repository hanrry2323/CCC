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

let _root = null;
let _timer = null;

function esc(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

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

  <div class="ops-sys-note">系统健康（节点 / 服务 / 管道 / 中转站）属控制台职责 → <a href="#/console">去控制台</a></div>
</div>`;
}

/* ── ① 项目健康 ─────────────────────────────── */

function projectStats(detail) {
  const counts = (detail && detail.counts) || { planned: 0, doing: 0, done: 0 };
  const total = (counts.done || 0) + (counts.doing || 0) + (counts.planned || 0);
  const risk = ((detail && detail.risks) || []).length;
  return { total, done: counts.done || 0, doing: counts.doing || 0, risk };
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
    el.innerHTML = '<div class="ops-empty">无业务线路数据（roadmap.md 未配置）</div>';
    return;
  }
  const cardsHtml = [];
  for (const rm of roadmaps) {
    const proj = rm.project || '未知';
    const detail = (details || {})[proj];
    if (!detail) continue; // 单项目无业务线路段落（404）时跳过，不整页空白
    const st = projectStats(detail);
    const pct = st.total ? Math.round((st.done / st.total) * 100) : 0;
    const issues = (reviewBy[proj] || 0) + (returnedBy[proj] || 0) + (findingsBy[proj] || 0);
    cardsHtml.push(`<div class="ops-proj-card ${st.risk ? 'risk' : st.total && st.done === st.total ? 'done' : 'active'}">
      <div class="ops-proj-head"><b>${esc(proj)}</b><span>${st.total} 卡</span></div>
      <div class="ops-proj-bar"><div class="ops-proj-fill" style="width:${pct}%"></div></div>
      <div class="ops-proj-stats">
        <span>完成 ${st.done}</span><span>进行中 ${st.doing}</span>
        ${st.risk ? `<span class="ops-proj-risk">风险 ${st.risk}</span>` : ''}
        ${issues ? `<span class="ops-proj-risk">待办 ${issues}</span>` : ''}
      </div>
    </div>`);
  }
  el.innerHTML = cardsHtml.length ? cardsHtml.join('') : '<div class="ops-empty">项目均无业务线路数据</div>';
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
  htmlParts.push(`<div class="ops-subgroup"><h5>打回待处理（${returned.length}）</h5>${returned.length ? returned.slice(0, 12).map((c) => item(c, '<span class="ops-todo-type returned">打回</span>')).join('') : '<div class="ops-empty">无打回卡</div>'}</div>`);
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
  el.innerHTML = htmlParts.length
    ? htmlParts.join('')
    : '<div class="ops-empty">无待审查项 🎉</div>';
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
    el.innerHTML = '<div class="ops-empty">代码健康无发现 🎉 项目治理干净</div>';
    return;
  }
  const adopted = _loadAdopted();
  const byProj = {};
  for (const f of findings) {
    (byProj[f.project || '其他'] = byProj[f.project || '其他'] || []).push(f);
  }
  const typeLabel = {
    missing_section: '缺段落', drift: '状态漂移', broken_link: '关联断裂', missing_four_questions: '维护区缺失',
  };
  const adoptBtn = (f) => {
    const done = adopted.has(f.title || '');
    return `<button type="button" class="hub-btn ops-act ${done ? 'adopted' : 'adopt'}" data-find="${esc(f.title || '')}" data-report="${esc(f._report)}" title="标记已处理（/loop/adopt 留档）" ${done ? 'disabled' : ''}>${done ? '已留档 ✓' : '已处理'}</button>`;
  };
  el.innerHTML = Object.entries(byProj).map(([proj, items]) => `
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
    </div>`).join('');
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
  el.innerHTML = `<div class="ops-loop-progress">
    ${segs.map(([n, label], i) => `
      <span class="ops-loop-seg ${n ? 'on' : ''}">
        <b>${n}</b>${label}
        ${i < segs.length - 1 ? '<i>→</i>' : ''}
      </span>`).join('')}
  </div>`;
}

/* ── poll ────────────────────────────────────── */

async function poll() {
  const [roadmapsData, loop, merge, cardsData] = await Promise.all([
    apiGet('/board/roadmap').catch(() => null),
    apiGet('/loop/findings').catch(() => null),
    apiGet('/board/ready_for_merge').catch(() => null),
    apiGet('/cards?page_size=500').catch(() => null),
  ]);
  const cards = (cardsData && cardsData.cards) || [];
  const roadmaps = (roadmapsData && roadmapsData.roadmaps) || [];
  const details = {};
  if (roadmaps.length) {
    const dets = await Promise.all(roadmaps.map((rm) =>
      apiGet(`/board/roadmap/${encodeURIComponent(rm.project)}`).catch(() => null)));
    roadmaps.forEach((rm, i) => {
      if (dets[i]) details[rm.project] = dets[i];
    });
  }
  renderProjects(roadmaps, details, cards, loop, merge);
  renderReview(merge, cards);
  renderFindings(loop);
  renderLoopProgress(loop, cards, merge);
  const cnt = _root.querySelector('#ops-todo-count');
  if (cnt) {
    const reviewN = ((merge && merge.cards) || []).length + cards.filter((c) => (c.board_column || c.state) === '打回').length;
    const auditN = cards.filter((c) => (c.board_column || c.state) === '机审').length;
    const findN = newFindingsCount(loop);
    cnt.textContent = String(reviewN + auditN + findN);
  }
}

export async function mountOps(el) {
  _root = el;
  el.innerHTML = html();
  el.querySelector('#ops-refresh')?.addEventListener('click', async () => {
    const btn = el.querySelector('#ops-refresh');
    btn.disabled = true;
    await poll();
    btn.disabled = false;
  });
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
