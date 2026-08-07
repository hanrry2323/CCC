/**
 * roadmapPage.js — 线路图（ARCH 体系 v1.0，2026-08-08 重构）
 *
 * 数据源：GET /board/arch → {version, updated_at, gallery:[{project,title,arch_version,status,html}]}
 * 展示：顶部集群全景图（cluster）iframe + 项目图库（点击切换 iframe）。
 * Archify 产物 self-contained HTML，经 /arch/<file>.html 静态托管（legacy-chat/ 前缀自动托管）。
 */

import { apiGet } from '../api.js';

let _root = null;
let _timer = null;
let _current = 'cluster';

const STATUS_TONE = {
  active: '#3d9a5f',
  frozen: '#5a7a9a',
  retired: '#a39e93',
};

function esc(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function html() {
  return `
<div class="roadmap-page hub-page">
  <div class="orch-hint">线路图 · 集群全景架构图（ARCH 体系 v1.0 · 数据来自 /board/arch）。2026-08-08 重构。</div>
  <div class="board-toolbar">
    <h2>线路图 · 架构图库</h2>
    <div class="board-toolbar-actions">
      <button type="button" class="hub-btn" id="roadmap-refresh" title="刷新">刷新</button>
    </div>
    <span class="st" id="roadmap-st">·</span>
  </div>
  <div class="arch-gallery" id="arch-gallery"></div>
  <div class="arch-stage" id="arch-stage">
    <div class="settings-loading"><div class="spinner"></div><span>加载架构图...</span></div>
  </div>
</div>`;
}

function galleryItem(g, active) {
  const tone = STATUS_TONE[g.status] || '#a39e93';
  return `
  <button type="button" class="arch-gallery-item${active ? ' is-active' : ''}" data-project="${esc(g.project)}">
    <span class="board-dot" style="background:${tone}"></span>
    <span class="arch-gallery-title">${esc(g.title)}</span>
    <span class="arch-gallery-ver">arch ${esc(g.arch_version)}</span>
  </button>`;
}

function renderGallery(gallery) {
  const host = _root.querySelector('#arch-gallery');
  host.innerHTML =
    (gallery && gallery.length
      ? gallery.map((g) => galleryItem(g, g.project === _current)).join('')
      : '<div class="board-empty">暂无架构图（ARCH 图库未就绪）</div>') +
    '<span class="arch-gallery-hint">点击项目查看其架构图</span>';
  host.querySelectorAll('.arch-gallery-item').forEach((btn) => {
    btn.addEventListener('click', () => {
      _current = btn.dataset.project;
      loadGallery();
      showStage(gallery);
    });
  });
}

function showStage(gallery) {
  const stage = _root.querySelector('#arch-stage');
  const g = (gallery || []).find((x) => x.project === _current);
  if (!g || !g.html) {
    stage.innerHTML = '<div class="board-empty">未找到该图</div>';
    return;
  }
  stage.innerHTML = `
    <div class="arch-stage-head">
      <strong>${esc(g.title)}</strong>
      <span class="arch-stage-meta">${esc(g.arch_version)} · ${esc(g.status)}</span>
    </div>
    <iframe class="arch-stage-frame" src="${esc(g.html)}" title="${esc(g.title)}" loading="lazy"></iframe>`;
}

async function loadRoadmap() {
  if (!_root) return;
  try {
    const data = await apiGet('/board/arch');
    const gallery = data.gallery || [];
    const st = _root.querySelector('#roadmap-st');
    if (st) st.textContent = `共 ${gallery.length} 张架构图`;
    renderGallery(gallery);
    showStage(gallery);
  } catch (err) {
    const stage = _root.querySelector('#arch-stage');
    if (stage) stage.innerHTML = '<div class="board-empty">架构图库不可用: ' + esc(err.message || String(err)) + '</div>';
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
