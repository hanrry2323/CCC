/**
 * agentAuth.js — 7788 对话口账号密码登录门（窗口 K）。
 *
 * 对话壳（:7788）登录门：POST /api/auth/agent-login 换会话 token（内存 TTL 1h），
 * token 只进 sessionStorage（不落 localStorage）；401 → 清 token + 弹登录门引导重登。
 * 服务端未配置凭证 → 登录 503「未配置登录凭证」，前端据此给出明确提示（无默认弱口令）。
 */

import { agentUrl } from './ports.js';

const AGENT_TOKEN_KEY = 'ccc_agent_session';

let _authResolvers = [];

function _resolvePending() {
  const pending = _authResolvers;
  _authResolvers = [];
  pending.forEach((r) => r());
}

// ── token 存取（sessionStorage，不落 localStorage）────────

export function getAgentToken() {
  try {
    return sessionStorage.getItem(AGENT_TOKEN_KEY) || '';
  } catch (_) {
    return '';
  }
}

export function setAgentToken(token) {
  try {
    sessionStorage.setItem(AGENT_TOKEN_KEY, token || '');
  } catch (_) {}
}

export function clearAgentToken() {
  try {
    sessionStorage.removeItem(AGENT_TOKEN_KEY);
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
  const resp = await fetch(agentUrl('/api/auth/agent-login'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user: user || '', password: pass || '' }),
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

/** 登出：吊销会话 token（幂等；网络失败忽略）。 */
export async function agentLogout() {
  try {
    await fetch(agentUrl('/api/auth/agent-logout'), {
      method: 'POST',
      headers: agentHeaders(),
    });
  } catch (_) {}
  clearAgentToken();
  applyAgentRoleUI();
}

/** 探活：GET /api/auth/agent-session；无效 → 清 token + false。 */
export async function probeAgentSession() {
  if (!hasAgentToken()) return false;
  try {
    const resp = await fetch(agentUrl('/api/auth/agent-session'), {
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

/** 初始化：改登录视图文案 + 绑表单/登出/401 事件。 */
export function initAgentAuth({ onAuthenticated } = {}) {
  const title = document.getElementById('login-title');
  if (title) title.textContent = 'CCC 对话口登录';
  const hint = document.getElementById('login-hint');
  if (hint) {
    hint.textContent =
      '账号密码由服务端配置（CCC_AGENT_AUTH_USER/PASS 或 ~/.ccc/agent-auth.json 0600）；未配置则无法登录。';
  }
  const userInput = document.getElementById('login-user');
  if (userInput) userInput.placeholder = '账号';

  const view = document.getElementById('login-view');
  const form = view && view.querySelector('form');
  if (form) {
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
  document.addEventListener('ccc-agent-auth-required', () => showLogin('会话已失效，请重新登录'));
  applyAgentRoleUI();
}

/**
 * 启动门：按 /health 判断是否需登录。
 * - /health 拉不到（sidecar 不可达）→ 放行，交给断连横幅；不误弹登录门。
 * - auth_required=false → 放行（未开鉴权）。
 * - auth_configured=false → 弹登录门 + 「未配置登录凭证」提示。
 * - 否则探活会话：有效放行 / 失效弹登录门。
 */
export async function ensureAgentAuthenticated() {
  let health = null;
  try {
    const resp = await fetch(agentUrl('/health'));
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

export { AGENT_TOKEN_KEY };
