# Plan: cockpit-v0303b-chatui — Chat UI 设计对齐 + 用户体验打磨

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-chat-server.py`（~2120 行，FastAPI + 内嵌 HTML/CSS/JS 单文件）
- **当前结构要点**：
  - 所有前端代码嵌入在 `HTML_UI` 多行字符串中（`scripts/ccc-chat-server.py:715-2063`），包含 `<style>`（~330 行 CSS）和 `<script>`（~920 行 JS）
  - `:root` 已定义 9 个 CSS 变量（`--bg`, `--surface`, `--text`, `--text-secondary`, `--border`, `--accent`, `--user-bg`, `--user-text`, `--assistant-bg`, `--code-bg`, `--shadow`, `--radius`, `--max-w`），但 CSS 中有大量硬编码颜色值/间距/圆角未被变量化（如 `.tab-btn` 硬编码 `color:var(--text-secondary)` 和 `var(--accent)` 混用、按钮背景 `#ff3b30` 无变量、终端深色主题 `#1a1b26` 等无 token）
  - `renderMarkdown()`（`:1912-1924`）是纯正则实现——代码块无反色/复制按钮，缺少表格/链接/多级列表支持
  - 两个独立流处理函数 `streamRequest()` 和 `terminalStream()` 有显著重复（fetch + SSE 解析 + 渲染逻辑重复）
  - `autoScroll` 变量在 chat 和 terminal 之间共享，切换 tab 时引用混乱
  - 会话列表每次对话结束后都调用 `loadHistory()`（`chat-server.py:1438`、`:1761`）——高频无关请求
  - `cancelStream()` 在流中断后不会清除 `currentMessages`/`execMessages` 中可能残留的半条 assistant 消息
- **待改动点**：全部集中在 `scripts/ccc-chat-server.py` 的 `HTML_UI` 字符串内，包括 `<style>` 块（CSS 变量/间距/按钮）、JS 函数（markdown 渲染/流处理/会话管理）、HTML 结构（气泡/输入区/TabBar）

---

## 范围

- **目标**：对 ccc-chat-server 的 Chat UI 完成设计系统对齐（CSS 变量化、间距 token、按钮统一），并打磨用户交互体验（markdown 渲染增强、输入/会话/滚动体验优化）
- **只改文件**：`scripts/ccc-chat-server.py`
- **不改文件**：`scripts/ccc-cockpit.py`（已由 v0303a-design 覆盖）、`.ccc/` 下任何文件、其他脚本
- **执行方式**：`manual`
- **Phase 数**：1（4 个 subtask 串行完成）

---

## 改动 1：Chat UI 设计对齐 + 用户体验打磨

### 做什么

当前 Chat 界面 CSS 沿用了 `:root` 变量定义但停留在早期阶段——有大量硬编码颜色、间距、和圆角；按钮、圆点、输入框没有统一的设计 token。同时，markdown 渲染仅靠纯正则，代码块无样式、链接/表格不可点击、滚动体验不流畅。

**分 4 个 subtask 完成：**

**1.1 CSS 变量补全 + 间距 token**：在 `:root` 补充 `--radius-sm`、`--radius-lg`、`--space-*`（`--space-xs`/`--space-sm`/`--space-md`/`--space-lg`/`--space-xl`）、`--shadow-sm`、`--shadow-lg`、`--danger`（`#ff3b30`）等 token。将 `<style>` 块中所有硬编码颜色值（除终端深色主题专用色外）替换为变量引用。

**1.2 聊天气泡**：气泡添加时间戳标签；用户/助手气泡区分度增强；代码块加复制按钮和深色背景；消息按角色分组连续显示时去掉重复的头像/装饰。

**1.3 输入框**：`#input-wrap` 聚焦效果增强（`box-shadow`）；发送按钮 disabled 态增加过渡动画；textarea placeholder 颜色走变量；`#mode-switch` 按钮样式统一对齐 `.btn` 风格。

**1.4 TabBar 增强**：Tab 图标/文字间距统一；active 态增加底部指示线动画；切换时内容区无抖动。

### 怎么做

**1.1 CSS 变量补全 + 间距 token**（`scripts/ccc-chat-server.py` 的 `<style>` 块内 `:root` 区块扩展）：
  - `:root` 中新增：
    ```css
    --space-xs: 4px; --space-sm: 8px; --space-md: 12px; --space-lg: 16px; --space-xl: 24px;
    --radius-sm: 8px; --radius-lg: 22px;
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
    --shadow-lg: 0 4px 12px rgba(0,0,0,0.12);
    --danger: #ff3b30;
    --accent-hover: #0056b3;
    ```
  - 全局搜索 <style> 块中所有 `padding`/`margin` 硬编码值（如 `padding:12px 16px` → `padding:var(--space-md) var(--space-lg)`）
  - 将按钮背景色 `#ff3b30`、`var(--accent)` 等统一：
    - `.icon-btn`、`#mode-switch`、`.tab-btn` 的硬编码色换 `var(--)`
    - `.tab-btn.active` 的 `color:var(--accent)` 不变，但 inactive 从硬编码 `var(--text-secondary)` 统一走 token
  - `.board-col-title` 颜色 > `var(--text-secondary)`
  - 删除重复的 CSS 规则（两条 `.exec-layout`、两条 `.file-tree-panel`、`.board-card` 重复定义）——合并去重

**1.2 聊天气泡**（`<style>` + `<script>`）：
  - 气泡添加时间戳：在 `.msg` 内部追加 `<div class="ts">HH:MM</div>`（`:after` 伪元素或用真实 DOM 节点），CSS 走 `--text-secondary`
  - 助手气泡代码块（`.bubble pre`）添加复制按钮：`renderMarkdown()` 中在每个 `<pre>` 后追加 `<button class="copy-btn" onclick="...">复制</button>`
  - 连续同角色消息合并间距：CSS 添加 `.msg + .msg.user` / `.msg + .msg.assistant` 的 `margin-top:4px`（替代默认 `16px`），只对同角色有效
  - `.msg .bubble pre` 的背景色设为 `--code-bg`（已在 `:root` 定义）
  - 用户气泡去掉 `box-shadow` 以增强与助手气泡的视觉区分

**1.3 输入框**（`<style>` 内 `#input-area` 相关区块）：
  - `#input-wrap:focus-within` 增加 `box-shadow: 0 0 0 2px var(--accent)`（iOS 风格聚焦环）
  - 按钮 `#send`/`#exec-send` 在 `:disabled` 时 `opacity:0.3` 加 `transition:opacity 0.2s`
  - `#mode-switch` 改为 `.icon-btn` 统一风格（背景透明、hover 变深），删除硬编码 `width:32px;height:32px`
  - textarea `::placeholder` 颜色改为 `var(--text-secondary)`
  - 输入框高度自适应逻辑保留，但发送后清空高度也恢复 `auto`

**1.4 TabBar**（`<style>` 内 `#tabbar` 区块）：
  - `.tab-btn` 增加 `position:relative`，active 态添加 `::after` 伪元素底部指示线（3px 高，`background:var(--accent)`，`border-radius:1.5px 1.5px 0 0`）
  - 指示线添加 `transition:all 0.2s` 渐变效果
  - TabBar 整体添加 `padding-top:4px` 对齐设计间距

### 验收清单

- [ ] 验收条件 1：`:root` 新增的 CSS 变量（space/radius/shadow/danger）全部定义且被引用
- [ ] 验收条件 2：`<style>` 块中不存在 `:root` 已有变量对应的硬编码颜色值（终端深色主题除外）
- [ ] 验收条件 3：重复 CSS 规则已合并删除（确认 `grep` 不会出现两条 `.exec-layout`/`.file-tree-panel`）
- [ ] 验收条件 4：代码块出现复制按钮，点击可复制内容
- [ ] 验收条件 5：连续同角色消息间距缩小（`8px` 内），不同角色间距保持 `16px`
- [ ] 验收条件 6：TabBar active 状态有底部指示线动画
- [ ] 验收条件 7：输入框聚焦时显示 iOS 风格聚焦环
- [ ] 验收条件 8：页面在 Chrome/Safari 上正常渲染，无 CSS breakage

### 验收

- [CSS 变量补全] `:root` 区块新增 `--space-xs`/`--space-sm`/`--space-md`/`--space-lg`/`--space-xl`/`--radius-sm`/`--radius-lg`/`--shadow-sm`/`--shadow-lg`/`--danger`/`--accent-hover`（参考：`grep 'var(--space' scripts/ccc-chat-server.py | head -5` 确认引用）
- [硬编码色清理] 除终端深色主题（`#1a1b26`、`#a9b1d6`、`#73daca` 等）外，`<style>` 块内不再出现魔数色值和一个已在 `:root` 中有对应变量的魔数间距值（参考：手动检查样式中无 `#ff3b30` 等出 token 外的色值）
- [CSS 去重] `.exec-layout`、`.file-tree-panel` 在 `<style>` 块中只出现一次（参考：`grep '\.exec-layout' scripts/ccc-chat-server.py` 输出 ≤1 行）
- [代码块复制按钮] 每个 `<pre>` 代码块下方有复制按钮，点击后代码可复制（参考：打开 `http://localhost:8084`，Chat 模式发送含代码块的消息）
- [连续消息间距] 连续用户消息间距 4px，连续助手消息间距 4px，不同角色间 16px（参考：浏览器实机验证）
- [TabBar 指示线] Tab active 时有底部蓝色条纹动画
- [聚焦环] 输入框点击时出现 2px 蓝色聚焦环
- [无回归] 页面渲染无误，终端模式/看板模式正常工作

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | CSS 变量补全 + 气泡/输入框/TabBar 样式对齐 + 代码块复制 + 消息间距优化 | `style(chatui): 设计系统对齐 + 用户体验打磨 (phase 1/1)` |

---

## 全局验收清单

- [ ] `python3 scripts/ccc-chat-server.py --port 8084` 正常启动，`http://localhost:8084` 正常渲染
- [ ] Chat/Execute/Board 三模式均正常切换和操作
- [ ] `renderMarkdown` 增强（代码块复制按钮、连续消息间距优化）正常工作
- [ ] TabBar 切换无布局抖动
- [ ] 输入框聚焦 UI 正常，无光标错位
- [ ] diff 范围仅限 `scripts/ccc-chat-server.py`
- [ ] 1 个 phase 对应 1 个 commit

---

## 后续步骤

完成后可继续将 `cockpit-v0303c-terminal.jsonl` 和 `cockpit-v0303d-mobile.jsonl` 从 backlog 推入 planned。