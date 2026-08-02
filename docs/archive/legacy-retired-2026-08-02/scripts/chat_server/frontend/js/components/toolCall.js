/** Agent 进度条：单排图标滑动窗口 + 步骤一句话概要 + 文件改动计数 */

const MAX_ICONS = 10;

const TOOL_LABELS = {
  Read: '查阅文件',
  Glob: '查找文件',
  Grep: '搜索代码',
  Write: '写入文件',
  Edit: '修改文件',
  StrReplace: '修改文件',
  Bash: '运行命令',
  Shell: '运行命令',
  Task: '子任务',
  WebFetch: '读取网页',
  WebSearch: '检索资料',
  NotebookEdit: '编辑笔记',
  TodoWrite: '更新待办',
};

const TOOL_ICONS = {
  Read: '📄',
  Glob: '🔎',
  Grep: '🔎',
  Write: '✏️',
  Edit: '✏️',
  StrReplace: '✏️',
  Bash: '⌘',
  Shell: '⌘',
  Task: '▸',
  WebFetch: '🌐',
  WebSearch: '🌐',
  TodoWrite: '☑',
  default: '•',
};

const WRITE_TOOLS = new Set(['Write', 'Edit', 'StrReplace', 'NotebookEdit']);

function leafPath(p) {
  const s = String(p || '');
  const parts = s.split(/[/\\]/);
  return parts[parts.length - 1] || s;
}

function short(s, n = 36) {
  const t = String(s || '').replace(/\s+/g, ' ').trim();
  if (t.length <= n) return t;
  return t.slice(0, n - 1) + '…';
}

/** 从 tool input 拼一句话概要（纯前端，不耗 token） */
export function humanToolLabel(name, input) {
  const n = name || 'tool';
  const base = TOOL_LABELS[n] || '处理中';
  const inp = input && typeof input === 'object' ? input : {};

  const file =
    inp.file_path ||
    inp.path ||
    inp.target_file ||
    inp.file ||
    (Array.isArray(inp.paths) ? inp.paths[0] : null);
  if (file && (n === 'Read' || WRITE_TOOLS.has(n) || n === 'Glob')) {
    return base + ' · ' + leafPath(file);
  }
  if ((n === 'Bash' || n === 'Shell') && (inp.command || inp.cmd || inp.description)) {
    if (inp.description) return base + ' · ' + short(inp.description, 40);
    const cmd = String(inp.command || inp.cmd || '').trim();
    return base + (cmd ? ' · ' + short(cmd, 42) : '');
  }
  if (n === 'Grep' && (inp.pattern || inp.query)) {
    return '搜索 · ' + short(inp.pattern || inp.query, 28);
  }
  if (n === 'Glob' && inp.glob_pattern) {
    return base + ' · ' + short(inp.glob_pattern, 28);
  }
  if (n === 'WebSearch' && (inp.search_term || inp.query)) {
    return base + ' · ' + short(inp.search_term || inp.query, 28);
  }
  if (n === 'WebFetch' && inp.url) {
    try {
      return base + ' · ' + short(new URL(inp.url).hostname, 24);
    } catch {
      return base;
    }
  }
  if (n === 'Task' && (inp.description || inp.prompt)) {
    return base + ' · ' + short(inp.description || inp.prompt, 32);
  }
  return base;
}

function fileFromInput(input) {
  if (!input || typeof input !== 'object') return null;
  return (
    input.file_path ||
    input.path ||
    input.target_file ||
    input.file ||
    null
  );
}

export function createProgressRail() {
  const rail = document.createElement('div');
  rail.className = 'agent-progress';
  rail._fileSet = new Set();
  rail._iconCount = 0;
  rail.innerHTML =
    '<div class="agent-progress-top">' +
      '<div class="agent-progress-label">准备中…</div>' +
      '<div class="agent-progress-files" hidden></div>' +
    '</div>' +
    '<div class="agent-progress-icons" aria-hidden="true"></div>';
  return rail;
}

function updateFilesBadge(rail) {
  const el = rail.querySelector('.agent-progress-files');
  if (!el) return;
  const n = rail._fileSet?.size || 0;
  if (n <= 0) {
    el.hidden = true;
    el.textContent = '';
    return;
  }
  el.hidden = false;
  el.textContent = '✏️ ' + n + ' 文件';
  el.title = [...rail._fileSet].slice(0, 20).join('\n');
}

export function appendProgressStep(rail, toolData) {
  if (!rail) return null;
  const name = toolData.name || 'tool';
  const input = toolData.input;
  const icons = rail.querySelector('.agent-progress-icons');
  const label = rail.querySelector('.agent-progress-label');

  if (WRITE_TOOLS.has(name)) {
    const fp = fileFromInput(input);
    if (fp) rail._fileSet.add(fp);
    else rail._fileSet.add(name + '#' + (rail._fileSet.size + 1));
    updateFilesBadge(rail);
  }

  // 单排：超出窗口则移除最旧
  while (icons.children.length >= MAX_ICONS) {
    icons.removeChild(icons.firstElementChild);
  }

  const step = document.createElement('span');
  step.className = 'agent-progress-step running';
  step.title = humanToolLabel(name, input);
  step.textContent = TOOL_ICONS[name] || TOOL_ICONS.default;
  icons.appendChild(step);
  // 闪一下最新图标
  step.classList.add('just-added');
  requestAnimationFrame(() => {
    setTimeout(() => step.classList.remove('just-added'), 450);
  });

  if (label) {
    const summary = humanToolLabel(name, input);
    const nFiles = rail._fileSet?.size || 0;
    label.textContent =
      summary + (nFiles ? `  ·  已改 ${nFiles} 文件` : '');
  }
  rail.classList.remove('done', 'hidden');
  rail._iconCount = (rail._iconCount || 0) + 1;
  return step;
}

export function completeProgressStep(step, ok = true) {
  if (!step) return;
  step.classList.remove('running');
  step.classList.add(ok ? 'done' : 'error');
}

export function finishProgressRail(rail, { hide = true } = {}) {
  if (!rail) return;
  const label = rail.querySelector('.agent-progress-label');
  const nFiles = rail._fileSet?.size || 0;
  if (label) {
    label.textContent =
      nFiles > 0 ? `完成 · ✏️ ${nFiles} 个文件已修改` : '完成';
  }
  updateFilesBadge(rail);
  rail.classList.add('done');
  if (hide) {
    setTimeout(() => {
      rail.classList.add('hidden');
    }, 900);
  }
}

export function getProgressFileCount(rail) {
  return rail?._fileSet?.size || 0;
}

// 兼容旧导入名
export function createToolCard(toolData) {
  const rail = createProgressRail();
  appendProgressStep(rail, toolData);
  return rail;
}
export function updateToolCardStatus() {}
export function setToolResult() {}
export function createThinkingIndicator() {
  const el = document.createElement('div');
  el.className = 'agent-progress';
  el.innerHTML =
    '<div class="agent-progress-top"><div class="agent-progress-label">思考中…</div></div>' +
    '<div class="agent-progress-icons"></div>';
  return el;
}
