/** Epic split_status 五态中文标签（无 DOM 依赖，可单测） */

const EPIC_LIFECYCLE_LABELS = {
  pending: '未规划',
  planned: '已规划',
  running: '开发中',
  done: '已完成',
  failed: '失败',
  // 存量别名
  active: '开发中',
  blocked: '失败',
};

export function epicLifecycleLabel(ss) {
  return EPIC_LIFECYCLE_LABELS[ss] || EPIC_LIFECYCLE_LABELS.pending;
}

export function normalizeEpicSplitStatus(ss) {
  if (ss === 'active') return 'running';
  if (ss === 'blocked') return 'failed';
  if (['pending', 'planned', 'running', 'done', 'failed'].includes(ss)) return ss;
  return 'pending';
}
