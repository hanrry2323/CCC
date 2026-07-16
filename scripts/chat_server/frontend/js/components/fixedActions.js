/** 固定动作：composer 工具条主按钮 + Dock 式伸缩「更多」。
 *
 * 主 4：对齐基线 · 下一步建议 · 起草任务 · 下达任务
 * 更多：扫风险 · 解释未提交 · 查看看板
 * 自定义排序：暂不实现（复杂度高、收益低）；顺序写死在 PRIMARY_IDS / MORE_IDS。
 */

export const FIXED_ACTIONS = [
  {
    id: 'baseline',
    label: '对齐基线',
    kind: 'baseline',
    primary: true,
  },
  {
    id: 'next',
    label: '下一步',
    kind: 'prompt',
    primary: true,
    prompt:
      '基于当前仓库与本会话已对齐的信息，用中文给出「下一步开发」建议。\n' +
      '要求：总字数 ≤200；列出 3 个选项 + 一行「最佳：…」；每条≤20字；不要代码块。\n' +
      '若本会话尚未对齐基线，先用一句点明假设再给建议。',
  },
  {
    id: 'draft-task',
    label: '起草任务',
    kind: 'prompt',
    primary: true,
    prompt:
      '把「当前最值得做的一件事」起草成可下达的 CCC 任务。\n' +
      '只输出：\n标题：…\n描述：…（≤120字，含验收意图）\n复杂度：small|medium|large\n' +
      '不要解释过程。',
  },
  {
    id: 'task',
    label: '下达任务',
    kind: 'slash',
    primary: true,
    slash: '/task',
  },
  {
    id: 'risks',
    label: '扫风险',
    kind: 'prompt',
    primary: false,
    prompt:
      '快速扫描当前项目风险（git 脏文件、明显坏味道、控制面/自动化隐患）。\n' +
      '要求：总字数 ≤180；只列会踩坑的项；无则写「无明显风险」；最后给 1 句处理建议。',
  },
  {
    id: 'explain-diff',
    label: '解释未提交',
    kind: 'prompt',
    primary: false,
    prompt:
      '解释当前未提交改动在做什么（git status / diff）。\n' +
      '要求：≤180字；按文件点名；风险一句；是否建议先 commit。',
  },
  {
    id: 'board',
    label: '看板',
    kind: 'slash',
    primary: false,
    slash: '/board',
  },
];

export const PRIMARY_IDS = ['baseline', 'next', 'draft-task', 'task'];
export const MORE_IDS = ['risks', 'explain-diff', 'board'];

function byIds(ids) {
  return ids.map((id) => FIXED_ACTIONS.find((a) => a.id === id)).filter(Boolean);
}

function btnHtml(a, cls) {
  return (
    '<button type="button" class="' +
    cls +
    '" data-fixed="' +
    a.id +
    '" title="' +
    a.label +
    '">' +
    a.label +
    '</button>'
  );
}

/** 渲染 composer 旁的动作条 HTML */
export function renderComposerActionDock() {
  const primary = byIds(PRIMARY_IDS)
    .map((a) => btnHtml(a, 'qa-chip qa-chip-primary'))
    .join('');
  const more = byIds(MORE_IDS)
    .map((a) => btnHtml(a, 'qa-chip qa-chip-more'))
    .join('');
  return (
    '<div class="qa-dock" id="qa-dock">' +
      '<div class="qa-primary">' +
        primary +
      '</div>' +
      '<div class="qa-more-wrap">' +
        '<button type="button" class="qa-more-toggle" id="qa-more-toggle" title="更多动作" aria-expanded="false">' +
          '<span class="qa-more-dots">···</span>' +
        '</button>' +
        '<div class="qa-more-tray" id="qa-more-tray" hidden>' +
          more +
        '</div>' +
      '</div>' +
    '</div>'
  );
}

export function bindFixedActions(root, { onBaseline, onPrompt, onSlash }) {
  if (!root) return;
  root.querySelectorAll('[data-fixed]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-fixed');
      const act = FIXED_ACTIONS.find((a) => a.id === id);
      if (!act) return;
      if (act.kind === 'baseline') onBaseline?.();
      else if (act.kind === 'prompt' && act.prompt) onPrompt?.(act.prompt);
      else if (act.kind === 'slash' && act.slash) onSlash?.(act.slash);
    });
  });
}

export function initComposerActionDock(handlers) {
  const toolbar = document.querySelector('.composer-toolbar');
  if (!toolbar || document.getElementById('qa-dock')) return;

  const mount = document.createElement('div');
  mount.className = 'qa-dock-slot';
  mount.innerHTML = renderComposerActionDock();
  // 插在 model-select 后面
  const model = toolbar.querySelector('#model-select') || toolbar.firstElementChild;
  if (model && model.nextSibling) {
    toolbar.insertBefore(mount, model.nextSibling);
  } else {
    toolbar.appendChild(mount);
  }

  bindFixedActions(mount, handlers);

  const toggle = mount.querySelector('#qa-more-toggle');
  const tray = mount.querySelector('#qa-more-tray');
  const wrap = mount.querySelector('.qa-more-wrap');
  toggle?.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = wrap?.classList.toggle('open');
    if (tray) tray.hidden = !open;
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  });

  document.addEventListener('click', (e) => {
    if (!wrap || wrap.contains(e.target)) return;
    wrap.classList.remove('open');
    if (tray) tray.hidden = true;
    toggle?.setAttribute('aria-expanded', 'false');
  });
}

/** @deprecated 空态用；保留兼容 */
export function renderFixedActionButtons(ids = null) {
  const list = ids
    ? FIXED_ACTIONS.filter((a) => ids.includes(a.id))
    : FIXED_ACTIONS.filter((a) => a.primary);
  return list.map((a) => btnHtml(a, 'empty-state-btn')).join('');
}
