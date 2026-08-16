/**
 * relayStats — 顶部栏「中转站调用量」实时模块。
 * 每 10s 拉 /ops/relay-stats：今日请求（总）+ Pro/flash/code 分桶，
 * 每个数字附近 10 秒增量；中转站异常 → 数字变红 + ⚠ 提醒。
 */

import { apiGet } from '../api.js';

const RELAY_POLL_MS = 10000;
let _timer = null;

const _EMPTY = {
  today: { total: 0, pro: 0, flash: 0, code: 0 },
  delta_10s: { total: 0, pro: 0, flash: 0, code: 0 },
  healthy: false,
  alert: '获取中转站数据失败',
};

function fmt(n) {
  return Number(n || 0).toLocaleString('en-US');
}

function render(data) {
  const el = document.getElementById('relay-stats');
  if (!el) return;
  const d = data || _EMPTY;
  const unhealthy = !d.healthy;
  el.classList.toggle('relay-alert', unhealthy);

  const rows = [
    ['今日请求', d.today.total, d.delta_10s.total],
    ['Pro', d.today.pro, d.delta_10s.pro],
    ['flash', d.today.flash, d.delta_10s.flash],
    ['code', d.today.code, d.delta_10s.code],
  ];
  el.innerHTML =
    rows
      .map(
        ([label, total, delta]) =>
          `<span class="relay-item${Number(delta) > 0 ? ' relay-live' : ''}" title="${label} 今日累计 ${fmt(total)} · 近10秒 +${fmt(delta)}">` +
          `<b>${label}</b><span class="relay-num">${fmt(total)}</span>` +
          `<span class="relay-delta">+${fmt(delta)}</span></span>`
      )
      .join('') +
    (unhealthy
      ? `<span class="relay-alert-tag" title="${String(d.alert || '中转站异常')}">⚠</span>`
      : '');
  el.title = unhealthy
    ? String(d.alert || '中转站异常')
    : '中转站调用量（今日累计 · 近10秒增量）';
}

export async function refreshRelayStats() {
  // M3：页面不可见时不拉（省服务器请求；回来立即拉一次刷新顶栏）
  if (typeof document !== 'undefined' && document.visibilityState !== 'visible') return;
  try {
    const data = await apiGet('/ops/relay-stats');
    render(data);
  } catch (_) {
    render(_EMPTY);
  }
}

export function initRelayStats() {
  if (_timer) return;
  refreshRelayStats();
  _timer = setInterval(refreshRelayStats, RELAY_POLL_MS);
}

export function stopRelayStats() {
  if (_timer) {
    clearInterval(_timer);
    _timer = null;
  }
}
