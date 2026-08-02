import { state } from '../state.js';

export function exportCurrentSession() {
  const msgs = state.get('currentMessages') || [];
  if (!msgs.length) {
    window.showToast?.('当前没有可导出的消息', 'error');
    return;
  }
  const lines = ['# CCC Chat Export', '', 'Project: ' + (state.get('currentProject') || ''), ''];
  for (const m of msgs) {
    const role = m.role === 'user' ? 'User' : 'Assistant';
    lines.push('## ' + role, '', m.content || '', '');
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'ccc-chat-' + (state.get('currentSessionId') || 'session').slice(0, 8) + '.md';
  a.click();
  URL.revokeObjectURL(a.href);
  window.showToast?.('已导出 Markdown', 'success');
}
