/**
 * App-parity sidebar（对齐 Desktop CodexSidebar）：
 * 重置 / 对话·看板·运维 → 项目卡（选中展开 thread）→ 搜索消息 → 用法/设置
 */
import { state } from '../state.js';
import { escapeHtml, debounce, desktopThreadId, resolveProjectPath } from '../utils.js';
import { showToast } from './toast.js';
import { setProjectActive } from './composer.js';
import { navigate, currentRoute } from '../router.js';
// api.js 新增：loadThreads 拉项目下会话（服务端会话存储）
import { loadThreads, deleteThread } from '../api.js';

let _projects = [];
// T47：项目下服务端会话缓存（{projectId: [thread...]}），选中项目时懒加载
let _serverThreads = {};

function projectDisplayName(p) {
  if (!p) return '';
  if (p.id === 'ccc') return 'CCC 平台';
  const n = String(p.name || '').trim();
  return n || p.id;
}

function tabsForProject(pid) {
  return (state.get('tabs') || []).filter((t) => (t.projectId || 'ccc') === pid);
}

function isMainSession(sid, pid) {
  return String(sid || '') === desktopThreadId(pid, 'main');
}

// T47：项目下会话 = 服务端持久化会话 + 本地已开 tabs（按 sessionId 去重，服务端优先）。
// 服务端会话列出的是「刷新/重启后仍在」的真会话；本地 tabs 是本次会话中已打开的上下文。
function mergedThreadsFor(pid) {
  const server = _serverThreads[pid] || [];
  const local = tabsForProject(pid);
  const seen = new Set();
  const out = [];
  for (const st of server) {
    const sid = st.thread_id || '';
    if (!sid) continue;
    seen.add(sid);
    out.push({
      _server: true,
      threadId: sid,
      sessionId: sid,
      title: st.title || '新对话',
      updated_at: st.updated_at || '',
      message_count: st.message_count || 0,
    });
  }
  for (const t of local) {
    const sid = t.sessionId || desktopThreadId(pid, t.id);
    if (seen.has(sid)) continue;
    seen.add(sid);
    out.push({
      _server: false,
      threadId: sid,
      sessionId: sid,
      id: t.id,
      tab: t,
      title: t.title || '对话',
    });
  }
  // 主会话（::main）排最前，其余按最后活动倒序
  out.sort((a, b) => {
    const am = isMainSession(a.sessionId, pid) ? 0 : 1;
    const bm = isMainSession(b.sessionId, pid) ? 0 : 1;
    if (am !== bm) return am - bm;
    return String(b.updated_at || '').localeCompare(String(a.updated_at || ''));
  });
  return out;
}

// T47：懒加载选中项目下服务端会话，刷新后渲染
async function loadServerThreads(pid) {
  if (_serverThreads[pid]) return;
  try {
    _serverThreads[pid] = await loadThreads(pid);
  } catch (_) {
    _serverThreads[pid] = [];
  }
  refreshSidebar();
}

export function renderAppSidebar(projects) {
  if (Array.isArray(projects)) {
    _projects = projects.slice();
    state.set('projects', _projects);
  } else {
    _projects = state.get('projects') || _projects || [];
  }
  const host = document.getElementById('sidebar-projects');
  if (!host) return;

  const activePid = state.get('currentProject') || 'ccc';
  const activeSid = state.get('currentSessionId');

  if (!_projects.length) {
    host.innerHTML =
      '<div class="sidebar-empty"><div class="sidebar-empty-title">暂无项目</div>' +
      '<div class="sidebar-empty-sub">Hub 恢复后自动出现</div></div>';
    return;
  }

  // T47：选中项目懒加载其服务端会话（仅一次；后续由刷新驱动）
  if (activePid) loadServerThreads(activePid);

  let html = '';
  for (const p of _projects) {
    const selected = p.id === activePid;
    const threads = mergedThreadsFor(p.id);
    const streaming = tabsForProject(p.id).some((t) => t._streaming);
    const status = streaming ? '对话中' : '';
    html +=
      '<div class="project-card-wrap" data-project-id="' +
      escapeHtml(p.id) +
      '">' +
      '<div class="project-card' +
      (selected ? ' selected' : '') +
      '" role="listitem">' +
      '<button type="button" class="project-card-main" data-act="open" title="' +
      escapeHtml(p.name || p.id) +
      '">' +
      '<span class="project-card-folder' +
      (selected ? ' is-open' : '') +
      '" aria-hidden="true"></span>' +
      '<span class="project-card-text">' +
      '<span class="project-card-name">' +
      escapeHtml(projectDisplayName(p)) +
      '</span>' +
      (status
        ? '<span class="project-card-status">' + escapeHtml(status) + '</span>'
        : '') +
      '</span>' +
      '</button>' +
      '<button type="button" class="project-card-plus" data-act="new" title="新建会话" aria-label="新建会话">+</button>' +
      '<span class="project-card-trail" aria-hidden="true">' +
      (streaming ? '<span class="project-card-spin"></span>' : '') +
      '</span>' +
      '</div>';

    if (selected) {
      html += '<div class="sidebar-thread-list">';
      const rows = threads.slice().slice(0, 12);
      if (!rows.length) {
        html +=
          '<div class="sidebar-thread-empty">暂无会话 · 点 + 新建</div>';
      } else {
        for (const t of rows) {
          const sid = t.sessionId || desktopThreadId(p.id, t.id);
          const on = sid === activeSid || t.id === state.get('activeTabId');
          const title =
            t.title && t.title !== '新对话'
              ? t.title
              : isMainSession(sid, p.id)
                ? '对话'
                : String(sid).split('::').pop()?.slice(0, 12) || '会话';
          // 服务端会话用 threadId 作 data-tab-id（打开时物化本地 tab）；本地会话用 t.id
          const tabId = t.id || encodeURIComponent(sid);
          html +=
            '<div class="sidebar-thread-row' +
            (on ? ' selected' : '') +
            '" data-tab-id="' +
            escapeHtml(tabId) +
            '" data-sid="' +
            escapeHtml(sid) +
            '"' +
            (t._server ? ' data-server="1"' : '') +
            ' title="单击打开 · 双击重命名">' +
            '<span class="sidebar-thread-icon" aria-hidden="true">○</span>' +
            '<span class="sidebar-thread-title">' +
            escapeHtml(title) +
            '</span>' +
            '<span class="sidebar-thread-actions">' +
            '<button type="button" class="sidebar-thread-act" data-act2="rename" title="重命名">✎</button>' +
            '<button type="button" class="sidebar-thread-act" data-act2="clear" title="删除本会话">⌫</button>' +
            '</span>' +
            '</div>';
        }
      }
      html += '</div>';
    }
    html += '</div>';
  }
  host.innerHTML = html;

  host.querySelectorAll('[data-act]').forEach((el) => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      const wrap = el.closest('.project-card-wrap');
      const pid = wrap?.dataset?.projectId;
      if (!pid) return;
      const act = el.dataset.act;
      if (act === 'open') {
        openProject(pid);
      } else if (act === 'new') {
        createThreadForProject(pid);
      }
    });
  });

  // T47/T45：会话行——单击打开、双击重命名、悬停操作（重命名/删除）
  // 服务端会话行（data-server="1"）在本地无 tab：打开时物化 tab，删除走服务端。
  host.querySelectorAll('.sidebar-thread-row').forEach((row) => {
    const pid = row.closest('.project-card-wrap')?.dataset?.projectId;
    const tabId = row.dataset.tabId;
    const sid = row.dataset.sid;
    if (row.dataset.server === '1') {
      row.addEventListener('click', (e) => {
        const act = e.target.closest('.sidebar-thread-act');
        if (act) {
          e.stopPropagation();
          if (act.dataset.act2 === 'rename') renameServerThread(row, pid, sid);
          else if (act.dataset.act2 === 'clear') deleteThreadConfirm(pid, sid);
          return;
        }
        openServerThread(pid, sid);
      });
      row.addEventListener('dblclick', (e) => {
        if (e.target.closest('.sidebar-thread-act')) return;
        renameServerThread(row, pid, sid);
      });
      return;
    }
    row.addEventListener('click', (e) => {
      const act = e.target.closest('.sidebar-thread-act');
      if (act) {
        e.stopPropagation();
        if (act.dataset.act2 === 'rename') renameThreadRow(row, tabId, pid);
        else if (act.dataset.act2 === 'clear') clearThread(tabId, pid);
        return;
      }
      openThreadTab(tabId, pid);
    });
    row.addEventListener('dblclick', (e) => {
      if (e.target.closest('.sidebar-thread-act')) return;
      renameThreadRow(row, tabId, pid);
    });
  });

  import('../streamRegistry.js')
    .then((m) => {
      const liveIds = new Set(m.streamingProjectIds() || []);
      host.querySelectorAll('.project-card-wrap').forEach((wrap) => {
        const pid = wrap.dataset.projectId;
        const trail = wrap.querySelector('.project-card-trail');
        const statusEl = wrap.querySelector('.project-card-status');
        if (liveIds.has(pid)) {
          if (trail && !trail.querySelector('.project-card-spin')) {
            trail.innerHTML = '<span class="project-card-spin"></span>';
          }
          if (statusEl) statusEl.textContent = '对话中';
          else {
            const text = wrap.querySelector('.project-card-text');
            if (text && !text.querySelector('.project-card-status')) {
              const s = document.createElement('span');
              s.className = 'project-card-status';
              s.textContent = '对话中';
              text.appendChild(s);
            }
          }
        }
      });
    })
    .catch(() => {});
}

function openProject(pid) {
  const p = _projects.find((x) => x.id === pid);
  navigate('chat');
  setProjectActive(pid, projectDisplayName(p) || pid);
  // project-change → switchToProjectTab（优先 ::main）
  syncDestHighlight();
  closeMobileSidebar();
}

function createThreadForProject(pid) {
  const p = _projects.find((x) => x.id === pid);
  navigate('chat');
  const name = projectDisplayName(p) || pid;
  state.set('currentProject', pid);
  try {
    localStorage.setItem('ccc_hub_last_project', pid);
  } catch (_) {}
  const sel = document.getElementById('project-select');
  if (sel) sel.value = pid;
  const display = document.getElementById('project-display');
  if (display) display.textContent = name;
  document.dispatchEvent(
    new CustomEvent('new-tab', { detail: { projectId: pid } })
  );
  refreshSidebar();
  closeMobileSidebar();
}

function openThreadTab(tabId, pid) {
  if (!tabId) return;
  navigate('chat');
  if (state.get('currentProject') !== pid) {
    const p = _projects.find((x) => x.id === pid);
    setProjectActive(pid, projectDisplayName(p) || pid);
  }
  document.dispatchEvent(new CustomEvent('switch-tab', { detail: { id: tabId } }));
  refreshSidebar();
  closeMobileSidebar();
}

// ── T47：服务端会话行交互（物化本地 tab / 重命名 / 删除） ──

/** 打开一个服务端持久化会话：若本地无对应 tab 则物化（建 tab + 拉历史）再切换。 */
async function openServerThread(pid, sid) {
  if (!sid) return;
  navigate('chat');
  if (state.get('currentProject') !== pid) {
    const p = _projects.find((x) => x.id === pid);
    setProjectActive(pid, projectDisplayName(p) || pid);
  }
  const tabs = state.get('tabs') || [];
  let tab = tabs.find((t) => (t.sessionId || desktopThreadId(pid, t.id)) === sid);
  if (!tab) {
    // 物化本地 tab：threadId 即 sessionId；消息首次渲染时由 loadSession 拉取
    const { loadSession } = await import('../api.js');
    const id = 'sid-' + encodeURIComponent(sid).replace(/%/g, '').slice(0, 24);
    tab = {
      id,
      title: sid.split('::').pop()?.slice(0, 12) || '会话',
      sessionId: sid,
      messages: [],
      projectId: pid,
    };
    try {
      const loaded = await loadSession(sid, pid);
      tab.messages = loaded.messages || [];
    } catch (_) {}
    tabs.push(tab);
    state.set('tabs', tabs);
  }
  state.set('activeTabId', tab.id);
  state.set('currentSessionId', sid);
  document.dispatchEvent(new CustomEvent('switch-tab', { detail: { id: tab.id } }));
  refreshSidebar();
  closeMobileSidebar();
}

/** 删除服务端会话（仅删会话存储/该 thread，不动任务卡/看板）。 */
async function deleteThreadConfirm(pid, sid) {
  if (!sid) return;
  if (!confirm('删除本会话？持久化记录将被删除，无法撤销。看板与编排任务不受影响。')) return;
  try {
    await deleteThread(pid, sid);
    if (_serverThreads[pid]) {
      _serverThreads[pid] = _serverThreads[pid].filter((t) => t.thread_id !== sid);
    }
    // 若本地开了对应 tab，一并移出
    const tabs = state.get('tabs') || [];
    const kept = tabs.filter((t) => (t.sessionId || desktopThreadId(pid, t.id)) !== sid);
    state.set('tabs', kept);
    if (state.get('currentSessionId') === sid) {
      state.set('currentSessionId', '');
    }
    refreshSidebar();
    showToast('会话已删除', 'success');
  } catch (e) {
    showToast(e.message || '删除失败', 'error');
  }
}

/** 重命名服务端会话（持久化标题）。行内输入，回车/失焦保存。 */
function renameServerThread(row, pid, sid) {
  if (!row || !sid) return;
  const titleEl = row.querySelector('.sidebar-thread-title');
  if (!titleEl) return;
  const orig = titleEl.textContent || '会话';
  const input = document.createElement('input');
  input.className = 'sidebar-thread-rename';
  input.value = orig;
  input.maxLength = 40;
  titleEl.replaceWith(input);
  input.focus();
  input.select();
  let done = false;
  const commit = async () => {
    if (done) return;
    done = true;
    const val = input.value.trim();
    if (val && val !== orig) {
      const { apiPost } = await import('../api.js');
      try {
        await apiPost(
          '/projects/' + encodeURIComponent(pid) + '/threads/' + encodeURIComponent(sid) + '/rename',
          { title: val }
        );
        if (_serverThreads[pid]) {
          const hit = _serverThreads[pid].find((t) => t.thread_id === sid);
          if (hit) hit.title = val;
        }
        // 同步已物化的本地 tab 标题
        const tabs = state.get('tabs') || [];
        const tab = tabs.find((t) => (t.sessionId || desktopThreadId(pid, t.id)) === sid);
        if (tab) {
          tab.title = val;
          import('./titlebar.js').then((m) => m.renderTabs(tabs, state.get('activeTabId')));
        }
      } catch (e) {
        showToast(e.message || '重命名失败', 'error');
      }
    }
    refreshSidebar();
  };
  input.addEventListener('blur', commit);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      commit();
    } else if (e.key === 'Escape') {
      done = true;
      refreshSidebar();
    }
  });
}

/** T45：会话重命名（本地）。双击会话行或点 ✎ → 行内输入，回车/失焦保存。 */
function renameThreadRow(row, tabId, pid) {
  if (!row || !tabId) return;
  const tabs = state.get('tabs') || [];
  const tab = tabs.find((t) => t.id === tabId);
  const titleEl = row.querySelector('.sidebar-thread-title');
  if (!titleEl) return;
  const orig = (tab && tab.title) || '对话';
  const input = document.createElement('input');
  input.className = 'sidebar-thread-rename';
  input.value = orig;
  input.maxLength = 40;
  titleEl.replaceWith(input);
  input.focus();
  input.select();
  let done = false;
  const commit = () => {
    if (done) return;
    done = true;
    const val = input.value.trim();
    if (tab && val && val !== tab.title) {
      tab.title = val;
      state.set('tabs', tabs);
      import('./titlebar.js').then((m) => m.renderTabs(tabs, state.get('activeTabId')));
    }
    refreshSidebar();
  };
  input.addEventListener('blur', commit);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      commit();
    } else if (e.key === 'Escape') {
      done = true;
      refreshSidebar();
    }
  });
}

/** T45：清空本会话（本地，仅清该 tab 消息，不删其他会话/看板）。 */
function clearThread(tabId, pid) {
  if (!tabId) return;
  if (!confirm('清空本会话？本机会话记录会被清空，无法撤销。看板与编排任务不受影响。')) return;
  const tabs = state.get('tabs') || [];
  const tab = tabs.find((t) => t.id === tabId);
  if (!tab) return;
  tab.messages = [];
  state.set('tabs', tabs);
  if (state.get('activeTabId') === tabId) {
    state.set('currentMessages', []);
    const container = document.getElementById('messages');
    if (container) {
      container.innerHTML = '';
      import('./message.js').then((m) => container.appendChild(m.createEmptyState()));
    }
  }
  refreshSidebar();
  showToast('本会话已清空', 'success');
}

function closeMobileSidebar() {
  document.getElementById('sidebar')?.classList.remove('open');
  document.querySelector('.sidebar-overlay')?.classList.remove('show');
  document.body.style.overflow = '';
}

async function dropSidecarSessions(_pid, _sessionIds) {
  // T30：旧 sidecar /api/session/drop 端点在新服务端不存在；no-op。
  // 重置对话仅清前端 in-memory 状态即可，不需要后端配合。
  return;
}

async function resetConversation() {
  const pid = state.get('currentProject') || 'ccc';
  if (
    !confirm(
      '重置当前项目的对话？\n本机会话记录会被清空，无法撤销。编排任务不受影响。'
    )
  ) {
    return;
  }
  snapshotHint();
  const tabs = state.get('tabs') || [];
  const projectTabs = tabs.filter((t) => (t.projectId || 'ccc') === pid);
  const sids = projectTabs.map(
    (t) => t.sessionId || desktopThreadId(pid, t.id)
  );
  sids.push(desktopThreadId(pid, 'main'));
  const uniq = [...new Set(sids)];

  for (const t of projectTabs) {
    try {
      const { cancelStream } = await import('../api.js');
      cancelStream(t.id);
    } catch (_) {}
  }
  await dropSidecarSessions(pid, uniq);

  const kept = tabs.filter((t) => (t.projectId || 'ccc') !== pid);
  const mainId = 'reset-' + Date.now().toString(36);
  const mainSid = desktopThreadId(pid, 'main');
  const mainTab = {
    id: mainId,
    title: '对话',
    sessionId: mainSid,
    messages: [],
    projectId: pid,
  };
  state.set('tabs', kept.concat([mainTab]));
  state.set('activeTabId', mainId);
  state.set('currentSessionId', mainSid);
  state.set('currentMessages', []);

  const container = document.getElementById('messages');
  if (container) {
    container.innerHTML = '';
    const { createEmptyState } = await import('./message.js');
    container.appendChild(createEmptyState());
  }
  document.dispatchEvent(
    new CustomEvent('switch-tab', { detail: { id: mainId } })
  );
  navigate('chat');
  refreshSidebar();
  showToast('对话已重置', 'success');
}

function snapshotHint() {
  /* reserved: active tab already snapshotted by switch handlers */
}

export function refreshSidebar() {
  renderAppSidebar(_projects.length ? _projects : state.get('projects'));
  syncDestHighlight();
}

/** @deprecated alias — App sidebar uses message search */
export function renderSidebar() {
  refreshSidebar();
}

function syncDestHighlight() {
  const route = currentRoute();
  document.querySelectorAll('#sidebar-nav .soft-row[data-dest]').forEach((btn) => {
    btn.classList.toggle('selected', btn.dataset.dest === route);
  });
}

function renderSearchResults(qRaw) {
  const host = document.getElementById('sidebar-search-results');
  if (!host) return;
  const q = String(qRaw || '')
    .trim()
    .toLowerCase();
  if (q.length < 2) {
    host.hidden = true;
    host.innerHTML = '';
    return;
  }
  const results = [];
  for (const t of state.get('tabs') || []) {
    const msgs = t.messages || [];
    for (let i = 0; i < msgs.length; i++) {
      const m = msgs[i];
      const content = String(m.content || m.text || '');
      if (!content.toLowerCase().includes(q)) continue;
      results.push({
        tabId: t.id,
        projectId: t.projectId || 'ccc',
        title: t.title || '对话',
        snippet: content.replace(/\s+/g, ' ').slice(0, 80),
        sid: t.sessionId,
      });
      if (results.length >= 20) break;
    }
    if (results.length >= 20) break;
  }
  if (!results.length) {
    host.hidden = false;
    host.innerHTML =
      '<div class="sidebar-search-empty">无匹配「' +
      escapeHtml(qRaw) +
      '」</div>';
    return;
  }
  host.hidden = false;
  host.innerHTML =
    '<div class="sidebar-search-meta">找到 ' +
    results.length +
    ' 条 · 点击打开</div>' +
    results
      .map(
        (r) =>
          '<button type="button" class="sidebar-search-hit" data-tab-id="' +
          escapeHtml(r.tabId) +
          '" data-project-id="' +
          escapeHtml(r.projectId) +
          '">' +
          '<span class="sidebar-search-hit-title">' +
          escapeHtml(r.title) +
          '</span>' +
          '<span class="sidebar-search-hit-snip">' +
          escapeHtml(r.snippet) +
          '</span></button>'
      )
      .join('');
  host.querySelectorAll('.sidebar-search-hit').forEach((btn) => {
    btn.addEventListener('click', () => {
      openThreadTab(btn.dataset.tabId, btn.dataset.projectId);
      const input = document.getElementById('sidebar-search');
      if (input) {
        input.value = '';
        document.getElementById('sidebar-search-clear')?.classList.remove('show');
      }
      host.hidden = true;
      host.innerHTML = '';
    });
  });
}

export function initAppSidebar(projects) {
  if (Array.isArray(projects)) {
    _projects = projects.slice();
    state.set('projects', _projects);
  }
  renderAppSidebar(_projects);

  const resetBtn = document.getElementById('sidebar-reset-btn');
  resetBtn?.addEventListener('click', () => {
    resetConversation().catch((e) =>
      showToast(e.message || '重置失败', 'error')
    );
  });

  document.querySelectorAll('#sidebar-nav .soft-row[data-dest]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const dest = btn.dataset.dest;
      if (!dest) return;
      if (dest === 'board') {
        // 跟当前项目工作区，避免完整看板默认落在空的 CCC
        import('./boardPanel.js').then(({ workspaceOf }) => {
          const ws = workspaceOf();
          const next = '#/board?ws=' + encodeURIComponent(ws);
          if (location.hash !== next) location.hash = next;
          else navigate('board');
          syncDestHighlight();
        });
        return;
      }
      navigate(dest);
      syncDestHighlight();
    });
  });

  document.getElementById('sidebar-settings-btn')?.addEventListener('click', () => {
    import('./settings.js').then((m) => m.openSettings());
  });
  document.getElementById('sidebar-help-btn')?.addEventListener('click', () => {
    showToast(
      '点项目卡进对话；定稿后转任务；看板/运维看编排。重置只清本机会话。',
      'info'
    );
  });

  setupSidebarSearch();
  syncDestHighlight();
  window.addEventListener('hashchange', syncDestHighlight);

  document.addEventListener('ccc-streams-changed', () => refreshSidebar());
  document.addEventListener('project-change', () => {
    // after setProjectActive; switchToProjectTab also refreshes
    setTimeout(() => refreshSidebar(), 0);
  });
}

export function setupSidebarSearch() {
  const input = document.getElementById('sidebar-search');
  const clearBtn = document.getElementById('sidebar-search-clear');
  if (!input || input.dataset.appSearchBound) return;
  input.dataset.appSearchBound = '1';

  input.addEventListener(
    'input',
    debounce(() => {
      renderSearchResults(input.value);
      clearBtn?.classList.toggle('show', input.value.length > 0);
    }, 200)
  );

  clearBtn?.addEventListener('click', () => {
    input.value = '';
    input.dispatchEvent(new Event('input'));
    input.focus();
    clearBtn.classList.remove('show');
  });
}
