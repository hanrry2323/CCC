import { state } from '../state.js';
import { createBoardTask, loadProjects } from '../api.js';
import { escapeHtml } from '../utils.js';

function nowIso() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const offset = -d.getTimezoneOffset();
  const sign = offset >= 0 ? '+' : '-';
  const oh = pad(Math.floor(Math.abs(offset) / 60));
  const om = pad(Math.abs(offset) % 60);
  return (
    d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) +
    'T' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds()) +
    sign + oh + ':' + om
  );
}

function slugify(title) {
  const base = String(title || 'task')
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40) || 'task';
  // Board Protocol: id must be [a-zA-Z0-9_-] — strip CJK for id
  const ascii = base.replace(/[^a-z0-9_-]+/g, '').replace(/^-+|-+$/g, '') || 'task';
  return ascii + '-' + Date.now().toString(36).slice(-4);
}

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
  const overlay = document.createElement('div');
  overlay.className = 'dialog-overlay task-overlay';
  overlay.addEventListener('click', close);
  document.body.appendChild(overlay);

  const dialog = document.createElement('div');
  dialog.className = 'task-dialog settings-sheet';
  const projectOpts = projects.map(p =>
    '<option value="' + escapeHtml(p.id) + '"' +
    (p.id === state.get('currentProject') ? ' selected' : '') + '>' +
    escapeHtml(p.name) + '</option>'
  ).join('');

  dialog.innerHTML =
    '<div class="settings-panel">' +
      '<div class="settings-header">' +
        '<span class="settings-title">下达 CCC 任务</span>' +
        '<button class="settings-close" id="task-close">×</button>' +
      '</div>' +
      '<div class="settings-body">' +
        '<p class="task-help">写入看板 <code>backlog</code> 并<strong>立即唤醒 Engine</strong>（自动 enabled）。流程：拆分→开发→pytest→验收→发布。</p>' +
        '<div class="settings-group">' +
          '<div class="settings-row"><span class="settings-label">项目</span>' +
            '<select class="settings-select" id="task-project">' + projectOpts + '</select></div>' +
          '<div class="settings-row"><span class="settings-label">标题</span>' +
            '<input class="settings-input" id="task-title" maxlength="500" placeholder="简洁可执行的任务标题" value="' +
              escapeHtml(prefill.title || '') + '"></div>' +
          '<div class="settings-row settings-row-col"><span class="settings-label">描述</span>' +
            '<textarea class="settings-textarea" id="task-desc" rows="6" maxlength="10000" placeholder="背景、验收意图、参考命令…">' +
              escapeHtml(defaultDesc) + '</textarea></div>' +
          '<div class="settings-row"><span class="settings-label">复杂度</span>' +
            '<select class="settings-select" id="task-complexity">' +
              '<option value="small">small</option>' +
              '<option value="medium" selected>medium</option>' +
              '<option value="large">large</option>' +
            '</select></div>' +
        '</div>' +
        '<div class="task-actions">' +
          '<button type="button" class="btn-secondary" id="task-cancel">取消</button>' +
          '<button type="button" class="btn-primary" id="task-submit">下达并开工</button>' +
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
    const complexity = document.getElementById('task-complexity')?.value || 'medium';
    const projectId = document.getElementById('task-project')?.value || state.get('currentProject');
    if (!title) {
      window.showToast?.('请填写标题', 'error');
      return;
    }
    const ts = nowIso();
    const id = slugify(title);
    const workspace = projectToWorkspace(projectId);
    const btn = document.getElementById('task-submit');
    if (btn) btn.disabled = true;
    try {
      const res = await createBoardTask({
        id,
        title,
        description,
        status: 'backlog',
        created_at: ts,
        updated_at: ts,
        schema_version: '1.2',
        complexity,
        tags: ['from-chat'],
        workspace,
        ...(prefill.plan_md ? { plan_md: prefill.plan_md } : {}),
        ...(prefill.phases_jsonl ? { phases_jsonl: prefill.phases_jsonl } : {}),
      });
      const tid = res.task_id || id;
      const skip = res.skip_product ? '（已预置 plan，跳过 product）' : '';
      const wake = res.engine_wake;
      const wakeHint = wake && wake.ok !== false
        ? ' · Engine 已唤醒'
        : (wake && wake.error ? ' · Engine 唤醒失败' : ' · Engine 已唤醒');
      window.showToast?.('已下达 ' + tid + skip + wakeHint, 'success');
      close();
      import('./boardPanel.js').then(m => {
        m.openBoardPanel?.();
        m.trackDispatchedTask?.(tid, workspace);
        m.refreshBoardPanel?.();
      });
    } catch (err) {
      window.showToast?.(err.message || '创建失败', 'error');
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
