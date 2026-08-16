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

import { apiGet, apiPost, apiPut, apiDelete } from '../api.js';
import { esc } from '../roadmapTimeline.js';

let _root = null;
let _timer = null;
let _rmFilter = 'all';
let _currentProject = null; // 二级页当前项目（闪退修复：loadRoadmap/定时器尊重当前视图，不再跳回一级）

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
  // 2026-08-16 口径统一（Bug 9）：有子项目的项目用「子项目完成率」（与二级页 compute_milestone_progress 一致），
  // 无子项目退回里程碑计数（旧口径）。
  let hasSub = false;
  let total = 0;
  let done = 0;
  for (const m of milestones) {
    const sps = m.subprojects || [];
    if (sps.length) {
      hasSub = true;
      total += sps.length;
      done += sps.filter(s => s.dev_status === '已开发').length;
    }
  }
  if (hasSub && total > 0) return Math.round((done / total) * 100);
  const t = milestones.length;
  const d = milestones.filter(m => m.status === '已完成').length;
  return t > 0 ? Math.round((d / t) * 100) : 0;
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

function _draftTitle(d) {
  return typeof d === 'string' ? d : (d.title || '');
}
function _draftSource(d) {
  if (typeof d === 'string') return '';
  return d.source || '';
}
function _draftCreated(d) {
  if (typeof d === 'string') return '';
  return d.created || '';
}

/* 草案池卡片化 + 二级页详情（2026-08-14 前端优化）
 * 卡片 = 来源徽标 + 标题（2 行截断）+ 操作；点击卡片 → 二级页看草案详情。 */
function _draftPoolHTML(drafts, project) {
  if (!drafts || !drafts.length) return '';
  return `<div class="rm2-drafts">
    <strong class="rm2-drafts-title">草案池（${drafts.length}）<span class="rm2-drafts-hint">未排期想法 · 列入里程碑才进入正式开发</span></strong>
    <div class="rm2-draft-grid">
      ${drafts.map((d, i) => {
        const title = _draftTitle(d);
        const src = _draftSource(d);
        return `<div class="rm2-draft-card" data-index="${i}" title="点击查看草案详情">
          <div class="rm2-draft-card-top">
            <span class="rm2-draft-src">${src ? esc(src) : '草案'}</span>
            <span class="rm2-draft-state">未排期</span>
          </div>
          <div class="rm2-draft-card-title">${esc(title)}</div>
          <div class="rm2-draft-card-actions">
            <button type="button" class="hub-btn rm2-draft-promote" data-project="${esc(project)}" data-index="${i}" title="人审节点①：老板确认后转正式方案">确认转方案</button>
            <button type="button" class="hub-btn rm2-draft-edit" data-project="${esc(project)}" data-index="${i}" title="修改草案文字（节点① 调整）">编辑</button>
            <button type="button" class="hub-btn rm2-draft-remove" data-project="${esc(project)}" data-index="${i}" title="取消草案（节点① 不再执行，直接移除）">取消</button>
          </div>
        </div>`;
      }).join('')}
    </div>
  </div>`;
}

/* 草案二级页详情（overlay）：全量文本 + 来源/日期 + 动作 */
function _showDraftDetail(project, index, drafts) {
  const d = drafts[index];
  if (!d) return;
  const title = _draftTitle(d);
  let overlay = _root?.querySelector('#rm2-draft-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'rm2-draft-overlay';
    overlay.className = 'plans-form-overlay';
    _root?.appendChild(overlay);
  }
  overlay.style.display = 'flex';
  overlay.innerHTML = `
    <div class="plans-form" role="dialog" aria-modal="true" aria-label="草案详情" style="max-width:640px">
      <div class="plans-form-head">
        <h3>草案详情 · ${esc(project)}</h3>
        <button type="button" class="ptool-btn-plain plans-form-x" id="rm2-draft-close" aria-label="关闭">×</button>
      </div>
      <div class="plans-form-field" style="align-items:flex-start">
        <label>来源</label>
        <span style="padding:6px 0">${_draftSource(d) ? esc(_draftSource(d)) : '未标注'}</span>
      </div>
      <div class="plans-form-field" style="align-items:flex-start">
        <label>日期</label>
        <span style="padding:6px 0">${_draftCreated(d) ? esc(_draftCreated(d)) : '—'}</span>
      </div>
      <div class="plans-form-field" style="align-items:flex-start">
        <label>内容</label>
        <div class="rm2-draft-detail-body">${esc(title)}</div>
      </div>
      <div class="plans-form-actions">
        <button type="button" class="ptool-new" id="rm2-draft-detail-promote">确认转方案</button>
        <button type="button" class="ptool-btn-plain" id="rm2-draft-detail-close">关闭</button>
      </div>
    </div>`;
  overlay.querySelector('#rm2-draft-close')?.addEventListener('click', () => { overlay.style.display = 'none'; });
  overlay.querySelector('#rm2-draft-detail-close')?.addEventListener('click', () => { overlay.style.display = 'none'; });
  overlay.querySelector('#rm2-draft-detail-promote')?.addEventListener('click', async () => {
    const btn = overlay.querySelector('#rm2-draft-detail-promote');
    btn.disabled = true; btn.textContent = '确认中…';
    try {
      await apiPost(`/roadmap/${encodeURIComponent(project)}/draft/promote-to-plan`, { index });
      overlay.style.display = 'none';
      window.showToast?.('草案已转为方案', 'success');
      await openProject(project);
    } catch (e) {
      window.showToast?.(e.message || '确认失败', 'error');
      btn.disabled = false; btn.textContent = '确认转方案';
    }
  });
}

function _milestoneProgressHTML(mile) {
  const plans = mile.linked_plans || [];
  if (!plans.length) return '';
  return `<div class="rm2-mile-progress">
    <span class="rm2-mile-progress-label">关联方案 ${plans.length}</span>
    <span class="rm2-mile-progress-tags">${plans.map(p => `<a class="rm2-mile-planlink" href="#/plans?plan=${encodeURIComponent(p)}" title="跳转计划页查看 ${esc(p)}">${esc(p)}</a>`).join(' ')}</span>
  </div>`;
}

function _milestoneDotClass(status) {
  // 里程碑模型状态色（PRIME-DIRECTIVE §2.1）：🟢已完成 / 🟡进行中 / 🟠部分 / 🔴阻滞 / ⚪未启动
  if (status === '已完成') return 'done';
  if (status === '进行中') return 'doing';
  if (status === '部分' || status === '部分完成') return 'partial';
  if (status === '阻滞' || status === '受阻') return 'blocked';
  return 'none';
}
function _milestoneLight(status) {
  return { done: '🟢', doing: '🟡', partial: '🟠', blocked: '🔴', none: '⚪' }[_milestoneDotClass(status)] || '⚪';
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
        const version = m.version && m.version !== '—' ? ` · ${esc(m.version)}` : '';
        return `<button type="button" class="rm2-mile" data-mile-idx="${i}" title="${esc(m.title)}">
          <span class="rm2-mile-dot ${dotClass}"></span>
          <div class="rm2-mile-body">
            <span class="rm2-mile-title">${esc(m.title)}</span>
            <span class="rm2-mile-meta">${_milestoneLight(m.status)} ${esc(m.status)}${version}</span>
          </div>
        </button>`;
      }).join('')}
    </div>
  </div>`;
}

/* 2026-08-16 子项目层：里程碑面板渲染「子项目列表」（替代里程碑详情卡）。
 * 右侧 rail 里程碑导航 + 左侧 子项目列表，可下钻方案、激活转计划。 */
/* 2026-08-16 线路图页改造：子任务卡片化（复用 .rm2-sp-grid/.rm2-sp-card 卡片样式） */
function _subprojectCardsHTML(mile, project) {
  const sps = mile.subprojects || [];
  if (!sps.length) return _milestoneProgressHTML(mile); // 旧格式里程碑：退回关联方案展示
  const statusCls = { '未开发': 'todo', '进行中': 'doing', '已开发': 'done', '已废弃': 'void' };
  const statusLight = { '未开发': '⚪', '进行中': '🟡', '已开发': '🟢', '已废弃': '⚫' };
  return `<div class="rm2-sp-hd">子任务（${sps.length}）<span class="rm2-sp-hint">激活转计划 → 生成方案 → 逐步投入</span></div>
    <div class="rm2-sp-grid">
      ${sps.map(sp => {
        const dev = sp.dev_status || '未开发';
        const cls = statusCls[dev] || 'todo';
        const planLink = sp.plan_id
          ? `<a class="rm2-mile-planlink" href="#/plans?plan=${encodeURIComponent(sp.plan_id)}" title="跳转计划页查看 ${esc(sp.plan_id)}">${esc(sp.plan_id)}</a>`
          : '';
        const activateBtn = sp.status === '未启动'
          ? `<button type="button" class="hub-btn rm2-sp-activate" data-project="${esc(project)}" data-milestone="${esc(mile.title)}" data-sp="${esc(sp.id)}" title="人审节点①：激活子项目转计划">激活</button>`
          : '';
        const prog = (sp.plan_progress && sp.plan_progress.total > 0)
          ? `<span class="rm2-sp-card-progress">进度 ${sp.plan_progress.closed}/${sp.plan_progress.total}</span>`
          : '';
        const planStatus = sp.plan_status ? `<span class="rm2-sp-card-meta">方案 ${esc(sp.plan_status)}</span>` : '';
        return `<div class="rm2-sp-card">
          <div class="rm2-sp-card-top">
            <span class="rm2-sp-card-id">${esc(sp.id)}</span>
            <span class="rm2-sp-card-status ${cls}">${statusLight[dev]} ${esc(dev)}</span>
          </div>
          <div class="rm2-sp-card-title">${esc(sp.title)}</div>
          <div class="rm2-sp-card-meta">${planStatus}${prog}${planLink ? ' · ' + planLink : ''}</div>
          <div class="rm2-sp-card-actions">${activateBtn}</div>
        </div>`;
      }).join('')}
    </div>`;
}

/* master-detail（2026-08-16）：右栏只显示选中里程碑的 header + 子任务卡片 */
function _subprojectPanelHTML(detail, activeIdx = 0) {
  const miles = detail.milestones || [];
  if (!miles.length) return '<div class="rm2-panel-wrap"><div class="rm2-empty">暂无里程碑</div></div>';
  const m = miles[activeIdx] || miles[0];
  const tone = m.status === '已完成' ? 'done' : m.status === '进行中' ? 'doing' : 'planned';
  const tl = m.timeline || m.target_date || '';
  const ver = m.version && m.version !== '—' ? m.version : '';
  const spCount = (m.subprojects && m.subprojects.length) ? `<span class="rm2-mile-sp-count" title="子任务">🧩 ${m.subprojects.length} 子任务</span>` : '';
  return `<div class="rm2-panel-wrap">
    <div class="rm2-mile-card" id="rm2-mile-${activeIdx}">
      <span class="rm2-mile-dot ${_milestoneDotClass(m.status)}"></span>
      <div class="rm2-mile-info">
        <div class="rm2-mile-title-row">
          <span class="rm2-mile-title">${esc(m.title)}</span>
          <span class="rm2-mile-status ${tone}">${_milestoneLight(m.status)} ${esc(m.status)}</span>
        </div>
        <div class="rm2-mile-sub">
          ${tl ? `<span class="rm2-mile-tl" title="时间线">📅 ${esc(tl)}</span>` : ''}
          ${ver ? `<span class="rm2-mile-ver" title="版本">🏷️ ${esc(ver)}</span>` : ''}
          ${spCount}
        </div>
        ${m.description ? `<span class="rm2-mile-desc">${esc(m.description)}</span>` : ''}
        ${_subprojectCardsHTML(m, detail.project)}
        <button type="button" class="hub-btn rm2-mile-edit" data-title="${esc(m.title)}" data-status="${esc(m.status)}" data-desc="${esc(m.description || '')}" data-plans="${esc((m.linked_plans || []).join(', '))}" title="编辑里程碑（状态/描述/关联方案）" style="margin-top:6px">编辑</button>
      </div>
    </div>
  </div>`;
}

/* master-detail 点击切换（2026-08-16 线路图页改造）：点左栏里程碑 → 重渲染右栏为该里程碑的子任务卡 */
function _setupRailNavigation(host, detail, project) {
  const rail = host.querySelector('.rm2-rail');
  const panelWrap = host.querySelector('.rm2-panel-wrap');
  if (!rail || !panelWrap) return;
  const railBtns = Array.from(rail.querySelectorAll('.rm2-mile'));
  if (!railBtns.length) return;

  function _render(idx) {
    if (idx < 0 || idx >= railBtns.length) return;
    railBtns.forEach((b, i) => b.classList.toggle('active', i === idx));
    const newHtml = _subprojectPanelHTML(detail, idx);
    const tmp = document.createElement('div');
    tmp.innerHTML = newHtml;
    const newPanel = tmp.firstElementChild;
    panelWrap.replaceWith(newPanel);
    _bindPanelEvents(newPanel, project);
  }

  railBtns.forEach((btn, i) => {
    btn.addEventListener('click', () => _render(i));
  });
  _render(0); // 默认选中第一个里程碑
  host._rmObserver = null;
}

/* 绑定右栏 panel 内交互（激活 + 编辑）；master-detail 重渲染后复用 */
function _bindPanelEvents(container, project) {
  container.querySelectorAll('.rm2-mile-edit').forEach((btn) => {
    btn.addEventListener('click', () => {
      _showMilestoneForm(project, {
        title: btn.dataset.title || '',
        status: btn.dataset.status || '待启动',
        description: btn.dataset.desc || '',
        linked_plans: (btn.dataset.plans || '').split(/[,，\s]+/).filter(Boolean),
      });
    });
  });
  container.querySelectorAll('.rm2-sp-activate').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const proj = btn.dataset.project;
      const milestone = btn.dataset.milestone;
      const sp = btn.dataset.sp;
      if (!window.confirm(`确认激活子项目「${sp}」转计划？将 1:1 生成一个方案。`)) return;
      btn.disabled = true;
      btn.textContent = '激活中…';
      try {
        const res = await apiPost(`/roadmap/${encodeURIComponent(proj)}/subproject/activate`, { milestone, subproject_id: sp });
        if (res && res.ok) {
          window.showToast?.(`子项目已激活 → ${res.plan}`, 'success');
          await openProject(proj);
        } else {
          window.showToast?.((res && res.error) || '激活失败', 'error');
          btn.disabled = false;
          btn.textContent = '激活';
        }
      } catch (e) {
        window.showToast?.(e.message || '激活失败', 'error');
        btn.disabled = false;
        btn.textContent = '激活';
      }
    });
  });
}

async function openProject(project) {
  _currentProject = project;
  const back = _root.querySelector('#roadmap-back');
  const body = _root.querySelector('#roadmap-body');
  if (back) back.style.display = 'inline-block';
  body.innerHTML = '<div class="board-empty">加载线路图…</div>';
  try {
    const detail = await apiGet(`/roadmap/${encodeURIComponent(project)}`);
    body.innerHTML = `
      <div class="rm2">
        ${_overviewHTML(detail)}
        <div class="rm2-actions" style="display:flex;gap:8px;margin:8px 0 4px">
          <button type="button" class="hub-btn" id="rm2-milestone-new">＋ 新建里程碑</button>
        </div>
        ${_draftPoolHTML(detail.drafts, project)}
        <div class="rm2-body">
          ${_railHTML(detail)}
          ${_subprojectPanelHTML(detail)}
        </div>
      </div>`;
    _setupRailNavigation(body, detail, project);
    // 027 缝隙5：里程碑写入口（创建 / 编辑：状态·描述·关联方案）
    body.querySelector('#rm2-milestone-new')?.addEventListener('click', () => _showMilestoneForm(project, null));
    _bindPanelEvents(body, project);
    // P0 全链路修复：草案→方案一键升级（人审节点①动作入口，老板确认后由 Agent 打标）
    body.querySelectorAll('.rm2-draft-promote').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const proj = btn.dataset.project;
        const index = Number(btn.dataset.index);
        btn.disabled = true;
        btn.textContent = '确认中…';
        try {
          await apiPost(`/roadmap/${encodeURIComponent(proj)}/draft/promote-to-plan`, { index });
          window.showToast?.('草案已转为方案（已自动打「老板确认方案」批准标签）', 'success');
          await openProject(proj); // 刷新草案池
        } catch (e) {
          btn.textContent = '转方案失败';
          window.showToast?.(e.message || '确认失败', 'error');
        }
      });
    });
    // 人审调整动作统一化：节点① 修改草案（PUT /roadmap/<proj>/draft/<index>）
    body.querySelectorAll('.rm2-draft-edit').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const proj = btn.dataset.project;
        const index = Number(btn.dataset.index);
        const oldTitle = btn.closest('.rm2-draft-card')?.querySelector('.rm2-draft-card-title')?.textContent || '';
        const newTitle = window.prompt('修改草案文字：', oldTitle);
        if (newTitle === null || !newTitle.trim()) return;
        try {
          await apiPut(`/roadmap/${encodeURIComponent(proj)}/draft/${index}`, { title: newTitle.trim() });
          window.showToast?.('草案已修改', 'success');
          await openProject(proj);
        } catch (e) {
          window.showToast?.(e.message || '修改失败', 'error');
        }
      });
    });
    // 人审调整动作统一化：节点① 取消草案（DELETE /roadmap/<proj>/draft/<index>，直接移除）
    body.querySelectorAll('.rm2-draft-remove').forEach((btn) => {
      btn.addEventListener('click', async (ev) => {
        ev.stopPropagation();
        const proj = btn.dataset.project;
        const index = Number(btn.dataset.index);
        if (!window.confirm('确定取消这条草案？将直接从草案池移除（git 历史仍可追溯）。')) return;
        try {
          await apiDelete(`/roadmap/${encodeURIComponent(proj)}/draft/${index}`);
          window.showToast?.('草案已取消', 'success');
          await openProject(proj);
        } catch (e) {
          window.showToast?.(e.message || '取消失败', 'error');
        }
      });
    });
    // 草案池卡片化：点击卡片 → 二级页详情（前端优化 2026-08-14）
    body.querySelectorAll('.rm2-draft-card').forEach((card) => {
      card.addEventListener('click', (ev) => {
        if (ev.target.closest('button')) return; // 动作按钮不触发详情
        const idx = Number(card.dataset.index);
        _showDraftDetail(project, idx, detail.drafts || []);
      });
    });
  } catch (err) {
    body.innerHTML = '<div class="board-empty">加载失败: ' + esc(err.message || String(err)) + '</div>';
  }
}

/* 027 缝隙5：里程碑写入口弹窗（创建 POST /roadmap/<proj>/milestone；编辑 PUT /roadmap/<proj>/milestone/<title>） */
function _showMilestoneForm(project, milestone) {
  let overlay = _root?.querySelector('#rm2-milestone-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'rm2-milestone-overlay';
    overlay.className = 'plans-form-overlay';
    _root?.appendChild(overlay);
  }
  const isEdit = !!milestone;
  overlay.style.display = 'flex';
  overlay.innerHTML = `
    <div class="plans-form" role="dialog" aria-modal="true" aria-label="${isEdit ? '编辑里程碑' : '新建里程碑'}" style="max-width:560px">
      <div class="plans-form-head">
        <h3>${isEdit ? '编辑里程碑' : '新建里程碑'}</h3>
        <button type="button" class="ptool-btn-plain plans-form-x" id="rm2-mile-close" aria-label="关闭">×</button>
      </div>
      <div class="plans-form-field">
        <label for="rm2-mile-title">标题</label>
        <input type="text" id="rm2-mile-title" class="plans-form-input" value="${esc(milestone ? milestone.title : '')}" ${isEdit ? 'readonly title="里程碑以标题为键，不可改名"' : ''}>
      </div>
      <div class="plans-form-field">
        <label for="rm2-mile-status">状态</label>
        <select id="rm2-mile-status" class="plans-status-select">
          ${['待启动', '进行中', '已完成'].map(s => `<option value="${s}" ${(milestone ? milestone.status : '') === s ? 'selected' : ''}>${s}</option>`).join('')}
        </select>
      </div>
      <div class="plans-form-field">
        <label for="rm2-mile-desc">描述</label>
        <input type="text" id="rm2-mile-desc" class="plans-form-input" value="${esc(milestone ? milestone.description || '' : '')}">
      </div>
      <div class="plans-form-field">
        <label for="rm2-mile-date">目标日期（可选，YYYY-MM-DD）</label>
        <input type="date" id="rm2-mile-date" class="plans-form-input" value="${esc(milestone && milestone.target_date ? milestone.target_date : '')}">
      </div>
      <div class="plans-form-field">
        <label for="rm2-mile-plans">关联方案（逗号分隔 plan ID，如 ccc-plan-001, ccc-plan-002）</label>
        <input type="text" id="rm2-mile-plans" class="plans-form-input" value="${esc(milestone ? (milestone.linked_plans || []).join(', ') : '')}">
      </div>
      <div class="plans-form-actions">
        <button type="button" class="ptool-btn-plain" id="rm2-mile-cancel">取消</button>
        <button type="button" class="ptool-new" id="rm2-mile-save">${isEdit ? '保存' : '创建'}</button>
      </div>
    </div>`;

  const close = () => { overlay.style.display = 'none'; };
  overlay.querySelector('#rm2-mile-close')?.addEventListener('click', close);
  overlay.querySelector('#rm2-mile-cancel')?.addEventListener('click', close);

  overlay.querySelector('#rm2-mile-save')?.addEventListener('click', async () => {
    const title = overlay.querySelector('#rm2-mile-title')?.value.trim();
    const status = overlay.querySelector('#rm2-mile-status')?.value;
    const desc = overlay.querySelector('#rm2-mile-desc')?.value.trim();
    const targetDate = overlay.querySelector('#rm2-mile-date')?.value.trim() || '';
    const plans = (overlay.querySelector('#rm2-mile-plans')?.value || '').split(/[,，\s]+/).filter(Boolean);
    const btn = overlay.querySelector('#rm2-mile-save');
    btn.disabled = true;
    btn.textContent = isEdit ? '保存中…' : '创建中…';
    try {
      let result;
      if (isEdit) {
        result = await apiPut(`/roadmap/${encodeURIComponent(project)}/milestone/${encodeURIComponent(milestone.title)}`, { status, description: desc, linked_plans: plans, target_date: targetDate });
      } else {
        if (!title) { alert('里程碑标题不能为空'); btn.disabled = false; btn.textContent = '创建'; return; }
        result = await apiPost(`/roadmap/${encodeURIComponent(project)}/milestone`, { title, status, description: desc, linked_plans: plans, target_date: targetDate });
      }
      overlay.style.display = 'none';
      if (result.ok) {
        window.showToast ? window.showToast(isEdit ? '里程碑已更新' : '里程碑已创建', 'success') : alert(isEdit ? '里程碑已更新' : '里程碑已创建');
        await openProject(project); // 刷新里程碑
      } else {
        alert(result.error || '操作失败');
        btn.disabled = false;
        btn.textContent = isEdit ? '保存' : '创建';
      }
    } catch (e) {
      btn.disabled = false;
      btn.textContent = isEdit ? '保存' : '创建';
      alert(e.message || '操作失败');
    }
  });
}

/* 二级页字段映射对齐 /roadmap/<project>（roadmap.py 模型：milestones 含 title/status/linked_plans/description/subprojects） */
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
    // 闪退修复：若在二级页，刷新当前项目详情（不跳回一级概览）
    if (_currentProject) {
      await openProject(_currentProject);
      return;
    }
    const data = await apiGet('/board/roadmap');
    renderOverview(data);
  } catch (err) {
    const host = _root.querySelector('#roadmap-body');
    if (host) host.innerHTML = '<div class="board-empty">线路图加载失败: ' + esc(err.message || String(err)) + '</div>';
  }
}

function goBackToOverview() {
  _currentProject = null;
  const back = _root.querySelector('#roadmap-back');
  if (back) back.style.display = 'none';
  loadRoadmap();
}

function bind() {
  _root.querySelector('#roadmap-refresh')?.addEventListener('click', async () => {
    const btn = _root.querySelector('#roadmap-refresh');
    if (btn) btn.disabled = true;
    await loadRoadmap();
    if (btn) btn.disabled = false;
  });
  _root.querySelector('#roadmap-back')?.addEventListener('click', () => {
    goBackToOverview();
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
