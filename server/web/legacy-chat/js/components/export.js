import { state } from '../state.js';

export function exportCurrentSession() {
  const msgs = state.get('currentMessages') || [];
  if (!msgs.length) {
    window.showToast?.('当前没有可导出的消息', 'error');
    return;
  }
  const lines = ['# CCC Chat Export', '', 'Project: ' + (state.get('currentProject') || ''), ''];
  for (const m of msgs) {
    // 2026-08-24 修复：system/tool 角色一刀切成 Assistant 导致导出失真，保留原始角色
    const role = m.role === 'user' ? 'User'
      : m.role === 'assistant' ? 'Assistant'
      : String(m.role || 'system');
    lines.push('## ' + role, '', m.content || '', '');
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  // 文件名字符白名单（sessionId 格式不受前端约束，防分隔符截断/替换）
  const sid = String(state.get('currentSessionId') || 'session').replace(/[^A-Za-z0-9_-]/g, '').slice(0, 24) || 'session';
  a.download = 'ccc-chat-' + sid + '.md';
  a.click();
  URL.revokeObjectURL(a.href);
  window.showToast?.('已导出 Markdown', 'success');
}
