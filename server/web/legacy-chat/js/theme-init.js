// T30：恢复深/浅主题。启动前从 localStorage 读 saved scheme 并应用，避免 FOUC。
(function () {
  var saved = 'system';
  try {
    saved = localStorage.getItem('ccc-theme') || 'system';
    var legacy = localStorage.getItem('opencode-color-scheme');
    if (!localStorage.getItem('ccc-theme') && legacy) {
      saved = legacy;
      localStorage.setItem('ccc-theme', legacy);
    }
  } catch (_) {}
  var resolved = saved;
  if (saved === 'system') {
    resolved = (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
  }
  document.documentElement.setAttribute('data-theme', resolved);
  document.documentElement.setAttribute('data-theme-scheme', saved);
})();
