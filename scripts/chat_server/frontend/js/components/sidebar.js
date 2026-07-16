import { state } from '../state.js';
import { loadHistory, deleteSession, cleanupTestSessions } from '../api.js';
import { escapeHtml, debounce } from '../utils.js';
import { showToast } from './toast.js';

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
  const currentSid = state.get('currentSessionId');

  if (!sessions || sessions.length === 0) {
    list.innerHTML =
      '<div style="padding:20px 16px;text-align:center;color:var(--ccc-text-faint);font-size:13px;line-height:1.5;">暂无对话历史<br><span style="font-size:11px;">发送一条消息，或切换到 Claude 源</span></div>';
    return;
  }

  const groups = {};
  const today = new Date();
  const todayStr = today.toISOString().slice(0, 10);
  const yesterdayStr = new Date(today.getTime() - 86400000).toISOString().slice(0, 10);

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
    html += '<div class="sidebar-group-label">' + label + '</div>';
    for (const s of items) {
      const active = s.session_id === currentSid ? ' active' : '';
      const isClaude = s.source === 'claude' || String(s.session_id || '').startsWith('claude:');
      const badge = isClaude
        ? '<span class="session-badge claude">Claude</span>'
        : '<span class="session-badge hub">Hub</span>';
      const del = isClaude
        ? ''
        : '<button class="delete-btn" title="删除">×</button>';
      html +=
        '<div class="session-item' +
        active +
        '" data-sid="' +
        escapeHtml(s.session_id) +
        '" data-source="' +
        (isClaude ? 'claude' : 'hub') +
        '">' +
        '<div class="session-item-title">' +
        badge +
        escapeHtml(s.title || '对话') +
        '</div>' +
        '<div class="session-item-meta">' +
        escapeHtml(s.updated_at || '') +
        '</div>' +
        del +
        '</div>';
    }
  }
  list.innerHTML = html;

  list.querySelectorAll('.session-item').forEach((el) => {
    el.addEventListener('click', (e) => {
      if (e.target.closest('.delete-btn')) return;
      const event = new CustomEvent('load-session', { detail: { id: el.dataset.sid } });
      document.dispatchEvent(event);
    });

    const delBtn = el.querySelector('.delete-btn');
    if (delBtn) {
      delBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const sid = el.dataset.sid;
        try {
          await deleteSession(sid, state.get('currentProject'));
          el.remove();
          showToast('对话已删除', 'success');
          if (!list.querySelector('.session-item')) {
            list.innerHTML =
              '<div style="padding:20px 16px;text-align:center;color:var(--ccc-text-faint);font-size:13px;">暂无对话历史</div>';
          }
        } catch (err) {
          showToast('删除失败', 'error');
        }
      });
    }
  });
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

  input.addEventListener('input', debounce(() => {
    const q = input.value.toLowerCase();
    document.querySelectorAll('.session-item').forEach((el) => {
      const title = el.querySelector('.session-item-title')?.textContent?.toLowerCase() || '';
      el.style.display = title.includes(q) ? '' : 'none';
    });
    if (clearBtn) {
      clearBtn.classList.toggle('show', input.value.length > 0);
    }
  }, 200));

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
      if (!confirm('清理侧栏里的 pytest/e2e 测试对话？（移入回收站，可恢复）')) return;
      try {
        const res = await cleanupTestSessions(state.get('currentProject') || 'ccc');
        showToast('已清理 ' + (res.moved || 0) + ' 条测试对话', 'success');
        await refreshSidebar();
      } catch (e) {
        showToast('清理失败: ' + (e.message || e), 'error');
      }
    });
  }
}
