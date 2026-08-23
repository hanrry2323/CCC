/**
 * plansPage.js — 计划页面（#/plans · 方案池）
 *
 * 设计：方案池 = 四态流水线看板（与看板页同语言）。
 * 列 = 状态（待排期/部分执行/已完成/作废），列内为紧凑方案条目：
 * 项目徽标 + 编号 + 标题 + 作者/工具 + 验收进度条 + 关联卡。
 * 项目筛选为看板同款按钮组；点击条目进详情面板。
 *
 * 数据源：GET /plans/list?project=&status=&q=
 * 详情：GET /plans/detail?path=...
 * 新建：POST /plans/create {project, title, content, author, tool}
 * 更新：POST /plans/update {path, status?, content?, cards?}
 * 转卡：POST /plans/convert {path}
 */

import { apiGet, apiPost } from '../api.js';
import { esc } from '../ui.js';

const STATUSES = ['已确定', '待排期', '部分执行', '待验收', '已完成', '作废'];
// 状态色：六态分类标识色板（集中定义；语义近似项已对齐令牌色系，
// 分类身份色保留字面量——用于列边框/徽章的类别区分，非主题语义）
const STATUS_COLORS = {
  '已确定': '#7a6cc4',
  '待排期': '#3d9a5f',
  '部分执行': '#c47a2c',
  '待验收': '#3d7cc4',
  '已完成': '#5a7a9a',
  '作废': '#b0563f',
};

const PROJECT_COLORS = {
  ccc: '#c96442',
  qb: '#3d9a5f',
  xy: '#5a7a9a',
  mx: '#8b6cc1',
  hp: '#c47a2c',
  clw: '#0f9f8f',
  tst: '#73726c',
};
const PROJECT_COLOR_FALLBACK = ['#5a7a9a', '#8b6cc1', '#3d9a5f', '#c47a2c', '#c96442'];

function projectColor(prefix) {
  if (PROJECT_COLORS[prefix]) return PROJECT_COLORS[prefix];
  let h = 0;
  for (const ch of String(prefix || '')) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return PROJECT_COLOR_FALLBACK[h % PROJECT_COLOR_FALLBACK.length];
}

let _root = null;
let _timer = null;
let _disposed = false;   // 2026-08-17 M3：卸载置位，异步回来不再写 DOM
let _plans = [];
let _cardStates = {};   // card_id → 实时状态（关联卡徽标）
let _planCardStates = {}; // plan_path → {total, cols}（流程条，/plans/card-states）
let _filterProject = '';
let _projects = [];
let _projectDisplay = {}; // prefix → 展示名
let _detailPath = null;  // 当前打开的详情路径，null=列表视图
let _formOpen = false;   // 新建表单是否打开
// 2026-08-24：显示已完成开关与搜索框按老板指令移除——六列恒全展示
let _colSigs = {};       // status → 列渲染签名（M4：数据没变不重建列 DOM）

// ── 工具 ──

/** 内联 SVG 图标（lucide 风格，stroke=currentColor，16px） */
function icon(name) {
  const p = {
    search: '<circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.4" y2="16.4"/>',
    plus: '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    back: '<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>',
    open: '<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>',
    convert: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    edit: '<path d="M17 3a2.8 2.8 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z"/>',
    file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
    tag: '<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.83z"/><line x1="7" y1="7" x2="7.01" y2="7"/>',
    check: '<polyline points="20 6 9 17 4 12"/>',
    close: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
  };
  const body = p[name] || '';
  return `<svg class="plans-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
}

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

function _globalKeydown(e) {
  if (e.key !== 'Escape' || !_formOpen) return;
  _formOpen = false;
  const overlay = _root?.querySelector('#plans-form-overlay');
  if (overlay) overlay.style.display = 'none';
}

// ── API ──

async function loadProjects() {
  try {
    const data = await apiGet('/projects');
    _projects = (data.projects || []).filter(p => p.is_taskable && p.prefix);
    _projectDisplay = {};
    for (const p of _projects) _projectDisplay[p.prefix] = p.display || p.name || p.prefix;
  } catch (e) {
    _projects = [];
  }
}

async function loadCards() {
  try {
    const data = await apiGet('/cards?page_size=500');
    _cardStates = {};
    for (const c of (data.cards || [])) {
      if (c && c.id) _cardStates[String(c.id).toLowerCase()] = c.state || '';
    }
  } catch (e) {
    _cardStates = {};
  }
}

async function loadPlans() {
  try {
    // M2：并行拉（原 /projects→/cards 串行 + plans 两个接口）；M2 缓存让命中零网络
    const [projData, cardsData, listData, statesData] = await Promise.all([
      _projects.length ? Promise.resolve() : apiGet('/projects'),
      apiGet('/cards?page_size=500'),
      apiGet('/plans/list'),
      apiGet('/plans/card-states').catch(() => null),
    ]);
    if (_disposed) return; // 卸载后回来不再写 DOM
    if (projData) {
      _projects = (projData.projects || []).filter(p => p.is_taskable && p.prefix);
      _projectDisplay = {};
      for (const p of _projects) _projectDisplay[p.prefix] = p.display || p.name || p.prefix;
    }
    _cardStates = {};
    for (const c of (cardsData.cards || [])) {
      if (c && c.id) _cardStates[String(c.id).toLowerCase()] = c.state || '';
    }
    _plans = (listData.plans || []);
    _planCardStates = (statesData && statesData.states) || {};
  } catch (e) {
    // M3：切页 pageScopeAbort 主动中止是预期行为，不打 error 噪音
    if (!(e && e.name === 'AbortError')) console.error('plans: load failed', e);
    // 2026-08-24 修复：瞬时失败不再清空已有方案池（原实现把完好数据清成
    // 「暂无方案」空看板直到下一轮成功）；首载尚无数据时才落空态
    if (!_plans.length) _planCardStates = {};
  }
  if (_disposed) return;
  if (_detailPath || _formOpen) {
    updateListOnly();
    return;
  }
  // 2026-08-24 修复：30s 轮询不再整页重建。壳（含搜索框/工具栏）只在首次构建；
  // 壳已存在时只刷列表列，防搜索输入焦点丢失、滚动跳顶、拖拽中断。
  if (_root.querySelector('#plans-flow')) {
    renderFlow();
    applyFlowColumns();
  } else {
    render();
  }
  _applyDeepLink(); // 数据到达后应用深链（M3 非阻塞：首帧 _plans 已就绪）
}

// ── 筛选（客户端，列即状态） ──

function filteredPlans() {
  return _plans.filter(p => !_filterProject || p.project === _filterProject);
}

// ── render ──

function renderPlanItem(plan) {
  const color = STATUS_COLORS[plan.status] || 'var(--ccc-text-faint)';
  const projColor = projectColor(plan.project);
  const projTint = projColor + '1f';
  const acc = plan.acceptance || {};
  const accPct = acc.total > 0 ? Math.round((acc.done / acc.total) * 100) : null;
  const cardsText = plan.cards && plan.cards !== '无' ? plan.cards : '';
  // 业务标签（老板 2026-08-12 评审）：计划 / 缺口 / 警示，不展示用户看不懂的卡 ID+状态
  const tags = [];
  const refIds = (cardsText ? cardsText.split(/[,，、\s]+/) : []).filter(Boolean);
  const warnRefs = refIds.filter((cid) => {
    const st = _cardStates[String(cid).toLowerCase()] || '';
    return !st || !/已关闭|已合入|已完成|已交付|released|closed|delivered/i.test(st);
  });
  if (warnRefs.length) tags.push('<span class="pcard-tag warn">警示</span>');
  if (accPct === null || acc.done < acc.total) tags.push('<span class="pcard-tag gap">缺口</span>');
  if (plan.status === '待排期' || plan.status === '部分执行') tags.push('<span class="pcard-tag plan">计划</span>');
  if (plan.approval) tags.push(`<span class="pcard-tag approved" title="人审批准：${esc(plan.approval)}">✓ 已批准</span>`);
  // 流程条：关联卡在看板六列的分布（ccc-plan-024）
  const cs = _planCardStates[plan.path] || { total: 0, cols: {} };
  const colOrder = [
    ['待分派', '待派'], ['执行中', '执行'], ['机审', '机审'],
    ['已回写', '待合入'], ['打回', '打回'], ['已关闭', '关闭'],
  ];
  const flowSegs = colOrder.map(([col, short]) => ({ col, short, n: (cs.cols || {})[col] || 0 }));
  const flowActive = flowSegs.filter((s) => s.n > 0);
  const flowBar = `<span class="pcard-flow-bar ${flowActive.length ? '' : 'empty'}">${flowActive.length
    ? flowSegs.map((s) => s.n ? `<i class="flow-${s.col}" style="width:${Math.round((s.n / (cs.total || 1)) * 100)}%"></i>` : '').join('')
    : ''}</span>`;
  const flowMeta = flowActive.length ? flowActive.map((s) => `${s.short}${s.n}`).join(' · ') : '未转卡';
  const title = String(plan.title || '').replace('方案 · ', '');

  return `
    <article class="pcard" data-path="${esc(plan.path)}" tabindex="0" role="button" draggable="true" aria-label="查看方案 ${esc(title)}">
      <span class="pcard-edge" style="background:${color}"></span>
      <div class="pcard-head">
        <span class="pcard-proj" style="background:${projTint};color:${projColor}">${esc(_projectDisplay[plan.project] || plan.project)}</span>
        <span class="pcard-id">#${esc(plan.num)}</span>
        <button type="button" class="pcard-open" title="查看方案详情">详情${icon('open')}</button>
      </div>
      <h3 class="pcard-title">${esc(title)}</h3>
      <div class="pcard-meta">${esc(plan.author)}<span class="pcard-dotsep">·</span>${esc(plan.tool)}</div>
      ${plan.milestone && plan.milestone !== '无' ? `<div class="pcard-mile" style="color:${projColor}">${icon('tag')}<span>${esc(plan.milestone)}</span></div>` : ''}
      <div class="pcard-flow" title="关联卡流程分布（待分派/执行中/机审/待合入/打回/已关闭）">
        ${flowBar}
        ${flowMeta ? `<span class="pcard-flow-meta">${esc(flowMeta)}</span>` : ''}
      </div>
      <div class="pcard-row">
        ${tags.length ? `<span class="pcard-tags">${tags.join('')}</span>` : ''}
        ${accPct !== null ? `
          <span class="pcard-acc" title="验收 ${acc.done}/${acc.total}">
            <span class="pcard-acc-bar"><span class="pcard-acc-fill" style="width:${accPct}%;background:${color}"></span></span>
            <span class="pcard-acc-num">${acc.done}/${acc.total}</span>
          </span>` : `<span class="pcard-acc-none">未验收</span>`}
      </div>
    </article>`;
}

function renderToolbar() {
  const projBtns = ['', ..._projects.map(p => p.prefix)].map(prefix => {
    const label = prefix ? (_projectDisplay[prefix] || prefix) : '全部';
    return `<button type="button" class="ptool-proj ${_filterProject === prefix ? 'on' : ''}" data-proj="${esc(prefix)}">${esc(label)}</button>`;
  }).join('');
  return `
    <div class="plans-toolbar k-topbar">
      <span class="k-topbar-title">计划</span>
      <div class="ptool-projects" role="group" aria-label="按项目筛选">${projBtns}</div>
      <div class="ptool-spacer"></div>
      <div class="k-topbar-stats"><span class="plans-total">${filteredPlans().length}</span> 个方案</div>
    </div>`;
}

/** 静态壳：toolbar + 列容器骨架 + detail + overlay。只建一次（M4），数据变化只刷 #plans-flow。 */
function shellHTML() {
  return `
    <div class="plans-page">
      ${renderToolbar()}
      <div class="plans-flow" id="plans-flow">
        ${STATUSES.map((s) => `<section class="pcol" data-status="${esc(s)}" data-drop-status="${esc(s)}"></section>`).join('')}
      </div>
      <div class="plans-detail" id="plans-detail" style="display:none"></div>
      <div class="plans-form-overlay" id="plans-form-overlay" style="display:none"></div>
    </div>`;
}

/** 列渲染签名：数据没变 → 复用列 DOM，不重建（根治整页 innerHTML 全量重建）。 */
function columnSig(list, status) {
  // 2026-08-24 修复回归：接收调用方已算好的 list（原先每列各自 filteredPlans()
  // 全表重算，一次 render 6~8 次）；并补 title/author/tool/milestone/approval，
  // 防「编辑标题/批准徽标变了但列签名不变 → 界面陈旧」
  const items = list.filter((p) => p.status === status);
  const sig = items
    .map((p) => {
      const acc = p.acceptance || {};
      const cs = _planCardStates[p.path] || { total: 0, cols: {} };
      return [
        p.path, p.status,
        p.title || '', p.author || '', p.tool || '', p.milestone || '', p.approval || '',
        acc.done + '/' + acc.total,
        (cs.total || 0) + ':' + Object.entries(cs.cols || {}).sort().map(([c, n]) => c + n).join(''),
        _cardStates[String(p.id || p.num || '').toLowerCase()] || '',
      ].join('|');
    })
    .join('\n');
  return sig;
}

/** 只刷列表列 + 总数（toolbar 静态；M4 列签名去抖）。 */
function renderFlow() {
  if (_disposed || !_root) return;
  const flowEl = _root.querySelector('#plans-flow');
  if (!flowEl) return;
  const list = filteredPlans(); // 每 render 只算 1 次（原 renderColumn/toolbar 各算 1 次，共 7 次）
  const countEl = _root.querySelector('.plans-total');
  if (countEl) countEl.textContent = String(list.length);
  // 每列：签名变了才重建该列；未变复用 DOM（拖拽/事件不重绑）
  for (const status of STATUSES) {
    const section = flowEl.querySelector(`.pcol[data-status="${esc(status)}"]`);
    if (!section) continue;
    section.style.display = '';
    const sig = columnSig(list, status);
    if (_colSigs[status] === sig) continue;
    _colSigs[status] = sig;
    const items = list.filter((p) => p.status === status);
    const color = STATUS_COLORS[status];
    // 2026-08-17 老板定：已确定旁不标「待确认」（删）；已确认改列名「待排期」，备注表下一步
    const hints = { '已确定': '', '待排期': '待转卡', '部分执行': '已转卡', '待验收': '待拍板', '已完成': '验收通过', '作废': '不执行' };
    section.innerHTML = `
      <header class="pcol-h">
        <span class="pcol-name"><span class="board-dot" style="background:${color}"></span>${esc(status)}</span>
        <span class="pcol-hint">${hints[status] || ''}</span>
        <span class="pcol-count">${items.length}</span>
      </header>
      <div class="pcol-body">
        ${items.length ? items.map(renderPlanItem).join('') : `<div class="pcol-empty"><div class="pcol-empty-line"></div><span>暂无方案</span></div>`}
      </div>`;
  }
  applyFlowColumns();
}

function render() {
  if (_disposed || !_root) return;
  _root.innerHTML = shellHTML();
  _colSigs = {}; // 整页重建 → 列签名重置
  bindEvents();
  applyFlowColumns();
  renderFlow(); // 首帧就填充列（数据已在 _plans 时）
}

function updateListOnly() {
  renderFlow();
}

// 手机族断点（与 css/mobile.css 的 md=768 同值）：横滑轮播态由 CSS 接管
const _mqlMobile = window.matchMedia('(max-width: 767px)');
function _applyFlowColumnsOnBreakpoint() { applyFlowColumns(); }

function applyFlowColumns() {
  const flow = _root?.querySelector('#plans-flow');
  if (!flow) return;
  if (_mqlMobile.matches) {
    // ccc-plan-046 M3：手机族 = 横滑轮播。清掉内联栅格，让 mobile.css 的
    // grid-auto-columns + scroll-snap 生效（内联样式会压过样式表规则）。
    flow.style.gridTemplateColumns = '';
    return;
  }
  flow.style.gridTemplateColumns = `repeat(${STATUSES.length}, minmax(0, 1fr))`;
}

// ── events ──

/** 壳事件一次性绑定（M4：toolbar 静态 + 列表用事件委托，列重建无需重绑）。 */
function bindEvents() {
  const root = _root;
  if (!root) return;

  root.querySelectorAll('.ptool-proj').forEach(btn => {
    btn.addEventListener('click', () => {
      const flow = _root?.querySelector('#plans-flow');
      const st = flow ? flow.scrollTop : 0;
      _filterProject = btn.dataset.proj || '';
      root.querySelectorAll('.ptool-proj').forEach(b => b.classList.toggle('on', b === btn));
      flow?.classList.add('no-anim');
      _colSigs = {};
      renderFlow();
      if (flow) flow.scrollTop = st;
      requestAnimationFrame(() => flow?.classList.remove('no-anim'));
    });
  });

  root.querySelector('#plans-empty-clear')?.addEventListener('click', () => {
    _filterProject = '';
    _colSigs = {};
    renderFlow();
  });

  // 事件委托（列 DOM 复用/重建都不重绑）：点击/键盘/拖拽 → 按 data-path 找方案
  const flow = root.querySelector('#plans-flow');
  if (flow) {
    const openFrom = (path) => { if (path) showDetail(path); };
    flow.addEventListener('click', (e) => {
      const openBtn = e.target.closest('.pcard-open');
      if (openBtn) { e.stopPropagation(); openFrom(openBtn.closest('.pcard')?.dataset.path); return; }
      const card = e.target.closest('.pcard');
      if (card) openFrom(card.dataset.path);
    });
    flow.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        const card = e.target.closest('.pcard');
        if (card) { e.preventDefault(); openFrom(card.dataset.path); }
      }
    });
    flow.addEventListener('dragstart', (e) => {
      const card = e.target.closest('.pcard');
      if (card) {
        e.dataTransfer.setData('text/plain', card.dataset.path || '');
        card.classList.add('dragging');
      }
    });
    flow.addEventListener('dragend', (e) => {
      e.target.closest('.pcard')?.classList.remove('dragging');
    });
    flow.addEventListener('dragover', (e) => {
      const col = e.target.closest('.pcol');
      if (col) { e.preventDefault(); col.classList.add('drag-over'); }
    });
    flow.addEventListener('dragleave', (e) => {
      e.target.closest('.pcol')?.classList.remove('drag-over');
    });
    flow.addEventListener('drop', (e) => {
      e.preventDefault();
      const col = e.target.closest('.pcol');
      col?.classList.remove('drag-over');
      const path = e.dataTransfer.getData('text/plain');
      const target = col?.dataset.dropStatus;
      if (path && target) doMoveCard(path, target);
    });
  }
}

const STATE_FLOW = {
  '已确定': ['待排期', '作废'],
  '待排期': ['部分执行', '作废'],
  '部分执行': ['待验收', '作废'],
  '待验收': ['已完成', '作废'],
  '已完成': [],
  '作废': [],
};

async function doMoveCard(path, targetStatus) {
  const plan = _plans.find((p) => p.path === path);
  if (!plan) return;
  const allowed = STATE_FLOW[plan.status] || [];
  if (!allowed.includes(targetStatus)) {
    alert(`状态流转非法：${plan.status} 不能直接到 ${targetStatus}`);
    return;
  }
  if (plan.status === targetStatus) return;
  try {
    await apiPost('/plans/update', { path, status: targetStatus });
    await loadPlans();
  } catch (e) {
    alert('状态更新失败: ' + e.message);
  }
}

// ── detail ──

async function showDetail(path) {
  _detailPath = path;
  const detailEl = _root?.querySelector('#plans-detail');
  const flowEl = _root?.querySelector('#plans-flow');
  if (!detailEl || !flowEl) return;

  // 2026-08-24 修复竞态：快速连点 A、B 时慢的旧响应会覆盖新面板并绑错操作目标；
  // 响应回来时校验仍是当前指向且页面未卸载，否则丢弃
  const seq = ++_detailSeq;
  try {
    const data = await apiGet('/plans/detail?path=' + encodeURIComponent(path));
    if (_disposed || seq !== _detailSeq || _detailPath !== path) return;
    flowEl.style.display = 'none';
    detailEl.style.display = 'block';
    detailEl.innerHTML = renderDetail(data);
    bindDetailEvents(path);
  } catch (e) {
    if (_disposed || seq !== _detailSeq) return; // 卸载/被更新的请求取代：静默
    alert('加载方案详情失败: ' + e.message);
  }
}
let _detailSeq = 0;

function _parseFuncCards(content) {
  const cards = [];
  const m = String(content || '').match(/## 功能卡\n([\s\S]*?)(?=\n## |\n$|$)/);
  if (!m) return cards;
  const section = m[1];
  const re = /###\s+(.+?)\n([\s\S]*?)(?=\n### |\n## |$)/g;
  let mm;
  while ((mm = re.exec(section))) {
    const title = mm[1].trim();
    const body = mm[2] || '';
    const goal = (body.match(/目标：(.+)/) || [])[1] || '';
    const impl = (body.match(/实现：([\s\S]*?)(?=\n验收：|\n$|$)/) || [])[1] || '';
    if (title) cards.push({ title, goal: goal.trim(), impl: impl.trim() });
  }
  return cards;
}

/** 功能卡清单卡片（ccc-plan-027）：人话目标 + 可展开实现 */
function _funcCardsHTML(content) {
  const cards = _parseFuncCards(content);
  if (!cards.length) return '';
  return `<div class="pdetail-funcs" style="margin:0 0 16px;border:1px solid var(--ccc-border-base);border-radius:10px;overflow:hidden">
    <div style="padding:8px 14px;font-size:13px;color:var(--ccc-text-muted);border-bottom:1px solid var(--ccc-border-base)">功能卡清单（${cards.length}）· 节点②确认对象</div>
    ${cards.map((c, i) => `<details style="padding:10px 14px;border-bottom:1px solid var(--ccc-border-subtle)">
      <summary style="cursor:pointer;font-weight:600;color:var(--ccc-text-base);list-style:none;display:flex;align-items:baseline;gap:8px">
        <span>${i + 1}. ${esc(c.title)}</span>
        ${c.goal ? `<span style="font-weight:400;color:var(--ccc-text-muted);font-size:12px">${esc(c.goal)}</span>` : ''}
        ${c.impl ? '<span style="color:var(--ccc-info);margin-left:auto;font-size:11px">实现 ▾</span>' : ''}
      </summary>
      ${c.impl ? `<div style="margin-top:8px;font-size:12px;color:var(--ccc-text-secondary);line-height:1.6">${renderMarkdown(c.impl)}</div>` : ''}
    </details>`).join('')}
  </div>`;
}

function renderDetail(plan) {
  const color = STATUS_COLORS[plan.status] || 'var(--ccc-text-faint)';
  const tint = color + '1f';
  const acc = plan.acceptance || {};
  const cardsText = plan.cards && plan.cards !== '无' ? plan.cards : '';
  return `
    <div class="pdetail">
      <div class="pdetail-bar">
        <button type="button" class="ptool-btn-plain pdetail-back" id="plans-detail-back">${icon('back')}返回方案池</button>
        <span class="pdetail-badge" style="background:${tint};color:${color}">${esc(plan.status)}</span>
        <span class="pdetail-id">${esc(plan.project)} · ${esc(plan.id)}</span>
      </div>
      <h2 class="pdetail-title">${esc(plan.title)}</h2>
      <div class="pdetail-meta">
        <span>作者：${esc(plan.author)}</span>
        <span>工具：${esc(plan.tool)}</span>
        ${plan.milestone && plan.milestone !== '无' ? `<span>里程碑：${esc(plan.milestone)}</span>` : ''}
        <span>更新：${esc(plan.updated || plan.created)}</span>
        ${cardsText ? `<span class="pcard-chip">${icon('tag')}<span>关联卡 ${esc(cardsText)}</span></span>` : ''}
        ${acc.total > 0 ? `<span class="pcard-acc" title="验收 ${acc.done}/${acc.total}"><span class="pcard-acc-bar"><span class="pcard-acc-fill" style="width:${Math.round(acc.done / acc.total * 100)}%;background:${color}"></span></span><span class="pcard-acc-num">验收 ${acc.done}/${acc.total}</span></span>` : ''}
      </div>
      ${_funcCardsHTML(plan.content)}
      <div class="pdetail-body">${renderMarkdown(plan.content)}</div>
      <div class="pdetail-actions">
        ${(plan.status === '待排期' || plan.status === '部分执行') ? `<button type="button" class="ptool-new" id="plans-detail-convert">${icon('convert')}转为任务卡</button>` : ''}
        ${plan.status === '待验收' ? `<button type="button" class="ptool-new" id="plans-detail-accept" title="033：老板/验收席按验收标准拍板">验收拍板</button>` : ''}
        <button type="button" class="ptool-new" id="plans-detail-edit">${icon('edit')}编辑</button>
        <select id="plans-detail-status" class="plans-status-select" aria-label="修改状态">
          <option value="">改状态…</option>
          ${STATUSES.map(s => `<option value="${s}"${plan.status === s ? ' selected' : ''}>${s}</option>`).join('')}
        </select>
      </div>
    </div>`;
}

function bindDetailEvents(path) {
  _root?.querySelector('#plans-detail-back')?.addEventListener('click', () => {
    _detailPath = null;
    const detailEl = _root?.querySelector('#plans-detail');
    const flowEl = _root?.querySelector('#plans-flow');
    if (detailEl) detailEl.style.display = 'none';
    if (flowEl) flowEl.style.display = '';
  });

  _root?.querySelector('#plans-detail-convert')?.addEventListener('click', () => doConvert(path));

  // 033 M4：验收拍板（待验收 → 已完成）
  _root?.querySelector('#plans-detail-accept')?.addEventListener('click', async () => {
    const btn = _root?.querySelector('#plans-detail-accept');
    if (!window.confirm('确认验收拍板？方案将由「待验收」置「已完成」（老板/验收席按验收标准确认）。')) return;
    if (btn) { btn.disabled = true; btn.textContent = '拍板中…'; }
    try {
      const res = await apiPost('/plans/accept', { path });
      if (res && res.ok) {
        window.showToast?.('验收拍板完成 → 已完成', 'success');
        await loadPlans();
      } else {
        alert((res && res.error) || '验收失败');
        if (btn) { btn.disabled = false; btn.textContent = '验收拍板'; }
      }
    } catch (e) {
      alert('验收失败: ' + e.message);
      if (btn) { btn.disabled = false; btn.textContent = '验收拍板'; }
    }
  });

  // 人审调整动作统一化：方案「修改」——节点② 改内容/功能卡清单
  _root?.querySelector('#plans-detail-edit')?.addEventListener('click', async () => {
    let rawContent = '';
    try {
      const d = await apiGet('/plans/detail?path=' + encodeURIComponent(path));
      rawContent = d.content || '';
    } catch (e) { /* 继续用空串 */ }
    const newContent = window.prompt('编辑方案内容（Markdown，含 ## 功能卡 段即可改拆卡清单）：', rawContent);
    if (newContent === null) return;
    try {
      const r = await apiPost('/plans/update', { path, content: newContent });
      if (r && r.cascaded && r.cascaded.length) {
        window.showToast?.(`已保存并级联作废 ${r.cascaded.length} 张卡`, 'success');
      } else {
        window.showToast?.('方案已保存', 'success');
      }
      showDetail(path);
      loadPlans();
    } catch (e) {
      window.showToast?.(e.message || '保存失败', 'error');
    }
  });

  _root?.querySelector('#plans-detail-status')?.addEventListener('change', async (e) => {
    const newStatus = e.target.value;
    if (!newStatus) return;
    await doUpdateStatus(path, newStatus);
    showDetail(path);
  });
}

// ── actions ──

async function doUpdateStatus(path, status) {
  // 人审调整动作统一化：作废方案是终态 + 级联作废关联卡 → 弹确认
  if (status === '作废') {
    const plan = _plans.find((p) => p.path === path);
    const cardCount = (plan && plan.cards)
      ? String(plan.cards).split(',').map((s) => s.trim()).filter(Boolean).length
      : 0;
    const confirmText = cardCount > 0
      ? `确定作废该方案？其 ${cardCount} 张关联卡将一并作废（不可逆）。`
      : '确定作废该方案？（不可逆）';
    if (!window.confirm(confirmText)) return;
  }
  try {
    const result = await apiPost('/plans/update', { path, status });
    if (result && result.cascaded && result.cascaded.length) {
      window.alert(`已作废方案，级联作废 ${result.cascaded.length} 张卡：${result.cascaded.join(', ')}`);
    }
    loadPlans();
  } catch (e) {
    alert('状态更新失败: ' + e.message);
  }
}

async function doConvert(path) {
  let detail;
  try {
    detail = await apiGet('/plans/detail?path=' + encodeURIComponent(path));
  } catch (e) {
    alert('加载方案详情失败: ' + e.message);
    return;
  }
  const content = detail.content || '';
  // 功能卡清单优先（027），回退旧「转卡计划」段
  let items = _parseFuncCards(content);
  if (!items.length) {
    const planSection = content.split('## 转卡计划')[1];
    if (planSection) {
      items = planSection.split('\n')
        .map(l => l.trim())
        .filter(l => l && !l.startsWith('#') && !l.startsWith('```') && !l.startsWith('|'))
        .map(l => ({ title: l.replace(/^[-*]\s*|^\d+\.\s*/, '').trim(), goal: '', impl: '' }))
        .filter(x => x.title);
    }
  }
  if (!items.length) {
    alert('方案缺少「功能卡」或「转卡计划」段，无法转卡');
    return;
  }
  _showConvertOverlay(path, items);
}

/** 节点②：确认功能卡清单 + 一次转卡（粒度 A，ccc-plan-027） */
function _showConvertOverlay(path, items) {
  let overlay = _root?.querySelector('#plans-convert-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'plans-convert-overlay';
    overlay.className = 'plans-form-overlay';
    _root?.appendChild(overlay);
  }
  overlay.style.display = 'flex';
  overlay.innerHTML = `
    <div class="plans-form" role="dialog" aria-modal="true" aria-label="节点②确认转卡" style="max-width:640px">
      <div class="plans-form-head">
        <h3>节点② · 确认功能卡清单并转卡</h3>
        <button type="button" class="ptool-btn-plain plans-form-x" id="plans-convert-cancel">${icon('close')}</button>
      </div>
      <div class="plans-convert-list" style="max-height:340px;overflow:auto;margin:12px 0">
        ${items.map((c, i) => `
          <div style="display:flex;gap:10px;padding:8px 2px;border-bottom:1px solid var(--ccc-border-subtle);align-items:flex-start">
            <input type="checkbox" class="plans-convert-check" data-title="${esc(c.title)}" checked style="margin-top:3px;flex:none" title="取消勾选=本张后续再转（逐步投入）">
            <span style="flex:none;width:22px;height:22px;border-radius:50%;background:var(--ccc-bg-hover);color:var(--ccc-text-muted);font-size:11px;display:flex;align-items:center;justify-content:center">${i + 1}</span>
            <div style="min-width:0">
              <div style="font-weight:600;color:var(--ccc-text-base)">${esc(c.title)}</div>
              ${c.goal ? `<div style="font-size:12px;color:var(--ccc-text-muted);margin-top:2px">${esc(c.goal)}</div>` : ''}
            </div>
          </div>`).join('')}
      </div>
      <div style="font-size:12px;color:var(--ccc-text-muted);margin-bottom:12px">默认全选。2026-08-16 子项目层：取消勾选 = 该功能卡本批不转，后续按子项目逐步投入。</div>
      <div class="plans-form-actions">
        <button type="button" class="ptool-btn-plain" id="plans-convert-cancel2">取消</button>
        <button type="button" class="ptool-new" id="plans-convert-ok">${icon('convert')}确认转卡（${items.length} 张）</button>
      </div>
    </div>`;

  const close = () => { overlay.style.display = 'none'; };
  overlay.querySelector('#plans-convert-cancel')?.addEventListener('click', close);
  overlay.querySelector('#plans-convert-cancel2')?.addEventListener('click', close);

  overlay.querySelector('#plans-convert-ok')?.addEventListener('click', async () => {
    const btn = overlay.querySelector('#plans-convert-ok');
    btn.disabled = true;
    btn.textContent = '转卡中…';
    try {
      // 2026-08-16 逐步投入：收集勾选的功能卡标题，取消勾选=本批不转（slices 子集）
      const checks = Array.from(overlay.querySelectorAll('.plans-convert-check'));
      const selected = checks.filter((c) => c.checked).map((c) => c.dataset.title).filter(Boolean);
      if (!selected.length) {
        alert('未选择任何功能卡（至少勾选一张才能转卡）');
        btn.disabled = false;
        btn.textContent = `确认转卡（${items.length} 张）`;
        return;
      }
      const body = { path };
      if (selected.length < checks.length) body.slices = selected; // 只转选中子集 → 逐步投入
      const result = await apiPost('/plans/convert', body);
      overlay.style.display = 'none';
      if (result.ok) {
        window.showToast ? window.showToast(`转卡成功：${(result.cards || []).join(', ')}`, 'success') : alert('转卡成功！生成卡片：' + (result.cards || []).join(', '));
        loadPlans();
      } else {
        alert('转卡失败: ' + (result.error || '未知错误'));
      }
    } catch (e) {
      btn.disabled = false;
      btn.textContent = `确认转卡（${items.length} 张）`;
      alert('转卡失败: ' + e.message);
    }
  });
}

// ── create form ──

// 新建方案表单已按老板指令移除（2026-08-24）；方案创建入口收敛到线路图子项目激活/转卡流程。

// ── markdown（块级解析，分组列表/表格/代码块） ──

function renderMarkdown(md) {
  if (!md) return '';
  const lines = String(md).replace(/\r\n/g, '\n').split('\n');

  const inline = (s) => {
    let out = esc(s);
    out = out.replace(/`([^`]+)`/g, '<code>$1</code>');
    out = out.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>');
    out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    out = out.replace(/(^|[\s>])(https?:\/\/[^\s<]+)/g, '$1<a href="$2" target="_blank" rel="noopener noreferrer">$2</a>');
    return out;
  };

  const html = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];

    // 代码块
    if (/^```/.test(line)) {
      const buf = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i++; }
      i++;
      html.push('<pre class="md-pre"><code>' + esc(buf.join('\n')) + '</code></pre>');
      continue;
    }
    // 表格
    if (/^\|.+\|$/.test(line) && i + 1 < lines.length && /^\|[\s:|-]+\|$/.test(lines[i + 1])) {
      const header = line.split('|').filter(c => c.trim() !== '');
      i += 2;
      const rows = [];
      while (i < lines.length && /^\|.+\|$/.test(lines[i])) {
        rows.push(lines[i].split('|').filter(c => c.trim() !== ''));
        i++;
      }
      html.push('<table class="md-table"><thead><tr>' + header.map(c => '<th>' + inline(c.trim()) + '</th>').join('') + '</tr></thead><tbody>' +
        rows.map(r => '<tr>' + r.map(c => '<td>' + inline(c.trim()) + '</td>').join('') + '</tr>').join('') + '</tbody></table>');
      continue;
    }
    // 标题
    const hm = line.match(/^(#{1,4})\s+(.+)$/);
    if (hm) {
      const lv = Math.min(4, hm[1].length + 1);
      html.push(`<h${lv} class="md-h">${inline(hm[2])}</h${lv}>`);
      i++;
      continue;
    }
    // checkbox 行
    const cbm = line.match(/^-\s+\[([ xX])\]\s+(.+)$/);
    if (cbm) {
      const done = /[xX]/.test(cbm[1]);
      html.push(`<label class="md-check${done ? ' done' : ''}"><input type="checkbox" disabled${done ? ' checked' : ''}>${inline(cbm[2])}</label>`);
      i++;
      continue;
    }
    // 无序列表（连续分组）
    if (/^\s*[-*]\s+\S/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*[-*]\s+\S/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ''));
        i++;
      }
      html.push('<ul class="md-ul">' + items.map(it => '<li>' + inline(it) + '</li>').join('') + '</ul>');
      continue;
    }
    // 有序列表
    if (/^\s*\d+\.\s+\S/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*\d+\.\s+\S/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ''));
        i++;
      }
      html.push('<ol class="md-ol">' + items.map(it => '<li>' + inline(it) + '</li>').join('') + '</ol>');
      continue;
    }
    // 引用
    if (/^>\s?/.test(line)) {
      const buf = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) { buf.push(lines[i].replace(/^>\s?/, '')); i++; }
      html.push('<blockquote class="md-quote">' + buf.map(b => inline(b)).join('<br>') + '</blockquote>');
      continue;
    }
    // 空行
    if (!line.trim()) { i++; continue; }
    // 普通段落（合并相邻行；孤立表格行/未匹配行兜底前进，防死循环）
    const buf = [];
    while (i < lines.length && lines[i].trim() && !/^```/.test(lines[i]) && !/^\|.+\|$/.test(lines[i]) && !/^#{1,4}\s/.test(lines[i]) && !/^\s*[-*>]/.test(lines[i]) && !/^\s*\d+\.\s/.test(lines[i])) {
      buf.push(lines[i].trim());
      i++;
    }
    if (buf.length === 0) {
      html.push('<p class="md-p">' + inline(lines[i]) + '</p>');
      i++;
      continue;
    }
    html.push('<p class="md-p">' + buf.map(inline).join('<br>') + '</p>');
  }
  return html.join('\n');
}

// ── mount / unmount ──

/** 2026-08-16 下钻深链：#/plans?plan=<plan-id> → 打开对应方案详情（从线路图子项目下钻）。
 * 2026-08-24 修复：深链参数用后即抹（history.replaceState），否则用户点「返回方案池」后
 * hash 里的 plan= 仍在，30s 轮询每轮 _applyDeepLink 都会把详情重新拽开。 */
function _applyDeepLink() {
  const m = (location.hash || '').match(/[?&]plan=([^&]+)/);
  if (!m) return;
  const planId = decodeURIComponent(m[1]);
  const target = _plans.find((p) => p.id === planId);
  if (target && target.path && target.path !== _detailPath) {
    try {
      const base = (location.hash || '').replace(new RegExp('[?&]plan=' + m[1]), '');
      history.replaceState(null, '', location.pathname + location.search + (base || '#/plans'));
    } catch (_) { /* 尽力而为：抹不掉也不阻塞打开 */ }
    showDetail(target.path);
  }
}

export function mountPlans(root, ctx = {}) {
  // 2026-08-24：同页重复导航时旧定时器句柄被覆盖泄漏，挂载前先清（与 unmount 等价）
  if (_timer) { clearInterval(_timer); _timer = null; }
  // 断点跨越（旋转/拉伸窗口）时重应用栅格模式
  _mqlMobile.addEventListener('change', _applyFlowColumnsOnBreakpoint);
  _root = root;
  _disposed = false;
  _colSigs = {};
  _root.innerHTML = '<div class="plans-loading">加载方案池…</div>';
  // M3 非阻塞：同步渲染骨架 → 后台拉数据（M2 缓存命中即零网络）；切回不重拉。
  // 深链（?plan=）在 loadPlans 数据到达 render 后应用（避免首帧 _plans 空丢失）。
  loadPlans();
  _timer = setInterval(() => {
    if (!_disposed && document.visibilityState === 'visible') loadPlans();
  }, 30000); // 30s 自动刷新（可见才刷）
}

export function unmountPlans() {
  _disposed = true;
  if (_timer) {
    clearInterval(_timer);
    _timer = null;
  }
  document.removeEventListener('keydown', _globalKeydown);
  _mqlMobile.removeEventListener('change', _applyFlowColumnsOnBreakpoint);
  _root = null;
  _plans = [];
  _detailPath = null;
  _formOpen = false;
}
