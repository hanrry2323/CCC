# CCC Chat Server v2 — 收尾 + 技术修复 + UI 打磨

> 一次性执行。严格按顺序执行。
>
> **关键**: 所有 edit 操作使用 `oldString` → `newString` 精确匹配。如果匹配失败，用 grep 确认当前文件内容后修正。

---

## Phase 0: 环境确认

```bash
cd /Users/apple/program/CCC
git status
```

---

## Phase 1: commit + 文档完善

### 1.1 .gitignore

```bash
echo "dashboard/" >> /Users/apple/program/CCC/.gitignore
```

### 1.2 更新 infrastructure.md

在 `/Users/apple/program/CCC/.ccc/infrastructure.md` 末尾追加：

```markdown
## CCC Chat Server v2（2026-07-15）

### 架构

```
scripts/ccc-chat-server.py          # 入口 (uvicorn.run)
scripts/chat_server/                # 模块化包
├── config.py                       # Pydantic 配置
├── models.py                       # 数据模型
├── auth.py                         # Basic Auth
├── app.py                          # FastAPI 工厂
├── routers/                        # 路由层
│   ├── chat.py                     # POST /api/chat SSE
│   ├── sessions.py                 # GET/DEL /api/history
│   ├── files.py                    # 文件浏览
│   ├── board.py                    # Board 代理
│   └── projects.py                 # 项目列表
├── services/                       # 服务层
│   ├── claude_client.py            # Claude 子进程 SSE
│   ├── session_store.py            # 会话持久化
│   └── board_client.py             # Board HTTP 客户端
└── frontend/                       # 纯前端 SPA
    ├── index.html
    ├── css/ (variables, base, themes, components)
    └── js/ (state, api, markdown, app + 5 components)
```

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects` | 项目列表 |
| POST | `/api/chat` | SSE 流式聊天 |
| POST | `/api/execute` | 执行模式 |
| GET | `/api/history` | 会话列表 |
| GET | `/api/history/{id}` | 单个会话 |
| DELETE | `/api/history/{id}` | 删除会话 |
| GET | `/api/projects/{id}/files` | 文件树 |
| GET | `/api/projects/{id}/file` | 文件内容 |
| GET | `/api/board/proxy/*` | Board 代理 |
| POST | `/api/board/proxy/*` | Board 代理 |
```

### 1.3 Commit 所有改动

```bash
cd /Users/apple/program/CCC
git add .gitignore
git add .ccc/infrastructure.md
git add scripts/ccc-chat-server.py
git add scripts/__init__.py
git add scripts/chat_server/
git add docs/chat-server-v2-cursor-prompt.md
git commit -m "feat(chat): v2 模块化重构 — 30-file modular backend + Codex-style frontend"
```

---

## Phase 2: 技术修复

### 2.1 Hamburger 菜单按钮 + 手机侧栏可打开

**问题**: `toggleMobileSidebar` 能关不能开，缺少 hamburger 按钮。

#### 2.1.1 index.html — 加 hamburger 按钮

匹配行（titlebar 区域）：

```
<button class="titlebar-btn" id="new-tab-btn" title="新对话">+</button>
```

替换为：

```
<button class="titlebar-btn" id="sidebar-toggle" title="侧栏">☰</button>
<button class="titlebar-btn" id="new-tab-btn" title="新对话">+</button>
```

#### 2.1.2 components.css — 加 hamburger 按钮桌面隐藏 + 手机侧栏过渡

在文件末尾追加：

```css
#sidebar-toggle {
  display: none;
}
@media (max-width: 768px) {
  #sidebar-toggle {
    display: flex;
  }
}
```

#### 2.1.3 index.html — 修复 toggleMobileSidebar 逻辑

将 `toggleMobileSidebar` 函数体：

```js
function toggleMobileSidebar() {
  document.getElementById('sidebar')?.classList.remove('open');
  document.querySelector('.sidebar-overlay')?.classList.remove('show');
}
```

替换为：

```js
function toggleMobileSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.querySelector('.sidebar-overlay');
  if (!sidebar) return;
  const isOpen = sidebar.classList.contains('open');
  sidebar.classList.toggle('open');
  if (overlay) overlay.classList.toggle('show');
  document.body.style.overflow = isOpen ? '' : 'hidden';
}
```

### 2.2 Edit 按钮暗色主题修复

**问题**: `.edit-save` 和 `.edit-cancel` 硬编码白色系，暗色主题不可见。

在 `components.css` 中找到：

```css
.edit-save { background: rgba(255,255,255,0.9); color: #007aff; }
.edit-cancel { background: rgba(255,255,255,0.2); color: rgba(255,255,255,0.8); }
```

替换为：

```css
.edit-save { background: var(--ccc-bg-accent); color: var(--ccc-text-inverse); }
.edit-cancel { background: var(--ccc-bg-layer); color: var(--ccc-text-muted); }
```

### 2.3 隐式全局 event 修复

**问题**: `message.js:24` 使用非标准的隐式全局 `window.event`。

在 `message.js` 中找到：

```js
div.addEventListener('dblclick', function () {
  if (event.target.closest('.edit-textarea, .edit-actions, button, .copy-btn')) return;
```

替换为：

```js
div.addEventListener('dblclick', function (e) {
  if (e.target.closest('.edit-textarea, .edit-actions, button, .copy-btn')) return;
```

### 2.4 冗余动态 import

#### 2.4.1 message.js — `setupCancel`

找到：

```js
export function setupCancel() {
  document.getElementById('cancel-btn')?.addEventListener('click', () => {
    import('../api.js').then(m => m.cancelStream());
```

替换为（保留静态 import 行 `import { streamChat, cancelStream } from '../api.js';` 已在文件顶部，直接引用）：

```js
export function setupCancel() {
  document.getElementById('cancel-btn')?.addEventListener('click', () => {
    cancelStream();
```

#### 2.4.2 composer.js — cancel handler

找到：

```js
  cancelBtn.addEventListener('click', () => {
    import('./message.js').then(m => {
      m.removeTyping();
```

替换为：

```js
  cancelBtn.addEventListener('click', () => {
    removeTyping();
```

并确保 `removeTyping` 已在静态 import 中（文件顶部已有 `import { sendMessage } from './message.js';` → 改为 `import { sendMessage, removeTyping } from './message.js';`）。

### 2.5 Dead code 清理

#### 2.5.1 utils.js — `debounce` 保留（Phase 3 会用），先不动

#### 2.5.2 message.js — 删无用 import `renderSidebar`

找到文件顶部：

```js
import { renderSidebar, refreshSidebar } from './sidebar.js';
```

替换为：

```js
import { refreshSidebar } from './sidebar.js';
```

#### 2.5.3 settings.js — 删无用 import `setupProjectSelect`

找到：

```js
import { state } from '../state.js';
import { loadProjects } from '../api.js';
import { setupProjectSelect } from './composer.js';
```

替换为：

```js
import { state } from '../state.js';
import { loadProjects } from '../api.js';
```

#### 2.5.4 titlebar.js — 删无用 import `generateId`

找到：

```js
import { state } from '../state.js';
import { generateId } from '../utils.js';
```

替换为：

```js
import { state } from '../state.js';
```

#### 2.5.5 titlebar.js — `renderTabs` 重构（内联 escapeDisplay）

找到：

```js
const title = t.title || '新对话';
    return '<div class="titlebar-tab' + (isActive ? ' active' : '') + '" data-tab-id="' + t.id + '">' +
      '<span>' + escapeDisplay(title) + '</span>' +
```

替换为（使用 `escapeHtml` 替代 `escapeDisplay`）：

```js
const title = t.title || '新对话';
    const safeTitle = String(title).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    return '<div class="titlebar-tab' + (isActive ? ' active' : '') + '" data-tab-id="' + t.id + '">' +
      '<span>' + safeTitle + '</span>' +
```

#### 2.5.6 titlebar.js — 删 `escapeDisplay` 函数

找到并删除整个函数：

```js
function escapeDisplay(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
```

### 2.6 markdown.js — 删重复 border-radius 内联样式

找到：

```js
h = h.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%;border-radius:8px;margin:8px 0;">');
```

替换为：

```js
h = h.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%;margin:8px 0;">');
```

### 2.7 搜索防抖

在 `sidebar.js` 中找到：

```js
export function setupSidebarSearch() {
  const input = document.getElementById('sidebar-search');
  if (!input) return;
  input.addEventListener('input', () => {
```

替换为：

```js
import { debounce } from '../utils.js';

export function setupSidebarSearch() {
  const input = document.getElementById('sidebar-search');
  if (!input) return;
  input.addEventListener('input', debounce(() => {
```

并找到对应结尾的 `});` 改为 `}, 200));`。

实际匹配：

```js
  input.addEventListener('input', () => {
    const q = input.value.toLowerCase();
    document.querySelectorAll('.session-item').forEach(el => {
      const title = el.querySelector('.session-item-title')?.textContent?.toLowerCase() || '';
      el.style.display = title.includes(q) ? '' : 'none';
    });
  });
}
```

替换为：

```js
  input.addEventListener('input', debounce(() => {
    const q = input.value.toLowerCase();
    document.querySelectorAll('.session-item').forEach(el => {
      const title = el.querySelector('.session-item-title')?.textContent?.toLowerCase() || '';
      el.style.display = title.includes(q) ? '' : 'none';
    });
  }, 200));
}
```

---

## Phase 3: UI 打磨到 Codex 级

### 3.1 Toast 通知系统

#### 3.1.1 新文件: frontend/js/components/toast.js

```javascript
let container = null;

function ensureContainer() {
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = [
      'position: fixed',
      'top: 52px',
      'right: 16px',
      'z-index: 200',
      'display: flex',
      'flex-direction: column',
      'gap: 8px',
      'max-width: 360px',
      'pointer-events: none',
    ].join(';');
    document.body.appendChild(container);
  }
  return container;
}

export function showToast(message, type = 'info', duration = 3000) {
  const c = ensureContainer();
  const el = document.createElement('div');
  const icons = { info: 'ℹ️', success: '✅', error: '❌', warning: '⚠️' };
  el.style.cssText = [
    'padding: 10px 16px',
    'border-radius: 10px',
    'font-size: 13px',
    'line-height: 1.4',
    'background: var(--ccc-bg-surface)',
    'color: var(--ccc-text-base)',
    'border: 0.5px solid var(--ccc-border-base)',
    'box-shadow: var(--ccc-shadow-floating)',
    'pointer-events: auto',
    'display: flex',
    'align-items: center',
    'gap: 8px',
    'animation: msg-in 0.2s ease-out',
    'backdrop-filter: blur(20px)',
    'max-width: 100%',
  ].join(';');
  el.innerHTML = '<span>' + (icons[type] || '') + '</span><span>' + message + '</span>';
  c.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateX(20px)';
    el.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
    setTimeout(() => el.remove(), 200);
  }, duration);
}

window.showToast = showToast;
```

#### 3.1.2 components.css — Toast 样式追加

```css
#toast-container {
  position: fixed;
  top: 52px;
  right: 16px;
  z-index: 200;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 360px;
  pointer-events: none;
}
#toast-container > * {
  pointer-events: auto;
}
```

### 3.2 空状态

在 `components.css` 末尾追加：

```css
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--ccc-text-faint);
  text-align: center;
  padding: 32px;
  gap: 8px;
}
.empty-state-icon {
  font-size: 36px;
  margin-bottom: 8px;
  opacity: 0.4;
}
.empty-state-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--ccc-text-muted);
}
.empty-state-hint {
  font-size: 13px;
  max-width: 260px;
  line-height: 1.5;
}
```

在 `message.js` 中找到 `loadMessages` 函数。在函数开头 `const container = document.getElementById('messages');` 之后，加一段空状态检查。

具体：找到 `loadMessages` 函数：

```js
export function loadMessages(data) {
  const container = document.getElementById('messages');
  container.innerHTML = '';
```

在 `container.innerHTML = '';` 之后追加空状态检查逻辑。

找到：

```js
export function loadMessages(data) {
  const container = document.getElementById('messages');
  container.innerHTML = '';
  const msgs = data.messages || [];
```

替换为：

```js
export function loadMessages(data) {
  const container = document.getElementById('messages');
  container.innerHTML = '';
  const msgs = data.messages || [];
  if (msgs.length === 0) {
    container.innerHTML = '<div class="empty-state">' +
      '<div class="empty-state-icon">💬</div>' +
      '<div class="empty-state-title">开始一个新对话</div>' +
      '<div class="empty-state-hint">在下方输入消息，或从侧栏选择一个已有对话</div>' +
      '</div>';
  }
```

同时需要在首次加载时也显示空状态。找到 `app.js` 中 `document.addEventListener('project-change', ...)` 事件处理，在 `container.innerHTML = '';` 后追加空状态：

```js
  document.addEventListener('project-change', () => {
    const container = document.getElementById('messages');
    container.innerHTML = '';
    container.innerHTML = '<div class="empty-state">' +
      '<div class="empty-state-icon">💬</div>' +
      '<div class="empty-state-title">开始一个新对话</div>' +
      '<div class="empty-state-hint">在下方输入消息，或从侧栏选择一个已有对话</div>' +
      '</div>';
```

### 3.3 键盘快捷键系统

#### 3.3.1 新文件: frontend/js/components/keyboard.js

```javascript
import { state } from '../state.js';
import { showToast } from './toast.js';

export function initKeyboard() {
  document.addEventListener('keydown', (e) => {
    const isMac = navigator.platform.includes('Mac');
    const mod = isMac ? e.metaKey : e.ctrlKey;

    // Cmd/Ctrl + K — 搜索
    if (mod && e.key === 'k') {
      e.preventDefault();
      const searchInput = document.getElementById('sidebar-search');
      if (searchInput) {
        searchInput.focus();
        searchInput.select();
      }
    }

    // Cmd/Ctrl + N — 新对话
    if (mod && e.key === 'n') {
      e.preventDefault();
      const event = new CustomEvent('new-tab');
      document.dispatchEvent(event);
    }

    // Cmd/Ctrl + Shift + Delete — 清空对话
    if (mod && e.shiftKey && e.key === 'Delete') {
      e.preventDefault();
      const container = document.getElementById('messages');
      if (container) {
        container.innerHTML = '<div class="empty-state">' +
          '<div class="empty-state-icon">💬</div>' +
          '<div class="empty-state-title">开始一个新对话</div>' +
          '<div class="empty-state-hint">在下方输入消息，或从侧栏选择一个已有对话</div>' +
          '</div>';
      }
      state.set('currentMessages', []);
      showToast('对话已清空', 'info');
    }

    // ↑ (在 composer 为空时) — 编辑上一条用户消息
    if (e.key === 'ArrowUp' && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
      const input = document.getElementById('composer-input');
      if (input && input === document.activeElement && input.value === '') {
        const msgs = state.get('currentMessages') || [];
        const lastUser = [...msgs].reverse().find(m => m.role === 'user');
        if (lastUser && lastUser.content) {
          input.value = lastUser.content;
          input.dispatchEvent(new Event('input'));
          input.focus();
          input.setSelectionRange(input.value.length, input.value.length);
        }
      }
    }

    // Escape — 关闭设置 / 取消编辑
    if (e.key === 'Escape') {
      const dialog = document.querySelector('.settings-dialog');
      if (dialog) {
        dialog.querySelector('.settings-close')?.click();
      }
    }
  });
}
```

### 3.4 代码块增强（行号 + 语言标签）

在 `markdown.js` 中找到代码块处理：

```js
    const langClass = lang ? ' class="lang-' + lang + '"' : '';
    codeBlocks.push(
      '<div class="code-block-wrap">' +
      '<pre><code' + langClass + '>' + code + '</code></pre>' +
      '<button class="copy-btn" onclick="copyCode(this)">复制</button>' +
      '</div>'
    );
```

替换为：

```js
    const langLabel = lang ? '<span class="code-lang-label">' + lang + '</span>' : '';
    codeBlocks.push(
      '<div class="code-block-wrap">' +
      langLabel +
      '<pre><code>' + code + '</code></pre>' +
      '<button class="copy-btn" onclick="copyCode(this)">复制</button>' +
      '</div>'
    );
```

并在 `components.css` 末尾追加：

```css
.code-lang-label {
  position: absolute;
  top: 0;
  right: 0;
  padding: 2px 10px;
  font-size: 11px;
  font-family: var(--ccc-font-mono);
  color: var(--ccc-text-faint);
  background: var(--ccc-bg-layer);
  border-radius: 0 var(--ccc-radius-md) 0 var(--ccc-radius-sm);
  text-transform: lowercase;
  letter-spacing: 0.3px;
}
.code-block-wrap {
  position: relative;
  margin: 8px 0;
}
.code-block-wrap .copy-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 2px 8px;
  font-size: var(--ccc-font-size-xs);
  color: var(--ccc-text-faint);
  background: var(--ccc-bg-layer);
  border: 0.5px solid var(--ccc-border-base);
  border-radius: var(--ccc-radius-sm);
  cursor: pointer;
  opacity: 0;
  transition: opacity var(--ccc-transition-fast);
  z-index: 1;
}
.code-block-wrap:hover .copy-btn {
  opacity: 1;
}
```

### 3.5 毛玻璃标题栏

在 `components.css` 中找到 `#titlebar`：

```css
#titlebar {
  display: flex;
  align-items: center;
  height: var(--ccc-titlebar-h);
  padding: 0 var(--ccc-space-sm);
  background: var(--ccc-bg-base);
  border-bottom: 0.5px solid var(--ccc-border-base);
  flex-shrink: 0;
  gap: 2px;
  -webkit-app-region: drag;
}
```

替换为：

```css
#titlebar {
  display: flex;
  align-items: center;
  height: var(--ccc-titlebar-h);
  padding: 0 var(--ccc-space-sm);
  background: color-mix(in srgb, var(--ccc-bg-base) 85%, transparent);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 0.5px solid var(--ccc-border-base);
  flex-shrink: 0;
  gap: 2px;
  -webkit-app-region: drag;
  position: sticky;
  top: 0;
  z-index: 10;
}
```

### 3.6 设置弹窗加载态

在 `components.css` 末尾追加：

```css
.settings-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  gap: 8px;
  color: var(--ccc-text-faint);
  font-size: 13px;
}
.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--ccc-border-base);
  border-top-color: var(--ccc-text-accent);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
```

在 `settings.js` 中，找到 `openSettings` 函数。在 `const projects = await loadProjects();` 前加加载动画。

找到：

```js
  const projects = await loadProjects();

  const dialog = document.createElement('div');
```

替换为：

```js
  // Show loading state
  const dialog = document.createElement('div');
  dialog.innerHTML = '<div class="settings-panel"><div class="settings-loading"><div class="spinner"></div><span>加载中...</span></div></div>';
  dialog.className = 'settings-dialog';
  dialog.style.cssText = 'position:fixed;inset:0;z-index:100;display:flex;align-items:center;justify-content:center;';
  document.body.appendChild(dialog);

  const projects = await loadProjects();

  // Remove loading, render real content
  dialog.innerHTML = '';
  dialog.style.cssText = '';
```

### 3.7 消息分组（同角色连续合并）

在 `message.js` 中，找到 `renderMessage` 函数。我们需要检查最后一条消息的 role，如果相同则追加到已有 bubble。

找到：

```js
export function renderMessage(container, role, content) {
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML = '<div class="bubble">' + renderMarkdown(content) + '</div>' +
    '<div class="time">' + ts() + '</div>';
  container.appendChild(div);
```

替换为：

```js
export function renderMessage(container, role, content) {
  // Group consecutive messages from same role
  const lastMsg = container.lastElementChild;
  if (lastMsg && lastMsg.classList.contains(role) && role === 'assistant') {
    const bubble = lastMsg.querySelector('.bubble');
    if (bubble) {
      // Append to existing bubble with separator
      const divider = document.createElement('hr');
      divider.style.cssText = 'margin:8px 0;border:none;border-top:0.5px solid var(--ccc-border-subtle);';
      bubble.appendChild(divider);
      const fragment = document.createElement('span');
      fragment.innerHTML = renderMarkdown(content);
      bubble.appendChild(fragment);
      // Update time
      const timeEl = lastMsg.querySelector('.time');
      if (timeEl) timeEl.textContent = ts();
      return lastMsg;
    }
  }

  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML = '<div class="bubble">' + renderMarkdown(content) + '</div>' +
    '<div class="time">' + ts() + '</div>';
  container.appendChild(div);
```

### 3.8 消息平滑 reflow 动画

在 `base.css` 中找到 `@keyframes msg-in` 增强：

原始：
```css
@keyframes msg-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
```

替换为：

```css
@keyframes msg-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
```

并为消息容器加 CSS 过渡：

在 `components.css` 中找到 `#messages`：

```css
#messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--ccc-space-lg);
  padding-bottom: var(--ccc-space-sm);
  display: flex;
  flex-direction: column;
  gap: var(--ccc-space-md);
}
```

在 `gap` 属性后追加一行：

```css
  scroll-behavior: smooth;
```

### 3.9 启动时集成键盘快捷键

在 `app.js` 中，找到 `init` 函数开头，在 `initTitlebar(); initComposer(); setupCancel(); setupSidebarSearch();` 后加：

```js
  import('./components/keyboard.js').then(m => m.initKeyboard());
```

（使用 dynamic import 避免页面加载阻塞）

### 3.10 Toast 错误替换 console.warn

在 `app.js` 中找到所有 `console.warn` 替换为 toast。

找到：

```js
    console.warn('Failed to load projects', e);
```

替换为：

```js
    window.showToast('项目加载失败: ' + e.message, 'error');
```

找到：

```js
      console.warn('Failed to load session', e);
```

替换为：

```js
      window.showToast('加载对话失败', 'error');
```

---

## Phase 4: 验证

```bash
cd /Users/apple/program/CCC

# Step 4.1: Python 语法检查
echo "=== Python 语法检查 ==="
python3 -c "import ast; ast.parse(open('scripts/ccc-chat-server.py').read()); print('OK: entry')"
python3 -c "import ast; ast.parse(open('scripts/chat_server/config.py').read()); print('OK: config')"
python3 -c "import ast; ast.parse(open('scripts/chat_server/models.py').read()); print('OK: models')"
python3 -c "import ast; ast.parse(open('scripts/chat_server/auth.py').read()); print('OK: auth')"
python3 -c "import ast; ast.parse(open('scripts/chat_server/services/session_store.py').read()); print('OK: session_store')"
python3 -c "import ast; ast.parse(open('scripts/chat_server/services/claude_client.py').read()); print('OK: claude_client')"
python3 -c "import ast; ast.parse(open('scripts/chat_server/services/board_client.py').read()); print('OK: board_client')"
python3 -c "import ast; ast.parse(open('scripts/chat_server/routers/chat.py').read()); print('OK: chat')"
python3 -c "import ast; ast.parse(open('scripts/chat_server/routers/sessions.py').read()); print('OK: sessions')"
python3 -c "import ast; ast.parse(open('scripts/chat_server/routers/files.py').read()); print('OK: files')"
python3 -c "import ast; ast.parse(open('scripts/chat_server/routers/board.py').read()); print('OK: board')"
python3 -c "import ast; ast.parse(open('scripts/chat_server/routers/projects.py').read()); print('OK: projects')"
python3 -c "import ast; ast.parse(open('scripts/chat_server/app.py').read()); print('OK: app')"

# Step 4.2: Python import 检查
echo "=== Python import 检查 ==="
python3 -c "from scripts.chat_server.app import create_app; app = create_app(); print('OK:', len(app.routes), 'routes')"

# Step 4.3: JS 语法检查（仅检查模块是否能 parse）
echo "=== JS 文件存在性检查 ==="
ls -la scripts/chat_server/frontend/js/components/toast.js
ls -la scripts/chat_server/frontend/js/components/keyboard.js

# Step 4.4: 启动服务测试
echo "=== 启动测试 ==="
# Kill old process
lsof -ti:8084 | xargs kill -9 2>/dev/null || true
sleep 1

python3 scripts/ccc-chat-server.py --no-open &
SERVER_PID=$!
sleep 3

echo "=== API 测试 ==="
curl -s -u ccc:claude2026 http://localhost:8084/api/projects | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK: projects:', len(d['projects']), 'projects')"

echo "=== 前端 200 检查 ==="
for path in / /css/variables.css /css/base.css /css/themes.css /css/components.css /js/app.js /js/api.js /js/markdown.js /js/state.js /js/utils.js /js/components/toast.js /js/components/keyboard.js /js/components/composer.js /js/components/message.js /js/components/sidebar.js /js/components/settings.js /js/components/titlebar.js; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -u ccc:claude2026 "http://localhost:8084${path}")
  echo "  $code $path"
done

echo "=== SSE 流测试 ==="
timeout 8 curl -s -u ccc:claude2026 -X POST http://localhost:8084/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Say hello in 2 words"}],"session_id":"polish-verify"}' | head -5

kill $SERVER_PID 2>/dev/null || true
echo ""
echo "=== ALL DONE ==="
```

---

## 附录：Phase 2/3 文件修改清单

| 文件 | 操作 |
|------|------|
| `scripts/chat_server/frontend/index.html` | edit (hamburger + toggleMobileSidebar) |
| `scripts/chat_server/frontend/css/components.css` | edit (4处: hamburger显示、edit颜色、毛玻璃、代码块label) |
| `scripts/chat_server/frontend/css/base.css` | edit (msg-in 动画增强) |
| `scripts/chat_server/frontend/js/components/message.js` | edit (4处: event参数、renderSidebar import、消息分组、setupCancel) |
| `scripts/chat_server/frontend/js/components/composer.js` | edit (2处: import + cancel handler) |
| `scripts/chat_server/frontend/js/components/settings.js` | edit (2处: 无用import、加载态) |
| `scripts/chat_server/frontend/js/components/titlebar.js` | edit (3处: 无用import、renderTabs内联、删escapeDisplay) |
| `scripts/chat_server/frontend/js/components/sidebar.js` | edit (搜索防抖) |
| `scripts/chat_server/frontend/js/markdown.js` | edit (2处: 图片style、代码块增强) |
| `scripts/chat_server/frontend/js/app.js` | edit (2处: console.warn->toast、空状态project-change) |
| `scripts/chat_server/frontend/js/components/toast.js` | **新文件** |
| `scripts/chat_server/frontend/js/components/keyboard.js` | **新文件** |
| `.gitignore` | append |
| `.ccc/infrastructure.md` | append |
