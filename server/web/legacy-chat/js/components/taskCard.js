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

/** 格式化已运行秒数 → 12s / 3m20s / 1h05m */
function fmtElapsed(sec) {
  const s = Math.max(0, Number(sec) || 0);
  if (s < 60) return `${s}s`;
  if (s < 3600) {
    const m = Math.floor(s / 60);
    const r = s % 60;
    return r ? `${m}m${String(r).padStart(2, '0')}s` : `${m}m`;
  }
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return m ? `${h}h${String(m).padStart(2, '0')}m` : `${h}h`;
}

/**
 * 卡片运行徽章（各列都展示，调用数只增不减）：
 * 调用 N · ⏱时长 · Δ文件 · +/−行
 */
export function renderWorktreeBadges(t) {
  const parts = [];

  const calls = t.tool_calls;
  if (calls != null && calls !== '' && Number(calls) >= 0) {
    parts.push(
      `<span class="board-card-badge badge-calls" title="累计工具调用（开发+机审各阶段日志汇总；高水位跟卡走，不因换列归零）">调用 ${escapeHtml(String(Number(calls)))}</span>`
    );
  }

  const elapsed = t.elapsed_s;
  if (elapsed != null && elapsed !== '' && Number(elapsed) >= 0) {
    const liveFlag = t.metrics_live === true || t.metrics_live === 'true';
    // 以运行时 marker 驱动（{id}.running / {id}-audit.running 存在即 live），
    // 不再依赖 45s 最近活动窗口——机审进行中同样显示动画指示。
    const st = t.board_column || t.state || '';
    const recent = liveFlag && st !== '已关闭' && st !== '打回';
    parts.push(
      `<span class="board-card-badge ${recent ? 'badge-live' : 'badge-elapsed'}" title="${recent ? '执行中/机审中 · 已运行时长' : '累计运行时长（结束后冻结，随卡进机审/回写）'}">⏱ ${escapeHtml(fmtElapsed(elapsed))}</span>`
    );
  }

  const dirty = t.dirty_files;
  if (dirty != null && dirty !== '' && Number(dirty) > 0) {
    parts.push(
      `<span class="board-card-badge badge-dirty" title="worktree 未提交改动文件数">Δ${escapeHtml(String(dirty))}</span>`
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
      `<span class="board-card-badge badge-lines" title="代码行变更（工作区优先；否则相对 main）"><span class="lines-ins">+${escapeHtml(String(lineIns))}</span><span class="lines-del">−${escapeHtml(String(lineDel))}</span></span>`
    );
  }

  return parts.join('');
}

export function renderTaskCard(t, opts = {}) {
  const state = t.board_column || t.state || t.status || '待分派';
  const tone = STATE_TONE[state] || 'pending';
  const color = STATE_COLORS[state] || '#a39e93';
  const streamHtml = opts.stream
    ? `<div class="board-card-stream" data-stream-id="${escapeHtml(t.id)}">
        <div class="board-card-stream-lines"><div class="board-card-stream-empty">连接实时日志…</div></div>
      </div>`
    : '';

  const auditStatus = t.audit_status ? `<span class="board-card-badge badge-audit badge-audit-${t.audit_status}" title="机审状态：${t.audit_status}">${t.audit_status}</span>` : '';

  const reject = Number(t.reject_count || 0);
  const rejectHtml = reject > 0
    ? `<span class="board-card-badge badge-reject" title="打回次数">↩ ${reject}</span>`
    : '';

  const statsHtml = renderWorktreeBadges(t);
  const metricsBlock = `<div class="board-card-metrics" style="min-height:16px" aria-label="运行指标">${
    statsHtml || '<span class="board-card-badge badge-none" title="暂无运行指标">—</span>'
  }</div>`;

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
        <div class="board-card-row-right">
          <span class="board-card-state state-${tone}">${escapeHtml(state)}</span>
          ${auditStatus}
          <button type="button" class="board-card-copy card-copy-btn" data-id="${escapeHtml(t.id)}" title="复制任务块" aria-label="复制任务块">
            <span class="card-copy-ico" aria-hidden="true">⧉</span>
          </button>
        </div>
      </div>
      <div class="board-card-title ti" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;line-height:1.35;min-height:2.7em;" title="${escapeHtml(t.title || t.id)}">${escapeHtml(t.title || t.id)}</div>
      ${metricsBlock}
      ${streamHtml}
      <div class="board-card-meta">
        ${executor}
        ${rejectHtml}
      </div>
      ${updatedHtml ? `<div class="board-card-foot">${updatedHtml}</div>` : ''}
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
