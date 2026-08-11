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
    return { ...m, x, y, done, planned, tone, hasCards: cards.length > 0 };
  });

  // 连接线
  const linePath = nodes.length > 1
    ? nodes.map((n, i) => (i === 0 ? `M ${n.x} ${top}` : `L ${n.x} ${n.y}`)).join(' ')
    : '';

  const nodeEls = nodes.map((n) => `
    <g class="rm-node">
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
        </div>`).join('')}
      </div>
    </div>`;
  };
  return `${rows('已完成', 'done', CARD_TONE.done)}
          ${rows('进行中', 'doing', CARD_TONE.doing)}
          ${rows('待开发', 'planned', CARD_TONE.planned)}`;
}

export function riskHTML(detail) {
  const risks = detail.risks || [];
  if (!risks.length) return '';
  return `<div class="rm-risk">
    <strong class="rm-risk-title">⚠ 风险提示（${risks.length}）</strong>
    ${risks.map((r) => `<div class="rm-risk-item">[${r.type}] ${esc(r.card_id)} — ${esc(r.detail)}</div>`).join('')}
  </div>`;
}

export function esc(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}
