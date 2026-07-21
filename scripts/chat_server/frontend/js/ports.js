/**
 * Dual-port bases（与 Desktop 同构）：
 *   Agent = M1 sidecar :7788
 *   Hub   = Mac2017 :7777
 * 见 docs/product/hub-remote-management.md
 */

const DEFAULT_HUB = 'http://192.168.3.116:7777';
const DEFAULT_AGENT = 'http://192.168.3.140:7788';

function _strip(u) {
  return String(u || '').replace(/\/$/, '');
}

/** Hub API origin；同机 Hub SPA 时返回空串（相对路径）。 */
export function hubBase() {
  if (typeof window !== 'undefined' && window.__CCC_HUB_BASE__ != null) {
    return _strip(window.__CCC_HUB_BASE__);
  }
  try {
    const ls = localStorage.getItem('ccc_hub_base');
    if (ls != null && ls !== '') return _strip(ls);
  } catch (_) {}
  const port = String(location.port || '');
  if (port === '7777' || port === '8084') return '';
  return DEFAULT_HUB;
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
