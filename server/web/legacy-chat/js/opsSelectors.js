/**
 * opsSelectors — ops 页数据选择纯函数（无 DOM 依赖，可 node 单测）。
 *
 * 契约核对（窗口 A2）：后端 ops_summary 的 daily 只发 reports 键，
 * 兼容 items / reviews 旧键 → 统一走 dailyItems 选择。
 */

/** 日审报告条目：items（旧）→ reviews（旧）→ reports（后端现发）→ []。 */
export function dailyItems(d) {
  if (!d || typeof d !== 'object') return [];
  return d.items || d.reviews || d.reports || [];
}
