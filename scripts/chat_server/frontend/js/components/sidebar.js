/**
 * App-parity sidebar（对齐 Desktop CodexSidebar）：
 * 重置 / 对话·看板·运维 → 项目卡（选中展开 thread）→ 搜索消息 → 用法/设置
 */
import { state } from '../state.js';
import { escapeHtml, debounce, desktopThreadId, resolveProjectPath } from '../utils.js';
import { showToast } from './toast.js';
import { setProjectActive } from './composer.js';
import { navigate, currentRoute } from '../router.js';

let _projects = [];

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

  let html = '';
  for (const p of _projects) {
    const selected = p.id === activePid;
    const threads = tabsForProject(p.id);
    const streaming = threads.some((t) => t._streaming);
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
      const rows = threads.slice().sort((a, b) => {
        const am = isMainSession(a.sessionId, p.id) ? 0 : 1;
        const bm = isMainSession(b.sessionId, p.id) ? 0 : 1;
        return am - bm;
      });
      if (!rows.length) {
        html +=
          '<div class="sidebar-thread-empty">暂无会话 · 点 + 新建</div>';
      } else {
        for (const t of rows.slice(0, 12)) {
          const sid = t.sessionId || desktopThreadId(p.id, t.id);
          const on = sid === activeSid || t.id === state.get('activeTabId');
          const title =
            t.title && t.title !== '新对话'
              ? t.title
              : isMainSession(sid, p.id)
                ? '对话'
                : String(sid).split('::').pop()?.slice(0, 12) || '会话';
          html +=
            '<button type="button" class="sidebar-thread-row' +
            (on ? ' selected' : '') +
            '" data-act="thread" data-tab-id="' +
            escapeHtml(t.id) +
            '" data-sid="' +
            escapeHtml(sid) +
            '">' +
            '<span class="sidebar-thread-icon" aria-hidden="true">○</span>' +
            '<span class="sidebar-thread-title">' +
            escapeHtml(title) +
            '</span>' +
            '</button>';
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
      } else if (act === 'thread') {
        openThreadTab(el.dataset.tabId, pid);
      }
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

function closeMobileSidebar() {
  document.getElementById('sidebar')?.classList.remove('open');
  document.querySelector('.sidebar-overlay')?.classList.remove('show');
  document.body.style.overflow = '';
}

async function dropSidecarSessions(pid, sessionIds) {
  const path = resolveProjectPath(pid);
  if (!path) return;
  const mode = state.get('toolMode') || 'engineer';
  for (const sid of sessionIds) {
    try {
      const { agentUrl } = await import('../ports.js');
      const tok =
        sessionStorage.getItem('ccc_agent_token') ||
        localStorage.getItem('ccc_agent_token') ||
        '';
      await fetch(agentUrl('/api/session/drop'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer ' + tok,
        },
        body: JSON.stringify({
          project_path: path,
          session_id: sid,
          reason: 'user-reset',
          tool_mode: mode,
        }),
      });
    } catch (_) {}
  }
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
