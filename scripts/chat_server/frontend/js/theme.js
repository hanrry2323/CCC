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
  const val = scheme === 'light' || scheme === 'dark' || scheme === 'system' ? scheme : 'system';
  localStorage.setItem(THEME_KEY, val);
  localStorage.removeItem(LEGACY_KEY);
  applyTheme(val);
  return val;
}

export function applyTheme(scheme) {
  const resolved = scheme || getThemeScheme();
  const isDark =
    resolved === 'dark' ||
    (resolved === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
}

export function toggleLightDark() {
  const current = getThemeScheme();
  const next = current === 'dark' ? 'light' : 'dark';
  return setThemeScheme(next);
}
