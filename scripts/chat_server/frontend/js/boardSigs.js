/**
 * boardSigs — 看板列 diff 签名纯函数（无 DOM 依赖，可 node 单测）。
 *
 * #/board 15s 轮询用 data-sig 判断列是否需重绘。
 * epic 列签名含 released 子卡计数 → 子卡进 released 列时 epic 列必重绘（进度条刷新）。
 */

/** 统计 epic 已发布子卡数：child_ids ∩ released 列 id 集合。 */
export function releasedChildCount(task, releasedIds) {
  const kids = task && Array.isArray(task.child_ids) ? task.child_ids : [];
  if (!kids.length) return 0;
  return kids.filter((id) => releasedIds.has(id)).length;
}

/**
 * epic 列签名：id + split_status + updated_at + released 子卡数。
 * releasedIds 为 Set（前端从 _state.columns.released 构造）。
 */
export function epicColumnSig(tasks, releasedIds) {
  return (tasks || [])
    .map(
      (t) =>
        (t && t.id ? t.id : '') +
        ':' +
        (t.split_status || '') +
        ':' +
        (t.updated_at || '') +
        ':' +
        releasedChildCount(t, releasedIds)
    )
    .join('|');
}
