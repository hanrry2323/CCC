/**
 * roadmapTimeline.js — SVG 时间线渲染器（2026-08-12 线路图图形化）
 *
 * 从单项目线路图数据（/board/roadmap/<project>）渲染 SVG 时间线：
 * - X 轴 = 时间（里程碑按日期定位）
 * - 节点 = 里程碑（圆点 + 标题 + 日期）
 * - 状态着色：已完成绿 / 进行中蓝 / 待开发灰
 * - 下方卡分组列表（已完成/进行中/待开发）+ 风险提示
 */

export const CARD_TONE = {
  done: '#3d9a5f',
  doing: '#3a7bd5',
  planned: '#8a8a8a',
  risk: '#c44',
};

export function buildTimelineSVG(detail, width = 900, height = 320) {
  const miles = (detail.milestones || []).filter((m) => m.date);
  const pad = 60;
  const top = 40;
  const bottom = height - 50;
  // 日期范围
  const dates = miles.map((m) => new Date(m.date).getTime());
  let min = dates.length ? Math.min(...dates) : Date.now() - 30 * 86400e3;
  let max = dates.length ? Math.max(...dates) : Date.now();
  if (max - min < 86400e3 * 7) {
    // 至少 7 天跨度
    const mid = (min + max) / 2;
    min = mid - 86400e3 * 4;
    max = mid + 86400e3 * 4;
  }
  const xOf = (ts) => pad + ((ts - min) / (max - min || 1)) * (width - pad * 2);

  // 节点（有日期的里程碑）
  const nodes = miles.map((m, i) => {
    const cards = m.cards || [];
    const done = cards.filter((c) => c.progress && /已交付|已关闭|已完成/.test(c.progress)).length;
    const planned = cards.filter((c) => c.progress && /待分派|未合入|⚠️|规划/.test(c.progress)).length;
    const x = xOf(new Date(m.date).getTime());
    const y = top + (i % 2 === 0 ? 0 : 40); // 上下错开
    const tone = done === cards.length && cards.length > 0 ? CARD_TONE.done : planned > 0 ? CARD_TONE.planned : CARD_TONE.doing;
    const srcIdx = detail.milestones.indexOf(m);
    return { ...m, x, y, done, planned, tone, hasCards: cards.length > 0, idx: srcIdx };
  });

  // 连接线
  const linePath = nodes.length > 1
    ? nodes.map((n, i) => (i === 0 ? `M ${n.x} ${top}` : `L ${n.x} ${n.y}`)).join(' ')
    : '';

  const nodeEls = nodes.map((n) => `
    <g class="rm-node" data-idx="${n.idx}" role="button" tabindex="0" aria-label="里程碑 ${esc(n.title)}">
      <title>${esc(n.title)} · ${esc(n.date)} · 完成 ${n.done}/${n.cards.length}</title>
      <circle cx="${n.x}" cy="${n.y}" r="${n.hasCards ? 7 : 4}" fill="${n.tone}"/>
      <text x="${n.x}" y="${n.y - 16}" text-anchor="middle" class="rm-node-title">${esc(n.title.slice(0, 22))}</text>
      <text x="${n.x}" y="${n.y + 22}" text-anchor="middle" class="rm-node-date">${n.date}${n.hasCards ? ` · ${n.done}/${n.cards.length}` : ''}</text>
    </g>`).join('');

  return `<svg class="rm-svg" viewBox="0 0 ${width} ${height}" width="100%">
    <line x1="${pad}" y1="${top}" x2="${width - pad}" y2="${top}" stroke="#555" stroke-width="2"/>
    ${linePath ? `<path d="${linePath}" fill="none" stroke="#666" stroke-width="1.5" stroke-dasharray="4,4"/>` : ''}
    ${nodeEls}
    <text x="${pad}" y="${height - 10}" class="rm-axis-label">时间 →</text>
    ${nodes.length === 0 ? `<text x="${width / 2}" y="${height / 2}" text-anchor="middle" class="rm-empty">无日期里程碑</text>` : ''}
  </svg>`;

  function esc(s) {
    if (s == null) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
}

export function cardListHTML(detail) {
  const groups = detail.groups || {};
  const rows = (label, key, tone, icon) => {
    const cards = groups[key] || [];
    if (!cards.length) return '';
    return `<div class="rm-group">
      <div class="rm-group-head"><span class="rm-dot" style="background:${tone}"></span><strong>${label}（${cards.length}）</strong></div>
      <div class="rm-group-cards">${cards.map((c) => `
        <div class="rm-card-chip">
          <span class="rm-card-id">${esc(c.card_id)}</span>
          <span class="rm-card-intent">${esc(c.intent)}</span>
          ${c.drift ? `<span class="rm-flag drift">漂移</span>` : ''}
          ${c.missing ? `<span class="rm-flag missing">缺失</span>` : ''}
          ${(c.drift || c.missing) ? `<a class="rm-goto" href="#/board" title="去看板处理">→</a>` : ''}
        </div>`).join('')}
      </div>
    </div>`;
  };
  return `<div class="rm-groups">
    ${rows('已完成', 'done', CARD_TONE.done)}
    ${rows('进行中', 'doing', CARD_TONE.doing)}
    ${rows('待开发', 'planned', CARD_TONE.planned)}
  </div>`;
}

export function riskHTML(detail) {
  const risks = detail.risks || [];
  if (!risks.length) return '';
  return `<div class="rm-risk">
    <strong class="rm-risk-title">⚠ 风险提示（${risks.length}）</strong>
    <div class="rm-risk-grid">
      ${risks.map((r) => `<div class="rm-risk-card ${r.type === 'missing' ? 'missing' : 'drift'}">
        <span class="rm-risk-type">${r.type === 'missing' ? '缺失' : '漂移'}</span>
        <span class="rm-risk-body">${esc(r.card_id)} — ${esc(r.detail)}</span>
      </div>`).join('')}
    </div>
  </div>`;
}

export function unplannedMilestonesHTML(detail) {
  const noDate = (detail.milestones || []).filter((m) => !m.date);
  if (!noDate.length) return '';
  return `<div class="rm-unplanned">
    <strong>未排期里程碑（${noDate.length}）</strong>
    <div class="rm-unplanned-list">${noDate.map((m) =>
      `<span class="rm-unplanned-item">${esc(m.title)}${m.cards && m.cards.length ? ` · ${m.cards.length} 卡` : ''}</span>`
    ).join('')}</div>
  </div>`;
}

/* ══ v2：线路图二级页完全重构（2026-08-12 老板指令）══
 * 布局：顶部总览条 → 左垂直里程碑时间线 + 右卡面板 → 底部风险。
 * 不再使用全宽 SVG 大图。 */

function _closed(s) {
  return /已交付|已关闭|已完成|已合入|released|closed|delivered/.test(s || '');
}

function _stateTone(c) {
  const s = c.real_state || c.progress || '';
  if (_closed(s)) return 'done';
  if (/已回写|执行中|开发中|机审|待验收|testing|verified|in_progress/.test(s)) return 'doing';
  return 'planned';
}

function _mileTone(m) {
  const cards = m.cards || [];
  if (!cards.length) return 'none';
  if (cards.every((c) => _closed(c.progress))) return 'done';
  if (cards.some((c) => c.drift || c.missing)) return 'risk';
  return 'doing';
}

export function buildTimelineOverview(detail) {
  const c = detail.counts || {};
  const cards = (detail.milestones || []).reduce((n, m) => n + (m.cards || []).length, 0);
  const riskN = (detail.risks || []).length;
  const pct = cards ? Math.round(((c.done || 0) / cards) * 100) : 0;
  return `<div class="rm2-overview">
    <div class="rm2-name">${esc(detail.project)}<span>线路图</span></div>
    <div class="rm2-stats">
      <span class="rm2-stat"><b>${cards}</b>总卡</span>
      <span class="rm2-stat done"><b>${c.done || 0}</b>已完成</span>
      <span class="rm2-stat doing"><b>${c.doing || 0}</b>进行中</span>
      <span class="rm2-stat planned"><b>${c.planned || 0}</b>待开发</span>
      ${riskN ? `<span class="rm2-stat risk"><b>${riskN}</b>风险</span>` : ''}
    </div>
    <div class="rm2-progress"><div class="rm2-progress-fill" style="width:${pct}%"></div></div>
  </div>`;
}

export function buildMilestoneRail(detail) {
  const miles = detail.milestones || [];
  const dated = miles.filter((m) => m.date);
  const undated = miles.filter((m) => !m.date);
  const item = (m) => `<button type="button" class="rm2-mile" data-idx="${detail.milestones.indexOf(m)}">
    <span class="rm2-mile-dot ${_mileTone(m)}"></span>
    <span class="rm2-mile-body">
      <span class="rm2-mile-title">${esc(m.title)}</span>
      <span class="rm2-mile-meta">${m.date ? esc(m.date) : '未排期'} · ${(m.cards || []).length} 卡</span>
    </span>
  </button>`;
  return `<div class="rm2-rail">
    <div class="rm2-rail-line" aria-hidden="true"></div>
    ${dated.map(item).join('')}
    ${undated.length ? `<div class="rm2-undated">未排期</div>${undated.map(item).join('')}` : ''}
  </div>`;
}

export function milestonePanelHTML(detail, mile) {
  const cards = (mile && mile.cards) || [];
  return `<div class="rm2-panel">
    <div class="rm2-panel-head">
      <h4>${esc(mile ? mile.title : '未选择里程碑')}</h4>
      ${mile && mile.date ? `<span class="rm2-panel-date">${esc(mile.date)}</span>` : ''}
      <span class="rm2-panel-count">${cards.length} 卡</span>
    </div>
    ${cards.length
      ? `<div class="rm2-cards">${cards.map((c) => `
        <div class="rm2-card">
          <span class="rm2-card-id">${esc(c.card_id)}</span>
          <span class="rm2-card-intent">${esc(c.intent)}</span>
          <span class="rm2-card-state ${_stateTone(c)}">${esc(c.progress || '未标注')}</span>
          ${c.drift ? `<span class="rm-flag drift">漂移</span>` : ''}
          ${c.missing ? `<span class="rm-flag missing">缺失</span>` : ''}
          ${(c.drift || c.missing) ? `<a class="rm-goto" href="#/board" title="去看板">→</a>` : ''}
        </div>`).join('')}</div>`
      : '<div class="rm2-empty">该里程碑暂无关联卡</div>'}
  </div>`;
}

export function esc(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}
