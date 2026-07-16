/** Agent 进度条：对人友好的短文案 + 图标序列（非工具明细卡）。 */

const TOOL_LABELS = {
  Read: '查阅文件',
  Glob: '查找文件',
  Grep: '搜索代码',
  Write: '写入文件',
  Edit: '修改文件',
  Bash: '运行命令',
  Shell: '运行命令',
  Task: '子任务',
  WebFetch: '读取网页',
  WebSearch: '检索资料',
  NotebookEdit: '编辑笔记',
};

const TOOL_ICONS = {
  Read: '📄',
  Glob: '🔎',
  Grep: '🔎',
  Write: '✏️',
  Edit: '✏️',
  Bash: '⌘',
  Shell: '⌘',
  Task: '▸',
  WebFetch: '🌐',
  WebSearch: '🌐',
  default: '•',
};

export function humanToolLabel(name, input) {
  const n = name || 'tool';
  const base = TOOL_LABELS[n] || '处理中';
  if ((n === 'Read' || n === 'Write' || n === 'Edit') && input && input.file_path) {
    const leaf = String(input.file_path).split('/').pop();
    return base + ' · ' + leaf;
  }
  if ((n === 'Bash' || n === 'Shell') && input && (input.command || input.cmd)) {
    const cmd = String(input.command || input.cmd).trim().split(/\s+/)[0];
    return base + (cmd ? ' · ' + cmd : '');
  }
  if (n === 'Grep' && input && input.pattern) {
    return '搜索 · ' + String(input.pattern).slice(0, 24);
  }
  return base;
}

export function createProgressRail() {
  const rail = document.createElement('div');
  rail.className = 'agent-progress';
  rail.innerHTML =
    '<div class="agent-progress-label">准备中…</div>' +
    '<div class="agent-progress-icons" aria-hidden="true"></div>';
  return rail;
}

export function appendProgressStep(rail, toolData) {
  if (!rail) return null;
  const name = toolData.name || 'tool';
  const icons = rail.querySelector('.agent-progress-icons');
  const label = rail.querySelector('.agent-progress-label');
  const step = document.createElement('span');
  step.className = 'agent-progress-step running';
  step.title = name;
  step.textContent = TOOL_ICONS[name] || TOOL_ICONS.default;
  icons.appendChild(step);
  if (label) {
    label.textContent = humanToolLabel(name, toolData.input);
  }
  rail.classList.remove('done', 'hidden');
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
  if (label) label.textContent = '完成';
  rail.classList.add('done');
  if (hide) {
    // 等一拍再藏，让用户看到「完成」
    setTimeout(() => {
      rail.classList.add('hidden');
    }, 600);
  }
}

// 兼容旧导入名（避免其它文件炸掉）
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
  el.innerHTML = '<div class="agent-progress-label">思考中…</div><div class="agent-progress-icons"></div>';
  return el;
}
