/**
 * agentAuth.js — 7788 对话口账号密码登录门（窗口 K）。
 *
 * 对话壳（:7788）登录门：POST /session 换 token（JSON body {username, password}），
 * 返回 {token, ttl_s, expires_at}；token 落 localStorage（键 ccc_chat_token）；
 * 401 → 清 token + 弹登录门引导重登。
 * 服务端未配置凭证 → 登录 503「未配置登录凭证」，前端据此给出明确提示（无默认弱口令）。
 *
 * T30：token 键统一为 `ccc_chat_token`，与 auth.js / api.js 共用同一键，
 * 保证登录后所有请求（对话/看板/运维）都带 Bearer。
 *
 * T40：index.html 内联早期脚本已绑定表单 + 探活；本模块负责 401 重登与登出。
 * initAgentAuth 检测 data-early-bound 标记，避免重复绑定。
 */

const AGENT_TOKEN_KEY = 'ccc_chat_token';

let _authResolvers = [];

function _resolvePending() {
  const pending = _authResolvers;
  _authResolvers = [];
  pending.forEach((r) => r());
}

// ── token 存取（localStorage）────────────────────────────

export function getAgentToken() {
  try {
    return localStorage.getItem(AGENT_TOKEN_KEY) || '';
  } catch (_) {
    return '';
  }
}

export function setAgentToken(token) {
  try {
    localStorage.setItem(AGENT_TOKEN_KEY, token || '');
  } catch (_) {}
}

export function clearAgentToken() {
  try {
    localStorage.removeItem(AGENT_TOKEN_KEY);
  } catch (_) {}
}

export function hasAgentToken() {
  return Boolean(getAgentToken());
}

/** Agent 请求头：Bearer 会话 token（无 token 返回空头）。 */
export function agentHeaders() {
  const tok = getAgentToken();
  return tok ? { Authorization: 'Bearer ' + tok } : {};
}

// ── 登录 / 登出 / 探活 ───────────────────────────────────

/** 登录：账号密码 → 会话 token。401 → 凭证错；503 → 未配置。 */
export async function agentLogin(user, pass) {
  const resp = await fetch('/session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: user || '', password: pass || '' }),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    if (resp.status === 401) throw new Error('账号或密码错误');
    if (resp.status === 503) {
      throw new Error(data.detail || '未配置登录凭证，请联系管理员配置服务端账号');
    }
    throw new Error(data.detail || ('登录失败: HTTP ' + resp.status));
  }
  if (!data.token) throw new Error('登录成功但未返回 token');
  setAgentToken(data.token);
  applyAgentRoleUI();
  _resolvePending();
  return data;
}

/** 登出：只清 localStorage，不再调后端。 */
export async function agentLogout() {
  clearAgentToken();
  applyAgentRoleUI();
}

/**
 * 探活：GET /board/states（带 Bearer token）。
 * T30：/health 是免鉴权端点，无法验证 token；改打最轻的鉴权端点 /board/states。
 * 200 → token 有效；401 → 清 token 返回 false（让登录门触发）。
 */
export async function probeAgentSession() {
  if (!hasAgentToken()) return false;
  try {
    const resp = await fetch('/board/states', {
      headers: agentHeaders(),
    });
    if (!resp.ok) {
      clearAgentToken();
      return false;
    }
    return true;
  } catch (_) {
    return false;
  }
}

// ── UI：登录视图（复用 A3 #login-view）───────────────────

function showLogin(hint) {
  const view = document.getElementById('login-view');
  if (view) {
    view.hidden = false;
    view.classList.add('open');
  }
  const errEl = document.getElementById('login-error');
  if (errEl && hint) errEl.textContent = hint;
}

function hideLogin() {
  const view = document.getElementById('login-view');
  if (view) {
    view.hidden = true;
    view.classList.remove('open');
  }
  const errEl = document.getElementById('login-error');
  if (errEl) errEl.textContent = '';
}

/** 对话壳登录态：nav 角色 chip + 登出按钮。 */
export function applyAgentRoleUI() {
  if (typeof document === 'undefined') return;
  const logged = hasAgentToken();
  const chip = document.getElementById('auth-role');
  if (chip) chip.textContent = logged ? '已登录' : '未登录';
  const logoutBtn = document.getElementById('auth-logout');
  if (logoutBtn) logoutBtn.style.display = logged ? '' : 'none';
}

/**
 * 初始化：改登录视图文案 + 绑表单/登出/401 事件。
 * T40：检测 data-early-bound 标记；内联脚本已绑表单时跳过重复绑定（仅补文案 + 401 + 登出）。
 * T44：登录文案按 /health 实际状态（auth_configured）显示，不再引用旧 sidecar 配置名；
 *      onAuthenticated 回调在登录成功后调用（app.js 用于导航到 #/chat）。
 */
export async function initAgentAuth({ onAuthenticated } = {}) {
  const title = document.getElementById('login-title');
  if (title) title.textContent = 'CCC 对话口登录';
  const hint = document.getElementById('login-hint');
  if (hint) {
    const notConfigured =
      '服务端未配置登录凭证（CCC_WEB_USERNAME / CCC_WEB_PASSWORD_HASH），请联系管理员。';
    const normal =
      '账号密码由服务端配置（CCC_WEB_USERNAME / CCC_WEB_PASSWORD_HASH）。';
    try {
      const r = await fetch('/health');
      const h = r.ok ? await r.json().catch(() => null) : null;
      hint.textContent = h && h.auth_configured === false ? notConfigured : normal;
    } catch (_) {
      hint.textContent = normal;
    }
  }
  const userInput = document.getElementById('login-user');
  if (userInput) userInput.placeholder = '账号';

  const view = document.getElementById('login-view');
  const form = view && view.querySelector('form');
  const alreadyBound = form && form.dataset.earlyBound === 'true';

  // T40：仅当内联脚本未绑表单时才绑定（避免双重提交）
  if (form && !alreadyBound) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const userEl = view.querySelector('#login-user');
      const passEl = view.querySelector('#login-pass');
      const errEl = view.querySelector('#login-error');
      const btn = view.querySelector('#login-btn');
      if (btn) btn.disabled = true;
      if (errEl) errEl.textContent = '';
      try {
        await agentLogin((userEl && userEl.value) || '', (passEl && passEl.value) || '');
        hideLogin();
        applyAgentRoleUI();
        if (onAuthenticated) onAuthenticated();
      } catch (err2) {
        if (errEl) errEl.textContent = err2 && err2.message ? err2.message : '登录失败';
      } finally {
        if (btn) btn.disabled = false;
      }
    });
  }
  const logoutBtn = document.getElementById('auth-logout');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      await agentLogout();
      showLogin();
    });
  }
  // T30：监听 api.js 401 派发的 ccc-auth-required（旧 ccc-agent-auth-required 保留兼容）
  document.addEventListener('ccc-auth-required', () => showLogin('会话已失效，请重新登录'));
  document.addEventListener('ccc-agent-auth-required', () => showLogin('会话已失效，请重新登录'));
  applyAgentRoleUI();
}

/**
 * 启动门：按 /health 判断是否需登录。
 * T40：内联脚本已做过一次探活；此处做二次确认（内联脚本可能因网络抖动失败）。
 * - /health 拉不到 → 放行，交给断连横幅；不误弹登录门。
 * - auth_required=false → 放行（未开鉴权）。
 * - auth_configured=false → 弹登录门 + 「未配置登录凭证」提示。
 * - 否则探活会话：有效放行 / 失效弹登录门。
 */
export async function ensureAgentAuthenticated() {
  // T40：若已有 token 且内联脚本已验证，直接放行（避免重复探活）
  if (hasAgentToken() && window.__CCC_LOGIN_EARLY_BOUND__) {
    // 仍需轻探一次以确认 token 未过期
    if (await probeAgentSession()) {
      hideLogin();
      applyAgentRoleUI();
      return true;
    }
  }
  let health = null;
  try {
    const resp = await fetch('/health');
    if (resp.ok) health = await resp.json().catch(() => null);
  } catch (_) {
    health = null;
  }
  if (!health || !health.auth_required) {
    // 未开鉴权 / 拉不到：不挡启动，连接层负责断连提示
    applyAgentRoleUI();
    return true;
  }
  if (health.auth_configured === false) {
    showLogin('服务端未配置登录凭证，请联系管理员配置后重试');
    return false;
  }
  if (await probeAgentSession()) {
    hideLogin();
    applyAgentRoleUI();
    return true;
  }
  showLogin();
  return false;
}

/** 等待登录完成（agentLogin 成功后 resolve）。 */
export function waitForAgentAuth() {
  return new Promise((resolve) => _authResolvers.push(resolve));
}