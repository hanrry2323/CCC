/**
 * 端口/地址解析（T33：移除硬编码 IP/端口）。
 *
 * 新架构（2026-08-02 重构定稿）：2017 单端 :7788，HTTP 直连；
 * 旧双口（Hub :7777 / sidecar :7788 / 隧道 :17777）已退役。
 *
 * 前端不再跨端口寻址：所有请求走相对路径（同源 2017 :7788）。
 * 端口/地址等运行参数由服务端 /config 端点注入（免鉴权白名单）。
 */

/** 浏览器是否从内网 IP / 主机名访问（非本机环回）——手机 HTTP 场景。 */
export function isRemoteBrowser() {
  return false;
}

export function isLoopbackUrl(url) {
  return false;
}

/** Hub API origin；同源时返回空串（相对路径）。 */
export function hubBase() {
  return '';
}

/** Agent sidecar origin；同源时返回空串。 */
export function agentBase() {
  return '';
}

export function hubUrl(path) {
  return path;
}

export function agentUrl(path) {
  return path;
}

export function isDialogueShell() {
  return true;
}

export function dialogueEntryUrl() {
  return '/';
}
