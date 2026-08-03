/**
 * chatErrors — 聊天错误文案与重试选择纯函数（无 DOM 依赖，可 node 单测）。
 *
 * humanizeBrainError：大脑 Agent 技术错误串 → 面向用户的中文文案（T45 人话化）。
 * friendlyChatError：HTTP 状态码/详情 → 友好中文文案（streamChat 原 inline 映射抽出）。
 * lastUserMessage：取最后一条 user 消息（错误气泡「重试」的目标）。
 */

/** 大脑技术错误串 → 人话（服务端错误码保留，前端翻译）。 */
export function humanizeBrainError(message) {
  const m = String(message || '');
  if (/not configured/i.test(m)) return '大脑服务未配置，请联系管理员';
  if (/busy/i.test(m)) return '大脑服务正忙，请稍后重试';
  if (/timeout/i.test(m)) return '大脑响应超时，请重试或换个模型档位';
  if (/brain failed/i.test(m)) return '大脑服务异常，请稍后重试';
  if (/empty content/i.test(m)) return '大脑未返回内容，请重试';
  return m;
}

/** 把 HTTP 状态码 + detail 映射为友好中文错误文案。 */
export function friendlyChatError(status, detail) {
  const d = String(detail || '');
  if (status === 401) {
    return '登录状态已失效，请刷新页面重新连接';
  }
  if (status === 403) {
    return d || '该项目路径不可用，请联系管理员';
  }
  if (status === 502 || status === 503) {
    if (/not configured/i.test(d)) return '大脑服务未配置，请联系管理员';
    if (/busy/i.test(d)) return '大脑服务正忙，请稍后重试';
    return d || '对话服务未就绪，请稍后重试';
  }
  if (status === 504) {
    return '大脑响应超时，请重试或换个模型档位';
  }
  if (status === 429) {
    return '并发会话已满或会话忙，请稍候';
  }
  return d || ('请求失败: HTTP ' + status);
}

/** 取最后一条 user 消息；无则返回 null。 */
export function lastUserMessage(msgs) {
  const list = Array.isArray(msgs) ? msgs : [];
  for (let i = list.length - 1; i >= 0; i--) {
    if (list[i] && list[i].role === 'user') return list[i];
  }
  return null;
}
