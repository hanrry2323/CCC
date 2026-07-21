(function () {
  var saved = localStorage.getItem('ccc-theme') || localStorage.getItem('opencode-color-scheme');
  var theme = saved === 'light' || saved === 'dark' ? saved
    : (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  document.documentElement.setAttribute('data-theme', theme);
})();
