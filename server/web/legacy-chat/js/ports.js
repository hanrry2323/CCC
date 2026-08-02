/**
 * Dual-port bases（与 Desktop 同构）：
 *   Desktop / 本机默认 Hub = 127.0.0.1:17777（隧道 · 硬共识）
 *   手机/内网 SPA 旁路 = LAN :7777（排障 · 非 Desktop 默认）
 *   Agent = M1 sidecar :7788
 * 见 docs/product/hub-remote-management.md · hub-ssh-tunnel.md
 */

/** @deprecated 旧对话页不再跨端口寻址，保留仅为兼容引用 */
const DEFAULT_HUB_LAN = 'http://192.168.3.116:7777';
/** @deprecated 旧对话页不再跨端口寻址，保留仅为兼容引用 */
const DEFAULT_HUB_LOCAL = 'http://127.0.0.1:17777';
/** @deprecated 旧对话页不再跨端口寻址，保留仅为兼容引用 */
const DEFAULT_AGENT = 'http://192.168.3.140:7788';

/** 浏览器是否从内网 IP / 主机名访问（非本机环回）——手机 HTTP 场景。 */
export function isRemoteBrowser() {
  return false;
}

export function isLoopbackUrl(url) {
  return false;
}

/** Hub API origin；同机 Hub SPA 时返回空串（相对路径）。 */
export function hubBase() {
  return '';
}

/** Agent sidecar origin；同机对话 SPA（:7788）时返回空串。 */
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

export { DEFAULT_HUB_LAN, DEFAULT_HUB_LOCAL, DEFAULT_AGENT };