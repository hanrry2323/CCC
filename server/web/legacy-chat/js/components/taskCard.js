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

/** 卡片进度徽章：Δ=未提交文件数（非 LLM 调用）；+/- = 行变更；执行中可显已用时。 */
export function renderWorktreeBadges(t) {
  const parts = [];

  const dirty = t.dirty_files;
  if (dirty != null && dirty !== '' && Number(dirty) > 0) {
    parts.push(
      `<span class="board-card-badge badge-dirty" title="worktree 未提交改动文件数（不是模型调用次数）">Δ${escapeHtml(String(dirty))}</span>`
    );
  }

  let ins = t.lines_insert;
  let del = t.lines_delete;
  const wtChurn = (Number(ins) || 0) + (Number(del) || 0);
  if (wtChurn === 0 && (t.branch_insert != null || t.branch_delete != null)) {
    ins = t.branch_insert;
    del = t.branch_delete;
  }
  const lineIns = Number(ins) || 0;
  const lineDel = Number(del) || 0;
  if (lineIns + lineDel > 0) {
    parts.push(
      `<span class="board-card-badge badge-lines" title="代码行变更（工作区优先；干净时用相对 main 的已提交 diff）"><span class="lines-ins">+${escapeHtml(String(lineIns))}</span><span class="lines-del">−${escapeHtml(String(lineDel))}</span></span>`
    );
  }

  // 执行中：日志在长、文件尚未落地时也给实时信号（已用时 / 最近活动）
  const elapsed = t.elapsed_s;
  if (elapsed != null && elapsed !== '' && Number(elapsed) >= 0) {
    const sec = Number(elapsed);
    const label = sec < 60 ? `${sec}s` : sec < 3600 ? `${Math.floor(sec / 60)}m` : `${Math.floor(sec / 3600)}h`;
    const recent =
      t.last_activity_at && (Date.now() - new Date(t.last_activity_at).getTime()) < 45000;
    const tone = recent ? 'badge-live' : 'badge-elapsed';
    const tip = recent
      ? '执行体日志近期有输出（模型在跑；Δ 仅在落盘改文件后变）'
      : '已用时（自执行日志创建起）';
    parts.push(
      `<span class="board-card-badge ${tone}" title="${tip}">⏱${escapeHtml(label)}</span>`
    );
  }

  return parts.join('');
}

export function renderTaskCard(t) {
  const state = t.board_column || t.state || t.status || '待分派';
  const tone = STATE_TONE[state] || 'pending';
  const color = STATE_COLORS[state] || '#a39e93';

  const reject = Number(t.reject_count || 0);
  const rejectHtml = reject > 0
    ? `<span class="board-card-badge badge-reject" title="打回次数">↩ ${reject}</span>`
    : '';

  const statsHtml = renderWorktreeBadges(t);

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
        <span class="board-card-stats">${statsHtml}</span>
        ${rejectHtml}
        ${updatedHtml}
        <button type="button" class="board-card-copy card-copy-btn" data-id="${escapeHtml(t.id)}" title="复制 ID" aria-label="复制 ID">
          <span class="card-copy-ico" aria-hidden="true">⧉</span>
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
