# Plan: cockpit-v0303-terminal — Cockpit v0.30.3 终端体验 + UI 美化

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

CCC Chat Server 的 Execute 模式采用聊天气泡样式展示执行结果，缺乏实时终端感。Cockpit Dashboard 的 CSS 是极简风格。

- **入口/核心文件**：
  - `scripts/ccc-chat-server.py`（1261 行）— FastAPI 应用，Chat/Execute/Board 三模式，HTML+CSS+JS 全内联于 `HTML_UI` 变量（494-1240 行）
  - `scripts/ccc-cockpit.py`（559 行）— Dashboard HTTP 服务器，服务端渲染 HTML

- **当前结构要点**：
  - Execute 模式后端（`ccc-chat-server.py:241-388`）：`/api/execute` 端点 → `claude -p` 子进程 → SSE 流式返回 JSON 事件（delta/tool_use/tool_result/cost/done）
  - Execute 模式前端渲染流（`HTML_UI` JS 内 `streamRequest()` 约 942-1060 行）：chat 气泡样式、markdown 渲染、工具调用以 `<details>` 卡片展示
  - 执行面板 HTML（约 754-764 行）：聊天气泡容器 `#exec-messages` + 输入区 `input-area`
  - **缺失功能**：无暗色终端背景、无命令提示符前缀、工具操作用 JSON 展示、无 diff 可视化、无文件变更摘要、流式输出无光标动画
  - v0.30.2 文件浏览器（planned）将重建 exec-panel 为 `exec-layout`（文件树侧栏 + exec-main），v0.30.3 需替换 exec-main 内部消息区为终端视图
  - Cockpit Dashboard（`ccc-cockpit.py`）CSS 风格极简，移动端适配较基础，无暗色模式

- **待改动点**（全在 `ccc-chat-server.py` 的 HTML_UI 内）：
  - Phase 1: Execute 面板全新终端式渲染（暗色背景、等宽字体、命令行前缀、流式输出光标动画、工具操作分段展示）
  - Phase 2: Diff 解析与彩色可视化（文件变更摘要行、增/删行绿/红高亮）
  - Phase 3: UI 全局美化 + 移动端适配（CSS 过渡动画、触控优化、视觉一致性、暗色模式）

---

## 范围

- **目标**：将 Execute 模式的聊天气泡展示改为类终端实时输出体验，支持 diff 彩色可视化和文件变更摘要，整体 UI 美化与移动端适配
- **只改文件**：
  - `scripts/ccc-chat-server.py`（Phase 1 + 2 + 3）
- **不改文件**：
  - `.ccc/infrastructure.md`、`.ccc/state.md`、`.ccc/profile.md`
  - `scripts/ccc-cockpit.py`、`scripts/ccc-board.py`、`scripts/ccc-board-server.py`
  - 其他任何脚本、测试、模板文件
- **执行方式**：`manual`
- **Phase 数**：3

---

## Phase 1：终端模式 Execute — 暗色终端面板 + 流式渲染

### 做什么
将 Execute 面板从聊天气泡模式改为暗色终端风格。用户指令显示为 `$` 命令行前缀，Claude 的思考和输出在等宽字体的黑底上实时流动，工具调用显示为分段展开区，整个体验让人感觉在观察一个开发者在终端工作。

### 怎么做

**CSS 新增**（`ccc-chat-server.py` HTML_UI 的 `<style>` 块，约 501-731 行）：

- `.terminal-output { background: #1a1b26; color: #a9b1d6; font-family: 'SF Mono','Menlo','Consolas',monospace; font-size: 13px; line-height: 1.7; padding: 14px; overflow-y: auto; flex: 1; }` — 终端主容器，暗紫深色背景
- `.terminal-prompt { color: #73daca; }` — 绿色 `$ ` 命令行前缀
- `.terminal-command { color: #c0caf5; font-weight: 500; }` — 命令行文本
- `.terminal-output-text { color: #c0caf5; white-space: pre-wrap; word-break: break-word; }` — 普通输出文本
- `.terminal-timestamp { color: #565f89; font-size: 11px; margin-right: 8px; }` — 时间戳
- `.terminal-cursor::after { content: '▊'; animation: term-blink 1s step-end infinite; color: #73daca; }` — 流式输出光标
- `@keyframes term-blink { 50% { opacity: 0; } }` — 光标闪烁
- `.terminal-tool-header { color: #7aa2f7; font-weight: 600; margin: 8px 0 4px; display: flex; align-items: center; gap: 6px; font-size: 12px; }` — 工具调用头
- `.terminal-tool-header .tool-status { font-size: 11px; color: #9ece6a; }` — 工具状态（running/done）
- `.terminal-tool-body { background: #1f2233; border-left: 3px solid #7aa2f7; border-radius: 4px; padding: 8px 12px; margin: 4px 0 10px; font-size: 12px; overflow-x: auto; }` — 工具体
- `.terminal-tool-body pre { margin: 0; font-size: 12px; color: #9aa5ce; }`
- `.terminal-separator { border: none; border-top: 1px solid #2f3346; margin: 6px 0; }` — 分隔线
- `.terminal-info { color: #565f89; font-size: 11px; }` — 元信息（tokens/cost）
- `.terminal-line { padding: 1px 0; }` — 每行基础
- 移除或保留 `.msg.execute` 系列样式（若冲突则替换，若保留则通过 hide 控制）

**Execute 面板 HTML 结构调整**（约 754-764 行，`<div id="exec-panel">`）：

- 当前结构：
```html
<div id="exec-panel" class="tab-panel">
  <div id="exec-messages"></div>
  ...
</div>
```
- v0.30.2 后结构（需兼容）：
```html
<div id="exec-panel" class="tab-panel">
  <div class="exec-layout">
    <div class="file-tree-panel">...</div>
    <div class="exec-main">
      <div id="exec-terminal" class="terminal-output"></div>
      <div id="input-area">...</div>
    </div>
  </div>
</div>
```
- 重点：用 `#exec-terminal` 替换 `#exec-messages`，`class="terminal-output"` 提供暗色终端样式
- 保留 `.exec-layout` / `.file-tree-panel` / `.exec-main` 的 v0.30.2 结构

**终端添加提示文字区域**（在 `#exec-terminal` 内作为初始化内容）：
- 默认显示 " CCC Execute Terminal\n输入指令开始执行..."
- 首次输入覆盖此提示

**JS 新增/修改**（`<script>` 块内，约 907 行 `sendExecute()` 起）：

- 修改 `sendExecute()`（约 929 行）：不再调用 `streamRequest('/api/execute', ...)`，改为调用 `terminalStream()` — 或保留 streamRequest 并传入渲染模式参数
- 新增 `async function terminalStream(messages, sessionId)`（约与 streamRequest 同级）：
  - 核心逻辑与 streamRequest 相同（fetch → SSE 读取）
  - 渲染差异：
    - **用户指令**：渲染为 `<div class="terminal-line"><span class="terminal-prompt">$ </span><span class="terminal-command">指令内容</span></div>`
    - **delta 文本**：逐字符追加到最后一个 `<div class="terminal-line terminal-output-text">` 内，末尾添加 `<span class="terminal-cursor"></span>`
    - 流结束时移除 cursor 元素
    - **tool_use**：渲染为 `<div class="terminal-tool-header"><span class="terminal-ts">12:34</span>  tool_name</div><div class="terminal-tool-body"><pre>input JSON</pre></div>`
    - 工具状态动画：tool_use 出现时 header 显示 "running..." 绿色状态，`tool_result` 收到后改为 "done "（修改已有 header 内容）
    - **tool_result**：追加到同级 `.terminal-tool-body` 的 `<pre>` 中
    - **cost/done**：渲染 `.terminal-separator` 分隔线 + `.terminal-info` 摘要："Tokens: X · $Y"
    - 自动滚动到 `#exec-terminal` 底部
  - 保持原有的 messages 追踪、session 保存、错误处理逻辑

- **工具图标映射**（新增字典/对象）：
  - `Bash` → ``，`Edit` → ``，`Read` → ``，`Write` → ``，`Think` → ``，其他 → ``
  - 在 terminal-tool-header 中使用对应图标

- **渲染模式选择**（可选方案）：在 `switchTab('execute')` 或 `sendExecute()` 中决定渲染模式：
  - 新增变量 `execRenderMode = 'terminal'`（未来可加 `'bubble'` 回退）
  - 加载历史对话时：检查 data.mode === 'execute'，按历史数据的渲染模式显示

**历史对话加载兼容**（约 1134 行 `loadSession()`）：
- 当 `mode === 'execute'` 且 `execRenderMode === 'terminal'` 时，将历史消息渲染为终端样式而非气泡样式
- 这需要通过 `_renderHistoryMessage(msg, container)` 函数，根据 msg.role 渲染为相应的 terminal-line

### 验收清单

- [ ] Execute 面板背景为暗色（深紫），等宽字体展示
- [ ] 用户指令前有 `$` 绿色前缀
- [ ] 输出内容实时逐字符流动，末尾有闪烁光标
- [ ] 工具调用以分段卡片显示，图标映射正确
- [ ] Bash 工具显示  图标，Edit 显示  图标
- [ ] 工具状态显示 running → done 变化
- [ ] 流结束时显示 tokens/cost 摘要
- [ ] 自动滚动跟随新内容
- [ ] 历史 execute 对话以终端风格加载
- [ ] 与 v0.30.2 文件树布局（exec-layout）兼容

### 验收

- [终端外观]（参考：打开 `/execute` 面板，观察暗色终端背景和等宽字体）
- [命令行前缀]（参考：输入指令，查看 `$` 绿色前缀出现）
- [工具调用可视化]（参考：执行含 Bash/Edit 的指令，观察 / 图标和状态动画）
- [流式光标]（参考：执行时长指令，观察末尾闪烁光标）
- [历史兼容]（参考：加载已保存的 execute 会话，显示终端样式）

---

## Phase 2：Diff 可视化 — 文件变更展示

### 做什么
当 Claude 执行文件编辑后，工具结果中包含的 diff 内容应被自动检测并以彩色方式展示。绿色行表示添加、红色行表示删除、文件路径以标签形式显示在 diff 区域顶部。同时提供文件变更摘要（"N 个文件变更，+M -K"）。

### 怎么做

**JS 新增 Diff 解析器**（`<script>` 块内，约与 `sendExecute()` 同级区域）：

```javascript
function parseDiff(text) {
  const files = [];
  let currentFile = null;

  const lines = text.split('\n');
  for (const line of lines) {
    const fileMatch = line.match(/^diff --git a\/(.+) b\/(.+)$/);
    if (fileMatch) {
      currentFile = { path: fileMatch[2], hunks: [], additions: 0, deletions: 0 };
      files.push(currentFile);
      continue;
    }
    const hunkMatch = line.match(/^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.+)?$/);
    if (hunkMatch && currentFile) {
      const hunk = { oldStart: +hunkMatch[1], oldLines: +(hunkMatch[2]||1), newStart: +hunkMatch[3], newLines: +(hunkMatch[4]||1), header: (hunkMatch[5]||'').trim(), lines: [] };
      currentFile.hunks.push(hunk);
      continue;
    }
    if (currentFile && currentFile.hunks.length > 0) {
      const hunk = currentFile.hunks[currentFile.hunks.length - 1];
      if (line.startsWith('+') && !line.startsWith('+++ ')) { hunk.lines.push({ type: 'add', text: line.slice(1) }); currentFile.additions++; }
      else if (line.startsWith('-') && !line.startsWith('--- ')) { hunk.lines.push({ type: 'del', text: line.slice(1) }); currentFile.deletions++; }
      else if (line.startsWith(' ')) { hunk.lines.push({ type: 'ctx', text: line.slice(1) }); }
      // Skip --- a/ and +++ b/ and \ No newline lines
    }
  }
  return files;
}
```

**JS 新增 Diff 渲染函数**：

```javascript
function renderDiff(files) {
  if (!files || files.length === 0) return '';
  let html = '';
  for (const f of files) {
    const totalChanged = f.additions + f.deletions;
    html += `<div class="diff-file">`;
    html += `<div class="diff-file-header"> ${escapeHtml(f.path)} <span class="diff-summary">+${f.additions} -${f.deletions}</span></div>`;
    for (const hunk of f.hunks) {
      html += `<div class="diff-hunk-header">@@ -${hunk.oldStart},${hunk.oldLines} +${hunk.newStart},${hunk.newLines} @@${hunk.header ? ' '+escapeHtml(hunk.header) : ''}</div>`;
      for (const line of hunk.lines) {
        const cls = line.type === 'add' ? 'diff-add' : (line.type === 'del' ? 'diff-del' : 'diff-ctx');
        const prefix = line.type === 'add' ? '+' : (line.type === 'del' ? '-' : ' ');
        html += `<div class="diff-line ${cls}"><span class="diff-prefix">${prefix}</span>${escapeHtml(line.text)}</div>`;
      }
    }
    html += `</div>`;
  }
  if (files.length > 1) {
    const totalAdd = files.reduce((s, f) => s + f.additions, 0);
    const totalDel = files.reduce((s, f) => s + f.deletions, 0);
    html = `<div class="diff-global-summary">${files.length} 个文件变更，+${totalAdd} -${totalDel}</div>` + html;
  }
  return html;
}
```

**CSS 新增 Diff 样式**（`<style>` 块内）：
- `.diff-file { margin: 12px 0; background: #1f2233; border-radius: 6px; overflow: hidden; }`
- `.diff-file-header { padding: 6px 12px; font-size: 12px; color: #7dcfff; background: #292e42; font-weight: 500; display: flex; justify-content: space-between; }`
- `.diff-summary { color: #9ece6a; font-size: 11px; }`
- `.diff-hunk-header { padding: 4px 12px; font-size: 11px; color: #565f89; background: #24283b; font-family: monospace; border-bottom: 1px solid #2f3346; }`
- `.diff-line { padding: 1px 12px; font-size: 12px; line-height: 1.6; font-family: 'SF Mono','Menlo',monospace; white-space: pre-wrap; display: flex; }`
- `.diff-prefix { width: 14px; flex-shrink: 0; text-align: center; }`
- `.diff-add { background: rgba(65, 179, 100, 0.12); color: #9ece6a; }`
- `.diff-del { background: rgba(245, 85, 85, 0.12); color: #f7768e; }`
- `.diff-ctx { color: #a9b1d6; }`
- `.diff-global-summary { padding: 6px 12px; font-size: 12px; color: #c0caf5; background: #292e42; border-radius: 6px; margin-bottom: 8px; text-align: center; }`

**集成到终端渲染**：
- 在 `terminalStream()` 中，当收到 `tool_result` 事件时：
  - 内容传入 `parseDiff()` 检测是否包含 diff 格式
  - 若检测到 diff（`files.length > 0`），调用 `renderDiff(files)` 生成 HTML
  - 渲染后的 diff 追加到当前 `.terminal-tool-body` 内
  - 若未检测到 diff，按普通文本追加

**集成到历史会话加载**：
- `_renderHistoryMessage()` 对 assistant 角色的 execute 消息内容，同样应用 `parseDiff` + `renderDiff` 检测

### 验收清单

- [ ] tool_result 中的 unified diff 被自动检测并彩色渲染
- [ ] 添加行以绿色背景 + 绿色文字 + `+` 前缀显示
- [ ] 删除行以红色背景 + 红色文字 + `-` 前缀显示
- [ ] 上下文行维持浅色
- [ ] diff 文件头显示文件名和 +N -M 统计
- [ ] 多个文件有全局摘要行 "N 个文件变更，+M -K"
- [ ] hunk 头（@@ -L +L @@）以淡蓝灰色显示
- [ ] 非 diff 内容的 tool_result 保持不变
- [ ] 历史会话的 diff 也正确渲染

### 验收

- [Diff 渲染]（参考：执行一个会修改代码文件的指令，观察终端中 diff 以绿/红展示）
- [文件统计]（参考：观察 "+3 -1" 类统计数字正确）
- [非误判]（参考：执行只打印信息的指令，确认无伪 diff 渲染）

---

## Phase 3：UI 美化 + 移动端适配

### 做什么
对 Chat Server 整体 UI 做视觉打磨：内容过渡动画、移动端触控优化、一致性检查（图标/颜色/间距）。让 Chats 和 Board 面板也享受与 Execute 面板同等品质的视觉体验。

### 怎么做

**CSS 过渡动画新增**（`<style>` 块内）：

- `.msg { animation: msg-fade-in 0.2s ease-out; }` — 新消息淡入（chat + board）
- `@keyframes msg-fade-in { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }`
- `.exec-main .terminal-output { transition: scroll-behavior 0.15s; }`
- `.tool-card { transition: border-color 0.2s, box-shadow 0.2s; }` — 工具卡片悬停增强
- `.tool-card:hover { border-color: var(--accent); box-shadow: 0 1px 6px rgba(0,122,255,0.1); }`

**移动端优化**（`@media(max-width:480px)` 已存在约 725 行，扩展/替换）：

```css
@media(max-width:480px) {
  #header { padding: 8px 10px; }
  #header h1 { font-size: 15px; }
  #project-select { max-width: 100px; font-size: 12px; }
  #messages, #exec-messages, .terminal-output { padding: 8px 10px; font-size: 12px; }
  #input-area { padding: 6px 10px; }
  #input-wrap { border-radius: 16px; padding: 4px 4px 4px 6px; }
  #input, #exec-input { font-size: 15px; }
  .msg .bubble { max-width: 92%; font-size: 13px; padding: 10px 12px; }
  .board-col { min-width: 180px; max-width: 180px; }
  #sidebar { width: 260px; left: -260px; }
  .tab-btn { font-size: 9px; }
  .tab-btn .tab-icon { font-size: 18px; }
  #footer-links { flex-direction: column; }
}
```

**新增 `@media(max-width: 768px)` 平板断点**：

```css
@media(max-width:768px) {
  .exec-layout { flex-direction: column; }
  .file-tree-panel { width: 100%; max-height: 160px; border-right: none; border-bottom: 1px solid var(--border); }
  #board-scroll { padding: 8px; gap: 8px; }
  .board-col { min-width: 160px; max-width: 160px; }
}
```

**全局视觉一致性检查与修复**：
- 统一所有标题、按钮、标签的 `font-size` 和 `font-weight`（使用已定义的 CSS 变量 `--text-secondary` 等）
- 确认 Chat/Execute/Board 三面板的间距、圆角、阴影一致
- 修复可能的前端错误：检查 `switchTab()`（853 行）在 Board 面板 `loadBoard()` 中处理异常
- 确保 `document.getElementById('board-offline')` 在板卡加载时正确处理状态切换

**暗色终端渲染背景统一**：
- Phase 1 新增 `.terminal-output` 背景色 `#1a1b26`，需保证该颜色不与现有 light mode 冲突
- 页面头部的颜色模式声明 `<meta name="color-scheme" content="light">`（已存在 499 行），`terminal-output` 使用固定暗色（不随系统模式变化）

**Checklist 增强**：
- 修复 `exec-cancel-btn` 的显示逻辑：当前 904 行 `showCancel()` 同时控制 chat 和 exec 的取消按钮，确保两个按钮独立正确显示
- 确保 `exec-panel` 中的 `#input-wrap` 在终端模式下保持浅色背景（与暗色终端体区分）

**状态栏/信息行增强**：
- 在 Chat 面板底部增加轻微状态指示（当前项目、tokens），位于输入框下方
- 在终端面板右下角新增小字号的项目路径指示

### 验收清单

- [ ] 新消息有淡入动画（非突兀出现）
- [ ] 工具卡片悬停有轻微高亮
- [ ] `480px` 以下手机布局：标题、输入框、按钮尺寸适配
- [ ] `768px` 以下平板布局：文件树在上方横向展示，看板列缩小
- [ ] 三个面板（Chat/Execute/Board）视觉风格一致（间距/圆角/阴影统一）
- [ ] Chat 面板的滚动和动画正常
- [ ] 回退到气泡模式的 `exec-messages` 样式不被误删（v0.30.2 兼容）

### 验收

- [动画]（参考：发送 chat 消息，观察淡入动画约 0.2s）
- [移动端]（参考：浏览器缩小至 375px 宽，观察布局适配）
- [平板端]（参考：浏览器缩小至 768px 宽，文件树变为顶部横栏）
- [视觉一致性]（参考：逐个切换 Chat/Execute/Board，感受统一质感）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | Execute 面板终端模式：暗色主题 + 流式渲染 + 工具操作可视化 | `feat(cockpit): 终端模式 Execute — 暗色面板 + 流式渲染 (phase 1/3)` |
| 2 | Diff 可视化：unified diff 解析 + 彩色行高亮 + 文件变更摘要 | `feat(cockpit): diff 可视化 — 文件变更彩色展示 (phase 2/3)` |
| 3 | UI 美化：动画过渡 + 移动端适配 + 视觉一致性 | `feat(cockpit): UI 美化 — 动画 + 移动适配 (phase 3/3)` |

规则：每个 phase 一个独立 commit，message 含 phase 编号。

---

## 全局验收清单

- [ ] Python 语法检查通过（参考：`python3 -m py_compile scripts/ccc-chat-server.py`）
- [ ] 重启 Chat Server 后页面正常展示，无 JS 错误
- [ ] Chat 模式不受改动影响，功能正常
- [ ] Board 模式不受改动影响，功能正常
- [ ] diff 范围仅限 `scripts/ccc-chat-server.py`
- [ ] 每个 phase 对应一个独立 commit
- [ ] phases.json 与 plan phase 数一致（3 个）
- [ ] Plan 中所有验收意图全部达成
- [ ] Phase 1/2/3 顺序依赖；不可跳过前置 phase

---

## 后续步骤

P1-P3 完成后，Execute 模式从「聊天气泡」进化为「终端式实时输出 + diff 可视化」。后续方向：

| 方向 | 说明 | 优先级 |
|------|------|--------|
| P4: 暗色模式全局化 | 支持 Chat/Board 面板也跟随暗色/亮色切换 | 低 |
| P5: 终端回放 | 录制备忘录会话为终端视频/GIF | 低 |
| P6: 多引擎支撑（v0.30.4） | 可切换 claude -p / opencode / cursor CLI | 中 |