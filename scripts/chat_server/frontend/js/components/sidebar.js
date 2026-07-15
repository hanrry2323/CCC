import { state } from '../state.js';
import { loadHistory, deleteSession } from '../api.js';
import { escapeHtml, debounce } from '../utils.js';
import { showToast } from './toast.js';

export async function refreshSidebar() {
  const project = state.get('currentProject');
  const sessions = await loadHistory(project);
  state.set('sessions', sessions);
  renderSidebar(sessions);
}

export function renderSidebar(sessions) {
  const list = document.getElementById('session-list');
  const currentSid = state.get('currentSessionId');

  if (!sessions || sessions.length === 0) {
    list.innerHTML = '<div style="padding:20px 16px;text-align:center;color:var(--ccc-text-faint);font-size:13px;line-height:1.5;">暂无对话历史<br><span style="font-size:11px;">发送一条消息开始对话</span></div>';
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

  const order = ['今天', '昨天', ...Object.keys(groups).filter(k => k !== '今天' && k !== '昨天').sort().reverse()];

  let html = '';
  for (const label of order) {
    const items = groups[label];
    if (!items || items.length === 0) continue;
    html += '<div class="sidebar-group-label">' + label + '</div>';
    for (const s of items) {
      const active = s.session_id === currentSid ? ' active' : '';
      html += '<div class="session-item' + active + '" data-sid="' + s.session_id + '">' +
        '<div class="session-item-title">' + escapeHtml(s.title || '对话') + '</div>' +
        '<div class="session-item-meta">' + escapeHtml(s.updated_at || '') + '</div>' +
        '<button class="delete-btn" title="删除">×</button>' +
        '</div>';
    }
  }
  list.innerHTML = html;

  list.querySelectorAll('.session-item').forEach(el => {
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
            list.innerHTML = '<div style="padding:20px 16px;text-align:center;color:var(--ccc-text-faint);font-size:13px;">暂无对话历史</div>';
          }
        } catch (e) {
          showToast('删除失败', 'error');
        }
      });
    }
  });
}

export function setupSidebarSearch() {
  const input = document.getElementById('sidebar-search');
  const clearBtn = document.getElementById('sidebar-search-clear');
  if (!input) return;

  input.addEventListener('input', debounce(() => {
    const q = input.value.toLowerCase();
    document.querySelectorAll('.session-item').forEach(el => {
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
}
