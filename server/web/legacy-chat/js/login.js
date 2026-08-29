/**
 * login.js — 看板登录门（2026-08-29 读闸收口）。
 *
 * 服务端读闸把「登录门之后的全部读端点」纳入凭证门槛后，看板打开即需口令换签：
 * 本模块提供全屏登录页（POST /session），供 app.js 启动门（打开即见登录页）与
 * api.js 401 重签路径共用。口令本体只进 POST /session 请求体，落库的仅是换签
 * 后的 token（localStorage，键与 api.js 一致）。
 */

import { getToken, setToken } from './api.js';

const KEY_OVERLAY = 'hub-login';
const KEY_USER = 'hub-login-user';
const KEY_PASS = 'hub-login-pass';
const KEY_ERR = 'hub-login-error';
const KEY_SUBMIT = 'hub-login-submit';
const KEY_FORM = 'hub-login-form';

let _pending = null; // 单例：并发登录请求合并为一次弹层

function _el(id) {
  return document.getElementById(id);
}

/** 口令换签（原生 fetch，不经 api.js 以避开 token 出口循环）。 */
async function _exchange(username, password) {
  const resp = await fetch('/session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  const data = await resp.json().catch(() => ({}));
  if (resp.status === 200 && data.token) return data.token;
  if (resp.status === 401) throw new Error('口令不正确，请重试');
  if (resp.status === 500) throw new Error('服务端未配置登录凭证（web-auth）');
  throw new Error('口令换签失败（HTTP ' + resp.status + '）');
}

/** 显示登录页，登录成功 resolve(token)。单例：并发调用合并为一次弹层。 */
export function showLogin() {
  if (_pending) return _pending;
  _pending = (async () => {
    const overlay = _el(KEY_OVERLAY);
    const form = _el(KEY_FORM);
    const user = _el(KEY_USER);
    const pass = _el(KEY_PASS);
    const err = _el(KEY_ERR);
    const submit = _el(KEY_SUBMIT);
    overlay.hidden = false;
    err.hidden = true;
    pass.value = '';
    const close = () => {
      overlay.hidden = true;
      submit.disabled = false;
      _pending = null;
    };
    return new Promise((resolve) => {
      const onsubmit = async (e) => {
        e.preventDefault();
        submit.disabled = true;
        err.hidden = true;
        try {
          const token = await _exchange(user.value.trim() || 'ccc', pass.value);
          setToken(token);
          close();
          form.removeEventListener('submit', onsubmit);
          resolve(token);
        } catch (exc) {
          err.textContent = exc.message || '登录失败';
          err.hidden = false;
          submit.disabled = false;
          pass.focus();
        }
      };
      form.addEventListener('submit', onsubmit);
      setTimeout(() => pass.focus(), 0);
    });
  })().finally(() => {});
  return _pending;
}

/** 隐藏登录页（不换签，仅 UI 关闭）。 */
export function hideLogin() {
  const overlay = _el(KEY_OVERLAY);
  if (overlay) overlay.hidden = true;
}

/** 启动门：已有 token 直接放行，否则唤起登录页等待换签。 */
export async function ensureLogin() {
  const tok = getToken();
  if (tok) return tok;
  return showLogin();
}
