/** CCC Hub hash router — #/board | #/ops | #/console | #/chat
 *
 * Hub = 编排口（看板/运维）；对话口在 M1 :7788。
 * 在 Hub(:7777) 打开 #/chat → 跳转 M1 dialogue_url（非产品聊入口）。
 * 见 docs/product/hub-remote-management.md
 */

import { dialogueEntryUrl, isDialogueShell } from './ports.js';

const ROUTES = ['chat', 'board', 'console', 'ops'];
const DEFAULT_ROUTE =
  typeof location !== 'undefined' && String(location.port || '') === '7788'
    ? 'chat'
    : 'board';

export function currentRoute() {
  const raw = (location.hash || '#/' + DEFAULT_ROUTE).replace(/^#\/?/, '');
  const name = (raw.split(/[/?#]/)[0] || DEFAULT_ROUTE).toLowerCase();
  return ROUTES.includes(name) ? name : DEFAULT_ROUTE;
}

export function navigate(route) {
  const r = ROUTES.includes(route) ? route : DEFAULT_ROUTE;
  if (r === 'chat' && !isDialogueShell()) {
    redirectHubChatToDialogue();
    return;
  }
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

/** Hub 编排机上的 #/chat → 外跳 M1 对话口。 */
export function redirectHubChatToDialogue() {
  const url = dialogueEntryUrl();
  const view = document.getElementById('view-chat');
  if (view) {
    view.innerHTML =
      '<div style="padding:48px 24px;max-width:420px;margin:0 auto;text-align:center;font-family:system-ui,sans-serif">' +
      '<p style="font-size:15px;line-height:1.5;margin:0 0 16px">对话口在 <strong>M1 :7788</strong>，与 Desktop 同热路径。</p>' +
      '<p style="font-size:13px;opacity:.75;margin:0 0 20px">Hub 只做看板 / 运维 / 下达。</p>' +
      '<a href="' +
      url +
      '" style="display:inline-block;padding:10px 18px;background:#0c4a6e;color:#fff;border-radius:8px;text-decoration:none;font-weight:600">打开对话口</a>' +
      '<p style="font-size:12px;margin-top:14px;opacity:.6"><a href="#/board">返回看板</a></p>' +
      '</div>';
  }
  // 自动跳转（可被用户点「返回看板」打断前已导航）
  try {
    if (!sessionStorage.getItem('ccc_skip_dialogue_redirect')) {
      location.assign(url);
    }
  } catch (_) {
    location.assign(url);
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
    redirectHubChatToDialogue();
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
