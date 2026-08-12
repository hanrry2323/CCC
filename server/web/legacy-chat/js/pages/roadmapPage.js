/**
 * roadmapPage.js — 线路图（2026-08-12 升级 v3 · roadmap.py 数据模型）
 *
 * 一级页面：项目卡片总览（草案池 + 里程碑进度）
 * 二级页面：单项目线路图（草案池 + 里程碑 + 进度条）
 *
 * 数据源：
 *   /board/roadmap → roadmaps（一级页项目列表，来自 roadmap.py parse_roadmap）
 *   /roadmap/<project> → 单项目详情（二级页）
 */

import { apiGet } from '../api.js';
import { esc } from '../roadmapTimeline.js';

let _root = null;
let _timer = null;
let _rmFilter = 'all';

function html() {
  return `
<div class="roadmap-page hub-page">
  <div class="board-toolbar">
    <h2>线路图</h2>
    <div class="board-toolbar-actions">
      <button type="button" class="hub-btn" id="roadmap-refresh" title="刷新">刷新</button>
      <button type="button" class="hub-btn" id="roadmap-back" style="display:none" title="返回项目列表">← 返回</button>
    </div>
    <span class="st" id="roadmap-st">·</span>
  </div>
  <div class="rm-filters" id="rm-filters">
    <button type="button" class="rm-filter ${_rmFilter === 'all' ? 'on' : ''}" data-filter="all">全部</button>
    <button type="button" class="rm-filter ${_rmFilter === 'doing' ? 'on' : ''}" data-filter="doing">进行中</button>
    <button type="button" class="rm-filter ${_rmFilter === 'done' ? 'on' : ''}" data-filter="done">已完成</button>
  </div>
  <div id="roadmap-body"><div class="board-empty">加载中…</div></div>
</div>`;
}

/* ── 一级页：项目卡片总览 ── */

function _progressPct(milestones) {
  if (!milestones || !milestones.length) return 0;
  // 统一口径：按里程碑数量算完成率（done / total），不再混用 linked_plans 计数（Bug 9）
  const total = milestones.length;
  const done = milestones.filter(m => m.status === '已完成').length;
  return total > 0 ? Math.round((done / total) * 100) : 0;
}

function projectCard(roadmap) {
  const miles = roadmap.milestones || [];
  const drafts = roadmap.drafts || [];
  const doneCount = miles.filter(m => m.status === '已完成').length;
  const doingCount = miles.filter(m => m.status === '进行中').length;
  const pct = _progressPct(miles);
  return `<button type="button" class="rm-project-card" data-project="${esc(roadmap.project)}" title="打开 ${esc(roadmap.project)} 线路图">
    <div class="rm-card-top">
      <span class="rm-card-name">${esc(roadmap.project)}</span>
      <span class="rm-card-meta">${drafts.length} 草案 · ${miles.length} 里程碑</span>
    </div>
    <div class="rm2-stats">
      <span class="rm2-stat"><b>${miles.length}</b>里程碑</span>
      <span class="rm2-stat done"><b>${doneCount}</b>已完成</span>
      ${doingCount ? `<span class="rm2-stat doing"><b>${doingCount}</b>进行中</span>` : ''}
      ${drafts.length ? `<span class="rm2-stat planned"><b>${drafts.length}</b>草案</span>` : ''}
    </div>
    <div class="rm-progress">
      <div class="rm-progress-track"><div class="rm-progress-fill" style="width:${pct}%"></div></div>
      <span class="rm-progress-label">完成率 ${pct}%</span>
    </div>
    <div class="rm-card-tags">
      ${doingCount ? `<span class="rm-tag doing">进行中 ${doingCount}</span>` : ''}
      ${drafts.length ? `<span class="rm-tag draft">草案 ${drafts.length}</span>` : ''}
    </div>
  </button>`;
}

function renderOverview(data) {
  const host = _root.querySelector('#roadmap-body');
  const st = _root.querySelector('#roadmap-st');
  const roadmaps = data.roadmaps || [];
  const filtered = roadmaps.filter((rm) => {
    if (_rmFilter === 'all') return true;
    const miles = rm.milestones || [];
    const doneCount = miles.filter(m => m.status === '已完成').length;
    const doingCount = miles.filter(m => m.status === '进行中').length;
    if (_rmFilter === 'done') return miles.length > 0 && doneCount === miles.length;
    if (_rmFilter === 'doing') return doingCount > 0;
    return true;
  });
  if (st) st.textContent = `${filtered.length}/${roadmaps.length} 个项目线路`;
  if (!roadmaps.length) {
    host.innerHTML = '<div class="board-empty">无线路图（roadmap.md 未配置）</div>';
    return;
  }
  host.innerHTML = `<div class="rm-grid">${filtered.map(projectCard).join('')}</div>
    <div class="rm-hint">点击项目卡片查看线路图详情</div>`;
  host.querySelectorAll('.rm-project-card').forEach((btn) => {
    btn.addEventListener('click', () => {
      openProject(btn.dataset.project);
    });
  });
}

/* ── 二级页：单项目线路图 ── */

function _draftPoolHTML(drafts) {
  if (!drafts || !drafts.length) return '';
  return `<div class="rm2-drafts">
    <strong class="rm2-drafts-title">草案池（${drafts.length}）</strong>
    <div class="rm2-draft-list">
      ${drafts.map(d => `<div class="rm2-draft-item">
        <span class="rm2-draft-title">${esc(typeof d === 'string' ? d : d.title || '')}</span>
      </div>`).join('')}
    </div>
  </div>`;
}

function _milestoneProgressHTML(mile) {
  const plans = mile.linked_plans || [];
  if (!plans.length) return '';
  return `<div class="rm2-mile-progress">
    <span class="rm2-mile-progress-label">关联方案 ${plans.length}</span>
    <span class="rm2-mile-progress-tags">${plans.map(p => `<code>${esc(p)}</code>`).join(' ')}</span>
  </div>`;
}

function _milestoneDotClass(status) {
  if (status === '已完成') return 'done';
  if (status === '进行中') return 'doing';
  return 'none';
}

function _railHTML(detail) {
  const miles = detail.milestones || [];
  if (!miles.length) return '<div class="rm2-rail-wrap"><div class="rm2-empty">暂无里程碑</div></div>';
  return `<div class="rm2-rail-wrap">
    <div class="rm2-rail-title">里程碑（${miles.length}）</div>
    <div class="rm2-rail">
      <div class="rm2-rail-line"></div>
      ${miles.map((m, i) => {
        const dotClass = _milestoneDotClass(m.status);
        return `<button type="button" class="rm2-mile" data-mile-idx="${i}" title="${esc(m.title)}">
          <span class="rm2-mile-dot ${dotClass}"></span>
          <div class="rm2-mile-body">
            <span class="rm2-mile-title">${esc(m.title)}</span>
            <span class="rm2-mile-meta">${esc(m.status)}</span>
          </div>
        </button>`;
      }).join('')}
    </div>
  </div>`;
}

function _milestoneCardsHTML(detail) {
  const miles = detail.milestones || [];
  if (!miles.length) return '<div class="rm2-panel-wrap"><div class="rm2-empty">暂无里程碑</div></div>';

  // 按状态分组：进行中 → 待确认 → 已完成
  const groups = [
    { key: 'doing', label: '进行中', miles: miles.filter(m => m.status === '进行中') },
    { key: 'planned', label: '待确认', miles: miles.filter(m => m.status !== '进行中' && m.status !== '已完成') },
    { key: 'done', label: '已完成', miles: miles.filter(m => m.status === '已完成') },
  ];

  let cardIdx = 0;
  return `<div class="rm2-panel-wrap">${groups.map(g => {
    if (!g.miles.length) return '';
    const cards = g.miles.map(m => {
      const idx = cardIdx++;
      const tone = g.key === 'done' ? 'done' : g.key === 'doing' ? 'doing' : 'planned';
      return `<div class="rm2-mile-card" id="rm2-mile-${idx}">
        <span class="rm2-mile-dot ${_milestoneDotClass(m.status)}"></span>
        <div class="rm2-mile-info">
          <span class="rm2-mile-title">${esc(m.title)}</span>
          <span class="rm2-mile-status ${tone}">${esc(m.status)}</span>
          ${m.description ? `<span class="rm2-mile-desc">${esc(m.description)}</span>` : ''}
          ${_milestoneProgressHTML(m)}
        </div>
      </div>`;
    }).join('');
    return `<div class="rm2-group">
      <div class="rm2-group-hd ${g.key}">
        <span class="rm2-group-dot"></span>
        <span class="rm2-group-label">${esc(g.label)}</span>
        <span class="rm2-group-cnt">${g.miles.length}</span>
      </div>
      ${cards}
    </div>`;
  }).join('')}</div>`;
}

function _setupRailNavigation(host) {
  const rail = host.querySelector('.rm2-rail');
  if (!rail) return;

  const panel = host.querySelector('.rm2-panel-wrap');
  if (!panel) return;

  const railBtns = Array.from(rail.querySelectorAll('.rm2-mile'));
  const cards = Array.from(panel.querySelectorAll('.rm2-mile-card'));

  if (!railBtns.length || !cards.length) return;

  let _activeIdx = 0;
  let _observer = null;

  function _highlight(idx) {
    if (idx < 0 || idx >= railBtns.length) return;
    _activeIdx = idx;
    railBtns.forEach((b, i) => b.classList.toggle('active', i === idx));
  }

  // 点击左侧导航项 → 右侧滚动到对应卡片
  railBtns.forEach((btn, i) => {
    btn.addEventListener('click', () => {
      _highlight(i);
      if (cards[i]) {
        cards[i].scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // IntersectionObserver：右侧滚动时，左侧自动高亮对应项
  if (typeof IntersectionObserver !== 'undefined') {
    _observer = new IntersectionObserver(
      (entries) => {
        // 找到当前可见卡片中第一个（最靠上的）
        let firstVisible = -1;
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const idx = cards.indexOf(entry.target);
            if (idx !== -1 && (firstVisible === -1 || idx < firstVisible)) {
              firstVisible = idx;
            }
          }
        }
        if (firstVisible >= 0) {
          _highlight(firstVisible);
        }
      },
      { root: panel, threshold: 0.3, rootMargin: '-20px 0px 0px 0px' }
    );
    cards.forEach((card) => _observer.observe(card));
  }

  // 默认选中第一个
  _highlight(0);

  // 暴露清理方法（unmount 时用）
  host._rmObserver = _observer;
}

async function openProject(project) {
  const back = _root.querySelector('#roadmap-back');
  const body = _root.querySelector('#roadmap-body');
  if (back) back.style.display = 'inline-block';
  body.innerHTML = '<div class="board-empty">加载线路图…</div>';
  try {
    const detail = await apiGet(`/roadmap/${encodeURIComponent(project)}`);
    body.innerHTML = `
      <div class="rm2">
        ${_overviewHTML(detail)}
        ${_draftPoolHTML(detail.drafts)}
        <div class="rm2-body">
          ${_railHTML(detail)}
          ${_milestoneCardsHTML(detail)}
        </div>
      </div>`;
    _setupRailNavigation(body);
  } catch (err) {
    body.innerHTML = '<div class="board-empty">加载失败: ' + esc(err.message || String(err)) + '</div>';
  }
}

/* Bug 7：二级页字段映射对齐 /roadmap/<project>（roadmap.py 模型：milestones 含 title/status/linked_plans/description）
 * 不用 buildTimelineOverview（它读旧 /board/roadmap/<project> 的 counts/cards/risks 字段，新数据下全为 0）。 */
function _overviewHTML(detail) {
  const miles = (detail && detail.milestones) || [];
  const doneN = miles.filter((m) => m.status === '已完成').length;
  const doingN = miles.filter((m) => m.status === '进行中').length;
  const plannedN = miles.length - doneN - doingN;
  const pct = _progressPct(miles);
  return `<div class="rm2-overview">
    <div class="rm2-name">${esc(detail.project)}<span>线路图</span></div>
    <div class="rm2-stats">
      <span class="rm2-stat"><b>${miles.length}</b>里程碑</span>
      <span class="rm2-stat done"><b>${doneN}</b>已完成</span>
      <span class="rm2-stat doing"><b>${doingN}</b>进行中</span>
      <span class="rm2-stat planned"><b>${plannedN}</b>待确认</span>
    </div>
    <div class="rm2-progress"><div class="rm2-progress-fill" style="width:${pct}%"></div></div>
  </div>`;
}

async function loadRoadmap() {
  if (!_root) return;
  try {
    const data = await apiGet('/board/roadmap');
    renderOverview(data);
  } catch (err) {
    const host = _root.querySelector('#roadmap-body');
    if (host) host.innerHTML = '<div class="board-empty">线路图加载失败: ' + esc(err.message || String(err)) + '</div>';
  }
}

function bind() {
  _root.querySelector('#roadmap-refresh')?.addEventListener('click', async () => {
    const btn = _root.querySelector('#roadmap-refresh');
    if (btn) btn.disabled = true;
    await loadRoadmap();
    if (btn) btn.disabled = false;
  });
  _root.querySelector('#roadmap-back')?.addEventListener('click', async () => {
    _root.querySelector('#roadmap-back').style.display = 'none';
    await loadRoadmap();
  });
  _root.querySelectorAll('.rm-filter').forEach((btn) => {
    btn.addEventListener('click', () => {
      _rmFilter = btn.dataset.filter || 'all';
      _root.querySelectorAll('.rm-filter').forEach((x) => x.classList.toggle('on', x === btn));
      loadRoadmap();
    });
  });
}

export async function mountRoadmap(el) {
  if (_root) {
    await loadRoadmap();
    return;
  }
  _root = el;
  el.innerHTML = html();
  bind();
  await loadRoadmap();
  _timer = setInterval(() => loadRoadmap().catch(() => {}), 30000);
}

export function unmountRoadmap() {
  if (_timer) {
    clearInterval(_timer);
    _timer = null;
  }
  // 清理 IntersectionObserver
  if (_root && _root._rmObserver) {
    _root._rmObserver.disconnect();
    _root._rmObserver = null;
  }
}
