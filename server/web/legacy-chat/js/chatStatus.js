/**
 * chatStatus — 对话壳感知层（窗口 1 任务 I）。
 *
 * 三个感知能力：
 *  - 断连横幅：sidecar 网络层抛错 / 健康轮询失败 → 顶部横幅「连接中断，正在重连…」
 *  - 模型档位警告：/health 失败或 models 空 → 输入区上方持久条
 *  - 首包等待：流式首包超时无响应 → 「等待模型响应…」
 *
 * 纯函数（无 DOM，node 可测）与 DOM 挂载（守卫内）分离：
 * 依赖仅 ports.js（agentUrl），node 导入安全。
 */

import { agentUrl } from './ports.js';

export const CONN_OK = 'ok';
export const CONN_DOWN = 'down';

export const HEALTH_OK = 'ok';
export const HEALTH_EMPTY_MODELS = 'empty-models';
export const HEALTH_UNREACHABLE = 'unreachable';

export const WAIT_HINT_TEXT = '等待模型响应…';

/** 连接状态机：failure → down（幂等）；其余 → ok。 */
export function nextConnStatus(status, event) {
  if (event === 'failure') return CONN_DOWN;
  return CONN_OK;
}

/** 健康判定：fetch 失败 → unreachable；payload 无非空 models → empty-models；否则 ok。 */
export function classifyHealth(outcome) {
  if (!outcome) return HEALTH_UNREACHABLE;
  if (outcome.fetchFailed) return HEALTH_UNREACHABLE;
  const h = outcome.payload;
  const models = h && Array.isArray(h.models) ? h.models : [];
  if (!h || models.length === 0) return HEALTH_EMPTY_MODELS;
  return HEALTH_OK;
}

/** 模型档位警告文案：ok → ''；两种异常态 → 非空。 */
export function healthWarnText(cls) {
  if (cls === HEALTH_UNREACHABLE) {
    return '模型档位不可用：对话服务未响应，恢复后自动消除';
  }
  if (cls === HEALTH_EMPTY_MODELS) {
    return '模型档位不可用：模型列表为空，恢复后自动消除';
  }
  return '';
}

/** 断连横幅文案。 */
export function connBannerText() {
  return '连接中断，正在重连…';
}

/** 首包等待提示：超时（elapsed >= timeout）且无首包 → 文案；否则 ''。 */
export function waitHintText(elapsedMs, timeoutMs, hasFirstPacket) {
  if (hasFirstPacket) return '';
  if (elapsedMs >= timeoutMs) return WAIT_HINT_TEXT;
  return '';
}

// ── DOM 挂载（守卫内；node 导入不执行）──────────────────────────────

const CONN_BANNER_ID = 'chat-conn-banner';
const MODEL_WARN_ID = 'chat-model-warn';
const HEALTH_PING_MS = 30000;

let _connEl = null;
let _warnEl = null;
let _pingTimer = null;
let _connStatus = CONN_OK;

function _ensureEls() {
  if (typeof document === 'undefined') return null;
  if (_connEl && _warnEl && _connEl.isConnected && _warnEl.isConnected) {
    return { conn: _connEl, warn: _warnEl };
  }
  _connEl = document.getElementById(CONN_BANNER_ID);
  _warnEl = document.getElementById(MODEL_WARN_ID);
  if (!_connEl || !_warnEl) {
    const host = document.getElementById('view-chat') || document.getElementById('app');
    if (!host) return null;
    if (!_connEl) {
      _connEl = document.createElement('div');
      _connEl.id = CONN_BANNER_ID;
      _connEl.className = 'chat-conn-banner';
      _connEl.setAttribute('role', 'status');
      _connEl.hidden = true;
      host.insertBefore(_connEl, host.firstChild);
    }
    if (!_warnEl) {
      _warnEl = document.createElement('div');
      _warnEl.id = MODEL_WARN_ID;
      _warnEl.className = 'chat-model-warn';
      _warnEl.hidden = true;
      const composer = document.getElementById('composer');
      const target = composer || host;
      target.parentNode.insertBefore(_warnEl, target);
    }
  }
  return { conn: _connEl, warn: _warnEl };
}

export function setConnBanner(visible, text) {
  const els = _ensureEls();
  if (!els) return;
  els.conn.textContent = text || connBannerText();
  els.conn.hidden = !visible;
}

export function setModelWarn(visible, text) {
  const els = _ensureEls();
  if (!els) return;
  els.warn.textContent = text || '';
  els.warn.hidden = !visible;
}

/** 网络层失败（sidecar 不可达）→ 顶部横幅。 */
export function reportConnectionFailure() {
  _connStatus = nextConnStatus(_connStatus, 'failure');
  setConnBanner(true, connBannerText());
}

/** 恢复（健康轮询成功）→ 横幅消失。 */
export function reportConnectionRecovery() {
  _connStatus = nextConnStatus(_connStatus, 'recovery');
  setConnBanner(false);
}

/** 健康轮询结果 → 横幅 + 模型警告联动；返回判定分类。 */
export function updateHealthFromPing(outcome) {
  const cls = classifyHealth(outcome);
  const warnText = healthWarnText(cls);
  setModelWarn(!!warnText, warnText);
  if (cls === HEALTH_UNREACHABLE) {
    setConnBanner(true, connBannerText());
  } else {
    setConnBanner(false);
  }
  return cls;
}

/** 启动 30s 健康轮询（幂等）；断连横幅据此恢复。 */
export function startHealthPing(intervalMs) {
  if (typeof window === 'undefined') return;
  if (_pingTimer != null) return;
  const ms = intervalMs || HEALTH_PING_MS;
  const ping = async () => {
    try {
      const r = await fetch(agentUrl('/health'));
      if (!r.ok) {
        updateHealthFromPing({ fetchFailed: true, payload: null });
        return;
      }
      const payload = await r.json().catch(() => null);
      updateHealthFromPing({ fetchFailed: false, payload });
    } catch (_) {
      updateHealthFromPing({ fetchFailed: true, payload: null });
    }
  };
  ping();
  _pingTimer = setInterval(ping, ms);
}

/** 对话壳启动时调用一次：注入 banner 元素 + 启动轮询。 */
export function initChatStatus() {
  _ensureEls();
  startHealthPing();
}
