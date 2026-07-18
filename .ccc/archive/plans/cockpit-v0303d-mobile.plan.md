# Plan: cockpit-v0303d-mobile — Mobile 端优化（触摸目标 + 侧栏底栏 + 键盘 + 横竖屏）

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-chat-server.py`（2123 行，FastAPI + 内嵌 HTML/CSS/JS 单文件）
- **当前结构要点**：
  - `<meta name="viewport">` 已设（`width=device-width,initial-scale=1,viewport-fit=cover`，行 719），safe-area 变量有 4 处引用（行 749、926、990、1004）
  - 已有两个媒体查询断点：480px（行 1019-1024：仅缩小 padding/font）和 768px（行 1046-1049：exec-layout 纵向排列 + file-tree 限高）
  - **无 iOS 虚拟键盘处理**——`visualViewport` 无监听，iPhone 上 textarea 会被键盘遮挡
  - **触摸目标不达标**：`#send`/`#exec-send` 36×36px、`#mode-switch` 32×32px、`#tabbar` 各 .tab-btn 只有 8px padding，均低于 Apple HIG 44px 最小触摸目标
  - 侧栏 `#sidebar` 固定 `left:-280px` → `left:0` 抽屉动画，在 iPhone SE（375px）下占用 >74% 屏幕宽度，无 mobile 专属交互（如底部弹出）
  - Board 列 `min-width:220px` 在小屏下无 snap-scroll，横向滚动体验生硬
  - 无 "回底部" FAB 按钮——长对话后需手动滚到底部
- **待改动点**：全部集中在 `scripts/ccc-chat-server.py` 的 `HTML_UI` 字符串内的 `<style>` + `<script>` 区域

---

## 范围

- **目标**：对已实现的 Web 界面做 Mobile-first 体验优化——触摸目标达标、侧栏移动化、iOS 键盘处理、横竖屏适配
- **只改文件**：`scripts/ccc-chat-server.py`
- **不改文件**：`.ccc/` 下任何文件、其他脚本、测试文件、`scripts/ccc-cockpit.py`
- **执行方式**：`manual`
- **Phase 数**：4

---

## Phase 1：触摸目标缩放 + 375px 断点补全

### 做什么

当前界面在 iPhone 上触摸目标偏小。Apple HIG 要求最小触摸目标 44×44pt，而发送按钮仅 36×36、模式切换仅 32×32、Tab 按钮 padding 仅 8px。同时缺少窄屏（375px，对应 iPhone SE / 小屏 Android）的专属适配。

### 怎么做

1. **按钮尺寸拉齐 44px**（CSS `<style>` 块内）：
   - `#send, #exec-send, #cancel-btn`：`width:44px; height:44px;`（原 36px）
   - `#mode-switch`：`width:44px; height:44px; border-radius:50%; font-size:16px;`（原 32px）
   - `#exec-cancel-btn` 透传 `.cancel-exec` 类时也保证 min-height:44px
   - `#input-wrap` 纵向高度自适应：`padding:2px 4px 2px 12px;`（因按钮变大后需补偿）

2. **Tab 按钮触摸区域扩展**（`.tab-btn`）：
   - `padding:6px 0 4px;` → `padding:8px 0 6px;`（实际触摸热区通过 `min-height:48px` 保证）
   - `.tab-btn .tab-icon` 字体加大 `font-size:22px`（原 20px）

3. **新增 375px 媒体查询**（`@media(max-width:375px)`）：
   - 缩小 `#header` padding 为 `8px 10px`
   - `#messages, #exec-messages` padding 为 `8px 10px`
   - `#input-area` padding 为 `6px 10px`
   - `.msg .bubble` `max-width:92%`（比 480px 断点更宽）
   - 隐藏 `#header h1` 标题文字以节省空间（或换短标题 "CCC"）
   - `#project-select` 宽度限 `100px`

4. **文件树/侧栏交互项目触摸**：
   - `.session-item` 增加 `padding:12px`（原 10px 12px）
   - `.file-item` 增加 `padding:6px 12px`（原 4px 12px）
   - `.board-card` 增加 `padding:12px`（原 10px）

### 验收

- `#send` / `#exec-send` / `#cancel-btn` 尺寸 ≥44px（参考：浏览器检查元素）
- `#mode-switch` 尺寸 ≥44px
- `.tab-btn` 有效触摸热区 ≥44px（含 padding + min-height）
- 375px 视口下标题自适应缩短，project 选择器宽度缩小
- 文件树 / 侧栏条目触摸区域增大，无误触

---

## Phase 2：侧栏移动化 — 底部弹出（Bottom Sheet）

### 做什么

当前侧栏是左侧抽屉（`left:-280px`），在 iPhone 上 >70% 屏幕宽度，操作体验差。在移动端（≤480px）改为底部弹出（Bottom Sheet）——从屏幕底部向上滑出，带圆角、拖拽手柄、背景半透明遮罩。

### 怎么做

1. **CSS 改造**（`<style>` 块内 `#sidebar` 块，行 935-941）：
   - 保留桌面端（>480px）的左侧抽屉样式不变
   - 在 `@media(max-width:480px)` 的 block 内覆盖 `#sidebar`：
     ```css
     #sidebar {
       position:fixed; top:auto; bottom:0; left:0; width:100%;
       height:auto; max-height:80vh;
       background:var(--surface); border-right:none;
       border-radius:16px 16px 0 0;
       transform:translateY(100%); /* 默认滑出屏幕下 */
       transition:transform 0.35s cubic-bezier(0.32, 0.72, 0, 1);
       padding:20px 16px; z-index:20;
       padding-bottom:calc(20px + env(safe-area-inset-bottom,0px));
     }
     #sidebar.open { left:0; transform:translateY(0); }
     ```
   - 添加拖拽手柄 `.sidebar-handle`：
     ```css
     .sidebar-handle {
       width:36px; height:4px; border-radius:2px;
       background:var(--border); margin:0 auto 12px;
       position:sticky; top:0;
     }
     ```
     在 HTML 中 `#sidebar` 内部首个子元素追加 `<div class="sidebar-handle"></div>`

2. **HTML 调整**（行 1125-1128）：
   - `#sidebar` 内首个子元素追加 `.sidebar-handle`
   - 保持 `<h2>对话历史</h2>` + `#sessionList` 结构不变

3. **JS 触摸关闭**（`<script>` 块）：
   - `toggleSidebar()` 行 1934-1937 保留（仍可被菜单按钮和遮罩关闭）
   - 新增触摸关闭：监听 `#sidebar` 内部 touchmove 检测向下滑动距离 >80px 自动关闭（调用 `toggleSidebar()`）
   - **取消按钮功能保留**：`#overlay` 点击仍关闭侧栏（行 1124 已有 `onclick="toggleSidebar()"`）

4. **侧栏遮罩适配**：
   - `#overlay` 在 ≤480px 时 `z-index:19` 保持不变

### 验收

- 桌面宽度（>768px）侧栏仍为左侧抽屉，行为不变
- 移动端（≤480px）侧栏从底部弹出，有圆角 + 拖拽手柄
- 向下拖拽 >80px 关闭侧栏
- 背景遮罩半透明，点击遮罩关闭
- 侧栏内容（历史会话）正常滚动
- safe-area-bottom 已适配

---

## Phase 3：iOS 虚拟键盘处理 + 回底 FAB

### 做什么

iOS Safari 虚拟键盘弹出时不触发 `window.resize`，已输入区域会被键盘遮挡。同时长对话后用户需手动上滚才能按发送——需要 "滚动到底部" FAB 按钮。

### 怎么做

1. **`visualViewport` 监听**（`<script>` 块）：
   - 在 `input.addEventListener('focus', ...)` / `execInput.addEventListener('focus', ...)` 中挂载 `window.visualViewport?.addEventListener('resize', handler)`：
     ```js
     function adjustForKeyboard(viewport) {
       const inputArea = document.getElementById('input-area');
       if (!viewport || !inputArea) return;
       // 计算键盘遮挡：视口高度变化 = 键盘高度
       const keyboardHeight = window.innerHeight - viewport.height;
       if (keyboardHeight > 100) {
         // 键盘弹出：滚动到输入区
         inputArea.style.transform = 'translateY(-' + (keyboardHeight - (window.innerHeight - viewport.height)) + 'px)';
         // 取消：滚动到底部
         setTimeout(() => {
           const el = currentTab === 'chat' ? messagesEl : execMessagesEl;
           if (el) el.scrollTop = el.scrollHeight;
         }, 50);
       } else {
         inputArea.style.transform = '';
       }
     }
     window.visualViewport?.addEventListener('resize', () => adjustForKeyboard(window.visualViewport));
     ```
   - on blur 时移除：`input.addEventListener('blur', () => inputArea.style.transform = '')`
   - 注意防抖——限制 `resize` 事件处理频率 ≤100ms

2. **"回到底部" FAB**（`<style>` + `<script>`）：
   - CSS 新增：
     ```css
     #scroll-bottom-fab {
       position:absolute; bottom:60px; right:16px;
       width:40px; height:40px; border-radius:50%;
       background:var(--surface); border:1px solid var(--border);
       color:var(--accent); font-size:18px; box-shadow:var(--shadow);
       cursor:pointer; z-index:8; display:none;
       align-items:center; justify-content:center;
       transition:opacity 0.2s, transform 0.2s;
     }
     #scroll-bottom-fab.show { display:flex; }
     ```
   - HTML：在 `#chat-panel` 和 `#exec-panel` 内部追加（`#messages` / `#exec-terminal` 同级兄弟）
   - JS：监听 `messagesEl.scroll` 和 `execTerminalEl.scroll`：
     - 当用户向上滚动 >200px（非底部）时显示 FAB
     - 点击时 `scrollTop = scrollHeight` 并隐藏 FAB
     - 仅在 ≤768px 时启用（桌面端屏幕大，不需要）

3. **调整 header 在键盘弹出时的 `position`**：
   - 当 `visualViewport` 高度变化 >100px 时，将 `#header` 的 `position:sticky` 临时切换为 `position:relative`（为用户让出最大可视区域）

### 验收

- iPhone Safari：点击 textarea，输入不遮挡键盘
- 键盘弹出时输入框可见，头像/header 自动上移
- 键盘收起后输入框回原位
- 消息列表向上滚 >200px 时出现返回底部 FAB
- 点击 FAB 回到最底，FAB 消失
- 桌面端（>768px）FAB 不显示

---

## Phase 4：Board 横滑 snap-scroll + 横竖屏优化

### 做什么

当前 Board 列在移动端横向滚动无 snap 吸附、无视觉提示。横屏模式下文件树和 TabBar 存在空间浪费。需做横竖屏专项优化。

### 怎么做

1. **Board 列 snap-scroll**（CSS `<style>` 块）：
   - 在 `@media(max-width:768px)` 内：
     ```css
     #board-scroll {
       scroll-snap-type: x mandatory;
       -webkit-overflow-scrolling:touch;
       gap:8px;
     }
     .board-col {
       scroll-snap-align: start;
       min-width:85vw; /* 移动端一列占大部分屏幕 */
     }
     ```

2. **横向分页指示器**（CSS + JS）：
   - CSS 新增 `.board-scroll-indicator`（细条容器行，位于 board-scroll 下方）
   - JS：监听 `#board-scroll` 的 `scroll` 事件，计算当前页索引，更新指示器圆点状态
   - 仅 ≤768px 时渲染指示器，桌面端隐藏

3. **文件树横屏优化**：
   - `@media(orientation:landscape)` 和 `@media(max-width:768px)` 同时匹配时：
     - `.file-tree-panel` 回归水平布局（`width:200px; max-height:none;`）
     - `.exec-layout` 水平排列（覆盖 768px 断点的 column 方向）

4. **TabBar 横屏紧凑模式**：
   - `@media(orientation:landscape)` 且 `@media(max-height:414px)`（iPhone 横屏典型高度）：
     - `.tab-btn .tab-icon` 缩小为 `font-size:16px`
     - `.tab-btn` padding 缩小为 `4px 0 2px`
     - TabBar 整体 `height:36px`（原 ~50px）

### 验收

- 移动端 board 页横向滑动，松手后吸附到最近一列
- 底部有指示器圆点，滑动时同步更新
- 横屏（landscape）下文件树恢复左右布局（非上下堆叠）
- 横屏 TabBar 紧凑显示，不占用过多垂直空间
- 桌面端（>768px）不受影响

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 触摸目标达标 + 375px 断点 | `style(mobile): touch target 44px + 375px breakpoint (phase 1/4)` |
| 2 | 侧栏底部弹出 Bottom Sheet | `feat(mobile): sidebar bottom sheet on small screens (phase 2/4)` |
| 3 | iOS 键盘 + scroll-to-bottom FAB | `feat(mobile): keyboard handling + back-to-bottom FAB (phase 3/4)` |
| 4 | Board snap-scroll + 横竖屏 | `style(mobile): board snap-scroll + orientation tuning (phase 4/4)` |

---

## 全局验收清单

- [ ] `python3 -m py_compile scripts/ccc-chat-server.py` 语法通过
- [ ] 启动后在 iPhone 视口（375px）所有按钮可触摸操作
- [ ] 侧栏在 ≤480px 从底部弹出
- [ ] 侧栏在 >480px 保持左侧抽屉
- [ ] iOS 键盘弹出时不遮挡输入框
- [ ] Board 列 snap-scroll 在移动端生效
- [ ] 横竖屏切换布局正常，无错乱
- [ ] diff 仅限 `scripts/ccc-chat-server.py`
- [ ] 4 个 phase 各对应独立 commit
- [ ] phases.json 与 plan phase 数一致
- [ ] 所有验收意图全部达成

---

## 后续步骤

完成后将 `cockpit-v0303d-mobile.jsonl` 从 backlog 推入 planned（若还未），即可开跑 dev_role。