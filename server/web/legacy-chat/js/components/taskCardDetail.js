import { escapeHtml } from './taskCard.js';

export function renderTaskCardDetail(t) {
  const phases = Array.isArray(t.phases) ? t.phases : [];
  const events = Array.isArray(t.events) ? t.events : [];

  const flowHtml = `
    <div class="board-detail-section">
      <div class="board-detail-h">状态流转</div>
      <div class="board-detail-flow">待分派 → 执行中 → 已回写 → 已关闭；打回 → 待分派（附问题清单）</div>
    </div>
  `;

  const noteHtml = t.note
    ? `<div class="board-detail-section">
         <div class="board-detail-h">描述</div>
         <div class="board-detail-note" style="white-space: pre-wrap; font-size: 11px; line-height: 1.5; color: var(--ccc-text-secondary);">${escapeHtml(t.note)}</div>
       </div>`
    : '<div class="board-detail-section"><div class="board-detail-h">描述</div><div class="board-detail-note" style="color: var(--ccc-text-faint); font-size: 11px;">(无描述)</div></div>';

  const acceptanceHtml = t.acceptance
    ? `<div class="board-detail-section">
         <div class="board-detail-h">验收标准</div>
         <div class="board-detail-acc" style="white-space: pre-wrap; font-size: 11px; line-height: 1.5; color: var(--ccc-text-secondary);">${escapeHtml(t.acceptance)}</div>
       </div>`
    : '';

  const phasesHtml = phases.length
    ? `<div class="board-detail-section">
         <div class="board-detail-h">阶段 / 回写</div>
         ${phases.map(p => `
           <div class="board-detail-phase" style="display: flex; align-items: center; justify-content: space-between; gap: 6px; font-size: 11px; padding: 3px 0; border-bottom: 1px dashed var(--ccc-border-subtle);">
             <span class="phase-name" style="font-weight: 500; color: var(--ccc-text-base);">${escapeHtml(p.name || '')}</span>
             <span class="phase-status st-${p.status || 'unknown'}" style="font-size: 10px; padding: 1px 6px; border-radius: 4px; background: var(--ccc-bg-layer); color: var(--ccc-text-muted);">${escapeHtml(p.status || '—')}</span>
             ${p.commit ? `<code class="phase-commit" style="font-family: var(--ccc-font-mono); font-size: 10px; color: var(--ccc-text-faint);">${escapeHtml(p.commit)}</code>` : ''}
           </div>
         `).join('')}
       </div>`
    : '';

  const eventsHtml = events.length
    ? `<div class="board-detail-section">
         <div class="board-detail-h">时间线</div>
         ${events.map(ev => `
           <div class="board-detail-event" style="font-size: 10px; color: var(--ccc-text-muted); padding: 3px 0; border-bottom: 1px dashed var(--ccc-border-subtle);">
             <span class="ev-ts" style="font-family: var(--ccc-font-mono); margin-right: 6px; color: var(--ccc-text-faint);">${escapeHtml(ev.ts || '')}</span>
             <span class="ev-role" style="font-weight: 600; margin-right: 6px; color: var(--ccc-text-muted);">@${escapeHtml(ev.role || 'system')}</span>
             <span class="ev-msg" style="color: var(--ccc-text-secondary);">${escapeHtml(ev.message || '')}</span>
           </div>
         `).join('')}
       </div>`
    : '';

  return `
    <div class="task-card-detail-unified" style="padding: 4px 0; border-top: 1px solid var(--ccc-border-subtle); margin-top: 8px;">
      ${flowHtml}
      ${noteHtml}
      ${acceptanceHtml}
      ${phasesHtml}
      ${eventsHtml}
    </div>
  `;
}
