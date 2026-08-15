/**
 * roadmapTimeline.js — SVG 时间线渲染器（2026-08-12 线路图图形化）
 *
 * 从单项目线路图数据（/board/roadmap/<project>）渲染 SVG 时间线：
 * - X 轴 = 时间（里程碑按日期定位）
 * - 节点 = 里程碑（圆点 + 标题 + 日期）
 * - 状态着色：已完成绿 / 进行中蓝 / 待开发灰
 * - 下方卡分组列表（已完成/进行中/待开发）+ 风险提示
 */

// esc 收敛（2026-08-15 前端架构重构 P0-3）：原本地实现与 utils.escapeHtml 语义等价，
// 统一 re-export 共享原语 ui.js，本文件不再自维护。
export { esc } from './ui.js';

