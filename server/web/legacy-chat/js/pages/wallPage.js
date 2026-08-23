/**
 * wallPage.js — DSH 监控墙视图（#/wall · ccc-plan-045 P1.5 深度融合）
 *
 * 源自 dsh-wall v0.3.4 独立页面的等价改造：
 * - 稳定宿主模型原样保留：格子 DOM 按 sid 存 cellHosts，槽位变化只 insertBefore
 *   搬节点；且宿主 Map 为模块级单例——切走再切回，格子内容/滚动位置/渲染游标全保留
 * - SSE 生命周期归页面管：mount 连接 / unmount 关闭，重连定时器一并清理
 * - 主题融合：不再自带主题切换，跟随壳层 data-theme（theme.js 单一来源），
 *   顶栏按钮调 toggleLightDark()
 * - 已读/筛选/通知偏好沿用原 localStorage 键（用户无感迁移）
 */

import { toggleLightDark, getThemeScheme } from '../theme.js';

// ── 模块级单例状态（跨 mount 保留 → 切回秒恢复）──────────────────
let sessions = {};       // id -> snapshot（运行中）
let lastGone = {};       // id -> {snap} 未读完成/错误会话（持续显示，直到手动已读）
let readSids = {};       // id -> ts 已读会话（localStorage 持久化）
let renderedCount = {};  // sid -> 已渲染块数（增量渲染）
const READ_KEY = 'dsh-wall-read-v1';
const LAYOUT_KEY = 'dsh-wall-layout-v1';
const FILTER_KEY = 'dsh-wall-filter-v1';
const NOTIF_KEY = 'dsh-wall-notif-v1';
const READ_KEEP_MS = 7 * 86400000;
let filterMode = (() => { try { return localStorage.getItem(FILTER_KEY) || 'all'; } catch (_) { return 'all'; } })();
let focusedSid = null;    // 聚焦模式：当前放大的会话 id（null = 总览）
let notifOn = (() => { try { return localStorage.getItem(NOTIF_KEY) === '1'; } catch (_) { return false; } })();
const notifiedErr = {};   // sid -> true（每个错误周期只弹一次通知）
const cellHosts = new Map(); // sid -> 格子宿主 DOM（稳定宿主，跨 mount 存活）
const followBottom = new Map(); // sid -> bool：粘底跟随（缺省 true）。用户上滚即解除，
                                // 滚回底部自动恢复——新内容只在粘底时才自动滚动，无竞态

// ── 视图内实例（每次 mount 重建）───────────────────────────────
let _root = null;
let _disposed = false;
let _es = null;
let _reconnectTimer = null;
let _titleTimer = null;
let _docListeners = [];   // [target, type, fn] 卸载时统一摘除

function _on(target, type, fn, opts) {
  target.addEventListener(type, fn, opts);
  _docListeners.push([target, type, fn]);
}

// ── 已读 ──
function loadRead() {
  try { readSids = JSON.parse(localStorage.getItem(READ_KEY) || '{}'); } catch (_) { readSids = {}; }
  const now = Date.now();
  for (const k in readSids) if (now - readSids[k] > READ_KEEP_MS) delete readSids[k];
}
function markRead(id) {
  readSids[id] = Date.now();
  try { localStorage.setItem(READ_KEY, JSON.stringify(readSids)); } catch (_) {}
  delete lastGone[id];
  // 已读 = 仅本设备隐藏。不回写 DSH 归档；DSH→墙方向仍生效。
  syncWall();
}

// ── 工具 ──
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// ── 迷你 Markdown 渲染（自包含）──
function mdInline(s) {
  s = esc(s);
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  return s;
}
function mdTable(lines) {
  let html = '<table><tbody>';
  for (let i = 0; i < lines.length; i++) {
    if (i === 1 && /^\s*\|?[\s:-]+\|[\s:-]+(\|[\s:-]+)*\|?\s*$/.test(lines[i])) continue;
    const cells = lines[i].replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => mdInline(c.trim()));
    html += '<tr>' + cells.map(c => (i === 0 ? '<th>' : '<td>') + c + (i === 0 ? '</th>' : '</td>')).join('') + '</tr>';
  }
  return html + '</tbody></table>';
}
function mdBlock(block) {
  let html = '';
  let list = null;
  let table = null;
  const lines = block.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) {
      if (list) { html += list === 'ul' ? '</ul>' : '</ol>'; list = null; }
      table = null;
      continue;
    }
    if (table) {
      if (/^\|.*\|$/.test(line)) { table.push(line); continue; }
      html += mdTable(table); table = null;
    }
    if (/^\|.*\|$/.test(line)) {
      if (list) { html += list === 'ul' ? '</ul>' : '</ol>'; list = null; }
      table = [line];
      continue;
    }
    if (list) { html += list === 'ul' ? '</ul>' : '</ol>'; list = null; }
    let m;
    if ((m = line.match(/^(#{1,4})\s+(.*)/))) {
      html += `<h${m[1].length}>${mdInline(m[2])}</h${m[1].length}>`;
    } else if ((m = line.match(/^>\s?(.*)/))) {
      html += `<blockquote>${mdInline(m[1])}</blockquote>`;
    } else if ((m = line.match(/^[-*]\s+\[([ xX])\]\s+(.*)/))) {
      html += `<ul class="tasks"><li class="task-${m[1] === 'x' || m[1] === 'X' ? 'done' : 'todo'}">${mdInline(m[2])}</li></ul>`;
    } else if ((m = line.match(/^[-*]\s+(.*)/))) {
      html += '<ul><li>' + mdInline(m[1]) + '</li></ul>';
    } else if ((m = line.match(/^\d+\.\s+(.*)/))) {
      html += '<ol><li>' + mdInline(m[1]) + '</li></ol>';
    } else if (/^(-{3,}|\*{3,})$/.test(line)) {
      html += '<hr>';
    } else {
      html += `<p>${mdInline(line)}</p>`;
    }
  }
  if (table) html += mdTable(table);
  if (list) html += list === 'ul' ? '</ul>' : '</ol>';
  return html;
}
function md(text) {
  const raw = String(text ?? '');
  const parts = raw.split(/```/);
  let out = '';
  for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 1) {
      let code = parts[i].replace(/^[a-zA-Z0-9_+-]+\n/, '');
      out += `<pre><code>${esc(code.trim())}</code></pre>`;
    } else {
      out += mdBlock(parts[i]);
    }
  }
  return out;
}

function fmtTime(sec) {
  if (sec == null || sec === 0) return '–';
  if (sec < 60) return Math.round(sec) + 's';
  if (sec < 3600) return Math.floor(sec/60) + 'm' + Math.round(sec%60) + 's';
  return Math.floor(sec/3600) + 'h' + Math.floor((sec%3600)/60) + 'm';
}
function fmtTokens(t) {
  if (!t || (t.input + t.output + t.cache) === 0) return '–';
  return ((t.input + t.output)/1000).toFixed(1) + 'k';
}

// ── 块渲染 ──
function blkHtml(b) {
  switch (b.type) {
    case 'user':      return `<div class="blk blk-user"><span class="blk-label">用户 · ${b.followup ? '追问' : '任务'}</span>${md(b.text)}</div>`;
    case 'assistant': return `<div class="blk blk-assistant">${md(b.text)}</div>`;
    case 'reasoning': return `<div class="blk blk-reasoning"><span class="blk-label">推理</span>${esc(b.text)}</div>`;
    case 'tool':      return `<div class="blk blk-tool"><span class="blk-label">工具</span>${esc(b.text)}</div>`;
    case 'step':      return `<div class="blk blk-step"><span>步骤 ${esc(b.text)}</span></div>`;
    case 'fold':      return `<div class="blk blk-fold">${esc(b.text)}</div>`;
    case 'error':     return `<div class="blk blk-error">${esc(b.text)}</div>`;
    default:          return `<div class="blk blk-assistant">${md(b.text)}</div>`;
  }
}

// ── 格子骨架 ──
function buildCell(sid) {
  const el = document.createElement('div');
  el.className = 'cell';
  el.dataset.sid = sid;
  el.innerHTML = `
    <div class="cell-head">
      <span class="cell-title"></span>
      <span class="badge"></span>
      <span class="dot"></span>
      <span class="cell-dur"></span>
    </div>
    <div class="cell-body"></div>
    <div class="cell-foot">
      <span class="foot-stats">
        <span title="轮次">↻ <b class="m-turn"></b></span>
        <span title="步骤">≡ <b class="m-step"></b></span>
        <span title="耗时">⏱ <b class="m-dur"></b></span>
        <span title="Token"><b class="m-tok"></b></span>
        <span title="模型" class="foot-model"><b class="m-model"></b></span>
      </span>
    </div>
    <div class="cell-input">
      <button class="ci-toggle">💬 发消息…</button>
      <div class="ci-box">
        <textarea class="ci-text" rows="2" placeholder="输入消息，Enter 发送（Shift+Enter 换行）"></textarea>
        <div class="ci-actions">
          <span class="ci-hint"></span>
          <button class="ci-send">发送 ▶</button>
        </div>
      </div>
    </div>
    <button class="jump-latest">↓ 回到最新</button>`;
  const body = el.querySelector('.cell-body');
  body.addEventListener('scroll', () => {
    const sid = el.dataset.sid;
    const dist = body.scrollHeight - body.scrollTop - body.clientHeight;
    // 用户每次滚动都同步粘底状态：贴近底部=跟随；上滚=立即解除跟随
    followBottom.set(sid, dist < 60);
    if (dist < 60) hideJump(el);
  });
  // 2026-08-24 手势修复（老板反馈）：正文区吃掉滚轮/触控板的横向分量，
  // 杜绝「按住正文滑动带动整列横漂」；纵向分量照常滚动。
  // 横轨的横向浏览改由格子间隙/格头区或手机轮播手势承担。
  body.addEventListener('wheel', (e) => {
    if (e.deltaX === 0) return;
    e.preventDefault();
    if (e.deltaY !== 0) body.scrollTop += e.deltaY;
  }, { passive: false });
  el.querySelector('.jump-latest').addEventListener('click', () => {
    followBottom.set(el.dataset.sid, true); // 点按钮 = 显式恢复跟随
    body.scrollTop = body.scrollHeight;
    hideJump(el);
  });
  return el;
}

// ── 更新已有格子（增量追加，不重建）──
function updateCell(el, s, first) {
  const sid = el.dataset.sid;
  // 状态类名三态：绿脉冲=active / 红闪=error / 橙静止=active+stalled（待人工介入）
  el.className = 'cell ' + (s.status === 'error' ? 'error'
    : s.stalled ? 'active stalled'
    : s.status === 'done' ? 'done' : 'active');
  el.querySelector('.cell-title').textContent = s.title || sid.slice(0, 20);
  el.querySelector('.cell-title').title = s.title || '';
  const badge = el.querySelector('.badge');
  if (s.source === 'ccc') { badge.className = 'badge ccc'; badge.textContent = 'CCC'; }
  else if (s.source === 'quant') { badge.className = 'badge quant'; badge.textContent = '量化'; }
  else if (s.source === 'manual') { badge.className = 'badge manual'; badge.textContent = '手动'; }
  else { badge.className = 'badge'; badge.textContent = ''; }
  el.querySelector('.cell-dur').textContent = fmtTime(s.elapsed);
  el.querySelector('.m-turn').textContent = s.turn;
  el.querySelector('.m-step').textContent = s.step;
  el.querySelector('.m-dur').textContent = fmtTime(s.elapsed);
  el.querySelector('.m-tok').textContent = fmtTokens(s.tokens);
  { const raw = s.model || '–'; const short = raw === '–' ? '–' : (raw.split('/').pop().split(':').pop().slice(0, 14) || raw.slice(0, 14)); const mEl = el.querySelector('.m-model'); mEl.textContent = short; mEl.title = raw; mEl.closest('.foot-model').title = raw; }
  let stall = el.querySelector('.stall-badge');
  if (s.stalled) {
    if (!stall) {
      stall = document.createElement('button');
      stall.className = 'stall-badge';
      stall.textContent = '⏸ 可能等待输入';
      el.querySelector('.cell-head').appendChild(stall);
    }
  } else if (stall) {
    stall.remove();
  }
  const head = el.querySelector('.cell-head');
  let btn = head.querySelector('.mark-read');
  if (s.status === 'done' || s.status === 'error') {
    if (!btn) {
      btn = document.createElement('button');
      btn.className = 'mark-read';
      btn.textContent = '已读';
      btn.onclick = () => markRead(sid);
      head.appendChild(btn);
    }
  } else if (btn) {
    btn.remove();
  }
  let reasonEl = el.querySelector('.cell-reason');
  if (s.reason && s.status === 'error') {
    if (!reasonEl) {
      reasonEl = document.createElement('div');
      reasonEl.className = 'cell-reason';
      el.appendChild(reasonEl);
    }
    reasonEl.textContent = s.reason;
  } else if (reasonEl) {
    reasonEl.remove();
  }
  const body = el.querySelector('.cell-body');
  const blocks = s.blocks || [];
  let from = renderedCount[sid] || 0;
  if (blocks.length < from) {
    body.innerHTML = '';
    from = 0;
    followBottom.set(sid, true); // 整格重建 = 内容上下文重置，恢复跟随
  }
  if (from < blocks.length) {
    // 粘底跟随（2026-08-24 语义升级）：缺省始终滚到底部；仅当用户上滚离开底部
    // （followBottom=false，由滚动事件实时维护）才不打扰阅读、浮出「回到最新」。
    // 用户滚回底部或点按钮即恢复跟随——无定时器、无竞态窗口。
    const pinned = followBottom.get(sid) !== false;
    const frag = document.createDocumentFragment();
    for (let k = from; k < blocks.length; k++) {
      const div = document.createElement('div');
      div.innerHTML = blkHtml(blocks[k]);
      frag.appendChild(div);
    }
    body.appendChild(frag);
    renderedCount[sid] = blocks.length;
    if (pinned || first) {
      requestAnimationFrame(() => { body.scrollTop = body.scrollHeight; hideJump(el); });
    } else {
      showJump(el);
    }
  } else {
    renderedCount[sid] = blocks.length;
    if (first) requestAnimationFrame(() => { body.scrollTop = body.scrollHeight; });
  }
}

function showJump(el) { const b = el.querySelector('.jump-latest'); if (b) b.classList.add('show'); }
function hideJump(el) { const b = el.querySelector('.jump-latest'); if (b) b.classList.remove('show'); }

// ── 来源筛选 ──
function matchFilter(sid) {
  const g = lastGone[sid] && lastGone[sid].snap;
  switch (filterMode) {
    case 'all':  return true;
    case 'err':  return !!(g && g.status === 'error');
    default:     return true; // 兼容旧 localStorage 残留 ccc/quant/manual
  }
}

// ── 格子同步（稳定宿主：DOM 按 sid 持久化，槽位变化只搬运节点不重建）──
function syncWall() {
  const wall = _root.querySelector('.wall');
  const statsEl = _root.querySelector('.stats');
  const now = Date.now();
  for (const k in readSids) if (now - readSids[k] > READ_KEEP_MS) delete readSids[k];

  const activeIds = Object.keys(sessions).filter(matchFilter);
  const goneIds = Object.keys(lastGone).filter(matchFilter);

  if (!focusedSid) {
    activeIds.sort((a, b) => (sessions[a].started_ms || 0) - (sessions[b].started_ms || 0));
    goneIds.sort((a, b) => (lastGone[b].snap.ended_ms || 0) - (lastGone[a].snap.ended_ms || 0));
  }
  const slots = activeIds.concat(goneIds);

  const live = new Set([...Object.keys(sessions), ...Object.keys(lastGone)]);
  for (const sid of [...cellHosts.keys()]) {
    if (!live.has(sid)) {
      const el = cellHosts.get(sid);
      if (el) el.remove();
      cellHosts.delete(sid);
      delete renderedCount[sid];
    }
  }

  const target = [];
  for (let i = 0; i < slots.length; i++) {
    const sid = slots[i];
    target.push({ sid, snap: sessions[sid] || lastGone[sid].snap });
  }
  if (focusedSid && !target.some(t => t.sid === focusedSid)) {
    const snap = sessions[focusedSid] || (lastGone[focusedSid] && lastGone[focusedSid].snap);
    if (snap) target.push({ sid: focusedSid, snap });
  }
  const emptyIdle = target.length === 0;
  const wantCount = emptyIdle ? 1 : target.length;

  for (let i = 0; i < target.length; i++) {
    const want = target[i];
    let el = cellHosts.get(want.sid);
    if (!el) {
      el = buildCell(want.sid);
      cellHosts.set(want.sid, el);
      renderedCount[want.sid] = 0;
    }
    updateCell(el, want.snap);
    const cur = wall.children[i];
    if (cur !== el) wall.insertBefore(el, cur || null);
  }
  if (emptyIdle) {
    const cur = wall.children[0];
    if (!cur || !cur.classList.contains('cell-idle')) {
      const idle = document.createElement('div');
      idle.className = 'cell cell-idle';
      idle.textContent = '等待活跃对话…';
      wall.insertBefore(idle, cur || null);
    }
  }
  while (wall.children.length > wantCount) wall.removeChild(wall.lastChild);

  if (focusedSid && !cellHosts.has(focusedSid)) focusedSid = null;
  applyFocusClasses();

  const tnow = new Date();
  statsEl.innerHTML = `活跃 ${activeIds.length} · 未读 ${goneIds.length}<span id="updTime"> · 更新 ${tnow.toTimeString().slice(0, 8)}</span>`;
  rebuildPager(target.length);
}

// ── 手机轮播页码指示器 ──
let pagerCount = 0;
function rebuildPager(n) {
  const pagerEl = _root.querySelector('#wall-pager');
  pagerCount = focusedSid ? 0 : n;
  if (!pagerCount) { pagerEl.innerHTML = ''; return; }
  let html = '';
  for (let i = 0; i < pagerCount; i++) html += `<button data-i="${i}" aria-label="第 ${i + 1} 格"></button>`;
  pagerEl.innerHTML = html;
  updatePagerActive();
}
function updatePagerActive() {
  const pagerEl = _root.querySelector('#wall-pager');
  if (!pagerCount || !pagerEl.children.length) return;
  const wall = _root.querySelector('.wall');
  const firstCell = wall.querySelector('.cell');
  const step = firstCell ? firstCell.getBoundingClientRect().width + 10 : wall.clientWidth;
  const idx = Math.min(pagerCount - 1, Math.max(0, Math.round(wall.scrollLeft / step)));
  for (let k = 0; k < pagerEl.children.length; k++) {
    pagerEl.children[k].classList.toggle('on', k === idx);
  }
}

// ── 聚焦模式样式同步 ──
function applyFocusClasses() {
  const wall = _root.querySelector('.wall');
  for (const el of wall.querySelectorAll('.cell')) {
    el.classList.toggle('focused', !!focusedSid && el.dataset.sid === focusedSid);
  }
  wall.classList.toggle('single', !!focusedSid);
}

// ── 错误系统通知 ──
function applyNotifBtn() {
  const notifBtn = _root.querySelector('#wall-notif-btn');
  notifBtn.textContent = notifOn ? '🔔 开' : '🔔 关';
  notifBtn.classList.toggle('on', notifOn);
}
function maybeNotify(s) {
  if (!notifOn) return;
  if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return;
  if (notifiedErr[s.id]) return;
  notifiedErr[s.id] = true;
  try {
    new Notification(`⚠ 任务出错 · ${s.title || s.id.slice(0, 20)}`, {
      body: s.reason || '任务异常结束',
      tag: 'dsh-wall-' + s.id,
    });
  } catch (_) {}
}

// ── 标题栏未读错误闪烁（仅本视图挂载期间运行）──
function startTitleBlink() {
  const BASE = 'CCC · 信息墙';
  stopTitleBlink();
  _titleTimer = setInterval(() => {
    const n = Object.values(lastGone).filter(g => g.snap.status === 'error' && !readSids[g.snap.id]).length;
    if (n > 0) {
      _titleTick++;
      document.title = (_titleTick % 2 ? `(${n}) ⚠ ` : '') + BASE;
    } else if (document.title !== BASE) {
      document.title = BASE;
      _titleTick = 0;
    }
  }, 1500);
}
function stopTitleBlink() {
  if (_titleTimer) { clearInterval(_titleTimer); _titleTimer = null; }
}
let _titleTick = 0;

// ── SSE ──
function applyState(sessList) {
  sessions = {};
  for (const s of sessList) {
    if (s.status === 'done' || s.status === 'error') {
      if (readSids[s.id]) continue;
      const prev = lastGone[s.id] && lastGone[s.id].snap;
      lastGone[s.id] = { snap: s };
      if (s.status === 'error' && (!prev || prev.reason !== s.reason)) maybeNotify(s);
      continue;
    }
    sessions[s.id] = s;
    delete lastGone[s.id];
  }
  syncWall();
}

function connect() {
  const offlineEl = _root.querySelector('#wall-offline');
  const es = new EventSource('/wall/api/stream');
  es.addEventListener('state', e => {
    offlineEl.style.display = 'none';
    try {
      const d = JSON.parse(e.data);
      if (Array.isArray(d.archived)) {
        for (const aid of d.archived) { delete sessions[aid]; delete lastGone[aid]; }
      }
      applyState(d.sessions || []);
    } catch (_) {}
  });
  es.onerror = () => {
    offlineEl.style.display = 'block';
    es.close();
    _reconnectTimer = setTimeout(connect, 3000);
  };
  return es;
}

// ── 格内对话：发送走 /wall/api/dsh/prompt → DSH session.prompt(queue)──
function closeInput(wrap) {
  wrap.classList.remove('open');
  wrap.querySelector('.ci-text').blur();
}
async function sendPrompt(wrap) {
  const sid = wrap.closest('.cell').dataset.sid;
  const ta = wrap.querySelector('.ci-text');
  const hint = wrap.querySelector('.ci-hint');
  const btn = wrap.querySelector('.ci-send');
  const text = ta.value.trim();
  if (!text || btn.disabled) return;
  btn.disabled = true;
  hint.classList.remove('err');
  hint.textContent = '发送中…';
  try {
    const r = await fetch('/wall/api/dsh/prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId: sid, text }),
    });
    const d = await r.json();
    if (d.ok) {
      hint.textContent = '已排队 ✓';
      ta.value = '';
      setTimeout(() => closeInput(wrap), 1200);
    } else {
      hint.textContent = d.error || '发送失败';
      hint.classList.add('err');
    }
  } catch (_) {
    hint.textContent = '网络错误，请重试';
    hint.classList.add('err');
  }
  btn.disabled = false;
}

// ── 视图骨架 ──
function shellHTML() {
  return `
  <div id="wall-offline" class="offline">连接中断，正在重连…</div>
  <div class="topbar">
    <h1>DSH 监控墙</h1>
    <div class="filter-switch" id="wall-filter-switch">
      <button data-f="all" class="active">全部</button>
      <button data-f="err" class="chip-err">错误</button>
    </div>
    <button class="theme-btn" id="wall-theme-btn" title="切换亮色/暗色"></button>
    <button class="theme-btn notif-btn" id="wall-notif-btn" title="任务出错时弹系统通知">🔔 关</button>
    <div class="stats" id="wall-stats"></div>
  </div>
  <div class="wall"></div>
  <div id="wall-pager"></div>`;
}

export function mountWall(rootEl, ctx = {}) {
  _root = rootEl;
  _disposed = false;
  _root.innerHTML = shellHTML();
  loadRead();

  // 主题按钮：跟随壳层 theme.js（融合点：不再独立存主题键）
  const themeBtn = _root.querySelector('#wall-theme-btn');
  const syncThemeBtn = () => {
    const t = getThemeScheme() === 'light' ? 'light'
      : getThemeScheme() === 'dark' ? 'dark'
      : (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    themeBtn.textContent = t === 'light' ? '☀' : '☾';
    themeBtn.title = t === 'light' ? '切到暗色' : '切到亮色';
  };
  syncThemeBtn();
  themeBtn.addEventListener('click', () => {
    toggleLightDark();
    setTimeout(syncThemeBtn, 0);
  });

  // 筛选切换
  const filterSwitch = _root.querySelector('#wall-filter-switch');
  filterSwitch.querySelectorAll('button').forEach(b =>
    b.classList.toggle('active', b.dataset.f === filterMode));
  filterSwitch.addEventListener('click', e => {
    const f = e.target.dataset.f;
    if (!f) return;
    filterMode = f;
    try { localStorage.setItem(FILTER_KEY, f); } catch (_) {}
    filterSwitch.querySelectorAll('button').forEach(b =>
      b.classList.toggle('active', b.dataset.f === f));
    syncWall();
  });

  applyNotifBtn();
  _on(_root.querySelector('#wall-notif-btn'), 'click', async () => {
    if (!notifOn) {
      if (!('Notification' in window)) { alert('此浏览器不支持系统通知'); return; }
      const p = await Notification.requestPermission();
      if (p !== 'granted') return;
      notifOn = true;
    } else {
      notifOn = false;
    }
    try { localStorage.setItem(NOTIF_KEY, notifOn ? '1' : '0'); } catch (_) {}
    applyNotifBtn();
  });

  const wall = _root.querySelector('.wall');

  // 聚焦模式：点击格子标题栏 → 单格放大
  _on(wall, 'click', e => {
    if (e.target.closest('.mark-read') || e.target.closest('.jump-latest')) return;
    const head = e.target.closest('.cell-head');
    if (!head) return;
    const sid = head.parentElement.dataset.sid;
    if (!sid) return;
    focusedSid = focusedSid === sid ? null : sid;
    syncWall();
  });

  // 停滞角标 → 对话化引导
  _on(wall, 'click', e => {
    const sb = e.target.closest('.stall-badge');
    if (!sb) return;
    const wrap = sb.closest('.cell').querySelector('.cell-input');
    wrap.classList.add('open');
    const ta = wrap.querySelector('.ci-text');
    ta.placeholder = 'DSH 可能在等待你的选择/指示，直接一句话回复即可…';
    const hint = wrap.querySelector('.ci-hint');
    hint.textContent = '⏸ 会话疑似停滞：直接回复一句话即可继续';
    hint.classList.remove('err');
    setTimeout(() => ta.focus(), 30);
  });

  // 推理折叠 + 输入框展开/发送
  _on(wall, 'click', e => {
    const reason = e.target.closest('.blk-reasoning');
    if (reason && !reason.classList.contains('open')) { reason.classList.add('open'); return; }
    if (reason && reason.classList.contains('open')) { reason.classList.remove('open'); return; }
    const tg = e.target.closest('.ci-toggle');
    if (tg) {
      const wrap = tg.closest('.cell-input');
      wrap.classList.add('open');
      setTimeout(() => wrap.querySelector('.ci-text').focus(), 30);
      return;
    }
    if (e.target.closest('.ci-send')) sendPrompt(e.target.closest('.cell-input'));
  });

  _on(wall, 'keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey && e.target.classList && e.target.classList.contains('ci-text')) {
      e.preventDefault();
      sendPrompt(e.target.closest('.cell-input'));
    }
    if (e.key === 'Escape' && e.target.classList && e.target.classList.contains('ci-text')) {
      closeInput(e.target.closest('.cell-input'));
    }
  });

  _on(wall, 'focusin', e => {
    if (e.target.classList && e.target.classList.contains('ci-text')) {
      setTimeout(() => e.target.scrollIntoView({ block: 'nearest', behavior: 'smooth' }), 250);
    }
  });

  // 横轨滚动 → 页码指示器同步
  _on(wall, 'scroll', () => {
    if (wall.scrollWidth > wall.clientWidth + 1) updatePagerActive();
  }, { passive: true });

  const pagerEl = _root.querySelector('#wall-pager');
  _on(pagerEl, 'click', e => {
    const b = e.target.closest('button[data-i]');
    if (!b) return;
    const firstCell = wall.querySelector('.cell');
    const step = firstCell ? firstCell.getBoundingClientRect().width + 10 : wall.clientWidth;
    wall.scrollTo({ left: (+b.dataset.i) * step, behavior: 'smooth' });
  });

  // 文档级监听（卸载时统一摘除）
  _on(document, 'keydown', e => {
    if (e.key === 'Escape' && focusedSid) { focusedSid = null; syncWall(); }
  });
  _on(document, 'click', e => {
    if (_disposed) return;
    if (!e.target.closest('.cell-input') && !e.target.closest('.stall-badge')) {
      _root.querySelectorAll('.cell-input.open').forEach(w => w.classList.remove('open'));
    }
  });
  _on(document, 'visibilitychange', () => {
    if (!document.hidden && _es && _es.readyState === EventSource.CLOSED) {
      _es.close();
      _es = connect();
    }
  });

  // 标题未读闪烁
  startTitleBlink();

  // 稳定宿主回填：上次挂载的格子节点重新插入横轨，滚动位置与渲染游标全保留
  const container = _root.querySelector('.wall');
  for (const el of cellHosts.values()) container.appendChild(el);

  // 启动流
  _es = connect();
}

export function unmountWall() {
  _disposed = true;
  if (_es) { _es.close(); _es = null; }
  if (_reconnectTimer) { clearTimeout(_reconnectTimer); _reconnectTimer = null; }
  stopTitleBlink();
  for (const [t, type, fn] of _docListeners) t.removeEventListener(type, fn);
  _docListeners = [];
  if (_titleTimer) { clearInterval(_titleTimer); _titleTimer = null; }
}
