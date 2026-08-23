import { state } from '../state.js';
import { loadProjects } from '../api.js';
import { escapeHtml } from '../utils.js';

function projectToWorkspace(projectId) {
  const map = state.get('projectWorkspaceMap') || {};
  if (projectId && map[projectId]) return map[projectId];
  if (!projectId) return 'CCC';
  if (projectId === 'ccc') return 'CCC';
  return projectId;
}

export async function openTaskDialog(prefill = {}) {
  document.querySelector('.task-dialog')?.remove();
  document.querySelector('.dialog-overlay.task-overlay')?.remove();

  const msgs = state.get('currentMessages') || [];
  const lastAssistant = [...msgs].reverse().find(m => m.role === 'assistant');
  const defaultDesc = prefill.description ||
    (lastAssistant ? String(lastAssistant.content || '').slice(0, 2000) : '');

  const projects = await loadProjects().catch(() => []);
  const dispatchable = projects.filter(
    (p) => p.role !== 'orch' && p.engine_eligible !== false
  );
  if (!dispatchable.length) {
    window.showToast?.(
      '无业务项目可下达。CCC 编排仓请用开发工具（Claude/OpenCode）改；请先登记业务仓。',
      'error'
    );
    return;
  }
  const overlay = document.createElement('div');
  overlay.className = 'dialog-overlay task-overlay';
  overlay.addEventListener('click', close);
  document.body.appendChild(overlay);

  const dialog = document.createElement('div');
  dialog.className = 'task-dialog settings-sheet';
  const prefer =
    dispatchable.find((p) => p.id === state.get('currentProject')) ||
    dispatchable.find((p) => p.id === state.get('defaultProject')) ||
    dispatchable[0];
  const projectOpts = dispatchable
    .map(
      (p) =>
        '<option value="' +
        escapeHtml(p.id) +
        '"' +
        (p.id === prefer.id ? ' selected' : '') +
        '>' +
        escapeHtml(p.name) +
        '</option>'
    )
    .join('');

  dialog.innerHTML =
    '<div class="settings-panel">' +
      '<div class="settings-header">' +
        '<span class="settings-title">下达 CCC 任务</span>' +
        '<button class="settings-close" id="task-close">×</button>' +
      '</div>' +
      '<div class="settings-body">' +
        '<p class="task-help">任务会交给<strong>大脑 Agent 写成任务卡</strong>（docs/dispatch/），看板自动刷新出现；Engine 随后派发执行。CCC 编排仓不可下达。</p>' +
        '<div class="settings-group">' +
          '<div class="settings-row"><span class="settings-label">项目</span>' +
            '<select class="settings-select" id="task-project">' + projectOpts + '</select></div>' +
          '<div class="settings-row"><span class="settings-label">标题</span>' +
            '<input class="settings-input" id="task-title" maxlength="500" placeholder="简洁可执行的任务标题" value="' +
              escapeHtml(prefill.title || '') + '"></div>' +
          '<div class="settings-row settings-row-col"><span class="settings-label">描述</span>' +
            '<textarea class="settings-textarea" id="task-desc" rows="6" maxlength="10000" placeholder="背景、验收意图、参考命令…">' +
              escapeHtml(defaultDesc) + '</textarea></div>' +
        '</div>' +
        '<div class="task-actions">' +
          '<button type="button" class="btn-secondary" id="task-cancel">取消</button>' +
          '<button type="button" class="btn-primary" id="task-submit">下达（大脑写卡）</button>' +
        '</div>' +
      '</div>' +
    '</div>';

  document.body.appendChild(dialog);
  document.getElementById('task-close')?.addEventListener('click', close);
  document.getElementById('task-cancel')?.addEventListener('click', close);
  document.getElementById('task-submit')?.addEventListener('click', submit);
  document.getElementById('task-title')?.focus();

  async function submit() {
    const title = document.getElementById('task-title')?.value.trim();
    const description = document.getElementById('task-desc')?.value.trim() || '';
    const projectId = document.getElementById('task-project')?.value || state.get('currentProject');
    if (!title) {
      window.showToast?.('请填写标题', 'error');
      return;
    }
    const meta = projects.find((p) => p.id === projectId);
    if (meta && (meta.role === 'orch' || meta.engine_eligible === false)) {
      window.showToast?.(
        'CCC 编排仓不可下达。平台请用开发工具（Claude/OpenCode）改 CCC；业务请选登记项目。',
        'error'
      );
      return;
    }
    const workspace = projectToWorkspace(projectId);
    const btn = document.getElementById('task-submit');
    if (btn) btn.disabled = true;
    // T45：HTTP 壳写操作闭环——任务交给大脑 Agent 写成任务卡（docs/dispatch/），
    // 看板自动刷新出现；不再调禁用的创建 API。
    const prompt =
      '请帮我写一张任务卡并投递到 docs/dispatch/（按 references/board-task-schema.md ' +
      '契约格式；标题与编号先读现有卡避免撞号，状态：待分派）：\n' +
      '【标题】' + title + '\n' +
      '【关联项目】' + workspace + '\n' +
      '【目标】\n' + (description || '（请补全为可执行的目标、范围与验收标准）');
    // 2026-08-24 修复：原先 close() 在校验/发送之前——流式中或发送抛错时用户填的
    // 标题/描述已随对话框销毁。改为全部通过后再关窗。
    try {
      const { isCurrentTabStreaming } = await import('../streamRegistry.js');
      if (isCurrentTabStreaming()) {
        window.showToast?.('当前对话仍在生成，请等待完成后再下达', 'error');
        if (btn) btn.disabled = false;
        return;
      }
      const { sendMessage } = await import('./message.js');
      sendMessage(prompt);
      close();
      window.showToast?.('任务已交给大脑写卡，完成后自动出现在看板', 'success');
    } catch (err) {
      window.showToast?.(err.message || '下达失败', 'error');
      if (btn) btn.disabled = false;
    }
  }

  function close() {
    dialog.remove();
    overlay.remove();
  }
}

export function openTaskFromReply() {
  const msgs = state.get('currentMessages') || [];
  const lastAssistant = [...msgs].reverse().find(m => m.role === 'assistant');
  const lastUser = [...msgs].reverse().find(m => m.role === 'user');
  openTaskDialog({
    title: lastUser ? String(lastUser.content || '').slice(0, 80) : '',
    description: lastAssistant ? String(lastAssistant.content || '').slice(0, 4000) : '',
  });
}
