/**
 * auth.js — Hub 会话登录态（窗口 A3）。
 *
 * 登录门只作用于 Hub 壳（直连 :7777）；对话壳(:7788) 的 Hub API 走 sidecar 代理
 * （sidecar 自带 Hub Basic），不强制登录，避免破坏 Desktop/sidecar 链路。
 * token 只进 sessionStorage（会话级，不落 localStorage）；Basic 凭证只在登录换 token 时用一次。
 */

import { state } from './state.js';
import { hubUrl, isDialogueShell } from './ports.js';

const TOKEN_KEY = 'ccc_hub_token';
const ROLE_KEY = 'ccc_hub_role';

// ── token / role 存取（sessionStorage）───────────────────────────

export function getToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY) || '';
  } catch (_) {
    return '';
  }
}

export function getRole() {
  try {
    return sessionStorage.getItem(ROLE_KEY) || '';
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
    sessionStorage.setItem(TOKEN_KEY, token || '');
    sessionStorage.setItem(ROLE_KEY, role || '');
  } catch (_) {
    /* ignore */
  }
  state.set('authRole', role || '');
  applyRoleUI(role);
  _emit(role);
}

export function clearToken() {
  try {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(ROLE_KEY);
  } catch (_) {
    /* ignore */
  }
  state.set('authRole', '');
  applyRoleUI('');
  _emit('');
}

// ── 登录 / 登出 / 探活 ───────────────────────────────────────────

/** 登录：Basic 凭证换 Bearer token（Basic 仅此一次；401 → throw 凭证错）。 */
export async function login(user, pass) {
  const resp = await fetch(hubUrl('/api/auth/token'), {
    method: 'POST',
    headers: {
      Authorization: 'Basic ' + btoa((user || '') + ':' + (pass || '')),
    },
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    if (resp.status === 401) throw new Error('账号或密码错误');
    throw new Error(data.detail || ('登录失败: HTTP ' + resp.status));
  }
  setToken(data.token, data.role);
  return data;
}

/** 登出：吊销 Bearer token（幂等；网络失败忽略）。 */
export async function logout() {
  try {
    await fetch(hubUrl('/api/auth/logout'), {
      method: 'POST',
      headers: authHeaders(),
    });
  } catch (_) {
    /* ignore */
  }
  clearToken();
}

/** 探活：GET /api/auth/session；无效 → 清 token。返回 role 或 null。 */
export async function probeSession() {
  if (!isAuthenticated()) return null;
  try {
    const resp = await fetch(hubUrl('/api/auth/session'), {
      headers: authHeaders(),
    });
    if (!resp.ok) {
      clearToken();
      return null;
    }
    const data = await resp.json().catch(() => ({}));
    const role = data.role || getRole();
    setToken(getToken(), role);
    return role || null;
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
 * 对话壳收到 auth-required → toast；Hub 壳 → 登录视图（不白屏不弹裸错误）。
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
    if (isDialogueShell()) {
      window.showToast?.('Hub 鉴权失效，请检查对话口配置', 'error');
    } else {
      showLogin();
    }
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

/** 启动门：Hub 壳必须有有效 token 才放行；否则显示登录视图并等待。 */
export async function ensureAuthenticated() {
  if (isDialogueShell()) {
    applyRoleUI(getRole());
    return true;
  }
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
