export function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
  return String(text).replace(/[&<>"]/g, c => map[c]);
}

export function ts() {
  const d = new Date();
  return String(d.getHours()).padStart(2, '0') + ':' +
         String(d.getMinutes()).padStart(2, '0');
}

export function scrollToBottom(el) {
  if (el) el.scrollTop = el.scrollHeight;
}

export function generateId() {
  if (crypto.randomUUID) return crypto.randomUUID();
  return Date.now().toString(36) + Math.random().toString(36).slice(2);
}

/** Desktop 同款 thread id：`{project}::main` 或 `{project}::{uuid}` */
export function desktopThreadId(projectId, suffix) {
  const pid = (projectId || 'ccc').trim() || 'ccc';
  let s = String(suffix || '').trim();
  if (s.startsWith('hub::')) {
    // 纠偏：剥掉错误前缀
    s = s.slice(5);
    if (s.startsWith(pid + '::')) s = s.slice(pid.length + 2);
  }
  if (s.includes('::')) return s;
  if (!s || s === 'main') return `${pid}::main`;
  return `${pid}::${s}`;
}

/** M1 本机 project_path（对话口 → sidecar）
 * 对齐 Desktop：业务仓无本机第二树时回落平台仓；勿臆造 apps/<id>。
 */
export function resolveProjectPath(projectId) {
  const pid = projectId || 'ccc';
  const cccHome = '/Users/apple/program/CCC';
  const map =
    (typeof window !== 'undefined' && window.__CCC_WORKSPACE_MAP__) ||
    {};
  if (map[pid]) return map[pid];
  try {
    const local = JSON.parse(
      localStorage.getItem('ccc_local_workspace_map') || '{}'
    );
    if (local[pid]) return local[pid];
  } catch (_) {}
  return cccHome;
}

export function relativeTime(iso) {
  if (!iso) return '';
  const raw = String(iso).trim();
  // Accept "2026-07-18T14:32:00+08:00" or space-separated
  const d = new Date(raw.includes('T') ? raw : raw.replace(' ', 'T'));
  if (Number.isNaN(d.getTime())) return raw.slice(0, 16);
  const now = new Date();
  const diffMs = now - d;
  const pad = (n) => String(n).padStart(2, '0');
  const hm = pad(d.getHours()) + ':' + pad(d.getMinutes());
  const dayMs = 86400000;
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startThat = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const dayDiff = Math.round((startToday - startThat) / dayMs);
  if (dayDiff === 0) return '今天 ' + hm;
  if (dayDiff === 1) return '昨天 ' + hm;
  if (dayDiff > 1 && dayDiff < 7) return dayDiff + '天前';
  return (
    d.getFullYear() +
    '-' +
    pad(d.getMonth() + 1) +
    '-' +
    pad(d.getDate()) +
    ' ' +
    hm
  );
}

export function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}
