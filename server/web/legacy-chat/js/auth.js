/**
 * auth.js — 新服务端会话登录态。
 *
 * 登录门：POST /session（JSON body）换 Bearer token，存 localStorage。
 * 探活：GET /health 带 Bearer token。
 * token 落 localStorage（持久会话），每次启动探活确认有效性。
 */

import { state } from './state.js';
import { hubUrl } from './ports.js';

const TOKEN_KEY = 'ccc_chat_token';
const ROLE_KEY = 'ccc_chat_role';

// ── token / role 存取（localStorage）──────────────────────────────

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || '';
  } catch (_) {
    return '';
  }
}

export function getRole() {
  try {
    return localStorage.getItem(ROLE_KEY) || '';
  } catch (_) {
    return '';
  }
}

export function isAuthenticated() {
  return Boolean(getToken());
}

/** 当前角色是否可写（operator）。 */
export function canWrite() {
  return canWriteRole(getRole());
}

/** 纯函数：角色 → 可写（node 单测目标）。 */
export function canWriteRole(role) {
  return role === 'operator';
}

/** 纯函数：token → Bearer 请求头（无 token 返回空头）。 */
export function authHeaders(token) {
  const t = token || getToken();
  return t ? { Authorization: 'Bearer ' + t } : {};
}

let _authResolvers = [];

function _emit(role) {
  window.dispatchEvent(
    new CustomEvent('ccc-auth-changed', { detail: { role } })
  );
  const pending = _authResolvers;
  _authResolvers = [];
  pending.forEach((r) => r());
}

export function setToken(token, role) {
  try {
    localStorage.setItem(TOKEN_KEY, token || '');
    localStorage.setItem(ROLE_KEY, role || '');
  } catch (_) {
    /* ignore */
  }
  state.set('authRole', role || '');
  applyRoleUI(role);
  _emit(role);
}

export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(ROLE_KEY);
  } catch (_) {
    /* ignore */
  }
  state.set('authRole', '');
  applyRoleUI('');
  _emit('');
}

// ── 登录 / 登出 / 探活 ───────────────────────────────────────────

/** 登录：用户名密码换 Bearer token（401 → throw 凭证错）。 */
export async function login(user, pass) {
  const resp = await fetch(hubUrl('/session'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: user || '', password: pass || '' }),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    if (resp.status === 401) throw new Error('账号或密码错误');
    throw new Error(data.detail || ('登录失败: HTTP ' + resp.status));
  }
  setToken(data.token, 'operator');
  return data;
}

/** 登出：只清本地 token，不再调后端。 */
export async function logout() {
  clearToken();
}

/** 探活：GET /health；无效 → 清 token。返回 'operator' 或 null。 */
export async function probeSession() {
  if (!isAuthenticated()) return null;
  try {
    const resp = await fetch(hubUrl('/health'), {
      headers: authHeaders(),
    });
    if (!resp.ok) {
      clearToken();
      return null;
    }
    // 200 即有效，返回固定角色 'operator'
    const role = 'operator';
    setToken(getToken(), role);
    return role;
  } catch (_) {
    return null;
  }
}

// ── UI：登录视图 / 角色态 / 写按钮拦截 ───────────────────────────

function showLogin() {
  const view = document.getElementById('login-view');
  if (view) {
    view.hidden = false;
    view.classList.add('open');
  }
}

function hideLogin() {
  const view = document.getElementById('login-view');
  if (view) {
    view.hidden = true;
    view.classList.remove('open');
  }
}

/** 角色 → body.ro-viewer + 登录态 chip。 */
export function applyRoleUI(role) {
  if (typeof document === 'undefined') return;
  document.body.classList.toggle('ro-viewer', role === 'viewer');
  const chip = document.getElementById('auth-role');
  if (chip) {
    chip.textContent =
      role === 'viewer' ? '只读' : role === 'operator' ? '可写' : '未登录';
  }
}

/**
 * 初始化：绑定登录表单 / 登出按钮 / 运行期 401（ccc-auth-required）。
 * 收到 auth-required → 显示登录视图。
 */
export function initAuth({ onAuthenticated } = {}) {
  // viewer 下写按钮全局拦截（data-write 标注；后端 require_write 403 是硬门）
  document.addEventListener(
    'click',
    (e) => {
      if (canWrite()) return;
      const w = e.target && e.target.closest && e.target.closest('[data-write]');
      if (w) {
        e.preventDefault();
        e.stopPropagation();
        window.showToast?.('只读账户（viewer）无写权限', 'error');
      }
    },
    true
  );
  document.addEventListener('ccc-auth-required', () => {
    showLogin();
  });

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
        await login((userEl && userEl.value) || '', (passEl && passEl.value) || '');
        hideLogin();
        applyRoleUI(getRole());
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
      await logout();
      showLogin();
    });
  }
}

/** 启动门：必须有有效 token 才放行；否则显示登录视图并等待。 */
export async function ensureAuthenticated() {
  const role = await probeSession();
  if (role) {
    hideLogin();
    applyRoleUI(role);
    return true;
  }
  showLogin();
  return false;
}

/** 等待登录完成（initAuth 登录成功后 resolve）。 */
export function waitForAuth() {
  return new Promise((resolve) => _authResolvers.push(resolve));
}