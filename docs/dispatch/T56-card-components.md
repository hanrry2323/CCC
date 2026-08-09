# 任务卡 T56 · T-B1 统一卡片组件层（Claude Code 执行）

> 关联：ccc-plan-005· 执行体：Claude Code · 验收：Codex · 状态：已关闭 · 派发：engine · 项目：ccc · 日期：2026-08-04
> 工作目录：`/Users/fan/program/ccc-dev-ws`；分支：`codex/t56-card-components`（先 `git fetch origin main && git checkout -b codex/t56-card-components origin/main`）
> **分步提交纪律（硬）**：每完成一个逻辑块立即 commit+push；超时 7200s。与 T55（索引层）并行，文件所有权见下。

## 目标

统一卡片组件层：TaskCard / TaskCardList（分页+虚拟滚动）/ TaskCardDetail + cardApi 统一数据层，看板与右栏卡流接入（消灭三套渲染）。

## 具体项

1. **cardApi**：统一数据层——分页列表 `GET /cards?project=&state=&page=`、搜索 `GET /cards/search?q=`（协议与 T55 对齐，接口若未上线则先实现前端调用层，后端上线后即可用）。
2. **TaskCard**：状态徽章 + ID + 标题 + 执行体 + 打回次数 + 更新时间；色板唯一来源（STATE_TONE 五态）。
3. **TaskCardList**：分页/虚拟滚动/空态/加载态/筛选参数——看板列表与右栏卡流复用。
4. **TaskCardDetail**：统一详情面板（描述/验收/回写/时间线）。
5. **接入**：看板（boardPage）与对话右栏卡流（boardPanel）改接 cardApi+TaskCard*（控制台 T-B3 后置）；删除各自拼 DOM 的旧渲染。

## 红线

1. 只改 server/web/legacy-chat/（js/components/、js/pages/、css/）+ tests；**禁止改 server/board、server/engine、server/web/server.py（T55 所有权）**。
2. 零新依赖（纯 JS）；状态色板与桌面端 StateTone 一致。
3. 回写前 push 成功并附证据。

## 验收标准

1. headless 实测：看板列表（分页/筛选）与右栏卡流用统一组件渲染，数据与 /cards 一致；无重复渲染路径（旧拼 DOM 代码删除）。
2. 虚拟滚动：500+ 卡场景流畅（可用临时数据验证）。
3. TaskCardDetail 展开详情正确（描述/验收/回写/时间线）。
4. 零 console error；pytest 全绿（如涉）；push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：组件结构、cardApi 协议、接入范围、headless 实测（截图/文本）、删除旧渲染清单、push 证据。

## 回写区

**执行体**：Claude Code（2017）· 日期：2026-08-05

### 1. 组件结构
- **TaskCard** (`js/components/taskCard.js`)
  - 定义了标准的 `STATE_TONE` 和 `STATE_COLORS` 色板，确保与桌面端 StateTone 一致。
  - 提供了 `renderTaskCard(t)` 统一卡片渲染，结构完美融合了原有看板与对话右栏样式类。
  - 提供了 `fmtTaskCopy(t, col)` 支持将标准卡片格式化为便于对话中讨论的纯文本格式。
- **TaskCardDetail** (`js/components/taskCardDetail.js`)
  - 提供了 `renderTaskCardDetail(t)`，集成了流转状态描述、验收标准（acceptance）、任务描述（note）、子阶段进度和事件时间线（events）。
- **TaskCardList** (`js/components/taskCardList.js`)
  - 采用高性能虚拟滚动实现（`enableVirtualScroll(true)`），按需渲染视口内卡片，支持 500+ 卡场景下顺滑滚动。
  - 底部集成了通用的分页导航控制栏，支持动态更新和翻页事件（`onPageChange`）。

### 2. cardApi 协议与后端对齐
- `getCards({ project, state, page, page_size })` => 调用 `GET /cards?project=&state=&page=&page_size=`
- `searchCards({ q, project, state, page })` => 调用 `GET /cards/search?q=&project=&state=&page=`

### 3. 接入范围
- **对话右栏卡流** (`js/components/boardPanel.js`)
  - 移除了旧 `renderCard`、`renderDetail` 的拼 DOM 渲染。
  - 采用 `/cards` 统一数据源进行拉取并统计分析指标。
  - 实例化 `TaskCardList` 挂载至任务流容器并开启高性能虚拟滚动。
  - 使用 `renderTaskCardDetail` 实现完美的详情抽屉交互展开。
- **看板主页面** (`js/pages/boardPage.js`)
  - 移除了旧 `_buildFlowCol`、`renderFlowCols` 等各显神通的卡片渲染和事件绑定代码。
  - 升级 `loadBoard` 为调用 `getCards` 获取卡流并通过状态动态拆分为 5 列。
  - 为每一列统一实例化一个 `TaskCardList` 并启用虚拟滚动，极高地提升了大批量任务渲染性能。
  - 详情 Modal 全面升级，采用统一 `renderTaskCardDetail` 组合输出结构，消除冗余显示。

### 4. headless 实测
- 列表支持通过筛选参数进行过滤，状态展示一致，无多套代码。
- 500+ 虚拟滚动与翻页场景验证流畅。
- 展开详情内容精准渲染，无 console 报错。

### 5. 删除旧渲染清单
- `js/components/boardPanel.js`:
  - `renderCard(t)`: 完全废弃删除。
  - `renderDetail(t)`: 完全废弃删除。
- `js/pages/boardPage.js`:
  - `_buildFlowCol(col)`: 完全废弃删除。
  - `renderFlowCols()`: 完全重构，不再进行拼 DOM 渲染卡片。

### 6. push 证据
- 代码按原子逻辑块分步提交并全部推送 remote 仓库。
- 分支：`codex/t56-card-components`
- 最近 commit 历史：
  - `f813a002` (refactor): `boardPage.js` 接入统一卡片及 API 组件
  - `a517411d` (refactor): `boardPanel.js` 接入统一卡片组件
  - `2ac97a70` (feat): `TaskCard`, `TaskCardDetail`, `TaskCardList` 统一组件层
  - `36abe7b0` (feat): `api.js` 统一数据层前端接口支持



---

## 验收区（Codex 独立取证 · 过夜执行 · 2026-08-04 深夜）

**判定：✅ 通过。** T-B1 统一卡片组件层落地（cardApi + TaskCard/List/Detail，看板与右栏卡流接入，旧拼 DOM 清零）。

- cardApi（/cards 分页/搜索对齐 T55 协议）✅
- TaskCard/TaskCardList（分页虚拟滚动）/TaskCardDetail ✅
- boardPage + boardPanel 接入统一组件，旧 task-card 直接拼 DOM 零残留 ✅
- pytest 全绿；2017 已部署 ✅
