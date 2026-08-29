/**
 * app.js — CCC 单端壳入口（ccc-plan-045 P1.5 深度融合后）。
 *
 * 旧对话栈（消息流/composer/侧栏会话/大脑桥前端/登录门/分屏/流注册表）已整体拆除；
 * 信息墙成为默认视图（#/wall），与看板/计划/线路图/运维/巡检/控制台同壳路由。
 */

import { applyTheme, getThemeScheme } from './theme.js';
import { initRouter, navigate } from './router.js';
import { pageScopeAbort, setRouteSwitching } from './api.js';
import { ensureLogin } from './login.js';

// 路由→已加载页面注册表。必须是模块级：onHubRoute 的 unmount 循环遍历它来卸载旧页。
// （2026-08-24 修复史：曾被懒加载改造误改为函数内局部 const，unmount 全部空转、
//   各页定时器跨路由泄漏累积——回归自 e9f2545ce，勿再降级。）
const PAGES = {};

const PAGES_LOADERS = {
  wall: () =>
    import('./pages/wallPage.js').then((m) => ({
      mount: m.mountWall,
      unmount: m.unmountWall,
    })),
  board: () =>
    import('./pages/boardPage.js').then((m) => ({
      mount: m.mountBoard,
      unmount: m.unmountBoard,
    })),
  plans: () =>
    import('./pages/plansPage.js').then((m) => ({
      mount: m.mountPlans,
      unmount: m.unmountPlans,
    })),
  roadmap: () =>
    import('./pages/roadmapPage.js').then((m) => ({
      mount: m.mountRoadmap,
      unmount: m.unmountRoadmap,
    })),
  console: () =>
    import('./pages/consolePage.js').then((m) => ({
      mount: m.mountConsole,
      unmount: m.unmountConsole,
    })),
  ops: () =>
    import('./pages/opsPage.js').then((m) => ({
      mount: m.mountOps,
      unmount: m.unmountOps,
    })),
  dsh: () =>
    import('./pages/dshPage.js').then((m) => ({
      mount: m.mountDsh,
      unmount: m.unmountDsh,
    })),
};

let _routeGen = 0;

async function onHubRoute(route) {
  const gen = ++_routeGen;
  setRouteSwitching(true);   // api.js：切换窗口内网络错误静默（不弹「网络中断」）
  pageScopeAbort();          // api.js：中断旧页全部页面级在途 GET
  try {
    const TITLES = {
      wall: 'CCC · 信息墙', board: 'CCC · 看板', plans: 'CCC · 计划',
      roadmap: 'CCC · 线路图', console: 'CCC · 控制台', ops: 'CCC · 运维',
      dsh: 'CCC · DSH 巡检',
    };
    document.title = TITLES[route] || 'CCC';
    for (const name of Object.keys(PAGES)) {
      if (name !== route) PAGES[name].unmount();
    }
    if (!PAGES[route]) {
      PAGES[route] = await PAGES_LOADERS[route]();
    }
    // 非阻塞 mount：页面内部同步渲染骨架、后台拉数据；数据到达时令牌失效则丢弃
    PAGES[route].mount(document.getElementById('view-' + route), { gen });
  } catch (err) {
    // 动态 import 失败（弱网首进）：给视图区一个可重试的错误态，不留死白屏
    const view = document.getElementById('view-' + route);
    if (view) {
      view.innerHTML =
        '<div style="padding:48px 24px;text-align:center;color:var(--ccc-text-muted)">' +
        '页面加载失败：<button type="button" class="hub-btn" onclick="location.reload()">重试</button>' +
        '</div>';
    }
    delete PAGES[route];
  } finally {
    setRouteSwitching(false);
  }
}

// （setRouteSwitching / pageScopeAbort 直接来自 api.js，见顶部 import）

async function init() {
  applyTheme(getThemeScheme());

  // toast 全局注册（window.showToast，各页面零依赖调用）
  await import('./components/toast.js');

  // 设置入口（原侧栏按钮随对话栈拆除，收编进 hub-nav）
  document.getElementById('hub-settings-btn')?.addEventListener('click', () => {
    import('./components/settings.js').then((m) => m.openSettings());
  });

  // 登录门（2026-08-29 读闸收口）：打开即见登录页，口令换签后才挂路由进看板。
  // 已存 token 直接放行；token 失效由各请求 401 → api.js 自动唤起登录页重签。
  await ensureLogin();

  initRouter(onHubRoute);

  // 健康横幅等感知层保留在 chatStatus？——已随对话栈拆除；
  // 断连提示由各页自身请求失败路径呈现。
}

if (document.readyState === 'interactive' || document.readyState === 'complete') {
  init();
} else {
  document.addEventListener('DOMContentLoaded', init);
}
