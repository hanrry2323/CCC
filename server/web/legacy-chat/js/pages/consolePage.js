/**
 * consolePage.js — 控制台（T30：新协议版）
 *
 * 数据源（全部走新服务端）：
 *   - 状态计数 KPI：GET /board/states → {状态: count} 或 GET /cards?project=X 聚合
 *   - 需注意清单：复用 TaskCard/TaskCardList (打回 / 执行中 / 已回写待验收)
 *   - 后台任务进程面板 (T53)
 *   - 运维告警数：GET /ops/summary → overview.alert_count
 *   - 项目列表：GET /board/summaries → {summaries: {项目: snapshot}}
 *
 * 旧字段（today_events / failures / risks / dashboard）已下线，保留占位提示。
 *
 * 写操作（reopen / move / create）已禁用：服务端不暴露。
 */

import { apiGet } from '../api.js';
import { TaskCardList } from '../components/taskCardList.js';
import { fmtTaskCopy, renderWorktreeBadges } from '../components/taskCard.js';

let _root = null;
let _timer = null;   // 看板快照轮询（15s）
let _rtimer = null;  // 后台任务进程轮询（8s，T53）
let _ws = 'all';

let _activeList = null;
let _abnList = null;
let _writtenList = null;
let _allCards = [];

let _isPolling = false;
let _loadingTimeout = null;
let _pollAbortController = null;

function esc(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function getBaseState(state) {
  if (!state) return '待分派';
  const clean = state.split(/[（(]/)[0].trim();
  const STATES = ['待分派', '执行中', '已回写', '已关闭', '打回'];
  if (STATES.includes(clean)) {
    return clean;
  }
  return '待分派';
}

async function copyTextToClipboard(text) {
  const payload = String(text || '');
  if (!payload) return false;
  try {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      await navigator.clipboard.writeText(payload);
      return true;
    }
  } catch (_) { /* fall through */ }
  try {
    const ta = document.createElement('textarea');
    ta.value = payload;
    ta.setAttribute('readonly', '');
    ta.style.cssText =
      'position:fixed;top:0;left:0;width:1px;height:1px;padding:0;border:0;opacity:0;';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, payload.length);
    const ok = document.execCommand('copy');
    ta.remove();
    return !!ok;
  } catch (_) {
    return false;
  }
}

function html() {
  return `
<div class="console-page hub-page" style="padding: 20px; box-sizing: border-box; display: flex; flex-direction: column; height: 100%; overflow: hidden;">
  <div class="console-banner" style="flex-shrink: 0; margin-bottom: 12px;">
    控制台为简化看板；详细运维请用 <a href="#/ops">运维页</a> 或任务卡 / Engine。
  </div>
  <div class="console-bar" style="flex-shrink: 0; margin-bottom: 16px;">
    <h2>控制台</h2>
    <button type="button" class="hub-btn" id="console-ws">工作区: <span id="console-ws-label">全部</span></button>
    <a class="hub-btn" href="#/ops" id="console-ops-link">运维告警 <span class="badge" id="console-ops-n">0</span></a>
    <span style="flex:1"></span>
    <button type="button" class="hub-btn primary" id="console-to-board">打开看板</button>
  </div>
  <div class="console-kpi" id="console-kpi" style="flex-shrink: 0;">
    <div class="console-kw"><div class="label">加载中…</div></div>
  </div>

  <div class="console-scroll-container" style="flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 20px; padding-right: 4px;">
    <div class="console-section">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
        <h3 style="margin: 0; display: flex; align-items: center; gap: 8px;">打回 <span class="badge" id="console-abn-n">0</span></h3>
        <a class="hub-btn text" href="#/board" style="font-size: 11px; text-decoration: none; color: var(--ccc-text-accent);">去看板看全部 &raquo;</a>
      </div>
      <div class="console-tasks-wrapper" id="console-abn-wrapper"></div>
    </div>

    <div class="console-section">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
        <h3 style="margin: 0; display: flex; align-items: center; gap: 8px;">执行中 <span class="badge" id="console-active-n">0</span></h3>
        <a class="hub-btn text" href="#/board" style="font-size: 11px; text-decoration: none; color: var(--ccc-text-accent);">去看板看全部 &raquo;</a>
      </div>
      <div class="console-tasks-wrapper" id="console-active-wrapper"></div>
    </div>

    <div class="console-section">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
        <h3 style="margin: 0; display: flex; align-items: center; gap: 8px;">已回写待验收 <span class="badge" id="console-written-n">0</span></h3>
        <a class="hub-btn text" href="#/board" style="font-size: 11px; text-decoration: none; color: var(--ccc-text-accent);">去看板看全部 &raquo;</a>
      </div>
      <div class="console-tasks-wrapper" id="console-written-wrapper"></div>
    </div>

    <div class="console-section">
      <h3 style="margin: 0 0 12px 0; display: flex; align-items: center; gap: 8px;">后台任务进程 <span class="badge" id="console-running-n">0</span></h3>
      <div class="console-tasks" id="console-running" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px;"></div>
    </div>

    <div class="console-section" style="margin-bottom: 12px;">
      <h3 style="margin: 0 0 12px 0;">最近失败 / 今日动态</h3>
      <div class="console-feed">
        <p class="ops-hint">旧 <code>/api/failures</code> / <code>/api/dashboard</code> 端点已下线。请 SSH 查 <code>~/.ccc/stats/failures.jsonl</code> 或看运维页 / 任务卡状态。</p>
      </div>
    </div>
  </div>
</div>`;
}

function renderKPI(counts) {
  const c = counts || {};
  const values = [
    { k: '待分派', label: '待分派', desc: '尚未执行' },
    { k: '执行中', label: '执行中', desc: '正在跑' },
    { k: '已回写', label: '已回写', desc: '待验收' },
    { k: '已关闭', label: '已关闭', desc: '已归档' },
    { k: '打回', label: '打回', desc: '需介入' },
  ];
  const box = _root.querySelector('#console-kpi');
  if (!box) return;
  box.innerHTML = values
    .map((item) => {
      const v = Number(c[item.k] || 0);
      return `<div class="console-kw"><div class="label">${esc(item.label)}</div><div class="big">${v}</div><div class="desc">${esc(item.desc)}</div></div>`;
    })
    .join('');
}

function fmtElapsed(secs) {
  if (secs == null) return '--';
  const s = Math.max(0, Math.round(secs));
  if (s < 60) return s + 's';
  if (s < 3600) return Math.floor(s / 60) + 'm' + Math.round(s % 60) + 's';
  return Math.floor(s / 3600) + 'h' + Math.round((s % 3600) / 60) + 'm';
}

function runningCard(t) {
  const tail = (t.log_tail || []).slice(-5);
  const tailHtml = tail.length ? tail.map((l) => esc(l)).join('<br>') : '（无日志）';
  const recent = t.last_activity_at
    ? (Date.now() - new Date(t.last_activity_at).getTime()) < 30000
    : false;
  const active = t.last_activity_at ? recent : (t.elapsed_s != null);
  const label = t.last_activity_at ? (active ? '活动' : '空闲') : '运行中';
  const color = '#2f7dd1'; // Blue tone for running background processes
  const dirty = renderWorktreeBadges(t);

  return `
    <div class="board-task-card board-card board-card-work state-running running"
         data-id="${esc(t.work_id)}"
         style="border-left-color: ${color}; --state-bar: ${color}; cursor: default; margin-bottom: 0;">
      <div class="board-card-row">
        <span class="board-card-id id">${esc(t.work_id)}</span>
        <span class="board-card-state state-running">${esc(label)}</span>
      </div>
      <div class="board-card-title ti" style="font-weight: 600; font-size: 14px; margin-bottom: 4px;">${esc(t.title || t.work_id)}</div>

      <div style="font-size: 11px; color: var(--ccc-text-muted); margin-bottom: 6px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
        <span>@${esc(t.executor || '')}</span>
        <span class="board-card-stats">${dirty}</span>
        <span>·</span>
        <span>已用时 ${fmtElapsed(t.elapsed_s)}</span>
        <span style="flex:1"></span>
        <span>日志尾 ${tail.length} 行</span>
      </div>

      <!-- indeterminate 进度条：无百分比进度，用 shimmer 滑动光带表示「进行中」 -->
      <div style="height:6px;border-radius:3px;background:var(--ccc-bg-hover);overflow:hidden;margin-bottom:8px">
        <div style="height:100%;background:linear-gradient(90deg,var(--ccc-bg-hover),#2f7dd1,var(--ccc-bg-hover));background-size:200% 100%;animation:shimmer 1.6s linear infinite"></div>
      </div>

      <pre style="margin:0;font-family:var(--ccc-font-mono);font-size:10px;line-height:1.5;color:var(--ccc-text-secondary);white-space:pre-wrap;word-break:break-all;max-height:96px;overflow:hidden;background:var(--ccc-bg-layer);border-radius:6px;padding:8px">${tailHtml}</pre>
    </div>
  `;
}

function renderRunning(tasks) {
  const el = _root.querySelector('#console-running');
  const nEl = _root.querySelector('#console-running-n');
  if (nEl) nEl.textContent = String(tasks.length);
  if (!el) return;
  if (!tasks.length) {
    el.innerHTML = '<div class="console-empty">当前无后台任务</div>';
    return;
  }
  el.innerHTML = tasks.map(runningCard).join('');
}

async function pollRunning() {
  try {
    const data = await apiGet('/tasks/running');
    renderRunning((data && data.tasks) || []);
  } catch (_) { /* 后台任务面板失败不阻断整体 */ }
}

function triggerLoadingTimeout() {
  if (_loadingTimeout) {
    clearTimeout(_loadingTimeout);
  }
  _loadingTimeout = setTimeout(() => {
    if (_abnList && _abnList.loading) {
      _abnList.loading = false;
      _abnList.scroller.innerHTML = `<div class="board-empty" style="color:#a33a2c;">数据加载异常，请尝试手动刷新</div>`;
    }
    if (_activeList && _activeList.loading) {
      _activeList.loading = false;
      _activeList.scroller.innerHTML = `<div class="board-empty" style="color:#a33a2c;">数据加载异常，请尝试手动刷新</div>`;
    }
    if (_writtenList && _writtenList.loading) {
      _writtenList.loading = false;
      _writtenList.scroller.innerHTML = `<div class="board-empty" style="color:#a33a2c;">数据加载异常，请尝试手动刷新</div>`;
    }
  }, 5000);
}

async function poll() {
  if (_isPolling) return;
  _isPolling = true;

  if (_pollAbortController) {
    _pollAbortController.abort();
  }
  _pollAbortController = new AbortController();
  const signal = _pollAbortController.signal;

  try {
    let counts;
    if (_ws === 'all') {
      // 1. 状态计数接 /board/states，真实状态
      counts = await apiGet('/board/states', { signal });
      const data = await apiGet('/cards?page_size=1000', { signal });
      _allCards = data.cards || [];
    } else {
      // 2. 状态计数接 /cards 聚合（按项目过滤）
      const data = await apiGet('/cards?project=' + encodeURIComponent(_ws) + '&page_size=1000', { signal });
      _allCards = data.cards || [];
      counts = { '待分派': 0, '执行中': 0, '已回写': 0, '已关闭': 0, '打回': 0 };
      for (const card of _allCards) {
        const state = getBaseState(card.state || card.status || '待分派');
        counts[state] = (counts[state] || 0) + 1;
      }
    }

    renderKPI(counts);

    // Filter cards for lists (slice each to ≤10)
    const abnCards = _allCards.filter(c => getBaseState(c.state || c.status) === '打回');
    const activeCards = _allCards.filter(c => getBaseState(c.state || c.status) === '执行中');
    const writtenCards = _allCards.filter(c => getBaseState(c.state || c.status) === '已回写');

    // Update section badges
    const abnBadge = _root.querySelector('#console-abn-n');
    if (abnBadge) abnBadge.textContent = String(abnCards.length);

    const activeBadge = _root.querySelector('#console-active-n');
    if (activeBadge) activeBadge.textContent = String(activeCards.length);

    const writtenBadge = _root.querySelector('#console-written-n');
    if (writtenBadge) writtenBadge.textContent = String(writtenCards.length);

    // Populate TaskCardList instances
    if (_abnList) _abnList.setItems(abnCards.slice(0, 10));
    if (_activeList) _activeList.setItems(activeCards.slice(0, 10));
    if (_writtenList) _writtenList.setItems(writtenCards.slice(0, 10));

  } catch (err) {
    if (err && err.name === 'AbortError') {
      return; // 忽略被 abort 产生的异常，保持 UI 最新状态
    }
    const box = _root.querySelector('#console-kpi');
    if (box) box.innerHTML = `<div class="console-empty">加载失败: ${esc(err?.message || String(err))}</div>`;

    if (_abnList) _abnList.showError(err);
    if (_activeList) _activeList.showError(err);
    if (_writtenList) _writtenList.showError(err);
  } finally {
    _isPolling = false;
    if (_loadingTimeout) {
      clearTimeout(_loadingTimeout);
      _loadingTimeout = null;
    }
  }

  // 运维告警数（来自 /ops/summary）
  try {
    const agg = await apiGet('/ops/summary', { signal });
    const badge = _root.querySelector('#console-ops-n');
    if (badge) {
      const alertCount = (agg.overview && agg.overview.alert_count) || 0;
      badge.textContent = String(alertCount);
    }
  } catch (_) { /* ops optional */ }

  const label = _root.querySelector('#console-ws-label');
  if (label) label.textContent = _ws === 'all' ? '全部' : _ws;
}

async function loadWorkspaceList() {
  try {
    const data = await apiGet('/board/summaries');
    const summaries = (data && data.summaries) || {};
    return ['all', ...Object.keys(summaries).sort()];
  } catch (_) {
    return ['all'];
  }
}

export async function mountConsole(el) {
  if (!_root) {
    _root = el;
    el.innerHTML = html();

    // Initialize list instances
    const onCardClick = (card, id) => {
      window.__PENDING_DETAIL_ID__ = id;
      const task = _allCards.find(x => x.id === id);
      if (task && (task.project || task.workspace)) {
        try {
          localStorage.setItem('ccc_hub_last_project', task.project || task.workspace);
        } catch (_) {}
      }
      location.hash = '#/board';
    };

    const onCopyClick = async (btn, id) => {
      const task = _allCards.find(x => x.id === id) || { id, title: '' };
      const ok = await copyTextToClipboard(fmtTaskCopy(task, task.state || task.status));
      if (ok) {
        window.showToast?.('已复制任务块，可粘贴到对话', 'success');
      } else {
        window.showToast?.('复制失败：请长按选中后手动复制', 'error');
      }
    };

    const abnWrapper = _root.querySelector('#console-abn-wrapper');
    if (abnWrapper) {
      _abnList = new TaskCardList(abnWrapper, { onCardClick, onCopyClick });
      _abnList.scroller.style.display = 'grid';
      _abnList.scroller.style.gridTemplateColumns = 'repeat(auto-fill, minmax(320px, 1fr))';
      _abnList.scroller.style.gap = '12px';
      _abnList.scroller.style.overflowY = 'visible';
    }

    const activeWrapper = _root.querySelector('#console-active-wrapper');
    if (activeWrapper) {
      _activeList = new TaskCardList(activeWrapper, { onCardClick, onCopyClick });
      _activeList.scroller.style.display = 'grid';
      _activeList.scroller.style.gridTemplateColumns = 'repeat(auto-fill, minmax(320px, 1fr))';
      _activeList.scroller.style.gap = '12px';
      _activeList.scroller.style.overflowY = 'visible';
    }

    const writtenWrapper = _root.querySelector('#console-written-wrapper');
    if (writtenWrapper) {
      _writtenList = new TaskCardList(writtenWrapper, { onCardClick, onCopyClick });
      _writtenList.scroller.style.display = 'grid';
      _writtenList.scroller.style.gridTemplateColumns = 'repeat(auto-fill, minmax(320px, 1fr))';
      _writtenList.scroller.style.gap = '12px';
      _writtenList.scroller.style.overflowY = 'visible';
    }

    _root.querySelector('#console-to-board').addEventListener('click', () => {
      location.hash = '#/board';
    });

    _root.querySelector('#console-ws').addEventListener('click', async () => {
      try {
        const keys = await loadWorkspaceList();
        const idx = keys.indexOf(_ws);
        _ws = keys[(idx + 1) % keys.length];

        if (_abnList) _abnList.showLoading();
        if (_activeList) _activeList.showLoading();
        if (_writtenList) _writtenList.showLoading();
        triggerLoadingTimeout();

        await poll();
      } catch (_) { /* ignore */ }
    });
  }

  if (_abnList) _abnList.showLoading();
  if (_activeList) _activeList.showLoading();
  if (_writtenList) _writtenList.showLoading();
  triggerLoadingTimeout();

  await poll();
  await pollRunning();

  if (!_timer) _timer = setInterval(() => poll().catch(() => {}), 15000);
  if (!_rtimer) _rtimer = setInterval(() => pollRunning().catch(() => {}), 8000);
}

export function unmountConsole() {
  if (_timer) {
    clearInterval(_timer);
    _timer = null;
  }
  if (_rtimer) {
    clearInterval(_rtimer);
    _rtimer = null;
  }
  if (_loadingTimeout) {
    clearTimeout(_loadingTimeout);
    _loadingTimeout = null;
  }
  if (_pollAbortController) {
    _pollAbortController.abort();
    _pollAbortController = null;
  }
  _activeList = null;
  _abnList = null;
  _writtenList = null;
  _root = null;
}
