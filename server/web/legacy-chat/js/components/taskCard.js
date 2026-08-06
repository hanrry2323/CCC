export const STATE_TONE = {
  '待分派': 'pending',
  '执行中': 'running',
  '机审': 'audit',
  '已回写': 'written',
  '已关闭': 'closed',
  '打回': 'returned',

  'pending': 'pending',
  'running': 'running',
  'audit': 'audit',
  'written': 'written',
  'closed': 'closed',
  'returned': 'returned'
};

export const STATE_COLORS = {
  '待分派': '#a39e93',
  '执行中': '#c47a2c',
  '机审': '#8b6cc1',
  '已回写': '#3d9a5f',
  '已关闭': '#5a7a9a',
  '打回': '#c44',

  'pending': '#a39e93',
  'running': '#c47a2c',
  'audit': '#8b6cc1',
  'written': '#3d9a5f',
  'closed': '#5a7a9a',
  'returned': '#c44'
};

export function escapeHtml(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

export function renderTaskCard(t) {
  const state = t.state || t.status || '待分派';
  const tone = STATE_TONE[state] || 'pending';
  const color = STATE_COLORS[state] || '#a39e93';

  const reject = Number(t.reject_count || 0);
  const rejectHtml = reject > 0
    ? `<span class="board-card-badge badge-reject" title="打回次数">↩ ${reject}</span>`
    : '';

  const dirty = t.dirty_files;
  const dirtyHtml =
    dirty != null && dirty !== '' && Number(dirty) >= 0
      ? `<span class="board-card-badge badge-dirty" title="worktree 未提交改动文件数">Δ ${escapeHtml(String(dirty))}</span>`
      : '';

  const executor = t.executor && t.executor !== '未知'
    ? `<span class="board-card-badge badge-exec" title="执行体">@${escapeHtml(t.executor)}</span>`
    : '';

  const updated = t.written_at && t.written_at !== '未知'
    ? t.written_at
    : (t.dispatched_at && t.dispatched_at !== '未知' ? t.dispatched_at : (t.updated_at || ''));
  const updatedHtml = updated
    ? `<span class="board-card-time" title="更新时间">${escapeHtml(updated)}</span>`
    : '';

  return `
    <div class="board-task-card board-card board-card-work state-${tone} ${tone === 'running' ? 'running' : ''}"
         data-id="${escapeHtml(t.id)}"
         data-col="${escapeHtml(state)}"
         style="border-left-color: ${color}; --state-bar: ${color}">
      <div class="board-card-row">
        <span class="board-card-id id">${escapeHtml(t.id)}</span>
        <span class="board-card-state state-${tone}">${escapeHtml(state)}</span>
      </div>
      <div class="board-card-title ti">${escapeHtml(t.title || t.id)}</div>
      <div class="board-card-meta">
        ${executor}
        ${dirtyHtml}
        ${rejectHtml}
        ${updatedHtml}
        <button type="button" class="board-card-copy card-copy-btn" data-id="${escapeHtml(t.id)}" title="复制 ID" aria-label="复制 ID">
          <span class="card-copy-ico" aria-hidden="true">⧉</span>
          <span class="card-copy-txt" style="font-size:10px;margin-left:2px">复制</span>
        </button>
      </div>
      <div class="board-card-detail" hidden></div>
    </div>
  `;
}

export function fmtTaskCopy(t, col) {
  const lines = [
    '<<<CCC_TASK>>>',
    'id: ' + (t.id || ''),
    'workspace: ' + (t.project || ''),
    'column: ' + (col || t.state || t.status || ''),
    'kind: ' + (t.card_kind || 'work'),
    'title: ' + (t.title || ''),
  ];
  if (t.parent_id) lines.push('parent: ' + t.parent_id);
  if (t.split_status) lines.push('split_status: ' + t.split_status);
  if (t.note) lines.push('note: ' + t.note);
  if (Array.isArray(t.phases) && t.phases.length) {
    lines.push('phases: ' + t.phases.map(p => p.name || p).join(', '));
  }
  lines.push('<<<END_CCC_TASK>>>');
  lines.push('（请围绕上述任务与我讨论：现状、风险、下一步）');
  return lines.join('\n');
}
