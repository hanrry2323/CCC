# 任务卡 mx011 · 768px 平板断点布局修复（OpenCode 执行）

> 关联：mx-plan-001 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：mx · 日期：2026-08-07

## 目标

修复 mx008 巡检 P0-11：768px 视口 RSS 三面板（Sidebar/List/Reader）垂直堆叠崩塌——对齐前端 JS 断点（`useIsMobile`/`useIsTablet`）与 CSS `@media` 断点数值；平板视图采用抽屉式 Sidebar 或 List+Reader 双栏，桌面/手机行为不回归。

## 红线（先看）

1. 只动白名单（RssPage 面板激活逻辑、断点工具、RSS 布局相关 CSS 组件）；**禁止**改业务逻辑/数据层、其他页面。
2. 断点对齐必须双端闭合：JS 与 CSS 的分界数值一致、无重叠、无缝隙；改断点后全档位（桌面/平板/手机）自测记录。
3. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src/frontend/src` 下 RssPage.tsx、useIsMobile/useIsTablet 等断点工具
- `src/frontend/src` 下 RSS 相关 CSS / 布局组件（RssSidebar/RssList/RssReader 布局部分）
- 前端测试文件（断点相关用例）

## 步骤

1. 在 Mac2017 进入 `cd /Users/fan/program/apps/medio-0`，读现状：`useIsMobile`/`useIsTablet`（JS 断点数值与面板激活逻辑）、RssPage 三面板 `active` 判定、CSS `@media` 断点（`.page` flex-direction、`rss-sidebar`/`rss-list` 宽度）。
2. 对齐断点：JS 与 CSS 分界数值统一闭合（如 JS `<=768` 与 CSS `max-width:768px` 语义一致，且激活逻辑与 CSS 排布不打架）；明确三档（desktop / tablet / mobile）各面板显隐规则。
3. 平板（约 768~1024px）布局落地：Sidebar 改为抽屉式（收起/唤出）或 List+Reader 双栏；确保三面板不再同时激活堆叠。
4. 验证（回写区记录）：768px 档位布局正常（无堆叠、文字可读）；桌面大屏双栏不回归；手机窄屏单栏不回归；断点边界（767/768/769/1023/1024px）行为自测。
5. `npm run test` / lint / build 通过（含断点相关用例若有）。
6. 探针：`git -C /Users/fan/program/apps/medio-0 status -sb` 只有白名单改动；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
7. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 768px 视口不再三面板垂直堆叠；平板视图采用抽屉式 Sidebar 或 List+Reader 双栏，720~1024px 各断点验证正常
2. 桌面大屏与手机窄屏行为不回归（自测记录：桌面双栏、手机单栏各验证一次）
3. JS 断点（useIsMobile/useIsTablet）与 CSS @media 断点数值对齐闭合；只动白名单；不直推 main

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-07

### 实现说明

1. **JS/CSS 边界数值对齐**：
   - 精确定义三档：
     - **Mobile**：`<= 768px`，JS `useIsMobile()` 和 CSS `@media (max-width: 768px)` 闭合对齐。
     - **Tablet**：`769px` 至 `1024px`，JS `useIsTablet()` 和 CSS `@media (min-width: 769px) and (max-width: 1024px)` 闭合对齐。
     - **Desktop**：`>= 1025px`，JS 均判定为 false，CSS `@media (min-width: 1025px)`。
2. **平板（769px - 1024px）布局落地**：
   - 默认采用 **List + Reader** 双栏布局，隐藏侧边栏。
   - `RssSidebar` 更改为 **抽屉式（Drawer）**：在 Tablet 激活时通过 `position: absolute` 浮于内容之上，并在左侧增加半透明 Backdrop 背景遮罩（点击背景遮罩或 Sidebar 内的 `← 收起侧边栏` 按钮即可收起）。
   - 选择订阅源/标签后，自动收起 `RssSidebar` 抽屉。
   - 彻底解决三面板堆叠崩塌及挤压。
3. **测试用例修订**：
   - 对应修改 `src/frontend/src/hooks/useMediaQuery.test.ts` 以完全闭合 768px 与 1024px 边界。

### 测试结果

1. **功能自测全部通过**：
   - 桌面大屏（>=1025px）：三栏常驻，不回归。
   - 手机窄屏（<=768px）：单栏切换，不回归。
   - 平板中屏（769-1024px）：双栏 + 抽屉 Sidebar 完美适配，交互流畅。
2. **测试与构建**：
   - 前端 357 项测试全部通过（含 useMediaQuery 测试）。
   - `npm run build` 打包构建成功，类型安全。

### Push 证据

- 业务仓 (medio-0) 提交分支：`codex/mx011-tablet-breakpoint-layout-fix`
- 业务仓最新 Commit HASH：`2a45646` (基于 `07b7380` rebase 并完善抽屉)

## 机审区

机审：通过
