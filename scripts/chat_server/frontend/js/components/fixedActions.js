/** 固定动作：composer 主栏 6 + Dock「更多」（内置 + 可自定义）。
 *
 * 主 6：对齐基线 · 下一步 · 扫风险 · 起草任务 · 解释未提交 · 下达任务
 * 更多：看板 · 定时任务(占位) · 创建 Skill(占位) · 用户自定义…
 *
 * 自定义存 localStorage: ccc_qa_custom_v1
 * 格式: [{ id, label, kind: 'prompt'|'slash', prompt?, slash? }]
 */

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
    id: 'draft-task',
    label: '起草任务',
    kind: 'prompt',
    prompt:
      '把「当前最值得做的一件事」起草成可下达的 CCC 任务。\n' +
      '只输出：\n标题：…\n描述：…（≤120字，含验收意图）\n复杂度：small|medium|large\n' +
      '不要解释过程。',
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

/** 主栏固定 6 个（日常闭环） */
export const PRIMARY_IDS = [
  'baseline',
  'next',
  'risks',
  'draft-task',
  'explain-diff',
  'task',
];

/** 更多里的内置项（不含用户自定义） */
export const MORE_BUILTIN_IDS = ['board', 'schedule', 'new-skill'];

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

export function renderComposerActionDock() {
  const primary = byIds(PRIMARY_IDS)
    .map((a) => btnHtml(a, 'qa-chip qa-chip-primary'))
    .join('');
  const custom = loadCustomActions();
  const moreBuiltin = byIds(MORE_BUILTIN_IDS)
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
        '<button type="button" class="qa-more-toggle" id="qa-more-toggle" title="更多 / 自定义" aria-expanded="false">' +
          '<span class="qa-more-dots">···</span>' +
        '</button>' +
        '<div class="qa-more-tray" id="qa-more-tray" hidden>' +
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

export function bindFixedActions(root, { onBaseline, onPrompt, onSlash, onSoon }) {
  if (!root) return;
  root.querySelectorAll('[data-fixed]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-fixed');
      const act = findAction(id);
      if (!act) return;
      if (act.kind === 'baseline') onBaseline?.();
      else if (act.kind === 'prompt' && act.prompt) onPrompt?.(act.prompt);
      else if (act.kind === 'slash' && act.slash) onSlash?.(act.slash);
      else if (act.kind === 'soon') onSoon?.(act);
    });
  });
}

function rebindDock(mount, handlers) {
  mount.innerHTML = renderComposerActionDock();
  wireDockChrome(mount, handlers);
  bindFixedActions(mount, handlers);
}

function wireDockChrome(mount, handlers) {
  const toggle = mount.querySelector('#qa-more-toggle');
  const tray = mount.querySelector('#qa-more-tray');
  const wrap = mount.querySelector('.qa-more-wrap');
  toggle?.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = wrap?.classList.toggle('open');
    if (tray) tray.hidden = !open;
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  });

  mount.querySelector('#qa-add-custom')?.addEventListener('click', (e) => {
    e.stopPropagation();
    const item = promptAddCustom();
    if (!item) return;
    window.showToast?.('已添加：' + item.label, 'success');
    rebindDock(mount, handlers);
    // 保持更多展开
    const w = mount.querySelector('.qa-more-wrap');
    const t = mount.querySelector('#qa-more-tray');
    const tg = mount.querySelector('#qa-more-toggle');
    w?.classList.add('open');
    if (t) t.hidden = false;
    tg?.setAttribute('aria-expanded', 'true');
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
  mount.innerHTML = renderComposerActionDock();
  host.appendChild(mount);

  wireDockChrome(mount, fullHandlers);
  bindFixedActions(mount, fullHandlers);

  document.addEventListener('click', (e) => {
    const wrap = mount.querySelector('.qa-more-wrap');
    const tray = mount.querySelector('#qa-more-tray');
    const toggle = mount.querySelector('#qa-more-toggle');
    if (!wrap || wrap.contains(e.target)) return;
    wrap.classList.remove('open');
    if (tray) tray.hidden = true;
    toggle?.setAttribute('aria-expanded', 'false');
  });
}

export function renderFixedActionButtons(ids = null) {
  const list = ids ? byIds(ids) : byIds(PRIMARY_IDS);
  return list.map((a) => btnHtml(a, 'empty-state-btn')).join('');
}
