/** CCC Hub hash router — #/board | #/console | #/ops
 *
 * 架构对齐 2026-07-19：#/chat 已删（对话主入口 = M1 Desktop + sidecar :7788）。
 * 网页 Hub 仅运维/兼容；看板/运维已迁入 Desktop（见 docs/deprecate-web-board-ops.md）。
 */

const ROUTES = ['board', 'console', 'ops'];
const DEFAULT_ROUTE = 'board';

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
  if (!location.hash || location.hash === '#' || location.hash === '#/chat') {
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
