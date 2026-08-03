/**
 * Engine 指示灯 + 手动启停（对话标题栏 / 看板工具栏共用）
 *
 * T30：新服务端（server/web/server.py）不提供 /api/runtime-status / /api/engine/*
 * 端点；本组件统一改为 no-op，避免页面误显「Engine 断开 / 启动」按钮误导用户。
 * Engine 状态请用桌面端或运维页 /ops/summary（集群节点 + 服务运行态）查看。
 */

let _last = { running: false, allowed: false, mode: '?', git: {}, counts: {} };

export function engineControlHtml(_idPrefix = 'eng') {
  // 不再渲染 engine 控件（新协议无对应端点）
  return '';
}

export async function refreshEngineControl() {
  // 新服务端无 engine 状态端点；保持默认值，不发请求
  return null;
}

export function mountEngineControlInTitlebar() {
  // no-op（新协议）
}

export function mountEngineControlInBoard(_toolbarActions) {
  // no-op（新协议）
}

export function initEngineControl() {
  // no-op（新协议）
}

export function getLastEngineStatus() {
  return _last;
}
