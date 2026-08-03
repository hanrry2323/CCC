/**
 * Composer 上方：队列摘要 + 工作区改动提示（不含「最近失败」）
 *
 * T30：新服务端（server/web/server.py）不提供 /api/runtime-status 端点；
 * 本组件统一改为 no-op，避免无谓请求与误导性显示。
 * 队列摘要请用看板页（/board/states）查看；工作区改动请用桌面端。
 */

let _timer = null;

export async function refreshRuntimeStatus() {
  // 新协议无对应端点；保持静默
  return;
}

export function initRuntimeStatus() {
  // 不再起轮询（无对应端点）
  if (_timer) {
    clearInterval(_timer);
    _timer = null;
  }
}
