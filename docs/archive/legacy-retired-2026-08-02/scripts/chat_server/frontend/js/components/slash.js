const COMMANDS = [
  { cmd: '/task', hint: '下达 CCC 看板任务', action: 'task' },
  { cmd: '/board', hint: '打开看板摘要', action: 'board' },
  { cmd: '/new', hint: '新建对话', action: 'new' },
  { cmd: '/export', hint: '导出当前对话为 Markdown', action: 'export' },
  { cmd: '/projects', hint: '打开设置切换项目', action: 'projects' },
];

export function handleSlashInput(input) {
  const val = input.value;
  if (!val.startsWith('/')) {
    hideSlashMenu();
    return;
  }
  const q = val.slice(1).toLowerCase();
  const matches = COMMANDS.filter(c => c.cmd.slice(1).startsWith(q) || c.hint.includes(q));
  showSlashMenu(matches, input);
}

export function showSlashMenu(items, input) {
  let menu = document.getElementById('slash-menu');
  if (!menu) {
    menu = document.createElement('div');
    menu.id = 'slash-menu';
    menu.className = 'slash-menu';
    document.getElementById('composer-inner')?.appendChild(menu);
  }
  if (!items.length) {
    hideSlashMenu();
    return;
  }
  menu.innerHTML = items.map((it, i) =>
    '<button type="button" class="slash-item' + (i === 0 ? ' active' : '') + '" data-cmd="' + it.cmd + '" data-action="' + it.action + '">' +
      '<span class="slash-cmd">' + it.cmd + '</span>' +
      '<span class="slash-hint">' + it.hint + '</span>' +
    '</button>'
  ).join('');
  menu.classList.add('open');

  menu.querySelectorAll('.slash-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const action = btn.dataset.action;
      input.value = '';
      input.dispatchEvent(new Event('input'));
      hideSlashMenu();
      executeAction(action);
    });
  });
}

export function hideSlashMenu() {
  const menu = document.getElementById('slash-menu');
  if (menu) menu.classList.remove('open');
}

export function tryExecuteSlash(text) {
  const raw = text.trim().split(/\s+/)[0].toLowerCase();
  const hit = COMMANDS.find(c => c.cmd === raw);
  if (!hit) return false;
  executeAction(hit.action);
  return true;
}

function executeAction(action) {
  if (action === 'task') {
    import('./taskDialog.js').then(m => m.openTaskDialog());
  } else if (action === 'board') {
    import('./boardPanel.js').then(m => m.openBoardPanel());
  } else if (action === 'new') {
    document.dispatchEvent(new CustomEvent('new-tab'));
  } else if (action === 'export') {
    import('./export.js').then(m => m.exportCurrentSession());
  } else if (action === 'projects') {
    import('./settings.js').then(m => m.openSettings());
  }
}
