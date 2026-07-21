/** CCC Hub hash router — #/chat | #/board | #/console | #/ops
 *
 * Hub = 远程管理口（会话分区）；产品主对话仍在 Desktop。
 * 见 docs/product/hub-remote-management.md
 */

const ROUTES = ['chat', 'board', 'console', 'ops'];
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
  if (!location.hash || location.hash === '#' ) {
    location.hash = '#/' + DEFAULT_ROUTE;
  } else {
    applyRoute(currentRoute());
  }
}

export function applyRoute(route) {
  const r = ROUTES.includes(route) ? route : DEFAULT_ROUTE;
  document.querySelectorAll('.hub-view').forEach((el) => {
    el.classList.toggle('active', el.id === 'view-' + r);
  });
  document.querySelectorAll('.hub-nav-link[data-route]').forEach((el) => {
    el.classList.toggle('active', el.dataset.route === r);
  });
  if (_onChange) _onChange(r);
}
