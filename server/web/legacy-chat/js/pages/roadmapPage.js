/**
 * roadmapPage.js — 线路图（图形化 · 2026-08-12 升级 v2）
 *
 * 一级页面：项目卡片总览（缩略时间线 + 状态统计，非文字列表）
 * 二级页面：单项目完整 SVG 线路图 + 卡分组 + 风险提示
 *
 * 数据源：
 *   /board/roadmap → business_lines（一级页项目列表）
 *   /board/roadmap/<project> → 单项目详情（二级页）
 */

import { apiGet } from '../api.js';
import {
  buildTimelineSVG,
  buildTimelineOverview,
  buildMilestoneRail,
  milestonePanelHTML,
  riskHTML,
  esc,
} from '../roadmapTimeline.js';

let _root = null;
let _timer = null;

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
  <div id="roadmap-body"><div class="board-empty">加载中…</div></div>
</div>`;
}

/* ── 一级页：项目卡片总览 ── */

function projectCard(section) {
  const miles = section.milestones || [];
  const allCards = miles.reduce((n, m) => n + (m.cards || []).length, 0);
  // 口径与二级页一致：优先卡真实状态（normalize_state closed bucket），无真实状态才看 roadmap 标注
  const doneCards = miles.reduce(
    (n, m) => n + (m.cards || []).filter((c) => {
      const s = c.real_state || c.progress || '';
      return /已交付|已关闭|已完成|已合入|released|closed|delivered/.test(s);
    }).length,
    0
  );
  const plannedCards = allCards - doneCards;
  const driftCount = miles.reduce(
    (n, m) => n + (m.cards || []).filter((c) => c.drift || c.missing).length,
    0
  );
  const pct = allCards ? Math.round((doneCards / allCards) * 100) : 0;
  const proj = section.project || '';
  return `<button type="button" class="rm-project-card" data-project="${esc(proj)}" title="打开 ${esc(proj)} 线路图">
    <div class="rm-card-top">
      <span class="rm-card-name">${esc(proj)}</span>
      <span class="rm-card-meta">${miles.length} 里程碑 · ${allCards} 卡</span>
    </div>
    <div class="rm-progress">
      <div class="rm-progress-track"><div class="rm-progress-fill" style="width:${pct}%"></div></div>
      <span class="rm-progress-label">已完成 ${doneCards}/${allCards}（${pct}%）</span>
    </div>
    <div class="rm-card-tags">
      <span class="rm-tag doing">待开发 ${plannedCards}</span>
      ${driftCount ? `<span class="rm-tag drift">漂移 ${driftCount}</span>` : ''}
      ${miles.length ? `<span class="rm-tag mile">里程碑 ${miles.length}</span>` : ''}
    </div>
  </button>`;
}

function renderOverview(data) {
  const host = _root.querySelector('#roadmap-body');
  const st = _root.querySelector('#roadmap-st');
  const lines = data.business_lines || [];
  if (st) st.textContent = `${lines.length} 个项目线路`;
  if (!lines.length) {
    host.innerHTML = '<div class="board-empty">无业务线路（roadmap.md 未配置）</div>';
    return;
  }
  host.innerHTML = `<div class="rm-grid">${lines.map(projectCard).join('')}</div>
    <div class="rm-hint">点击项目卡片查看该项目的图形化线路图</div>`;
  host.querySelectorAll('.rm-project-card').forEach((btn) => {
    btn.addEventListener('click', () => {
      openProject(btn.dataset.project);
    });
  });
}

/* ── 二级页：单项目线路图 ── */

async function openProject(project) {
  const back = _root.querySelector('#roadmap-back');
  const body = _root.querySelector('#roadmap-body');
  if (back) back.style.display = 'inline-block';
  body.innerHTML = '<div class="board-empty">加载线路图…</div>';
  try {
    const detail = await apiGet(`/board/roadmap/${encodeURIComponent(project)}`);
    const first = detail.milestones.find((m) => (m.cards || []).length) || detail.milestones[0];
    body.innerHTML = `
      <div class="rm2">
        ${buildTimelineOverview(detail)}
        <div class="rm2-body">
          <div class="rm2-rail-wrap">
            <div class="rm2-rail-title">里程碑</div>
            ${buildMilestoneRail(detail)}
          </div>
          <div class="rm2-panel-wrap">${milestonePanelHTML(detail, first)}</div>
        </div>
        ${riskHTML(detail)}
      </div>`;
    bindMilestoneRail(body, detail);
  } catch (err) {
    body.innerHTML = '<div class="board-empty">加载失败: ' + esc(err.message || String(err)) + '</div>';
  }
}

function bindMilestoneRail(body, detail) {
  const panel = body.querySelector('.rm2-panel-wrap');
  if (!panel) return;
  body.querySelectorAll('.rm2-mile').forEach((btn) => {
    const open = () => {
      const idx = Number(btn.dataset.idx || -1);
      const mile = detail.milestones[idx];
      if (!mile) return;
      panel.innerHTML = milestonePanelHTML(detail, mile);
      body.querySelectorAll('.rm2-mile').forEach((x) => x.classList.toggle('active', x === btn));
    };
    btn.addEventListener('click', open);
  });
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
}
