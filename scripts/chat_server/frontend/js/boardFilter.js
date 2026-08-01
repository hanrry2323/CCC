/**
 * boardFilter — 看板筛选/排序纯函数（无 DOM 依赖，可 node 单测）。
 *
 * 后端 /api/board 只支持 workspace/fields/include_hidden，不做关键词/状态/排序，
 * 因此筛选与排序在前端 client-side 作用在已拉取的 columns 上。
 */

import { normalizeEpicSplitStatus } from './epicLifecycle.js';

/** 关键词命中：id/title/parent_id/description 小写子串；空关键词 → 全过。 */
export function matchesKeyword(task, kw) {
  const q = String(kw == null ? '' : kw).trim().toLowerCase();
  if (!q) return true;
  if (!task) return false;
  const hay = [task.id, task.title, task.parent_id, task.description]
    .map((s) => (s == null ? '' : String(s).toLowerCase()))
    .join(' ');
  return hay.includes(q);
}

/** 待办大卡拆分状态筛选：status 空 → 全部；否则按归一化 split_status 精确匹配。 */
export function filterEpicsBySplit(tasks, status) {
  if (!Array.isArray(tasks)) return [];
  const st = String(status || '').trim();
  if (!st) return tasks;
  return tasks.filter((t) => normalizeEpicSplitStatus(t && t.split_status) === st);
}

function _cmpId(a, b) {
  return String(a.id || '').localeCompare(String(b.id || ''));
}

function _cmpCreated(a, b) {
  return String(a.created_at || '').localeCompare(String(b.created_at || '')) || _cmpId(a, b);
}

/** 流转列排序（非变异）：default=(created_at,id) 升序；updated=updated_at 降序；title=中文标题。 */
export function sortTasks(tasks, key) {
  if (!Array.isArray(tasks)) return [];
  const arr = tasks.slice();
  const k = String(key || 'default').trim() || 'default';
  if (k === 'updated') {
    arr.sort(
      (a, b) =>
        String(b.updated_at || '').localeCompare(String(a.updated_at || '')) || _cmpId(a, b)
    );
  } else if (k === 'title') {
    arr.sort(
      (a, b) => String(a.title || '').localeCompare(String(b.title || ''), 'zh') || _cmpId(a, b)
    );
  } else {
    arr.sort(_cmpCreated);
  }
  return arr;
}
