/**
 * roadmapPage.js — 线路图（T44：新增五视图之一）
 *
 * 数据源：GET /board/roadmap → {overview: [{bucket, count}], by_project: [...]}
 *   - overview：全项目按线路图桶聚合（未开发 / 开发中 / 已开发待验收 /
 *     已验收待确认 / 确认可用 / 有问题）
 *   - by_project：各项目桶聚合（按任务数倒序）
 * 只读视图（写操作在桌面端/编排口）。
 */

import { apiGet } from '../api.js';

const BUCKET_TONE = {
  '未开发': '#a39e93',
  '开发中': '#c47a2c',
  '已开发待验收': '#c9a227',
  '已验收待确认': '#3d9a5f',
  '确认可用': '#5a7a9a',
  '有问题': '#c44',
};

let _root = null;
let _timer = null;

function esc(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function html() {
  return `
<div class="roadmap-page hub-page">
  <div class="orch-hint">线路图 · 数据来自 /board/roadmap（按项目聚合，T53）。2017 单端 :7788 五视图。</div>
  <div class="board-toolbar">
    <h2>线路图</h2>
    <div class="board-toolbar-actions">
      <button type="button" class="hub-btn" id="roadmap-refresh" title="刷新">刷新</button>
    </div>
    <span class="st" id="roadmap-st">·</span>
  </div>
  <div class="roadmap-overview" id="roadmap-overview">
    <div class="settings-loading"><div class="spinner"></div><span>加载中...</span></div>
  </div>
  <div class="roadmap-by-project" id="roadmap-by-project"></div>
</div>`;
}

function overviewBar(bucket, count, total) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  const color = BUCKET_TONE[bucket] || '#a39e93';
  return `
  <div class="roadmap-bucket">
    <div class="roadmap-bucket-head">
      <span class="roadmap-bucket-name"><span class="board-dot" style="background:${color}"></span>${esc(bucket)}</span>
      <span class="roadmap-bucket-count">${count}</span>
    </div>
    <div class="roadmap-bar"><div class="roadmap-bar-fill" style="width:${pct}%;background:${color}"></div></div>
  </div>`;
}

function projectRow(row) {
  const counts = (row.buckets || []).map((b) => b.count || 0);
  const total = counts.reduce((s, n) => s + n, 0);
  const cells = (row.buckets || [])
    .map((b) => {
      const color = BUCKET_TONE[b.bucket] || '#a39e93';
      const pct = total > 0 ? Math.round(((b.count || 0) / total) * 100) : 0;
      return `<td class="roadmap-proj-cell"><div class="roadmap-bar"><div class="roadmap-bar-fill" style="width:${pct}%;background:${color}"></div></div><span class="roadmap-proj-n">${b.count || 0}</span></td>`;
    })
    .join('');
  return `
  <tr class="roadmap-proj-row">
    <td class="roadmap-proj-name">${esc(row.project)}<span class="roadmap-proj-total">· 共 ${row.count} 卡</span></td>
    ${cells}
  </tr>`;
}

async function loadRoadmap() {
  if (!_root) return;
  const host = _root.querySelector('#roadmap-overview');
  const byHost = _root.querySelector('#roadmap-by-project');
  try {
    const data = await apiGet('/board/roadmap');
    const overview = data.overview || [];
    const byProject = data.by_project || [];
    const total = overview.reduce((s, b) => s + (b.count || 0), 0);
    const st = _root.querySelector('#roadmap-st');
    if (st) st.textContent = `共 ${total} 张任务卡`;
    if (host) {
      host.innerHTML = overview.length
        ? overview.map((b) => overviewBar(b.bucket, b.count || 0, total)).join('')
        : '<div class="board-empty">暂无数据</div>';
    }
    if (byHost) {
      byHost.innerHTML =
        '<h3 class="roadmap-proj-h">按项目</h3>' +
        (byProject.length
          ? '<table class="roadmap-proj-table"><thead><tr><th>项目</th><th>未开发</th><th>开发中</th><th>已开发待验收</th><th>已验收待确认</th><th>确认可用</th><th>有问题</th></tr></thead><tbody>' +
            byProject.map(projectRow).join('') +
            '</tbody></table>'
          : '<div class="board-empty">暂无项目数据</div>');
    }
  } catch (err) {
    if (host) host.innerHTML = '<div class="board-empty">线路图不可用: ' + esc(err.message || String(err)) + '</div>';
    if (byHost) byHost.innerHTML = '';
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
  _timer = setInterval(() => loadRoadmap().catch(() => {}), 15000);
}

export function unmountRoadmap() {
  if (_timer) {
    clearInterval(_timer);
    _timer = null;
  }
}
