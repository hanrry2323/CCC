/**
 * roadmapPage.js — 线路图（业务线路 · 2026-08-12 升级）
 *
 * 数据源：GET /board/roadmap → { overview, by_project, business_lines }
 *   business_lines: [{ project, milestones: [{ title, cards: [{card_id, intent, progress, real_state, drift, missing}] }] }]
 *
 * 展示：按项目分区，每区显示业务线路里程碑 + 卡进度 + 漂移标记。
 * 用户一眼看到：哪些项目在推进、哪些卡状态漂移/缺失。
 */

import { apiGet } from '../api.js';

let _root = null;
let _timer = null;
let _active = null;

function esc(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function html() {
  return `
<div class="roadmap-page hub-page">
  <div class="board-toolbar">
    <h2>线路图</h2>
    <div class="board-toolbar-actions">
      <button type="button" class="hub-btn" id="roadmap-refresh" title="刷新">刷新</button>
    </div>
    <span class="st" id="roadmap-st">·</span>
  </div>
  <div id="roadmap-body"><div class="board-empty">加载中…</div></div>
</div>`;
}

function driftBadge(card) {
  if (card.drift) {
    return `<span class="roadmap-badge drift" title="roadmap 进度与卡真实状态不一致">漂移</span>`;
  }
  if (card.missing) {
    return `<span class="roadmap-badge missing" title="卡文件不存在">缺失</span>`;
  }
  return '';
}

function progressTone(progress) {
  const p = progress || '';
  if (p.includes('已交付') || p.includes('已关闭') || p.includes('已完成')) return 'done';
  if (p.includes('未合入') || p.includes('⚠️')) return 'warn';
  if (p.includes('执行中') || p.includes('进行')) return 'doing';
  return 'idle';
}

function cardRow(card) {
  const tone = progressTone(card.progress);
  const real = card.real_state ? ` · 卡状态:${esc(card.real_state)}` : '';
  return `<tr class="roadmap-card ${tone}">
    <td><strong>${esc(card.card_id)}</strong></td>
    <td>${esc(card.intent)}</td>
    <td class="roadmap-progress">${esc(card.progress)}${real}</td>
    <td>${driftBadge(card)}</td>
  </tr>`;
}

function milestoneBlock(mile) {
  const cards = mile.cards || [];
  return `<div class="roadmap-milestone">
    <div class="roadmap-milestone-title">${esc(mile.title)}</div>
    ${cards.length
      ? `<table class="ops-table"><thead><tr><th>卡号</th><th>意图</th><th>进度</th><th></th></tr></thead><tbody>${cards.map(cardRow).join('')}</tbody></table>`
      : '<div class="ops-empty">暂无卡</div>'}
  </div>`;
}

function projectBlock(section) {
  const miles = section.milestones || [];
  const total = miles.reduce((n, m) => n + (m.cards || []).length, 0);
  const driftCount = miles.reduce(
    (n, m) => n + (m.cards || []).filter((c) => c.drift || c.missing).length,
    0
  );
  return `<div class="roadmap-project" data-project="${esc(section.project)}">
    <div class="roadmap-project-head">
      <span class="roadmap-project-name">${esc(section.project)}</span>
      <span class="roadmap-project-meta">${total} 卡 · ${miles.length} 里程碑${driftCount ? ` · <span class="roadmap-drift-count">${driftCount} 漂移</span>` : ''}</span>
    </div>
    ${miles.map(milestoneBlock).join('')}
  </div>`;
}

function renderRoadmap(data) {
  const host = _root.querySelector('#roadmap-body');
  const st = _root.querySelector('#roadmap-st');
  const lines = data.business_lines || [];
  if (st) st.textContent = `${lines.length} 个项目线路`;
  if (!lines.length) {
    host.innerHTML = '<div class="board-empty">无业务线路（roadmap.md 未配置）</div>';
    return;
  }
  host.innerHTML = lines.map(projectBlock).join('');
}

async function loadRoadmap() {
  if (!_root) return;
  try {
    const data = await apiGet('/board/roadmap');
    renderRoadmap(data);
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
