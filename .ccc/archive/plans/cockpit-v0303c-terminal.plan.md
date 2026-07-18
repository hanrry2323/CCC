# Plan: cockpit-v0303c-terminal — 终端模式边缘清理 + 稳定性打磨

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-chat-server.py`（2124 行，FastAPI + 内嵌 HTML/CSS/JS 单文件）
- **当前结构要点**：
  - v0303a-design + v0303b-chatui 完成后，终端模式的**骨架功能已存在**：
    - 终端暗色主题 CSS（`.terminal-output`、`.terminal-prompt`、`.terminal-cursor` 等）— 行 825-853
    - `terminalStream()` 完整 SSE 流式渲染函数 — 行 1559-1709
    - 辅助函数：`renderTerminalCommand()`、`appendTerminalInfo()`、`appendTerminalSeparator()`、`resetTerminal()`、`renderTerminalHistory()` — 行 1460-1749
    - Diff 解析/渲染：`parseDiff()`（行 1498-1533）、`renderDiff()`（行 1535-1557）
    - 工具图标字典 `TOOL_ICONS` — 行 1441-1444
    - `sendExecute()` 使用 `terminalStream()` 而非 `streamRequest()` — 行 1751-1762
    - HTML 结构：`exec-layout` → `file-tree-panel` + `exec-main` → `exec-terminal` — 行 1076-1099
    - UI 动画（`msg-fade-in`、`tool-card:hover`）— 行 820-823
    - 响应式断点（480px/768px）— 行 1021-1052
  - **已实现但存在边缘 bug 的遗留问题**：
    - `cancelStream()` 不对终端模式做任何清理（光标残留、工具 stuck 在 running）— 行 1421-1427
    - CSS 重复定义：`.exec-layout`/`.file-tree-panel`/`.exec-main` 在行 881-887 和行 1025-1030 各出现一次，padding 丢失
    - `showFilePreview()` 写入不存在的 `#exec-messages` — 行 1399-1402
    - `.mode-switch-exec` 和 `#exec-cancel-btn` 无 CSS 类，使用内联 style 硬编码 — 行 1093、1096
    - `autoScroll` 在 chat 和 terminal 之间共享，切换 tab 后终端自动滚动失效
- **待改动点**：全部集中在 `scripts/ccc-chat-server.py` 的 HTML_UI 字符串内

---

## 范围

- **目标**：对已实现的终端模式做边缘清理——中断状态清理、CSS 去重+样式对齐、滚动分离+性能优化
- **只改文件**：`scripts/ccc-chat-server.py`
- **不改文件**：`.ccc/` 下任何文件、其他脚本、测试文件
- **执行方式**：`manual`
- **Phase 数**：3

---

## Phase 1：取消流的中断状态清理 — cancelStream 终端感知

### 做什么

当前 `cancelStream()` 只做 `abortController.abort()` + 隐藏按钮/加载动画，对终端模式无感知。用户按取消后：
- 光标 `▊` 停留在最后一行不动（`removeCursor()` 未调用）
- 工具状态 stuck 在 "running..." 永不更新
- `AbortError` 在 catch 块中显示 "网络错误" — 对用户主动取消来说是误导

### 怎么做

1. **修改 `cancelStream()`**（行 1421-1427）：
   - `abortController.abort()` 之后读取 `currentTab`，若为 `'execute'`：
     - `getTerminal()?.querySelector('.terminal-cursor')?.remove()`
     - 查询 `getTerminal()` 内的 `.terminal-tool-header .tool-status.running`，改为 `" cancelled"` 并移除 running 类
     - `appendTerminalInfo(' 用户终止')` 追加一行提示

2. **修改 `terminalStream()` catch 块**（行 1697-1701）：
   - `if (e.name === 'AbortError')` 时直接 `return`，不渲染 "网络错误"

### 验收

- 执行长指令，按取消，光标 `▊` 立即消失
- 执行含 Bash 工具的指令，取消时 running → " cancelled"
- 取消后终端出现 " 用户终止" ，无 "网络错误"
- Chat 模式取消不受影响

---

## Phase 2：CSS 去重 + 样式补齐 + 文件预览修复

### 做什么

当前 CSS 存在重复定义，两个按钮使用内联 style 硬编码，文件树预览写入已不存在的 `#exec-messages`。

### 怎么做

1. **CSS 去重**（`<style>` 块）：
   - 删除第一组（行 881-892）的 `.exec-layout`/`.file-tree-panel`/`.exec-main`/`.exec-meta-bar`
   - 保留第二组（行 1025-1030）为唯一定义，补回 `padding:12px`

2. **`.mode-switch-exec` 样式归一**：新增 CSS 类，复用 `#mode-switch` 同款风格

3. **`#exec-cancel-btn` 硬编码 → CSS 类**：新增 `.cancel-exec` 类，删除内联 `style`

4. **`showFilePreview()` 修复**：改写入 `#exec-terminal` 并以 `.terminal-line` 格式渲染

### 验收

- `grep '\.exec-layout' scripts/ccc-chat-server.py` ≤1 行
- `.file-tree-panel` 含 `padding:12px`
- `#exec-cancel-btn` HTML 无内联 style，使用 `.cancel-exec` 类
- 文件树点击文件，终端出现预览行

---

## Phase 3：autoScroll 状态分离 + 终端性能打磨

### 做什么

`autoScroll` 被 chat 和 terminal 共享写入，切换 tab 后自动滚动失效。`loadHistory()` 高频调用。

### 怎么做

1. **autoScroll 分离**：`let chatAutoScroll = true;` + `let execAutoScroll = true;`，各 scroll 监听器写各自变量，终端滚动函数读 `execAutoScroll`，chat 读 `chatAutoScroll`

2. **`loadHistory()` 防抖**：`sendExecute()` 末尾 `setTimeout(() => loadHistory(), 300)`

3. **终端行间距**：`.terminal-line + .terminal-line { margin-top: 2px; }`

### 验收

- chat 中滚动后切换 execute 执行指令，终端自动滚到底部
- 连续快速 sendExecute 两次，只触发一次 `/api/history`
- 输出多行时每行 2px 间隔

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | cancelStream 终端状态清理 | `fix(cockpit): cancelStream 终端中断清理 (phase 1/3)` |
| 2 | CSS 去重 + 样式补齐 + showFilePreview | `style(cockpit): CSS 去重 + 按钮样式 + 文件预览修复 (phase 2/3)` |
| 3 | autoScroll 分离 + loadHistory 防抖 | `perf(cockpit): 滚动分离 + 请求防抖 (phase 3/3)` |

---

## 全局验收清单

- [ ] `python3 -m py_compile scripts/ccc-chat-server.py` 语法通过
- [ ] 启动后三面板正常渲染，无 JS 异常
- [ ] diff 仅限 `scripts/ccc-chat-server.py`
- [ ] 3 个 phase 各对应独立 commit
- [ ] phases.json 与 plan phase 数一致
- [ ] 所有验收意图全部达成