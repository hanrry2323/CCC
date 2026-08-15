/**
 * roadmapTimeline.js — SVG 时间线渲染器（2026-08-12 线路图图形化）
 *
 * 从单项目线路图数据（/board/roadmap/<project>）渲染 SVG 时间线：
 * - X 轴 = 时间（里程碑按日期定位）
 * - 节点 = 里程碑（圆点 + 标题 + 日期）
 * - 状态着色：已完成绿 / 进行中蓝 / 待开发灰
 * - 下方卡分组列表（已完成/进行中/待开发）+ 风险提示
 */

export function esc(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

