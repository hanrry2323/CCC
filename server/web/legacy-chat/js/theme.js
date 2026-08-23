/**
 * theme.js — 深/浅主题切换（T30 恢复）
 *
 * 三态循环：light → dark → system → light ...
 * - light：强制浅色（暖米色）
 * - dark：强制深色（暖灰）
 * - system：跟随系统 prefers-color-scheme
 *
 * 键：localStorage['ccc-theme']（值：'light' | 'dark' | 'system'）
 * HTML 根元素 data-theme 属性 = 当前实际主题；'system' 时按系统偏好映射。
 */

const THEME_KEY = 'ccc-theme';
const LEGACY_KEY = 'opencode-color-scheme';

const SYSTEM_DARK_MEDIA =
  typeof window !== 'undefined' && window.matchMedia
    ? window.matchMedia('(prefers-color-scheme: dark)')
    : null;

export function getThemeScheme() {
  // localStorage 在受限隐私环境会抛 SecurityError；init() 最早一步就调本函数，
  // 不兜底 = 白屏死站（theme-init.js 同一读取有 try/catch，此处补齐）
  try {
    const legacy = LEGACY_KEY && localStorage.getItem(LEGACY_KEY);
    const current = localStorage.getItem(THEME_KEY);
    if (!current && legacy) {
      localStorage.setItem(THEME_KEY, legacy);
      return legacy;
    }
    return current || 'system';
  } catch (_) {
    return 'system';
  }
}

function _resolveSystem() {
  return SYSTEM_DARK_MEDIA && SYSTEM_DARK_MEDIA.matches ? 'dark' : 'light';
}

export function applyTheme(scheme) {
  const s = scheme === 'light' || scheme === 'dark' ? scheme : 'system';
  const resolved = s === 'system' ? _resolveSystem() : s;
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', resolved);
    // 同时保留 'system' 标记用于 CSS 媒体查询（themes.css 用 [data-theme="system"]）
    document.documentElement.setAttribute('data-theme-scheme', s);
    // 'system' 模式下让 themes.css 的 :root[data-theme="system"] 生效
    if (s === 'system') {
      document.documentElement.setAttribute('data-theme', _resolveSystem());
      document.documentElement.setAttribute('data-theme-scheme', 'system');
    }
  }
  return resolved;
}

export function setThemeScheme(scheme) {
  const val = scheme === 'light' || scheme === 'dark' || scheme === 'system' ? scheme : 'system';
  try {
    localStorage.setItem(THEME_KEY, val);
    if (LEGACY_KEY) localStorage.removeItem(LEGACY_KEY);
  } catch (_) {}
  applyTheme(val);
  return val;
}

/** 三态循环：light → dark → system → light ... */
export function toggleLightDark() {
  const cur = getThemeScheme();
  const next = cur === 'light' ? 'dark' : cur === 'dark' ? 'system' : 'light';
  return setThemeScheme(next);
}

// 系统主题变化时，若当前为 'system' 模式则实时切换
if (SYSTEM_DARK_MEDIA) {
  SYSTEM_DARK_MEDIA.addEventListener('change', () => {
    if (getThemeScheme() === 'system') {
      applyTheme('system');
    }
  });
}
