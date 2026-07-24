/**
 * Dual-port bases（与 Desktop 同构）：
 *   Desktop / 本机默认 Hub = 127.0.0.1:17777（隧道 · 硬共识）
 *   手机/内网 SPA 旁路 = LAN :7777（排障 · 非 Desktop 默认）
 *   Agent = M1 sidecar :7788
 * 见 docs/product/hub-remote-management.md · hub-ssh-tunnel.md
 */

/** 排障·手机/内网 SPA 旁路（非 Desktop 默认） */
const DEFAULT_HUB_LAN = 'http://192.168.3.116:7777';
/** Desktop / sidecar 默认 = 本机隧道 */
const DEFAULT_HUB_LOCAL = 'http://127.0.0.1:17777';
const DEFAULT_AGENT = 'http://192.168.3.140:7788';

function _strip(u) {
  return String(u || '').replace(/\/$/, '');
}

/** 浏览器是否从内网 IP / 主机名访问（非本机环回）——手机 HTTP 场景。 */
export function isRemoteBrowser() {
  if (typeof location === 'undefined') return false;
  const h = String(location.hostname || '');
  if (!h) return false;
  if (h === 'localhost' || h === '127.0.0.1' || h === '::1') return false;
  return true;
}

export function isLoopbackUrl(url) {
  try {
    const u = new URL(String(url || ''));
    return (
      u.hostname === '127.0.0.1' ||
      u.hostname === 'localhost' ||
      u.hostname === '::1'
    );
  } catch (_) {
    return /127\.0\.0\.1|localhost/.test(String(url || ''));
  }
}

function _lanHubCandidate() {
  if (typeof window !== 'undefined' && window.__CCC_HUB_BASE_LAN__) {
    return _strip(window.__CCC_HUB_BASE_LAN__);
  }
  return DEFAULT_HUB_LAN;
}

/** Hub API origin；同机 Hub SPA 时返回空串（相对路径）。 */
export function hubBase() {
  if (typeof window !== 'undefined' && window.__CCC_HUB_BASE__ != null) {
    const forced = _strip(window.__CCC_HUB_BASE__);
    if (forced && isRemoteBrowser() && isLoopbackUrl(forced)) {
      return _lanHubCandidate();
    }
    return forced;
  }
  try {
    const ls = localStorage.getItem('ccc_hub_base');
    if (ls != null && ls !== '') {
      const stored = _strip(ls);
      if (isRemoteBrowser() && isLoopbackUrl(stored)) {
        return _lanHubCandidate();
      }
      return stored;
    }
  } catch (_) {}
  const port = String(location.port || '');
  if (port === '7777' || port === '8084') return '';
  if (isRemoteBrowser()) return _lanHubCandidate();
  return DEFAULT_HUB_LOCAL;
}

/** Agent sidecar origin；同机对话 SPA（:7788）时返回空串。 */
export function agentBase() {
  if (typeof window !== 'undefined' && window.__CCC_AGENT_BASE__ != null) {
    return _strip(window.__CCC_AGENT_BASE__);
  }
  try {
    const ls = localStorage.getItem('ccc_agent_base');
    if (ls != null && ls !== '') return _strip(ls);
  } catch (_) {}
  const port = String(location.port || '');
  if (port === '7788') return '';
  if (typeof window !== 'undefined' && window.__CCC_DESKTOP_AGENT_URL__) {
    return _strip(window.__CCC_DESKTOP_AGENT_URL__);
  }
  return DEFAULT_AGENT;
}

export function hubUrl(path) {
  const p = path.startsWith('/') ? path : '/' + path;
  const b = hubBase();
  return b ? b + p : p;
}

export function agentUrl(path) {
  const p = path.startsWith('/') ? path : '/' + path;
  const b = agentBase();
  return b ? b + p : p;
}

export function isDialogueShell() {
  if (typeof window !== 'undefined' && window.__CCC_SHELL__ === 'dialogue') {
    return true;
  }
  return String(location.port || '') === '7788';
}

export function dialogueEntryUrl() {
  if (typeof window !== 'undefined' && window.__CCC_DIALOGUE_URL__) {
    return _strip(window.__CCC_DIALOGUE_URL__) + '/';
  }
  const a = agentBase();
  return (a || DEFAULT_AGENT) + '/';
}

export { DEFAULT_HUB_LAN, DEFAULT_HUB_LOCAL, DEFAULT_AGENT };
