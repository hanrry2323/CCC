import { state } from '../state.js';
import { apiGet, loadHistory } from '../api.js';
import { escapeHtml } from '../utils.js';

export async function refreshSidebar() {
  const project = state.get('currentProject');
  const sessions = await loadHistory(project);
  state.set('sessions', sessions);
  renderSidebar(sessions);
}

export function renderSidebar(sessions) {
  const list = document.getElementById('session-list');

  if (!sessions || sessions.length === 0) {
    list.innerHTML = '<div style="padding:16px;text-align:center;color:var(--ccc-text-faint);font-size:13px;">暂无对话历史</div>';
    return;
  }

  // Group by date
  const groups = {};
  const today = new Date();
  const todayStr = today.toISOString().slice(0, 10);
  const yesterdayStr = new Date(today.getTime() - 86400000).toISOString().slice(0, 10);

  for (const s of sessions) {
    const date = (s.updated_at || '').slice(0, 10);
    let label;
    if (date === todayStr) label = '今天';
    else if (date === yesterdayStr) label = '昨天';
    else label = date || '更早';
    (groups[label] = groups[label] || []).push(s);
  }

  const order = ['今天', '昨天', ...Object.keys(groups).filter(k => k !== '今天' && k !== '昨天').sort().reverse()];

  let html = '';
  for (const label of order) {
    if (!groups[label]) continue;
    html += '<div class="sidebar-group-label">' + label + '</div>';
    for (const s of groups[label]) {
      const active = s.session_id === state.get('currentSessionId') ? ' active' : '';
      html += '<div class="session-item' + active + '" data-sid="' + s.session_id + '">' +
        '<div class="session-item-title">' + escapeHtml(s.title) + '</div>' +
        '<div class="session-item-meta">' + escapeHtml(s.updated_at || '') + '</div>' +
        '</div>';
    }
  }
  list.innerHTML = html;

  // Click handlers
  list.querySelectorAll('.session-item').forEach(el => {
    el.addEventListener('click', () => {
      const event = new CustomEvent('load-session', { detail: { id: el.dataset.sid } });
      document.dispatchEvent(event);
    });
  });
}

export function setupSidebarSearch() {
  const input = document.getElementById('sidebar-search');
  if (!input) return;
  input.addEventListener('input', () => {
    const q = input.value.toLowerCase();
    document.querySelectorAll('.session-item').forEach(el => {
      const title = el.querySelector('.session-item-title')?.textContent?.toLowerCase() || '';
      el.style.display = title.includes(q) ? '' : 'none';
    });
  });
}
