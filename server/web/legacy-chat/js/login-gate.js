/**
 * login-gate.js — T40 早期登录门绑定（经典脚本，非模块）。
 *
 * 在 index.html 中通过 <script src> 加载，确保在 app.js 模块之前执行。
 * 不依赖任何 ES Module 导入；成功登录后刷新页面让 app.js 接管。
 * 401 重登由 agentAuth.js 处理（initAgentAuth 检测 data-early-bound 跳过重复绑定）。
 */
(function () {
  var TOKEN_KEY = 'ccc_chat_token';

  function getToken() {
    try { return localStorage.getItem(TOKEN_KEY) || ''; } catch (_) { return ''; }
  }
  function setToken(t) {
    try { localStorage.setItem(TOKEN_KEY, t || ''); } catch (_) {}
  }
  function clearToken() {
    try { localStorage.removeItem(TOKEN_KEY); } catch (_) {}
  }
  function showLoginView(hint) {
    var view = document.getElementById('login-view');
    if (view) { view.hidden = false; view.classList.add('open'); }
    var err = document.getElementById('login-error');
    if (err && hint) err.textContent = hint;
  }
  function hideLoginView() {
    var view = document.getElementById('login-view');
    if (view) { view.hidden = true; view.classList.remove('open'); }
  }

  function bindForm() {
    var view = document.getElementById('login-view');
    if (!view) return;
    var form = view.querySelector('form');
    if (!form || form.dataset.earlyBound === 'true') return;
    form.dataset.earlyBound = 'true';

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var userEl = view.querySelector('#login-user');
      var passEl = view.querySelector('#login-pass');
      var errEl = view.querySelector('#login-error');
      var btn = view.querySelector('#login-btn');
      var user = (userEl && userEl.value) || '';
      var pass = (passEl && passEl.value) || '';
      if (btn) btn.disabled = true;
      if (errEl) errEl.textContent = '';
      if (!user || !pass) {
        if (errEl) errEl.textContent = '请填写账号和密码';
        if (btn) btn.disabled = false;
        return;
      }
      fetch('/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: user, password: pass })
      }).then(function (resp) {
        return resp.json().then(function (data) {
          if (!resp.ok) {
            var msg = resp.status === 401 ? '账号或密码错误' :
                      (data.detail || data.error || ('登录失败: HTTP ' + resp.status));
            throw new Error(msg);
          }
          if (!data.token) throw new Error('登录成功但未返回 token');
          setToken(data.token);
          // T44：登录后直达对话视图（不再停留看板）
          if ((location.hash || '').indexOf('#/chat') !== 0) {
            location.hash = '#/chat';
          }
          hideLoginView();
          location.reload();
        });
      }).catch(function (err) {
        if (errEl) errEl.textContent = (err && err.message) || '登录失败';
        if (btn) btn.disabled = false;
      });
    });
  }

  function checkAuth() {
    fetch('/health').then(function (r) { return r.json(); }).then(function (h) {
      if (!h || !h.auth_required) {
        hideLoginView();
        return;
      }
      if (h.auth_configured === false) {
        showLoginView('服务端未配置登录凭证，请联系管理员配置后重试');
        return;
      }
      var tok = getToken();
      if (!tok) {
        showLoginView('');
        return;
      }
      fetch('/board/states', { headers: { Authorization: 'Bearer ' + tok } })
        .then(function (r) {
          if (r.ok) {
            hideLoginView();
          } else {
            clearToken();
            showLoginView('会话已失效，请重新登录');
          }
        })
        .catch(function () {
          hideLoginView();
        });
    }).catch(function () {
      hideLoginView();
    });
  }

  function run() {
    bindForm();
    checkAuth();
    window.__CCC_LOGIN_EARLY_BOUND__ = true;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }
})();
