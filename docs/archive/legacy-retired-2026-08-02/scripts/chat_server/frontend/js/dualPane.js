/**
 * Dual-pane chat — DEPRECATED as product surface (2026-07-19).
 *
 * Product main client is SwiftUI `desktop/` (project / plan chat / flow rail).
 * This module remains for ops/debug only. Do not advertise dual-pane in VISION.
 *
 * Enabled when:
 *   - URL ?desktop=1 / ?dual=1
 *   - localStorage ccc_dual_pane=1
 *   - Tauri (__TAURI__ / userAgent)
 */

import { state } from './state.js';

const LS_KEY = 'ccc_dual_pane';

export function shouldEnableDualPane() {
  try {
    const q = new URLSearchParams(location.search);
    if (q.get('desktop') === '1' || q.get('dual') === '1') return true;
    if (q.get('dual') === '0' || q.get('desktop') === '0') return false;
    if (localStorage.getItem(LS_KEY) === '1') return true;
    if (localStorage.getItem(LS_KEY) === '0') return false;
  } catch (_) {
    /* ignore */
  }
  if (typeof window !== 'undefined' && window.__TAURI__) return true;
  if (/Tauri/i.test(navigator.userAgent || '')) return true;
  return false;
}

export function isEnabled() {
  return !!state.get('dualPaneEnabled');
}

export function focusedPane() {
  return state.get('dualPaneFocus') === 'right' ? 'right' : 'left';
}

export function setFocusedPane(pane) {
  state.set('dualPaneFocus', pane === 'right' ? 'right' : 'left');
  document.querySelectorAll('.chat-pane').forEach((el) => {
    el.classList.toggle('focused', el.dataset.pane === (pane === 'right' ? 'right' : 'left'));
  });
}

export function paneTabIds() {
  return {
    left: state.get('paneLeftTabId') || null,
    right: state.get('paneRightTabId') || null,
  };
}

export function isTabVisible(tabId) {
  if (!tabId) return false;
  if (!isEnabled()) {
    return state.get('activeTabId') === tabId;
  }
  const { left, right } = paneTabIds();
  return tabId === left || tabId === right;
}

/** Messages DOM for a tab (visible pane), or focused pane as fallback. */
export function messagesElForTab(tabId) {
  if (!isEnabled()) {
    return document.getElementById('messages');
  }
  const { left, right } = paneTabIds();
  if (tabId && tabId === right) {
    return document.getElementById('messages-b') || document.getElementById('messages');
  }
  if (tabId && tabId === left) {
    return document.getElementById('messages');
  }
  return focusedPane() === 'right'
    ? document.getElementById('messages-b') || document.getElementById('messages')
    : document.getElementById('messages');
}

export function activeMessagesEl() {
  return messagesElForTab(state.get('activeTabId'));
}

export function assignTabToPane(pane, tabId) {
  if (pane === 'right') state.set('paneRightTabId', tabId);
  else state.set('paneLeftTabId', tabId);
  document.dispatchEvent(new CustomEvent('ccc-panes-changed'));
}

/** Put tab into focused pane; keep the other pane untouched. */
export function showTabInFocusedPane(tabId) {
  const pane = focusedPane();
  assignTabToPane(pane, tabId);
}

export function ensureDom() {
  const panel = document.getElementById('chat-panel');
  if (!panel || document.getElementById('chat-panes')) return;

  const messages = document.getElementById('messages');
  const fab = document.getElementById('scroll-fab');
  const composer = document.getElementById('composer');
  if (!messages || !composer) return;

  const panes = document.createElement('div');
  panes.id = 'chat-panes';
  panes.className = 'chat-panes';

  const left = document.createElement('div');
  left.className = 'chat-pane focused';
  left.dataset.pane = 'left';
  const leftHead = document.createElement('div');
  leftHead.className = 'chat-pane-head';
  leftHead.textContent = '窗格 A';
  left.appendChild(leftHead);
  left.appendChild(messages);
  messages.classList.add('messages-pane');

  const right = document.createElement('div');
  right.className = 'chat-pane';
  right.dataset.pane = 'right';
  const rightHead = document.createElement('div');
  rightHead.className = 'chat-pane-head';
  rightHead.textContent = '窗格 B';
  const messagesB = document.createElement('div');
  messagesB.id = 'messages-b';
  messagesB.className = 'messages-pane';
  right.appendChild(rightHead);
  right.appendChild(messagesB);

  panes.appendChild(left);
  panes.appendChild(right);

  panel.insertBefore(panes, composer);
  if (fab) panel.insertBefore(fab, composer);

  left.addEventListener('mousedown', () => setFocusedPane('left'));
  right.addEventListener('mousedown', () => setFocusedPane('right'));
}

export function enable() {
  if (isEnabled()) return;
  try {
    localStorage.setItem(LS_KEY, '1');
  } catch (_) {
    /* ignore */
  }
  state.set('dualPaneEnabled', true);
  state.set('dualPaneFocus', 'left');
  ensureDom();
  document.body.classList.add('dual-pane-mode');
  const active = state.get('activeTabId');
  if (active) {
    state.set('paneLeftTabId', active);
  }
  const btn = document.getElementById('dual-pane-btn');
  if (btn) btn.classList.add('active');
}

export function disable() {
  try {
    localStorage.setItem(LS_KEY, '0');
  } catch (_) {
    /* ignore */
  }
  state.set('dualPaneEnabled', false);
  document.body.classList.remove('dual-pane-mode');
  const btn = document.getElementById('dual-pane-btn');
  if (btn) btn.classList.remove('active');
}

/** Open a second tab in the right pane (create if needed). */
export function splitWithNewOrNextTab(generateId) {
  enable();
  const active = state.get('activeTabId');
  const pid = state.get('currentProject') || state.get('defaultProject') || 'ccc';
  state.set('paneLeftTabId', active);
  setFocusedPane('left');

  let tabs = state.get('tabs') || [];
  let other = tabs.find(
    (t) => t.id !== active && (t.projectId || 'ccc') === pid
  );
  if (!other) {
    const id = generateId();
    other = {
      id,
      title: '新对话',
      sessionId: id,
      messages: [],
      projectId: pid,
    };
    tabs = tabs.concat([other]);
    state.set('tabs', tabs);
  }
  state.set('paneRightTabId', other.id);
  document.dispatchEvent(
    new CustomEvent('ccc-render-pane', { detail: { pane: 'right', tabId: other.id } })
  );
  document.dispatchEvent(new CustomEvent('ccc-panes-changed'));
  window.showToast?.('已分屏：左侧当前对话，右侧另一会话', 'info');
  return other;
}

export function initDualPaneControls(generateId) {
  if (shouldEnableDualPane()) {
    enable();
  }
  const btn = document.getElementById('dual-pane-btn');
  if (btn) {
    btn.addEventListener('click', () => {
      if (isEnabled() && state.get('paneRightTabId')) {
        // toggle off right pane content but keep mode? prefer disable
        disable();
        window.showToast?.('已关闭分屏', 'info');
        return;
      }
      splitWithNewOrNextTab(generateId);
      import('./components/titlebar.js').then((m) => {
        m.renderTabs(
          (state.get('tabs') || []).filter(
            (t) => (t.projectId || 'ccc') === (state.get('currentProject') || 'ccc')
          ),
          state.get('activeTabId')
        );
      });
    });
    if (isEnabled()) btn.classList.add('active');
  }
}
