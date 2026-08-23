/** CCC hash router — #/wall | #/board | #/plans | #/roadmap | #/ops | #/console | #/dsh
 *
 * 2017 单端 :7788 统一入口。ccc-plan-045 P1.5：信息墙为默认视图，
 * 旧对话路由随对话栈拆除（git 历史可回滚）。
 */

const ROUTES = ['wall', 'board', 'plans', 'console', 'ops', 'roadmap', 'dsh'];
// 信息墙 = DSH 会话实时观察面，是打开 CCC 的第一屏。
const DEFAULT_ROUTE = 'wall';

export function currentRoute() {
  const raw = (location.hash || '#/' + DEFAULT_ROUTE).replace(/^#\/?/, '');
  const name = (raw.split(/[/?#]/)[0] || DEFAULT_ROUTE).toLowerCase();
  if (!ROUTES.includes(name)) {
    // 未知路由折叠为默认视图时同步归一 hash——否则地址栏停在
    // #/foo，之后任何 navigate(DEFAULT) 都因同路由判定直接 return，hash 永不纠正
    try { history.replaceState(null, '', location.pathname + location.search + '#/' + DEFAULT_ROUTE); } catch (_) {}
    return DEFAULT_ROUTE;
  }
  return name;
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
  applyRoute(currentRoute());
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
