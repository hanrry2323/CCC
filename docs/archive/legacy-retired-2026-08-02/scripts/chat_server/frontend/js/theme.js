/** Unified theme helpers — key: ccc-theme */

const THEME_KEY = 'ccc-theme';
const LEGACY_KEY = 'opencode-color-scheme';

export function getThemeScheme() {
  const legacy = localStorage.getItem(LEGACY_KEY);
  const current = localStorage.getItem(THEME_KEY);
  if (!current && legacy) {
    localStorage.setItem(THEME_KEY, legacy);
    return legacy;
  }
  return current || 'system';
}

export function setThemeScheme(scheme) {
  const val = scheme === 'light' || scheme === 'system' ? scheme : 'system';
  localStorage.setItem(THEME_KEY, val);
  localStorage.removeItem(LEGACY_KEY);
  applyTheme(val);
  return val;
}

export function applyTheme(scheme) {
  // 暗色模式已取消，始终使用 light 主题
  document.documentElement.setAttribute('data-theme', 'light');
}

export function toggleLightDark() {
  // 暗色模式已取消，始终为 light
  return setThemeScheme('light');
}
