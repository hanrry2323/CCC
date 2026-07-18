# Plan: cockpit-v0303a-design — Cockpit 设计系统规范化

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-cockpit.py`（单文件约 1210 行，Python HTTP 服务 + 内嵌 HTML/CSS/JS）
- **当前结构要点**：
  - 颜色通过 `THEME` 字典硬编码在 6 个键中（`bg`/`surface`/`text`/`muted`/`accent`/`border`/`green`/`red`/`yellow`），通过 f-string 注入 CSS 和 HTML（`scripts/ccc-cockpit.py:63-73` 定义，`render_html()` 中通过 `{THEME[...]}` 散布使用）
  - CSS 全部内嵌在 Python f-string 中（`scripts/ccc-cockpit.py:930-988`），导致样式定义重复、无法被编辑器语法高亮、难以维护
  - 布局间距不一致：`.sec-title` 硬编码 `margin:24px 0 10px`，卡片和表格间距缺乏统一 token
  - 按钮样式不统一：快速跳转链接（`scripts/ccc-cockpit.py:1001-1007`）、日志控制按钮（`:981-982`）、KB 搜索按钮（`:1012-1013`）各有不同的 border-radius、padding、hover 表现
  - 状态圆点仅 3 个 CSS 类（`.dot-green`/`.dot-red`/`.dot-gray`），8px 实心圆，无动画/光晕，视觉区分度低
- **待改动点**：全部集中在 `scripts/ccc-cockpit.py` 的 CSS 块（`render_html()` 的 style 标签内）和相关的 JS 交互元素

---

## 范围

- **目标**：抽离魔数颜色 → CSS 自定义属性；统一间距 token；统一按钮视觉语言；增强状态圆点视觉反馈
- **只改文件**：`scripts/ccc-cockpit.py`
- **不改文件**：`scripts/ccc-chat-server.py`（chatui 任务覆盖）、`.ccc/` 下任何文件、其他脚本
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1：设计系统规范化

### 做什么

当前 Cockpit 页面的颜色和间距散布在 Python f-string 和 CSS 硬编码值中，导致两处问题：
- 改一个颜色要改 6+ 个 f-string 位置，容易遗漏
- 没有统一的间距/字体/间距 token，各个组件有自己的 padding/margin，视觉上缺乏系统性

把 `THEME` 字典的 6 色映射到 CSS 自定义属性（`:root`），将间距、圆角、按钮默认态也归纳为 token，同时统一所有按钮交互态（hover/active 样式），并给状态圆点增加脉冲动画。

### 怎么做

1. **CSS 变量化**（`scripts/ccc-cockpit.py:render_html()` 的 `<style>` 块顶部）：删除 f-string `THEME` 注入改显式 `:root { --bg: #f5f5f7; --surface: #fff; ... }`，让内联 CSS 恢复为纯字符串，不再依赖 Python 变量
2. **间距 token**：定义 `--space-xs: 4px; --space-sm: 8px; --space-md: 14px; --space-lg: 20px; --space-xl: 24px`，将代码中所有魔数间距（10px、12px、16px、24px）替换为 token 引用
3. **按钮统一**：添加 `.btn` 基类（12px/14px 两规格，`--accent` 主色，hover 变深 10%，active scale 0.97），将快速链接、搜索按钮、日志按钮全部改为引用 `.btn` 类
4. **状态圆点**：给 `.dot-green`/`.dot-red`/`.dot-gray` 增加 `box-shadow` 光晕（对应颜色半透明），绿色的在 alive 时添加 `@keyframes pulse` 呼吸动画（scale 1→1.15→1，2s 循环）

### 验收

- [CSS 变量定义] `:root` 区块定义了 `--bg`, `--surface`, `--text`, `--muted`, `--accent`, `--border`, `--green`, `--red`, `--yellow` 共 9 个 CSS 变量，样式块中不再出现 `{THEME[...]}` f-string 注入（参考：打开 Cockpit 页面，检查 `<style>` 首段应见 `:root` 块）
- [间距 token] 全页面所有 padding/margin 不再出现硬编码 4/8/10/12/14/16/20/24px 值，统一引用 token（参考：`grep -n 'margin\|padding' scripts/ccc-cockpit.py | grep -v '^\s*//\|#\|--spacing\|var(--space' 应不产生 token 之外的新魔数）
- [按钮统一] 所有按钮（快速链接跳转、搜索、日志查看）点击时有视觉反馈，hover 时颜色变深（参考：浏览器实机验证）
- [状态圆点] 绿色圆点有呼吸动画，红色有光晕效果（参考：`:7778` 端口探测结果页面观察圆点状态）
- [边界场景] 无按钮点击时，所有交互元素无异常布局抖动
- [安全相关] CSS 变量名无注入风险（纯 CSS 自定义属性，无用户输入参与）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | THEME → CSS 变量；统一间距 token；统一按钮样式；状态圆点动画 | `style(cockpit): 设计系统规范化 — CSS 变量 + 间距 token + 按钮统一 + 圆点动画 (phase 1/1)` |

---

## 全局验收清单

- [ ] CSS 无语法错误，页面正常渲染（python3 scripts/ccc-cockpit.py + 打开 `http://localhost:7778`）
- [ ] 所有颜色与改动前一致（视觉回归无偏差）
- [ ] 内联 CSS 不再依赖 Python `{THEME[...]}` f-string 注入
- [ ] `.btn` 类全线统一，无遗漏的未改按钮
- [ ] diff 范围仅限 `scripts/ccc-cockpit.py` 的 CSS 块和主题变量定义
- [ ] 1 个 phase 对应 1 个 commit

---

## 后续步骤

完成后可继续将 `cockpit-v0303b-chatui.jsonl` 从 backlog 推入 planned，对 Chat 界面做类似的设计对齐。