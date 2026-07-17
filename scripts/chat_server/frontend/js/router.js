/** CCC Hub hash router — #/chat | #/board | #/console | #/ops */

const ROUTES = ['chat', 'board', 'console', 'ops'];

export function currentRoute() {
  const raw = (location.hash || '#/chat').replace(/^#\/?/, '');
  const name = (raw.split(/[/?#]/)[0] || 'chat').toLowerCase();
  return ROUTES.includes(name) ? name : 'chat';
}

export function navigate(route) {
  const r = ROUTES.includes(route) ? route : 'chat';
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
    location.hash = '#/chat';
  } else {
    applyRoute(currentRoute());
  }
}

export function applyRoute(route) {
  const r = ROUTES.includes(route) ? route : 'chat';
  document.querySelectorAll('.hub-view').forEach((el) => {
    el.classList.toggle('active', el.id === 'view-' + r);
  });
  document.querySelectorAll('.hub-nav-link[data-route]').forEach((el) => {
    el.classList.toggle('active', el.dataset.route === r);
  });
  if (_onChange) _onChange(r);
}
