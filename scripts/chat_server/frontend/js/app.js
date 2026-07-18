import { state } from './state.js';
import { generateId } from './utils.js';
import { loadProjects, loadSession, loadHubConfig } from './api.js';
import { applyTheme, getThemeScheme } from './theme.js';
import { initTitlebar, renderTabs } from './components/titlebar.js';
import { initComposer, setupProjectSelect } from './components/composer.js';
import { loadMessages, setupCancel, createEmptyState } from './components/message.js';
import { refreshSidebar, setupSidebarSearch } from './components/sidebar.js';
import { initRuntimeStatus } from './components/runtimeStatus.js';
import { initEngineControl } from './components/engineControl.js';
import { initRouter } from './router.js';
import { mountBoard, unmountBoard } from './pages/boardPage.js';
import { mountConsole, unmountConsole } from './pages/consolePage.js';
import { mountOps, unmountOps } from './pages/opsPage.js';

function snapshotActiveTab() {
  const tabs = state.get('tabs') || [];
  const activeId = state.get('activeTabId');
  const tab = tabs.find((t) => t.id === activeId);
  if (!tab) return;
  tab.sessionId = state.get('currentSessionId');
  tab.messages = (state.get('currentMessages') || []).slice();
  tab.projectId = state.get('currentProject') || tab.projectId || 'ccc';
  state.set('tabs', tabs);
}

/** Tabs belonging to the current project (for titlebar). */
export function tabsForCurrentProject() {
  const project = state.get('currentProject') || 'ccc';
  return (state.get('tabs') || []).filter(
    (t) => (t.projectId || 'ccc') === project
  );
}

function renderProjectTabs(activeId) {
  renderTabs(tabsForCurrentProject(), activeId || state.get('activeTabId'));
}

function showTabContent(tab) {
  const container = document.getElementById('messages');
  container.innerHTML = '';
  state.set('currentSessionId', tab.sessionId || tab.id);
  const msgs = tab.messages || [];
  state.set('currentMessages', msgs);
  if (!msgs.length) {
    container.appendChild(createEmptyState());
  } else {
    loadMessages({ messages: msgs, title: tab.title });
  }
  import('./streamRegistry.js').then((m) => {
    m.syncStreamingFlagForActiveTab();
  });
  import('./components/message.js').then((m) => m.updateComposerState());
}

/**
 * Switch visible chat to a tab for `projectId` without cancelling other projects' streams.
 * Creates a fresh tab if none exists for that project.
 */
function switchToProjectTab(projectId) {
  snapshotActiveTab();
  const pid = projectId || state.get('currentProject') || 'ccc';
  let tabs = state.get('tabs') || [];
  // Prefer most recently touched tab for this project (last in list with that projectId)
  let tab = null;
  for (let i = tabs.length - 1; i >= 0; i--) {
    if ((tabs[i].projectId || 'ccc') === pid) {
      tab = tabs[i];
      break;
    }
  }
  if (!tab) {
    const id = generateId();
    tab = {
      id,
      title: '新对话',
      sessionId: id,
      messages: [],
      projectId: pid,
    };
    tabs = tabs.concat([tab]);
    state.set('tabs', tabs);
  }
  state.set('activeTabId', tab.id);
  renderProjectTabs(tab.id);
  showTabContent(tab);
  refreshSidebar();

  import('./streamRegistry.js').then((m) => {
    const others = m.streamingProjectIds().filter((p) => p && p !== pid);
    if (others.length) {
      window.showToast?.(
        '其他项目仍有生成中的对话（' + others.join(', ') + '）',
        'info'
      );
    }
    // Update project chip live dots
    document.dispatchEvent(new CustomEvent('ccc-streams-changed'));
  });
}

async function onHubRoute(route) {
  document.title =
    route === 'board' ? 'CCC Hub · 看板' :
    route === 'console' ? 'CCC Hub · 控制台' :
    route === 'ops' ? 'CCC Hub · 运维' :
    'CCC Hub';
  if (route === 'board') {
    unmountConsole();
    unmountOps();
    await mountBoard(document.getElementById('view-board'));
  } else if (route === 'console') {
    unmountBoard();
    unmountOps();
    await mountConsole(document.getElementById('view-console'));
  } else if (route === 'ops') {
    unmountBoard();
    unmountConsole();
    await mountOps(document.getElementById('view-ops'));
  } else {
    unmountBoard();
    unmountConsole();
    unmountOps();
  }
}

async function init() {
  applyTheme(getThemeScheme());
  initRouter(onHubRoute);
  initTitlebar();
  initComposer();
  initRuntimeStatus();
  initEngineControl();
  setupCancel();
  setupSidebarSearch();
  await import('./components/toast.js');
  import('./components/keyboard.js').then((m) => m.initKeyboard());

  try {
    const cfg = await loadHubConfig();
    if (cfg?.chat_session_max_live) {
      state.set('maxLiveStreams', cfg.chat_session_max_live);
    }
  } catch (_) {
    /* keep default 4 */
  }

  try {
    const projects = await loadProjects();
    setupProjectSelect(projects);
    const map = {};
    for (const p of projects) map[p.id] = p.workspace || p.id;
    state.set('projectWorkspaceMap', map);
  } catch (e) {
    window.showToast('项目加载失败: ' + e.message, 'error');
  }

  const project = state.get('currentProject') || 'ccc';
  const tabId = generateId();
  const tabs = [
    {
      id: tabId,
      title: '新对话',
      sessionId: tabId,
      messages: [],
      projectId: project,
    },
  ];
  state.set('tabs', tabs);
  state.set('activeTabId', tabId);
  state.set('currentSessionId', tabId);
  renderProjectTabs(tabId);
  document.getElementById('messages').appendChild(createEmptyState());

  refreshSidebar();

  document.addEventListener('new-tab', () => {
    snapshotActiveTab();
    const id = generateId();
    const pid = state.get('currentProject') || 'ccc';
    const tabsNow = state.get('tabs') || [];
    tabsNow.push({
      id,
      title: '新对话',
      sessionId: id,
      messages: [],
      projectId: pid,
    });
    state.set('tabs', tabsNow);
    state.set('activeTabId', id);
    state.set('currentSessionId', id);
    state.set('currentMessages', []);
    const container = document.getElementById('messages');
    container.innerHTML = '';
    container.appendChild(createEmptyState());
    document.getElementById('composer-input').value = '';
    document.getElementById('send-btn').disabled = true;
    renderProjectTabs(id);
  });

  document.addEventListener('switch-tab', (e) => {
    const { id } = e.detail;
    if (id === state.get('activeTabId')) return;
    snapshotActiveTab();
    const tabsNow = state.get('tabs') || [];
    const tab = tabsNow.find((t) => t.id === id);
    if (!tab) return;
    state.set('activeTabId', id);
    renderProjectTabs(id);
    showTabContent(tab);
  });

  document.addEventListener('close-tab', (e) => {
    let tabsNow = state.get('tabs') || [];
    const { id } = e.detail;
    const pid = state.get('currentProject') || 'ccc';
    const projectTabs = tabsNow.filter((t) => (t.projectId || 'ccc') === pid);
    if (projectTabs.length <= 1) return;
    snapshotActiveTab();
    import('./streamRegistry.js').then((m) => m.cancelStream(id));
    tabsNow = tabsNow.filter((t) => t.id !== id);
    state.set('tabs', tabsNow);
    const activeId = state.get('activeTabId');
    if (activeId === id) {
      const remaining = tabsNow.filter((t) => (t.projectId || 'ccc') === pid);
      const newActive = remaining[remaining.length - 1];
      if (newActive) {
        state.set('activeTabId', newActive.id);
        showTabContent(newActive);
      }
    }
    renderProjectTabs(state.get('activeTabId'));
  });

  document.addEventListener('load-session', async (e) => {
    const { id } = e.detail;
    try {
      snapshotActiveTab();
      const data = await loadSession(id, state.get('currentProject'));
      state.set('currentSessionId', id);
      loadMessages(data);

      const tabsNow = state.get('tabs') || [];
      let tab = tabsNow.find((t) => t.id === state.get('activeTabId'));
      if (tab) {
        tab.title = data.title || '对话';
        tab.sessionId = id;
        tab.messages = data.messages || [];
        tab.projectId = state.get('currentProject') || tab.projectId;
        renderProjectTabs(state.get('activeTabId'));
      }

      document.querySelectorAll('.session-item').forEach((el) => {
        el.classList.toggle('active', el.dataset.sid === id);
      });

      document.getElementById('sidebar')?.classList.remove('open');
      document.querySelector('.sidebar-overlay')?.classList.remove('show');
    } catch (err) {
      window.showToast('加载对话失败', 'error');
    }
  });

  document.addEventListener('project-change', () => {
    switchToProjectTab(state.get('currentProject'));
  });

  document.addEventListener('ccc-streams-changed', () => {
    renderProjectTabs(state.get('activeTabId'));
  });
}

document.addEventListener('DOMContentLoaded', init);
