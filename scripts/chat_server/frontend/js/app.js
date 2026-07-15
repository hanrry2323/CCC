import { state } from './state.js';
import { generateId } from './utils.js';
import { loadProjects, loadSession, deleteSession } from './api.js';
import { initTitlebar, renderTabs } from './components/titlebar.js';
import { initComposer, setupProjectSelect } from './components/composer.js';
import { loadMessages, setupCancel } from './components/message.js';
import { refreshSidebar, setupSidebarSearch } from './components/sidebar.js';

const EMPTY_STATE_HTML = '<div class="empty-state">' +
  '<div class="empty-state-icon">💬</div>' +
  '<div class="empty-state-title">开始一个新对话</div>' +
  '<div class="empty-state-hint">在下方输入消息，或从侧栏选择一个已有对话</div>' +
  '</div>';

async function init() {
  initTitlebar();
  initComposer();
  setupCancel();
  setupSidebarSearch();
  await import('./components/toast.js');
  import('./components/keyboard.js').then(m => m.initKeyboard());

  // Load projects
  try {
    const projects = await loadProjects();
    setupProjectSelect(projects);
  } catch (e) {
    window.showToast('项目加载失败: ' + e.message, 'error');
  }

  // Create initial tab
  const tabId = generateId();
  const tabs = [{ id: tabId, title: '新对话' }];
  state.set('tabs', tabs);
  state.set('activeTabId', tabId);
  state.set('currentSessionId', tabId);
  renderTabs(tabs, tabId);
  document.getElementById('messages').innerHTML = EMPTY_STATE_HTML;

  // Refresh history
  refreshSidebar();

  // Tab events
  document.addEventListener('new-tab', () => {
    const id = generateId();
    const tabs = state.get('tabs') || [];
    tabs.push({ id, title: '新对话' });
    state.set('tabs', tabs);
    state.set('activeTabId', id);
    state.set('currentSessionId', id);
    state.set('currentMessages', []);
    document.getElementById('messages').innerHTML = EMPTY_STATE_HTML;
    document.getElementById('composer-input').value = '';
    document.getElementById('send-btn').disabled = true;
    renderTabs(tabs, id);
  });

  document.addEventListener('switch-tab', (e) => {
    const { id } = e.detail;
    const tabs = state.get('tabs') || [];
    state.set('activeTabId', id);
    // For now, all tabs share the same messages
    renderTabs(tabs, id);
  });

  document.addEventListener('close-tab', (e) => {
    let tabs = state.get('tabs') || [];
    const { id } = e.detail;
    if (tabs.length <= 1) return;
    tabs = tabs.filter(t => t.id !== id);
    state.set('tabs', tabs);
    const activeId = state.get('activeTabId');
    if (activeId === id) {
      const newActive = tabs[tabs.length - 1].id;
      state.set('activeTabId', newActive);
    }
    renderTabs(tabs, state.get('activeTabId'));
  });

  document.addEventListener('load-session', async (e) => {
    const { id } = e.detail;
    try {
      const data = await loadSession(id, state.get('currentProject'));
      state.set('currentSessionId', id);
      loadMessages(data);

      // Update tab title
      const tabs = state.get('tabs') || [];
      const tab = tabs.find(t => t.id === state.get('activeTabId'));
      if (tab) {
        tab.title = data.title || '对话';
        renderTabs(tabs, state.get('activeTabId'));
      }

      // Update sidebar active
      document.querySelectorAll('.session-item').forEach(el => {
        el.classList.toggle('active', el.dataset.sid === id);
      });

      // Close mobile sidebar
      document.getElementById('sidebar')?.classList.remove('open');
      document.querySelector('.sidebar-overlay')?.classList.remove('show');
    } catch (e) {
      window.showToast('加载对话失败', 'error');
    }
  });

  document.addEventListener('project-change', () => {
    const container = document.getElementById('messages');
    container.innerHTML = '';
    container.innerHTML = EMPTY_STATE_HTML;
    state.set('currentMessages', []);
    state.set('currentSessionId', generateId());
    refreshSidebar();
  });
}

document.addEventListener('DOMContentLoaded', init);
