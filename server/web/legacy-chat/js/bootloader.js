/**
 * T68: critical ES-module boot with retry + degradable banner.
 *
 * Trade-off (see T68 writeback):
 *   ES module failures stick in the browser module map, so same-page
 *   `import()` retries of `./state.js` are unreliable. We keep the happy
 *   path identical to a bare `<script type="module" src=app.js>` (no
 *   prefetch), and on failure use sessionStorage + short exponential
 *   backoff full reload (clears the module map). After MAX_ATTEMPTS,
 *   show a clickable banner instead of a silent white screen.
 */
(function () {
  var VERSION = '20260809t10';
  var STORAGE_KEY = 'ccc-resource-boot-fails';
  var MAX_ATTEMPTS = 3;
  var BASE_DELAY_MS = 400;
  var PREFETCH_TRIES = 3;
  var APP_SRC = '/js/app.js?v=' + VERSION;
  var CRITICAL = [
    '/js/state.js?v=' + VERSION,
    '/js/app.js?v=' + VERSION,
  ];

  var settled = false;
  var bootListening = true;

  function failCount() {
    // P0 加固：sessionStorage 在无痕模式/禁用存储下会抛 SecurityError，
    // 必须包裹 try-catch 平滑降级，否则守护代码反而引发永久白屏。
    var raw;
    try {
      raw = sessionStorage.getItem(STORAGE_KEY) || '0';
    } catch (_) {
      return 0;
    }
    var n = parseInt(raw, 10);
    return isNaN(n) || n < 0 ? 0 : n;
  }

  function setFailCount(n) {
    try {
      sessionStorage.setItem(STORAGE_KEY, String(n));
    } catch (_) { /* 存储被禁用时静默降级：本次会话不持久化计数 */ }
  }

  function clearFailCount() {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch (_) { /* ignore */ }
  }

  function showBanner() {
    if (document.getElementById('ccc-resource-fail-banner')) return;
    var bar = document.createElement('button');
    bar.id = 'ccc-resource-fail-banner';
    bar.type = 'button';
    bar.className = 'ccc-resource-fail-banner';
    bar.setAttribute('role', 'alert');
    bar.textContent = '资源加载失败，点击重试';
    bar.addEventListener('click', function () {
      clearFailCount();
      location.reload();
    });
    var nav = document.getElementById('hub-nav');
    if (nav && nav.parentNode) {
      nav.parentNode.insertBefore(bar, nav.nextSibling);
    } else {
      document.body.insertBefore(bar, document.body.firstChild);
    }
  }

  function scheduleReload(attemptIndex) {
    var delay = BASE_DELAY_MS * Math.pow(2, attemptIndex);
    setTimeout(function () {
      location.reload();
    }, delay);
  }

  function onBootFailure() {
    if (settled) return;
    settled = true;
    bootListening = false;
    var used = failCount();
    var next = used + 1;
    if (next >= MAX_ATTEMPTS) {
      setFailCount(next);
      showBanner();
      return;
    }
    setFailCount(next);
    scheduleReload(used);
  }

  function onBootSuccess() {
    if (settled) return;
    settled = true;
    bootListening = false;
    clearFailCount();
  }

  function sleep(ms) {
    return new Promise(function (resolve) {
      setTimeout(resolve, ms);
    });
  }

  function fetchOk(url) {
    return fetch(url, { cache: 'no-store', credentials: 'same-origin' }).then(
      function (res) {
        if (!res.ok) throw new Error('http ' + res.status);
        return res.text();
      }
    );
  }

  function prefetchCritical() {
    var chain = Promise.resolve();
    CRITICAL.forEach(function (url) {
      chain = chain.then(function () {
        var attempt = 0;
        function tryOnce() {
          return fetchOk(url).catch(function (err) {
            attempt += 1;
            if (attempt >= PREFETCH_TRIES) throw err;
            return sleep(BASE_DELAY_MS * Math.pow(2, attempt - 1)).then(tryOnce);
          });
        }
        return tryOnce();
      });
    });
    return chain;
  }

  function injectApp() {
    var s = document.createElement('script');
    s.type = 'module';
    s.src = APP_SRC;
    s.dataset.cccBoot = '1';
    s.addEventListener('load', onBootSuccess);
    s.addEventListener('error', onBootFailure);
    document.body.appendChild(s);
  }

  // Backup: some browsers surface dependency fetch failures as window errors
  // rather than script.onerror. Only armed during boot.
  window.addEventListener(
    'error',
    function (ev) {
      if (!bootListening || settled) return;
      var t = ev && ev.target;
      if (t && t.tagName === 'SCRIPT' && t.dataset && t.dataset.cccBoot === '1') {
        onBootFailure();
        return;
      }
      var file = String((ev && ev.filename) || '');
      var msg = String((ev && ev.message) || '');
      if (
        /\bjs\/(?:state|app)\.js/i.test(file) ||
        /Failed to (load|fetch) module|error loading dynamically imported module|Load failed/i.test(
          msg
        )
      ) {
        onBootFailure();
      }
    },
    true
  );

  var used = failCount();
  if (used >= MAX_ATTEMPTS) {
    showBanner();
    return;
  }

  // Retry visits: prefetch critical files before re-entering the module map.
  if (used > 0 && typeof fetch === 'function') {
    prefetchCritical().then(injectApp).catch(onBootFailure);
    return;
  }

  injectApp();
})();
