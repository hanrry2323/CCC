/**
 * chatErrors — 聊天错误文案与重试选择纯函数（无 DOM 依赖，可 node 单测）。
 *
 * friendlyChatError：HTTP 状态码/详情 → 友好中文文案（streamChat 原 inline 映射抽出）。
 * lastUserMessage：取最后一条 user 消息（错误气泡「重试」的目标）。
 */

/** 把 HTTP 状态码 + detail 映射为友好中文错误文案。 */
export function friendlyChatError(status, detail) {
  if (status === 401) {
    return '对话口鉴权已开启但未通过（默认已关；勿弹 Token）';
  }
  if (status === 403) {
    return detail || 'project_path 不被 sidecar 允许（检查 workspace map）';
  }
  if (status === 502 || status === 503) {
    return detail || 'M1 sidecar 不可达（检查 :7788）';
  }
  if (status === 429) {
    return '并发会话已满或会话忙，请稍候';
  }
  return detail || ('请求失败: HTTP ' + status);
}

/** 取最后一条 user 消息；无则返回 null。 */
export function lastUserMessage(msgs) {
  const list = Array.isArray(msgs) ? msgs : [];
  for (let i = list.length - 1; i >= 0; i--) {
    if (list[i] && list[i].role === 'user') return list[i];
  }
  return null;
}
