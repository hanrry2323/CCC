/** CCC hash router — #/board | #/ops | #/console | #/roadmap | #/chat
 *
 * 2017 单端 :7788 五视图统一入口（对话/看板/线路图/运维/控制台）。
 * 见 docs/architecture.md
 */

import { dialogueEntryUrl, isDialogueShell } from './ports.js';

const ROUTES = ['chat', 'board', 'plans', 'console', 'ops', 'roadmap'];
// T44：首要场景是对话，默认路由固定 #/chat（登录后直达对话视图）。
const DEFAULT_ROUTE = 'chat';

export function currentRoute() {
  const raw = (location.hash || '#/' + DEFAULT_ROUTE).replace(/^#\/?/, '');
  const name = (raw.split(/[/?#]/)[0] || DEFAULT_ROUTE).toLowerCase();
  return ROUTES.includes(name) ? name : DEFAULT_ROUTE;
}

export function navigate(route) {
  const r = ROUTES.includes(route) ? route : DEFAULT_ROUTE;
  if (currentRoute() === r && location.hash) {
    applyRoute(r);
    return;
  }
  location.hash = '#/' + r;
}

let _onChange = null;

export function initRouter(onChange) {
  _onChange = onChange;
  window.addEventListener('hashchange', () => applyRoute(currentRoute()));
  if (!location.hash || location.hash === '#') {
    location.hash = '#/' + DEFAULT_ROUTE;
  } else {
    applyRoute(currentRoute());
  }
}

/** Hub 编排机上的 #/chat → 内联渲染跳转提示，不再自动跳转。 */
function showHubChatNotice() {
  const url = dialogueEntryUrl();
  const view = document.getElementById('view-chat');
  if (view) {
    view.innerHTML =
      '<div style="padding:48px 24px;max-width:420px;margin:0 auto;text-align:center;font-family:system-ui,sans-serif">' +
      '<p style="font-size:15px;line-height:1.5;margin:0 0 16px">对话口在 <strong>2017 :7788</strong>，HTTP 直连单端服务。</p>' +
      '<p style="font-size:13px;opacity:.75;margin:0 0 20px">当前为编排视图；对话请开 2017 :7788。</p>' +
      '<a href="' +
      url +
      '" style="display:inline-block;padding:10px 18px;background:#0c4a6e;color:#fff;border-radius:8px;text-decoration:none;font-weight:600">打开对话口</a>' +
      '<p style="font-size:12px;margin-top:14px;opacity:.6"><a href="#/board">返回看板</a></p>' +
      '</div>';
  }
}

export function applyRoute(route) {
  const r = ROUTES.includes(route) ? route : DEFAULT_ROUTE;
  if (r === 'chat' && !isDialogueShell()) {
    document.querySelectorAll('.hub-view').forEach((el) => {
      el.classList.toggle('active', el.id === 'view-chat');
    });
    document.querySelectorAll('.hub-nav-link[data-route]').forEach((el) => {
      el.classList.toggle('active', el.dataset.route === 'chat');
    });
    showHubChatNotice();
    if (_onChange) _onChange('chat');
    return;
  }
  document.querySelectorAll('.hub-view').forEach((el) => {
    el.classList.toggle('active', el.id === 'view-' + r);
  });
  document.querySelectorAll('.hub-nav-link[data-route]').forEach((el) => {
    el.classList.toggle('active', el.dataset.route === r);
  });
  if (_onChange) _onChange(r);
}
