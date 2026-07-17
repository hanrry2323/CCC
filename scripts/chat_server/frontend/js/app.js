import { state } from './state.js';
import { generateId } from './utils.js';
import { loadProjects, loadSession } from './api.js';
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
  const tab = tabs.find(t => t.id === activeId);
  if (!tab) return;
  tab.sessionId = state.get('currentSessionId');
  tab.messages = (state.get('currentMessages') || []).slice();
  state.set('tabs', tabs);
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
  import('./components/keyboard.js').then(m => m.initKeyboard());

  try {
    const projects = await loadProjects();
    setupProjectSelect(projects);
    // Cache workspace map on state for task dialog
    const map = {};
    for (const p of projects) map[p.id] = p.workspace || p.id;
    state.set('projectWorkspaceMap', map);
  } catch (e) {
    window.showToast('项目加载失败: ' + e.message, 'error');
  }

  const tabId = generateId();
  const tabs = [{ id: tabId, title: '新对话', sessionId: tabId, messages: [] }];
  state.set('tabs', tabs);
  state.set('activeTabId', tabId);
  state.set('currentSessionId', tabId);
  renderTabs(tabs, tabId);
  document.getElementById('messages').appendChild(createEmptyState());

  refreshSidebar();

  document.addEventListener('new-tab', () => {
    snapshotActiveTab();
    const id = generateId();
    const tabs = state.get('tabs') || [];
    tabs.push({ id, title: '新对话', sessionId: id, messages: [] });
    state.set('tabs', tabs);
    state.set('activeTabId', id);
    state.set('currentSessionId', id);
    state.set('currentMessages', []);
    const container = document.getElementById('messages');
    container.innerHTML = '';
    container.appendChild(createEmptyState());
    document.getElementById('composer-input').value = '';
    document.getElementById('send-btn').disabled = true;
    renderTabs(tabs, id);
  });

  document.addEventListener('switch-tab', (e) => {
    const { id } = e.detail;
    if (id === state.get('activeTabId')) return;
    snapshotActiveTab();
    const tabs = state.get('tabs') || [];
    const tab = tabs.find(t => t.id === id);
    if (!tab) return;
    state.set('activeTabId', id);
    renderTabs(tabs, id);
    showTabContent(tab);
  });

  document.addEventListener('close-tab', (e) => {
    let tabs = state.get('tabs') || [];
    const { id } = e.detail;
    if (tabs.length <= 1) return;
    snapshotActiveTab();
    import('./streamRegistry.js').then((m) => m.cancelStream(id));
    tabs = tabs.filter(t => t.id !== id);
    state.set('tabs', tabs);
    const activeId = state.get('activeTabId');
    if (activeId === id) {
      const newActive = tabs[tabs.length - 1];
      state.set('activeTabId', newActive.id);
      showTabContent(newActive);
    }
    renderTabs(tabs, state.get('activeTabId'));
  });

  document.addEventListener('load-session', async (e) => {
    const { id } = e.detail;
    try {
      snapshotActiveTab();
      const data = await loadSession(id, state.get('currentProject'));
      state.set('currentSessionId', id);
      loadMessages(data);

      const tabs = state.get('tabs') || [];
      let tab = tabs.find(t => t.id === state.get('activeTabId'));
      if (tab) {
        tab.title = data.title || '对话';
        tab.sessionId = id;
        tab.messages = data.messages || [];
        renderTabs(tabs, state.get('activeTabId'));
      }

      document.querySelectorAll('.session-item').forEach(el => {
        el.classList.toggle('active', el.dataset.sid === id);
      });

      document.getElementById('sidebar')?.classList.remove('open');
      document.querySelector('.sidebar-overlay')?.classList.remove('show');
    } catch (err) {
      window.showToast('加载对话失败', 'error');
    }
  });

  document.addEventListener('project-change', () => {
    snapshotActiveTab();
    const container = document.getElementById('messages');
    container.innerHTML = '';
    container.appendChild(createEmptyState());
    state.set('currentMessages', []);
    const id = generateId();
    state.set('currentSessionId', id);
    const tabs = state.get('tabs') || [];
    const tab = tabs.find(t => t.id === state.get('activeTabId'));
    if (tab) {
      tab.sessionId = id;
      tab.messages = [];
      tab.title = '新对话';
      renderTabs(tabs, state.get('activeTabId'));
    }
    refreshSidebar();
  });
}

document.addEventListener('DOMContentLoaded', init);
