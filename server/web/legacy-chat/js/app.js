import { state } from './state.js';
import { generateId, desktopThreadId } from './utils.js';
import { loadProjects, loadSession, loadHubConfig } from './api.js';
import { initChatStatus } from './chatStatus.js';
import { applyTheme, getThemeScheme } from './theme.js';
import { initTitlebar, renderTabs } from './components/titlebar.js';
import { initComposer, setupProjectSelect } from './components/composer.js';
import {
  loadMessages,
  setupCancel,
  createEmptyState,
} from './components/message.js';
import { refreshSidebar, initAppSidebar } from './components/sidebar.js';
import { initRuntimeStatus } from './components/runtimeStatus.js';
import { initEngineControl } from './components/engineControl.js';
import { initRouter, navigate } from './router.js';
import { mountBoard, unmountBoard } from './pages/boardPage.js?v=20260809t10';
import { mountConsole, unmountConsole } from './pages/consolePage.js?v=20260809t10';
import { mountOps, unmountOps } from './pages/opsPage.js?v=20260809t10';
import { mountPlans, unmountPlans } from './pages/plansPage.js?v=20260809t10';
import { mountRoadmap, unmountRoadmap } from './pages/roadmapPage.js?v=20260809t10';
import {
  initDualPaneControls,
  isEnabled as dualPaneEnabled,
  showTabInFocusedPane,
  messagesElForTab,
  paneTabIds,
  setFocusedPane,
} from './dualPane.js';

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

function renderTabIntoContainer(tab, container) {
  if (!container) return;
  container.innerHTML = '';
  const msgs = tab.messages || [];
  if (!msgs.length) {
    container.appendChild(createEmptyState());
    return;
  }
  // Temporarily point loadMessages at this container via active pane semantics:
  // loadMessages uses activeMessagesEl(); ensure focus pane matches container.
  const { left, right } = paneTabIds();
  if (dualPaneEnabled() && tab.id === right) setFocusedPane('right');
  else setFocusedPane('left');
  state.set('currentSessionId', tab.sessionId || tab.id);
  state.set('currentMessages', msgs);
  loadMessages({ messages: msgs, title: tab.title });
}

function showTabContent(tab) {
  if (dualPaneEnabled()) {
    showTabInFocusedPane(tab.id);
    const container = messagesElForTab(tab.id);
    renderTabIntoContainer(tab, container);
  } else {
    const container = document.getElementById('messages');
    renderTabIntoContainer(tab, container);
  }
  import('./streamRegistry.js').then((m) => {
    m.syncStreamingFlagForActiveTab();
  });
  import('./components/message.js').then((m) => m.updateComposerState());
  // 流式 tab 切回：仍在途且尚无 assistant 内容 → 重挂 typing（恢复「等待中」感知）
  import('./streamRegistry.js').then((m) => {
    if (!m.isTabStreaming(tab.id)) return;
    const hasAssistant = (tab.messages || []).some(
      (msg) => msg.role === 'assistant' && String(msg.content || '').trim()
    );
    if (hasAssistant) return;
    const container = messagesElForTab(tab.id);
    if (!container) return;
    import('./components/message.js').then((msg) => {
      msg.showTyping(container, tab.id);
    });
  });
}

function renderPaneByTabId(tabId) {
  const tabs = state.get('tabs') || [];
  const tab = tabs.find((t) => t.id === tabId);
  if (!tab) return;
  const container = messagesElForTab(tabId);
  if (!container) return;
  const prevActive = state.get('activeTabId');
  const prevMsgs = state.get('currentMessages');
  const prevSid = state.get('currentSessionId');
  // Render without stealing focus if not focused pane
  const { left, right } = paneTabIds();
  const focus = state.get('dualPaneFocus') === 'right' ? 'right' : 'left';
  const isFocus =
    (focus === 'right' && tabId === right) || (focus === 'left' && tabId === left);
  container.innerHTML = '';
  const msgs = tab.messages || [];
  if (!msgs.length) {
    container.appendChild(createEmptyState());
  } else if (isFocus) {
    state.set('currentSessionId', tab.sessionId || tab.id);
    state.set('currentMessages', msgs);
    loadMessages({ messages: msgs, title: tab.title });
  } else {
    // Off-focus pane: paint snapshot without clobbering composer state long-term
    state.set('currentSessionId', tab.sessionId || tab.id);
    state.set('currentMessages', msgs);
    loadMessages({ messages: msgs, title: tab.title });
    if (prevActive) {
      state.set('activeTabId', prevActive);
      state.set('currentMessages', prevMsgs || []);
      state.set('currentSessionId', prevSid);
    }
  }
}

/**
 * Switch visible chat to a tab for `projectId` without cancelling other projects' streams.
 * Prefers `{pid}::main`, then most recent tab; creates ::main if none.
 */
function switchToProjectTab(projectId) {
  snapshotActiveTab();
  const pid = projectId || state.get('currentProject') || 'ccc';
  let tabs = state.get('tabs') || [];
  const mainSid = desktopThreadId(pid, 'main');
  let tab =
    tabs.find(
      (t) =>
        (t.projectId || 'ccc') === pid &&
        String(t.sessionId || '') === mainSid
    ) || null;
  if (!tab) {
    for (let i = tabs.length - 1; i >= 0; i--) {
      if ((tabs[i].projectId || 'ccc') === pid) {
        tab = tabs[i];
        break;
      }
    }
  }
  if (!tab) {
    const id = generateId();
    tab = {
      id,
      title: '对话',
      sessionId: mainSid,
      messages: [],
      projectId: pid,
    };
    tabs = tabs.concat([tab]);
    state.set('tabs', tabs);
  }
  state.set('activeTabId', tab.id);
  state.set('currentSessionId', tab.sessionId || mainSid);
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
    document.dispatchEvent(new CustomEvent('ccc-streams-changed'));
  });
}

async function onHubRoute(route) {
  // T46 A1 护栏：路由切换 / 视图 mount-unmount 不得调用 cancelStream/abort。
  // 流的取消仅允许用户主动点停止（composer cancel-btn → cancelStream），或
  // 关闭 tab（close-tab 里 cancelStream）。切到 #/board 再回 #/chat，活跃流
  // 保持接收、DOM 容器不被重建（showTabContent 从 tab.messages 增量重绘）。
  // 违反此约定的代码 = 切换即中断的回归源。
  document.title =
    route === 'chat' ? 'CCC · 对话' :
      route === 'board' ? 'CCC · 看板' :
        route === 'plans' ? 'CCC · 计划' :
          route === 'roadmap' ? 'CCC · 线路图' :
            route === 'console' ? 'CCC · 控制台' :
            route === 'ops' ? 'CCC · 运维' :
              'CCC';
  if (route === 'chat') {
    unmountBoard();
    unmountConsole();
    unmountOps();
    unmountPlans();
    unmountRoadmap();
    // T40 三栏：进入对话视图时自动打开右栏任务卡流（用户曾手动关闭则不强制）
    import('./components/boardPanel.js').then((m) => m.maybeAutoOpen());
  } else if (route === 'board') {
    unmountConsole();
    unmountOps();
    unmountPlans();
    unmountRoadmap();
    await mountBoard(document.getElementById('view-board'));
  } else if (route === 'plans') {
    unmountBoard();
    unmountConsole();
    unmountOps();
    unmountRoadmap();
    await mountPlans(document.getElementById('view-plans'));
  } else if (route === 'roadmap') {
    unmountBoard();
    unmountConsole();
    unmountOps();
    unmountPlans();
    await mountRoadmap(document.getElementById('view-roadmap'));
  } else if (route === 'console') {
    unmountBoard();
    unmountOps();
    unmountPlans();
    unmountRoadmap();
    await mountConsole(document.getElementById('view-console'));
  } else if (route === 'ops') {
    unmountBoard();
    unmountConsole();
    unmountPlans();
    unmountRoadmap();
    await mountOps(document.getElementById('view-ops'));
  } else {
    unmountBoard();
    unmountConsole();
    unmountOps();
    unmountRoadmap();
  }
}

function applyShellMode() {
  const dialogue =
    String(location.port || '') === '7788' ||
    window.__CCC_SHELL__ === 'dialogue';
  if (dialogue) {
    window.__CCC_SHELL__ = 'dialogue';
    document.documentElement.setAttribute('data-shell', 'dialogue');
    document.body.classList.add('dialogue-mode');
    document.body.classList.add('hub-mode');
    document.title = 'CCC';
  } else {
    document.documentElement.setAttribute('data-shell', 'hub');
    document.body.classList.remove('dialogue-mode');
    document.body.classList.add('hub-mode');
  }
}

async function init() {
  applyShellMode();
  applyTheme(getThemeScheme());
  // 登录门：T40 — 无条件绑定（不再依赖 isDialogueShell 分支）
  // 2017 单端 :7788 唯一入口；旧 Hub/双壳分支已退役。
  const agentAuth = await import('./agentAuth.js');
  // T44：登录成功后直达对话视图（默认路由已固定 #/chat）
  await agentAuth.initAgentAuth({ onAuthenticated: () => navigate('chat') });
  const authed = await agentAuth.ensureAgentAuthenticated();
  if (!authed) await agentAuth.waitForAgentAuth();
  initRouter(onHubRoute);
  initTitlebar();
  initDualPaneControls(generateId);
  import('./components/relayStats.js').then((m) => m.initRelayStats());
  initComposer();
  initRuntimeStatus();
  initEngineControl();
  setupCancel();
  await import('./components/toast.js');
  import('./components/keyboard.js').then((m) => m.initKeyboard());

  document.addEventListener('ccc-render-pane', (e) => {
    const tabId = e.detail?.tabId;
    if (tabId) renderPaneByTabId(tabId);
  });

  const handleTaskStatusEvent = async () => {
    const { refreshBoardPanel } = await import('./components/boardPanel.js');
    refreshBoardPanel({ quiet: true });
  };
  document.addEventListener('task_status', handleTaskStatusEvent);
  document.addEventListener('task-status', handleTaskStatusEvent);
  document.addEventListener('ccc-task-status', handleTaskStatusEvent);

  try {
    // T40：单端 :7788 唯一入口；旧 Hub/sidecar 分支已退役。
    window.__CCC_SHELL__ = 'dialogue';
    window.__CCC_AGENT_BASE__ = window.__CCC_AGENT_BASE__ ?? '';
    const cfg = await loadHubConfig();
    if (cfg?.chat_session_max_live) {
      state.set('maxLiveStreams', cfg.chat_session_max_live);
    }
    if (cfg?.desktop_agent_url) {
      window.__CCC_DESKTOP_AGENT_URL__ = cfg.desktop_agent_url;
    }
    if (cfg?.dialogue_url) {
      window.__CCC_DIALOGUE_URL__ = cfg.dialogue_url;
    }
  } catch (_) {
    /* keep default */
  }

  try {
    const projects = await loadProjects();
    setupProjectSelect(projects);
    initAppSidebar(projects);
    const map = {};
    for (const p of projects) map[p.id] = p.workspace || p.id;
    state.set('projectWorkspaceMap', map);
  } catch (e) {
    window.showToast('项目加载失败: ' + e.message, 'error');
    initAppSidebar([]);
  }

  // 感知层：注入断连横幅/模型警告元素 + 启动 30s 健康轮询
  initChatStatus();

  const project =
    state.get('currentProject') ||
    state.get('defaultProject') ||
    (() => {
      try {
        return localStorage.getItem('ccc_hub_last_project');
      } catch (_) {
        return null;
      }
    })() ||
    null;
  if (!state.get('currentProject') && project) state.set('currentProject', project);
  const tabId = generateId();
  const bootSid = desktopThreadId(project || 'ccc', 'main');
  const tabs = [
    {
      id: tabId,
      title: '对话',
      sessionId: bootSid,
      messages: [],
      projectId: project,
    },
  ];
  state.set('tabs', tabs);
  state.set('activeTabId', tabId);
  state.set('currentSessionId', bootSid);
  if (dualPaneEnabled()) {
    state.set('paneLeftTabId', tabId);
  }
  renderProjectTabs(tabId);
  const bootMsg = messagesElForTab(tabId) || document.getElementById('messages');
  if (bootMsg) bootMsg.appendChild(createEmptyState());

  refreshSidebar();

  document.addEventListener('new-tab', (e) => {
    snapshotActiveTab();
    const id = generateId();
    const pid =
      e.detail?.projectId ||
      state.get('currentProject') ||
      state.get('defaultProject') ||
      'ccc';
    const sid = desktopThreadId(pid, id);
    const tabsNow = state.get('tabs') || [];
    tabsNow.push({
      id,
      title: '新对话',
      sessionId: sid,
      messages: [],
      projectId: pid,
    });
    state.set('tabs', tabsNow);
    state.set('currentProject', pid);
    state.set('activeTabId', id);
    state.set('currentSessionId', sid);
    state.set('currentMessages', []);
    if (dualPaneEnabled()) showTabInFocusedPane(id);
    const container = messagesElForTab(id) || document.getElementById('messages');
    if (container) {
      container.innerHTML = '';
      container.appendChild(createEmptyState());
    }
    document.getElementById('composer-input').value = '';
    document.getElementById('send-btn').disabled = true;
    renderProjectTabs(id);
    refreshSidebar();
  });

  document.addEventListener('switch-tab', (e) => {
    const { id } = e.detail;
    if (id === state.get('activeTabId') && !dualPaneEnabled()) {
      refreshSidebar();
      return;
    }
    snapshotActiveTab();
    const tabsNow = state.get('tabs') || [];
    const tab = tabsNow.find((t) => t.id === id);
    if (!tab) return;
    state.set('activeTabId', id);
    if (tab.projectId) state.set('currentProject', tab.projectId);
    renderProjectTabs(id);
    showTabContent(tab);
    refreshSidebar();
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
    refreshSidebar();
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

      document.querySelectorAll('.sidebar-thread-row').forEach((el) => {
        el.classList.toggle('selected', el.dataset.sid === id);
      });

      document.getElementById('sidebar')?.classList.remove('open');
      document.querySelector('.sidebar-overlay')?.classList.remove('show');
      refreshSidebar();
    } catch (err) {
      window.showToast('加载对话失败', 'error');
    }
  });

  document.addEventListener('project-change', () => {
    switchToProjectTab(state.get('currentProject'));
  });

  document.addEventListener('ccc-streams-changed', () => {
    renderProjectTabs(state.get('activeTabId'));
    refreshSidebar();
  });

  state.on('currentSessionId', (sid) => {
    startConversationLongPoll(sid);
  });
  // Start initial polling
  const initialSid = state.get('currentSessionId');
  if (initialSid) {
    startConversationLongPoll(initialSid);
  }
}

let currentPollAbort = null;

async function startConversationLongPoll(sid) {
  if (currentPollAbort) {
    currentPollAbort.abort();
    currentPollAbort = null;
  }
  if (!sid) return;
  const abort = new AbortController();
  currentPollAbort = abort;

  const pid = state.get('currentProject') || 'ccc';

  while (!abort.signal.aborted) {
    if (document.visibilityState !== 'visible' || state.get('activeTabId') === '') {
      await new Promise(r => setTimeout(r, 2000));
      continue;
    }
    try {
      const { loadSession } = await import('./api.js');
      const data = await loadSession(sid, pid);
      if (abort.signal.aborted) break;

      const tabsNow = state.get('tabs') || [];
      let tab = tabsNow.find((t) => t.sessionId === sid);
      if (tab) {
        const msgs = data.messages || [];
        if (msgs.length > tab.messages.length) {
          tab.messages = msgs;
          state.set('tabs', tabsNow);
          if (state.get('currentSessionId') === sid) {
            state.set('currentMessages', msgs);
            const { loadMessages } = await import('./components/message.js');
            loadMessages({ messages: msgs });

            // Check if last message is system/status notification
            const lastMsg = msgs[msgs.length - 1];
            if (lastMsg && (lastMsg.type === 'task_status' || lastMsg.role === 'system')) {
              const { refreshBoardPanel } = await import('./components/boardPanel.js');
              refreshBoardPanel({ quiet: true });
            }
          }
        }
      }
      await new Promise(r => setTimeout(r, 100));
    } catch (err) {
      if (abort.signal.aborted) break;
      await new Promise(r => setTimeout(r, 3000));
    }
  }
}

if (document.readyState === 'interactive' || document.readyState === 'complete') {
  init();
} else {
  document.addEventListener('DOMContentLoaded', init);
}
