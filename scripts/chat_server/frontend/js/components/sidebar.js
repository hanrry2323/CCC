import { state } from '../state.js';
import {
  loadHistory,
  deleteSession,
  cleanupTestSessions,
  renameSession,
} from '../api.js';
import { escapeHtml, debounce, relativeTime } from '../utils.js';
import { showToast } from './toast.js';

function emptyHtml(msg, sub) {
  return (
    '<div class="sidebar-empty">' +
    '<div class="sidebar-empty-title">' +
    escapeHtml(msg) +
    '</div>' +
    (sub
      ? '<div class="sidebar-empty-sub">' + escapeHtml(sub) + '</div>'
      : '') +
    '</div>'
  );
}

export async function refreshSidebar() {
  const project = state.get('currentProject');
  const source = state.get('historySource') || 'all';
  const sessions = await loadHistory(project, source);
  state.set('sessions', sessions);
  renderSidebar(sessions);
  _syncSourceTabs(source);
}

export function renderSidebar(sessions) {
  const list = document.getElementById('session-list');
  if (!list) return;
  const currentSid = state.get('currentSessionId');

  if (!sessions || sessions.length === 0) {
    list.innerHTML = emptyHtml(
      '暂无对话历史',
      '发送一条消息，或切换到 Claude 源'
    );
    return;
  }

  const groups = {};
  const today = new Date();
  const todayStr = today.toISOString().slice(0, 10);
  const yesterdayStr = new Date(today.getTime() - 86400000)
    .toISOString()
    .slice(0, 10);

  for (const s of sessions) {
    const date = (s.updated_at || '').slice(0, 10);
    if (date === todayStr) {
      (groups['今天'] = groups['今天'] || []).push(s);
    } else if (date === yesterdayStr) {
      (groups['昨天'] = groups['昨天'] || []).push(s);
    } else {
      (groups[date || '更早'] = groups[date || '更早'] || []).push(s);
    }
  }

  const order = [
    '今天',
    '昨天',
    ...Object.keys(groups)
      .filter((k) => k !== '今天' && k !== '昨天')
      .sort()
      .reverse(),
  ];

  let html = '';
  for (const label of order) {
    const items = groups[label];
    if (!items || items.length === 0) continue;
    html +=
      '<div class="sidebar-group" data-group="' +
      escapeHtml(label) +
      '">' +
      '<div class="sidebar-group-label">' +
      label +
      '</div>';
    for (const s of items) {
      const active = s.session_id === currentSid ? ' active' : '';
      const isClaude =
        s.source === 'claude' ||
        String(s.session_id || '').startsWith('claude:');
      const badge = isClaude
        ? '<span class="session-badge claude" title="只读 · 在 Claude Code 中管理">Claude</span>'
        : '<span class="session-badge hub">Hub</span>';
      const menu = isClaude
        ? '<button type="button" class="session-menu-btn" title="只读" disabled>⋯</button>'
        : '<button type="button" class="session-menu-btn" title="更多" aria-label="更多">⋯</button>';
      html +=
        '<div class="session-item' +
        active +
        '" data-sid="' +
        escapeHtml(s.session_id) +
        '" data-source="' +
        (isClaude ? 'claude' : 'hub') +
        '" data-title="' +
        escapeHtml(s.title || '对话') +
        '">' +
        '<div class="session-item-title">' +
        badge +
        '<span class="session-title-text">' +
        escapeHtml(s.title || '对话') +
        '</span></div>' +
        '<div class="session-item-meta">' +
        escapeHtml(relativeTime(s.updated_at) || s.updated_at || '') +
        '</div>' +
        menu +
        '</div>';
    }
    html += '</div>';
  }
  list.innerHTML = html;

  list.querySelectorAll('.session-item').forEach((el) => {
    el.addEventListener('click', (e) => {
      if (e.target.closest('.session-menu-btn') || e.target.closest('.session-menu'))
        return;
      document.dispatchEvent(
        new CustomEvent('load-session', { detail: { id: el.dataset.sid } })
      );
    });

    el.addEventListener('dblclick', (e) => {
      if (el.dataset.source === 'claude') return;
      e.preventDefault();
      e.stopPropagation();
      startInlineRename(el);
    });

    const menuBtn = el.querySelector('.session-menu-btn:not([disabled])');
    if (menuBtn) {
      menuBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleSessionMenu(el, menuBtn);
      });
    }
  });

  // Re-apply search filter if any
  const input = document.getElementById('sidebar-search');
  if (input?.value) {
    applySearchFilter(input.value);
  }
}

function closeAllMenus() {
  document.querySelectorAll('.session-menu').forEach((m) => m.remove());
}

function toggleSessionMenu(el, btn) {
  const existing = el.querySelector('.session-menu');
  if (existing) {
    existing.remove();
    return;
  }
  closeAllMenus();
  const menu = document.createElement('div');
  menu.className = 'session-menu';
  menu.innerHTML =
    '<button type="button" data-act="rename">重命名</button>' +
    '<button type="button" data-act="copy">复制 ID</button>' +
    '<button type="button" data-act="delete" class="danger">删除</button>';
  el.appendChild(menu);
  menu.addEventListener('click', async (e) => {
    e.stopPropagation();
    const act = e.target.closest('button')?.dataset?.act;
    if (!act) return;
    menu.remove();
    const sid = el.dataset.sid;
    if (act === 'rename') {
      startInlineRename(el);
    } else if (act === 'copy') {
      try {
        await navigator.clipboard.writeText(sid);
        showToast('已复制会话 ID', 'success');
      } catch {
        showToast(sid, 'info');
      }
    } else if (act === 'delete') {
      await confirmAndDelete(el, sid);
    }
  });
  setTimeout(() => {
    const once = (ev) => {
      if (!menu.contains(ev.target) && ev.target !== btn) {
        menu.remove();
        document.removeEventListener('click', once);
      }
    };
    document.addEventListener('click', once);
  }, 0);
}

function startInlineRename(el) {
  if (el.dataset.source === 'claude') return;
  const titleEl = el.querySelector('.session-title-text');
  if (!titleEl || el.querySelector('.session-rename-input')) return;
  const old = el.dataset.title || titleEl.textContent || '';
  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'session-rename-input';
  input.value = old;
  input.maxLength = 80;
  titleEl.replaceWith(input);
  input.focus();
  input.select();

  const finish = async (save) => {
    const val = input.value.trim();
    const span = document.createElement('span');
    span.className = 'session-title-text';
    if (!save || !val || val === old) {
      span.textContent = old;
      input.replaceWith(span);
      return;
    }
    try {
      await renameSession(el.dataset.sid, state.get('currentProject'), val);
      span.textContent = val;
      el.dataset.title = val;
      input.replaceWith(span);
      showToast('已重命名', 'success');
    } catch (err) {
      span.textContent = old;
      input.replaceWith(span);
      showToast(err.message || '重命名失败', 'error');
    }
  };

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      finish(true);
    } else if (e.key === 'Escape') {
      finish(false);
    }
  });
  input.addEventListener('blur', () => finish(true));
}

async function confirmAndDelete(el, sid) {
  if (!confirm('确定删除这条对话？此操作不可撤销。')) return;
  try {
    await deleteSession(sid, state.get('currentProject'));
    const wasActive = sid === state.get('currentSessionId');
    el.remove();
    showToast('对话已删除', 'success');
    const list = document.getElementById('session-list');
    // Hide empty groups
    list?.querySelectorAll('.sidebar-group').forEach((g) => {
      if (!g.querySelector('.session-item')) g.remove();
    });
    if (!list?.querySelector('.session-item')) {
      list.innerHTML = emptyHtml('暂无对话历史');
    }
    if (wasActive) {
      document.dispatchEvent(new CustomEvent('new-tab'));
    }
  } catch (err) {
    showToast('删除失败', 'error');
  }
}

function applySearchFilter(qRaw) {
  const q = String(qRaw || '').toLowerCase().trim();
  const list = document.getElementById('session-list');
  if (!list) return;
  list.querySelector('.sidebar-no-results')?.remove();

  let visibleCount = 0;
  list.querySelectorAll('.session-item').forEach((el) => {
    const title =
      el.querySelector('.session-title-text')?.textContent?.toLowerCase() ||
      el.dataset.title?.toLowerCase() ||
      '';
    const show = !q || title.includes(q);
    el.style.display = show ? '' : 'none';
    if (show) visibleCount++;
  });

  list.querySelectorAll('.sidebar-group').forEach((g) => {
    const any = [...g.querySelectorAll('.session-item')].some(
      (el) => el.style.display !== 'none'
    );
    g.style.display = any ? '' : 'none';
  });

  if (q && visibleCount === 0 && list.querySelector('.session-item')) {
    const tip = document.createElement('div');
    tip.className = 'sidebar-no-results';
    tip.textContent = '无匹配「' + qRaw + '」的对话';
    list.appendChild(tip);
  }
}

function _syncSourceTabs(source) {
  document.querySelectorAll('.history-source-btn').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.source === source);
  });
}

export function setupSidebarSearch() {
  const input = document.getElementById('sidebar-search');
  const clearBtn = document.getElementById('sidebar-search-clear');
  if (!input) return;

  input.addEventListener(
    'input',
    debounce(() => {
      applySearchFilter(input.value);
      if (clearBtn) {
        clearBtn.classList.toggle('show', input.value.length > 0);
      }
    }, 200)
  );

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      input.value = '';
      input.dispatchEvent(new Event('input'));
      input.focus();
      clearBtn.classList.remove('show');
    });
  }

  document.querySelectorAll('.history-source-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      state.set('historySource', btn.dataset.source || 'all');
      refreshSidebar().catch(() => showToast('刷新失败', 'error'));
    });
  });

  const cleanBtn = document.getElementById('cleanup-tests-btn');
  if (cleanBtn) {
    cleanBtn.addEventListener('click', async () => {
      if (
        !confirm('清理侧栏里的 pytest/e2e 测试对话？（移入回收站，可恢复）')
      )
        return;
      try {
        const res = await cleanupTestSessions(
          state.get('currentProject') || 'ccc'
        );
        showToast('已清理 ' + (res.moved || 0) + ' 条测试对话', 'success');
        await refreshSidebar();
      } catch (e) {
        showToast('清理失败: ' + (e.message || e), 'error');
      }
    });
  }
}
