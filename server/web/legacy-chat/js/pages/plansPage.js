/**
 * plansPage.js — 计划页面（#/plans）
 *
 * 数据源：GET /plans/list?project=&status=&q=
 * 详情：GET /plans/detail?path=...
 * 新建：POST /plans/create {project, title, content, author, tool}
 * 更新：POST /plans/update {path, status?, content?, cards?}
 * 转卡：POST /plans/convert {path}
 */

import { apiGet, apiPost } from '../api.js';

const STATUSES = ['草案', '已确认', '部分执行', '已完成', '作废'];
const STATUS_COLORS = {
  '草案': '#a39e93',
  '已确认': '#3d9a5f',
  '部分执行': '#c47a2c',
  '已完成': '#5a7a9a',
  '作废': '#999',
};

let _root = null;
let _timer = null;
let _plans = [];
let _filterProject = '';
let _filterStatus = '';
let _searchQ = '';
let _detailPath = null;  // 当前打开的详情路径，null=列表视图
let _formOpen = false;   // 新建表单是否打开

function esc(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function h(html) {
  return String(html || '');
}

// ── API ──

async function loadPlans() {
  const params = new URLSearchParams();
  if (_filterProject) params.set('project', _filterProject);
  if (_filterStatus) params.set('status', _filterStatus);
  if (_searchQ) params.set('q', _searchQ);

  const qs = params.toString();
  const path = '/plans/list' + (qs ? '?' + qs : '');
  try {
    const data = await apiGet(path);
    _plans = data.plans || [];
  } catch (e) {
    console.error('plans: load failed', e);
    _plans = [];
  }

  // 详情或表单打开时只更新列表数据，不重建区域
  if (_detailPath || _formOpen) {
    updateListOnly();
    return;
  }
  render();
}

// ── render ──

// ── partial update (不破坏详情/表单状态) ──

function updateListOnly() {
  const listEl = _root?.querySelector('#plans-list');
  const countEl = _root?.querySelector('.plans-count');
  if (listEl) listEl.innerHTML = renderList();
  if (countEl) countEl.textContent = `${_plans.length} 个方案`;
  // 重新绑定列表事件（但保留详情/表单区域不变）
  rebindListEvents();
}

function rebindListEvents() {
  const root = _root;
  if (!root) return;
  root.querySelectorAll('#plans-list [data-action]').forEach(el => {
    el.addEventListener('click', async (e) => {
      e.stopPropagation();
      const action = el.dataset.action;
      const path = el.dataset.path;
      if (action === 'detail') await showDetail(path);
      else if (action === 'convert') await doConvert(path);
    });
  });
  root.querySelectorAll('#plans-list select[data-action="status"]').forEach(el => {
    el.addEventListener('change', async (e) => {
      e.stopPropagation();
      const path = el.dataset.path;
      const newStatus = el.value;
      if (!newStatus) return;
      await doUpdateStatus(path, newStatus);
    });
  });
  root.querySelectorAll('#plans-list .plans-card').forEach(card => {
    card.addEventListener('click', () => {
      const path = card.dataset.path;
      if (path) showDetail(path);
    });
  });
}

function renderToolbar() {
  return `
    <div class="plans-toolbar">
      <select id="plans-filter-project" class="plans-select">
        <option value="">全部项目</option>
        <option value="ccc"${_filterProject === 'ccc' ? ' selected' : ''}>CCC</option>
        <option value="xy"${_filterProject === 'xy' ? ' selected' : ''}>xianyu</option>
        <option value="mx"${_filterProject === 'mx' ? ' selected' : ''}>medio-0</option>
        <option value="hp"${_filterProject === 'hp' ? ' selected' : ''}>知识库</option>
        <option value="qb"${_filterProject === 'qb' ? ' selected' : ''}>qb</option>
      </select>
      <select id="plans-filter-status" class="plans-select">
        <option value="">全部状态</option>
        ${STATUSES.map(s => `<option value="${s}"${_filterStatus === s ? ' selected' : ''}>${s}</option>`).join('')}
      </select>
      <input type="search" id="plans-search" class="plans-search" placeholder="搜索方案..." value="${esc(_searchQ)}">
      <button id="plans-btn-new" class="plans-btn-primary">+ 新建方案</button>
    </div>`;
}

function renderPlanCard(plan) {
  const color = STATUS_COLORS[plan.status] || '#999';
  const acc = plan.acceptance || {};
  const accText = acc.total > 0 ? `${acc.done}/${acc.total}` : '—';
  const cardsText = plan.cards && plan.cards !== '无' ? plan.cards : '';

  return `
    <div class="plans-card" data-path="${esc(plan.path)}">
      <div class="plans-card-header">
        <span class="plans-card-project">${esc(plan.project)}</span>
        <span class="plans-card-status" style="background:${color}">${esc(plan.status)}</span>
        <span class="plans-card-id">#${esc(plan.num)}</span>
        <span class="plans-card-title">${esc(plan.title.replace('方案 · ', ''))}</span>
      </div>
      <div class="plans-card-meta">
        <span>作者：${esc(plan.author)} · ${esc(plan.tool)}</span>
        <span>${esc(plan.updated || plan.created)}</span>
        ${cardsText ? `<span>关联卡：${esc(cardsText)}</span>` : ''}
        <span>验收：${accText}</span>
      </div>
      <div class="plans-card-actions">
        <button class="plans-btn-sm" data-action="detail" data-path="${esc(plan.path)}">详情</button>
        ${plan.status !== '已完成' && plan.status !== '作废' ? `<button class="plans-btn-sm plans-btn-convert" data-action="convert" data-path="${esc(plan.path)}">转为任务卡</button>` : ''}
        <select class="plans-status-select" data-action="status" data-path="${esc(plan.path)}">
          <option value="">改状态...</option>
          ${STATUSES.map(s => `<option value="${s}"${plan.status === s ? ' selected' : ''}>${s}</option>`).join('')}
        </select>
      </div>
    </div>`;
}

function renderList() {
  if (_plans.length === 0) {
    return `<div class="plans-empty">暂无方案。点击「+ 新建方案」开始。</div>`;
  }
  return _plans.map(renderPlanCard).join('');
}

function render() {
  if (!_root) return;
  _root.innerHTML = `
    <div class="plans-page">
      <div class="plans-header">
        <h2>计划</h2>
        <span class="plans-count">${_plans.length} 个方案</span>
      </div>
      ${renderToolbar()}
      <div class="plans-list" id="plans-list">
        ${renderList()}
      </div>
      <div class="plans-detail" id="plans-detail" style="display:none"></div>
      <div class="plans-form-overlay" id="plans-form-overlay" style="display:none"></div>
    </div>`;

  bindEvents();
}

// ── events ──

function bindEvents() {
  const root = _root;
  if (!root) return;

  // 筛选
  const selProject = root.querySelector('#plans-filter-project');
  const selStatus = root.querySelector('#plans-filter-status');
  const search = root.querySelector('#plans-search');

  selProject?.addEventListener('change', () => {
    _filterProject = selProject.value;
    loadPlans();
  });
  selStatus?.addEventListener('change', () => {
    _filterStatus = selStatus.value;
    loadPlans();
  });
  search?.addEventListener('input', debounce(() => {
    _searchQ = search.value.trim();
    loadPlans();
  }, 300));

  // 新建
  root.querySelector('#plans-btn-new')?.addEventListener('click', showCreateForm);

  // 卡片操作
  root.querySelectorAll('[data-action]').forEach(el => {
    el.addEventListener('click', async (e) => {
      e.stopPropagation();
      const action = el.dataset.action;
      const path = el.dataset.path;

      if (action === 'detail') {
        await showDetail(path);
      } else if (action === 'convert') {
        await doConvert(path);
      }
    });
  });

  // 状态选择
  root.querySelectorAll('select[data-action="status"]').forEach(el => {
    el.addEventListener('change', async (e) => {
      e.stopPropagation();
      const path = el.dataset.path;
      const newStatus = el.value;
      if (!newStatus) return;
      await doUpdateStatus(path, newStatus);
    });
  });

  // 卡片点击 → 详情
  root.querySelectorAll('.plans-card').forEach(card => {
    card.addEventListener('click', () => {
      const path = card.dataset.path;
      if (path) showDetail(path);
    });
  });
}

// ── detail ──

async function showDetail(path) {
  _detailPath = path;
  const detailEl = _root?.querySelector('#plans-detail');
  const listEl = _root?.querySelector('#plans-list');
  if (!detailEl || !listEl) return;

  try {
    const data = await apiGet('/plans/detail?path=' + encodeURIComponent(path));
    listEl.style.display = 'none';
    detailEl.style.display = 'block';
    detailEl.innerHTML = renderDetail(data);
    bindDetailEvents(path);
  } catch (e) {
    alert('加载方案详情失败: ' + e.message);
  }
}

function renderDetail(plan) {
  const color = STATUS_COLORS[plan.status] || '#999';
  const acc = plan.acceptance || {};

  return `
    <div class="plans-detail-inner">
      <div class="plans-detail-header">
        <button class="plans-btn-sm" id="plans-detail-back">← 返回列表</button>
        <h3>${esc(plan.title)}</h3>
        <span class="plans-card-status" style="background:${color}">${esc(plan.status)}</span>
      </div>
      <div class="plans-detail-meta">
        <span>${esc(plan.project)} · ${esc(plan.id)}</span>
        <span>作者：${esc(plan.author)} · ${esc(plan.tool)}</span>
        <span>${esc(plan.updated || plan.created)}</span>
        ${plan.cards && plan.cards !== '无' ? `<span>关联卡：${esc(plan.cards)}</span>` : ''}
        ${acc.total > 0 ? `<span>验收：${acc.done}/${acc.total}</span>` : ''}
      </div>
      <div class="plans-detail-body">${renderMarkdown(plan.content)}</div>
      <div class="plans-detail-actions">
        ${plan.status !== '已完成' && plan.status !== '作废' ? `<button class="plans-btn-primary" id="plans-detail-convert">转为任务卡</button>` : ''}
        <select id="plans-detail-status">
          <option value="">改状态...</option>
          ${STATUSES.map(s => `<option value="${s}"${plan.status === s ? ' selected' : ''}>${s}</option>`).join('')}
        </select>
      </div>
    </div>`;
}

function bindDetailEvents(path) {
  _root?.querySelector('#plans-detail-back')?.addEventListener('click', () => {
    _detailPath = null;
    const detailEl = _root?.querySelector('#plans-detail');
    const listEl = _root?.querySelector('#plans-list');
    if (detailEl) detailEl.style.display = 'none';
    if (listEl) listEl.style.display = 'block';
  });

  _root?.querySelector('#plans-detail-convert')?.addEventListener('click', () => doConvert(path));

  _root?.querySelector('#plans-detail-status')?.addEventListener('change', async (e) => {
    const newStatus = e.target.value;
    if (!newStatus) return;
    await doUpdateStatus(path, newStatus);
    showDetail(path); // refresh
  });
}

// ── actions ──

async function doUpdateStatus(path, status) {
  try {
    await apiPost('/plans/update', { path, status });
    loadPlans();
  } catch (e) {
    alert('状态更新失败: ' + e.message);
  }
}

async function doConvert(path) {
  if (!confirm('确定将此方案转为任务卡？转卡后方案状态将自动推进为「部分执行」。')) return;

  try {
    const result = await apiPost('/plans/convert', { path });
    if (result.ok) {
      alert('转卡成功！生成卡片：' + (result.cards || []).join(', '));
      loadPlans();
    } else {
      alert('转卡失败: ' + (result.error || '未知错误'));
    }
  } catch (e) {
    alert('转卡失败: ' + e.message);
  }
}

// ── create form ──

function showCreateForm() {
  _formOpen = true;
  const overlay = _root?.querySelector('#plans-form-overlay');
  if (!overlay) return;

  overlay.style.display = 'flex';
  overlay.innerHTML = `
    <div class="plans-form">
      <h3>新建方案</h3>
      <div class="plans-form-field">
        <label>项目</label>
        <select id="plans-form-project">
          <option value="ccc">CCC</option>
          <option value="xy">xianyu</option>
          <option value="mx">medio-0</option>
          <option value="hp">知识库</option>
          <option value="qb">qb</option>
        </select>
      </div>
      <div class="plans-form-field">
        <label>标题</label>
        <input type="text" id="plans-form-title" placeholder="方案标题">
      </div>
      <div class="plans-form-field">
        <label>作者</label>
        <input type="text" id="plans-form-author" placeholder="作者名">
      </div>
      <div class="plans-form-field">
        <label>工具</label>
        <input type="text" id="plans-form-tool" placeholder="如 Claude Code" value="Claude Code">
      </div>
      <div class="plans-form-field">
        <label>内容（Markdown，从「## 目标」开始）</label>
        <textarea id="plans-form-content" rows="12" placeholder="## 目标&#10;&#10;...&#10;&#10;## 背景&#10;&#10;...&#10;&#10;## 方案内容&#10;&#10;...&#10;&#10;## 验收标准&#10;&#10;- [ ] ...&#10;&#10;## 转卡计划&#10;&#10;- ...&#10;&#10;## 备注&#10;&#10;..."></textarea>
      </div>
      <div class="plans-form-actions">
        <button class="plans-btn-sm" id="plans-form-cancel">取消</button>
        <button class="plans-btn-primary" id="plans-form-submit">创建</button>
      </div>
    </div>`;

  overlay.querySelector('#plans-form-cancel')?.addEventListener('click', () => {
    _formOpen = false;
    overlay.style.display = 'none';
  });

  overlay.querySelector('#plans-form-submit')?.addEventListener('click', async () => {
    const project = overlay.querySelector('#plans-form-project')?.value;
    const title = overlay.querySelector('#plans-form-title')?.value.trim();
    const author = overlay.querySelector('#plans-form-author')?.value.trim();
    const tool = overlay.querySelector('#plans-form-tool')?.value.trim();
    const content = overlay.querySelector('#plans-form-content')?.value.trim();

    if (!title || !content) {
      alert('标题和内容不能为空');
      return;
    }

    try {
      const result = await apiPost('/plans/create', { project, title, content, author, tool });
      if (result.ok) {
        _formOpen = false;
        overlay.style.display = 'none';
        loadPlans();
      } else {
        alert('创建失败: ' + (result.error || '未知错误'));
      }
    } catch (e) {
      alert('创建失败: ' + e.message);
    }
  });
}

// ── markdown (simple) ──

function renderMarkdown(md) {
  if (!md) return '';
  let html = esc(md);
  // Headers
  html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>');
  html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>');
  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Checkboxes
  html = html.replace(/^- \[x\] (.+)$/gm, '<label class="plans-checkbox done"><input type="checkbox" checked disabled> $1</label>');
  html = html.replace(/^- \[ \] (.+)$/gm, '<label class="plans-checkbox"><input type="checkbox" disabled> $1</label>');
  // Blockquotes
  html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');
  // Line breaks
  html = html.replace(/\n\n/g, '</p><p>');
  html = html.replace(/\n/g, '<br>');
  return '<p>' + html + '</p>';
}

// ── utils ──

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

// ── mount / unmount ──

export async function mountPlans(root) {
  _root = root;
  await loadPlans();
  _timer = setInterval(loadPlans, 30000); // 30s 自动刷新
}

export function unmountPlans() {
  if (_timer) {
    clearInterval(_timer);
    _timer = null;
  }
  _root = null;
  _plans = [];
  _detailPath = null;
  _formOpen = false;
}