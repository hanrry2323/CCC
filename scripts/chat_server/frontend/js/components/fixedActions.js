/** 固定动作：composer 装饰横条 + 「更多」；主栏按宽度自适应。
 *
 * 候选主栏（宽→多显）：对齐基线 · 下一步 · 定稿方案 · 转任务 · 扫风险 · 解释未提交
 * 更多：装不下的主栏项 + 下达任务 · 看板 · 定时/Skill(占位) · 自定义
 */

import { FINALIZE_PLAN_PROMPT } from './dispatchFormat.js';

const CUSTOM_KEY = 'ccc_qa_custom_v1';

export const FIXED_ACTIONS = [
  {
    id: 'baseline',
    label: '对齐基线',
    kind: 'baseline',
  },
  {
    id: 'next',
    label: '下一步',
    kind: 'prompt',
    prompt:
      '基于当前仓库与本会话已对齐的信息，用中文给出「下一步开发」建议。\n' +
      '要求：总字数 ≤200；列出 3 个选项 + 一行「最佳：…」；每条≤20字；不要代码块。\n' +
      '若本会话尚未对齐基线，先用一句点明假设再给建议。',
  },
  {
    id: 'risks',
    label: '扫风险',
    kind: 'prompt',
    prompt:
      '快速扫描当前项目风险（git 脏文件、明显坏味道、控制面/自动化隐患）。\n' +
      '要求：总字数 ≤180；只列会踩坑的项；无则写「无明显风险」；最后给 1 句处理建议。',
  },
  {
    id: 'finalize-plan',
    label: '定稿方案',
    kind: 'prompt',
    prompt: '', // set from FINALIZE_PLAN_PROMPT below
  },
  {
    id: 'explain-diff',
    label: '解释未提交',
    kind: 'prompt',
    prompt:
      '解释当前未提交改动在做什么（git status / diff）。\n' +
      '要求：≤180字；按文件点名；风险一句；是否建议先 commit。',
  },
  {
    id: 'transfer-task',
    label: '转任务',
    kind: 'transfer',
  },
  {
    id: 'task',
    label: '下达任务',
    kind: 'slash',
    slash: '/task',
  },
  {
    id: 'board',
    label: '看板',
    kind: 'slash',
    slash: '/board',
  },
  {
    id: 'schedule',
    label: '定时任务',
    kind: 'soon',
    hint: '后续：为当前项目挂日审 / 定时扫风险',
  },
  {
    id: 'new-skill',
    label: '创建 Skill',
    kind: 'soon',
    hint: '后续：从对话沉淀一条可复用 skill',
  },
];

/** 主栏候选（优先级从高到低；宽度够则多显示） */
export const PRIMARY_CANDIDATES = [
  'baseline',
  'next',
  'finalize-plan',
  'transfer-task',
  'risks',
  'explain-diff',
];

/** 兼容旧引用：默认主栏（窄屏基线） */
export const PRIMARY_IDS = PRIMARY_CANDIDATES.slice(0, 4);

/** 始终放进「更多」的内置项 */
export const MORE_ALWAYS_IDS = ['task', 'board', 'schedule', 'new-skill'];

/** @deprecated 使用 moreIdsFor(primary) */
export const MORE_BUILTIN_IDS = [
  'risks',
  'explain-diff',
  ...MORE_ALWAYS_IDS,
];

const _fp = FIXED_ACTIONS.find((a) => a.id === 'finalize-plan');
if (_fp) _fp.prompt = FINALIZE_PLAN_PROMPT;

/** 当前主栏（由 ResizeObserver 更新） */
let _activePrimary = PRIMARY_IDS.slice();

export function loadCustomActions() {
  try {
    const raw = localStorage.getItem(CUSTOM_KEY);
    const list = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(list)) return [];
    return list
      .filter((a) => a && a.id && a.label && (a.kind === 'prompt' || a.kind === 'slash'))
      .slice(0, 12);
  } catch {
    return [];
  }
}

export function saveCustomActions(list) {
  localStorage.setItem(CUSTOM_KEY, JSON.stringify(list.slice(0, 12)));
}

export function addCustomAction({ label, kind, prompt, slash }) {
  const list = loadCustomActions();
  const id =
    'custom-' +
    String(label || 'act')
      .toLowerCase()
      .replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-')
      .slice(0, 24) +
    '-' +
    Date.now().toString(36).slice(-4);
  const item = { id, label: String(label).slice(0, 16), kind };
  if (kind === 'prompt') item.prompt = String(prompt || '').slice(0, 2000);
  if (kind === 'slash') item.slash = String(slash || '').slice(0, 80);
  list.push(item);
  saveCustomActions(list);
  return item;
}

export function removeCustomAction(id) {
  saveCustomActions(loadCustomActions().filter((a) => a.id !== id));
}

function findAction(id) {
  return (
    FIXED_ACTIONS.find((a) => a.id === id) ||
    loadCustomActions().find((a) => a.id === id) ||
    null
  );
}

function byIds(ids) {
  return ids.map((id) => findAction(id)).filter(Boolean);
}

/** 粗估 chip 宽度（11px 字号 + 左右 padding） */
export function estimateChipWidth(label) {
  let w = 22;
  for (const c of String(label || '')) {
    w += /[\u4e00-\u9fff]/.test(c) ? 11 : 6.5;
  }
  return Math.ceil(w);
}

/**
 * 按可用宽度决定主栏显示哪些按钮（至少 2，最多 6）。
 * @param {number} hostWidth
 */
export function fitPrimaryIds(hostWidth) {
  const moreBtn = 34;
  const gap = 4;
  const dockPad = 14;
  const width = Math.max(0, Number(hostWidth) || 0);
  let left = width - moreBtn - dockPad;
  const fitted = [];
  for (const id of PRIMARY_CANDIDATES) {
    const act = findAction(id);
    if (!act) continue;
    const w = estimateChipWidth(act.label);
    if (fitted.length === 0) {
      if (w > left + moreBtn * 0.5) {
        // 极窄：仍塞第一个
        fitted.push(id);
        break;
      }
      fitted.push(id);
      left -= w + gap;
      continue;
    }
    if (left < w + gap) break;
    fitted.push(id);
    left -= w + gap;
    if (fitted.length >= 6) break;
  }
  if (fitted.length < 2) {
    return PRIMARY_CANDIDATES.slice(0, Math.min(2, PRIMARY_CANDIDATES.length));
  }
  return fitted;
}

export function moreIdsFor(primaryIds) {
  const inPrimary = new Set(primaryIds || []);
  const overflow = PRIMARY_CANDIDATES.filter((id) => !inPrimary.has(id));
  const always = MORE_ALWAYS_IDS.filter((id) => !inPrimary.has(id));
  return [...overflow, ...always];
}

function sameIds(a, b) {
  return (
    Array.isArray(a) &&
    Array.isArray(b) &&
    a.length === b.length &&
    a.every((id, i) => id === b[i])
  );
}

function btnHtml(a, cls) {
  const soon = a.kind === 'soon' ? ' qa-chip-soon' : '';
  return (
    '<button type="button" class="' +
    cls +
    soon +
    '" data-fixed="' +
    a.id +
    '" title="' +
    (a.hint || a.label) +
    '">' +
    a.label +
    '</button>'
  );
}

export function renderComposerActionDock(primaryIds) {
  const primaryList = primaryIds || _activePrimary;
  const primary = byIds(primaryList)
    .map((a) => btnHtml(a, 'qa-chip qa-chip-primary'))
    .join('');
  const custom = loadCustomActions();
  const moreBuiltin = byIds(moreIdsFor(primaryList))
    .map((a) => btnHtml(a, 'qa-chip qa-chip-more'))
    .join('');
  const moreCustom = custom
    .map((a) => btnHtml(a, 'qa-chip qa-chip-more qa-chip-custom'))
    .join('');
  return (
    '<div class="qa-dock" id="qa-dock">' +
      '<div class="qa-primary">' +
        primary +
      '</div>' +
      '<div class="qa-more-wrap">' +
        '<button type="button" class="qa-more-toggle" id="qa-more-toggle" title="更多 / 自定义" aria-expanded="false" aria-haspopup="true">' +
          '<span class="qa-more-dots">···</span>' +
        '</button>' +
        '<div class="qa-more-tray" id="qa-more-tray" hidden role="menu">' +
          moreBuiltin +
          moreCustom +
          '<button type="button" class="qa-chip qa-chip-more qa-chip-add" id="qa-add-custom" title="添加自定义动作">＋ 自定义</button>' +
        '</div>' +
      '</div>' +
    '</div>'
  );
}

function promptAddCustom() {
  const label = window.prompt('自定义按钮名称（≤8 字）', '');
  if (!label || !label.trim()) return null;
  const prompt = window.prompt(
    '点击后发给 Claude 的提示词（短一些更好）',
    '用中文简要说明：'
  );
  if (prompt == null) return null;
  return addCustomAction({
    label: label.trim().slice(0, 8),
    kind: 'prompt',
    prompt: prompt.trim() || '用中文简要说明当前情况。',
  });
}

export function bindFixedActions(root, { onBaseline, onPrompt, onSlash, onSoon, onTransfer }) {
  if (!root) return;
  root.querySelectorAll('[data-fixed]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-fixed');
      const act = findAction(id);
      if (!act) return;
      if (act.kind === 'baseline') onBaseline?.();
      else if (act.kind === 'prompt' && act.prompt) onPrompt?.(act.prompt);
      else if (act.kind === 'slash' && act.slash) onSlash?.(act.slash);
      else if (act.kind === 'transfer') onTransfer?.();
      else if (act.kind === 'soon') onSoon?.(act);
    });
  });
}

function setTrayOpen(mount, open) {
  const wrap = mount.querySelector('.qa-more-wrap');
  const tray = mount.querySelector('#qa-more-tray');
  const toggle = mount.querySelector('#qa-more-toggle');
  if (open) wrap?.classList.add('open');
  else wrap?.classList.remove('open');
  if (tray) tray.hidden = !open;
  toggle?.setAttribute('aria-expanded', open ? 'true' : 'false');
}

function rebindDock(mount, handlers, { keepOpen = false } = {}) {
  mount.innerHTML = renderComposerActionDock(_activePrimary);
  wireDockChrome(mount, handlers);
  bindFixedActions(mount, handlers);
  if (keepOpen) setTrayOpen(mount, true);
}

function wireDockChrome(mount, handlers) {
  const toggle = mount.querySelector('#qa-more-toggle');
  toggle?.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    const wrap = mount.querySelector('.qa-more-wrap');
    const willOpen = !wrap?.classList.contains('open');
    setTrayOpen(mount, willOpen);
  });

  mount.querySelector('#qa-add-custom')?.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    const item = promptAddCustom();
    if (!item) return;
    window.showToast?.('已添加：' + item.label, 'success');
    rebindDock(mount, handlers, { keepOpen: true });
  });
}

export function initComposerActionDock(handlers) {
  const host =
    document.getElementById('qa-dock-host') ||
    document.querySelector('.composer-toolbar');
  if (!host || document.getElementById('qa-dock')) return;

  const fullHandlers = {
    ...handlers,
    onSoon: (act) => {
      window.showToast?.(
        (act.label || '该功能') + '：即将支持（可先用「＋ 自定义」加自己的提示词）',
        'info'
      );
    },
  };

  const mount = document.createElement('div');
  mount.className = 'qa-dock-slot';
  host.appendChild(mount);

  const applyFit = () => {
    const w = host.clientWidth || host.getBoundingClientRect().width;
    const next = fitPrimaryIds(w);
    const keepOpen = mount.querySelector('.qa-more-wrap')?.classList.contains('open');
    if (sameIds(next, _activePrimary) && mount.querySelector('#qa-dock')) {
      return;
    }
    _activePrimary = next;
    rebindDock(mount, fullHandlers, { keepOpen });
  };

  // 首次渲染
  _activePrimary = fitPrimaryIds(host.clientWidth || 320);
  rebindDock(mount, fullHandlers);

  if (typeof ResizeObserver !== 'undefined') {
    let raf = 0;
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(applyFit);
    });
    ro.observe(host);
  } else {
    window.addEventListener('resize', applyFit);
  }

  // 点外侧关闭；用 pointerdown 避免与 toggle 的 click 打架
  document.addEventListener(
    'pointerdown',
    (e) => {
      const wrap = mount.querySelector('.qa-more-wrap');
      if (!wrap || !wrap.classList.contains('open')) return;
      if (wrap.contains(e.target)) return;
      setTrayOpen(mount, false);
    },
    true
  );
}

export function renderFixedActionButtons(ids = null) {
  const list = ids ? byIds(ids) : byIds(_activePrimary.length ? _activePrimary : PRIMARY_IDS);
  return list.map((a) => btnHtml(a, 'empty-state-btn')).join('');
}
