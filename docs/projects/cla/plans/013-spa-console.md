# 方案 · 轻量级 SPA 控制台搭建（M5-5.3 · 对应架构定稿 M5.F 三功能卡）

> 项目：cla · 编号：cla-plan-013 · 状态：已完成 · 作者：OpenCode · 工具：opencode
> 创建：2026-08-17 · 更新：2026-08-18（红线修正：删 mock 表述，数据面板以真实 gov 数据验证）
> 关联卡：cla026, cla027, cla028
> 关联方案：cla-plan-011（审核 API）、cla-plan-012（推送）
> 进度：3/3 (100%)
> 里程碑：M5 · 前端控制台、合规审核与企微触达
> 环境准备：Python >= 3.10, 前端静态托管（FastAPI 内置）
> 子项目：5.3 轻量级 SPA 控制台搭建 (Vite + React)
> 决策源：/Users/apple/qx-map/__archive__/decisions/ClawMed-CCC-Architecture-2026-08-17.md

## 目标

落地轻量级前端控制台：Vite + React + Tailwind + Zustand，FastAPI 一体化挂载静态单页，目标整机内存 ≤30MB（前端 + 后端 + 任务），含数据面板/机会流/合规审核三视图（架构定稿 M5.F 三功能卡）。

## 背景

架构定稿（M5.F · 一体化决策控制台与合规前端）：
- 技术栈：Vite + React 18 + TailwindCSS + Zustand；构建产物纯静态，FastAPI `StaticFiles` 一体化挂载（低配设备不跑独立前端服务）。
- M5.F 三功能卡：
  - Data Panel（SQLite 数据面板：gov/电商价格表 + 趋势）
  - Opportunity Stream（实时机会流：SSE 推送新机会，websocket 备选）
  - Compliance Panel（合规审核台：调用审核 API，三级审核操作界面）
- 前端轻量化：无重依赖 UI 框架（纯 Tailwind 手写组件），生产构建后整体内存目标 ≤30MB。

## 方案内容

### 1. 前端工程骨架
- `frontend/`（Vite + React + Tailwind + Zustand），构建产物输出到 `src/api/static/`（FastAPI 挂载目录）。
- 页面路由：数据面板 / 机会流 / 合规审核台。

### 2. 三个视图
- Data Panel：gov_prices/ecommerce_prices 表格 + 筛选 + 简单趋势图（轻量，无 ECharts 重依赖，先用 CSS/表格表达）。
- Opportunity Stream：SSE 实时接收新机会（后端 `/api/stream`），卡片式展示。
- Compliance Panel：待审列表 → 详情 → approve/reject 操作，调审核 API。

### 3. FastAPI 一体化挂载
- `src/api/app.py`：FastAPI 应用 + `/api/*` 路由 + StaticFiles 挂载前端构建产物。
- SSE 端点：`/api/stream`（机会/审核事件推送）。

## 验收标准

- [x] 构建产物被 FastAPI 挂载可访问
- [x] 数据面板展示两表数据 + 筛选可用
- [x] 新机会 SSE 实时上屏，断线重连，历史初始加载
- [x] 审核台待审列表/详情/动作全流程可用
- [x] 整机内存 ≤30MB（观测记录）

## 功能卡

### Data Panel 数据面板

目标：完成前端工程骨架 + 数据面板视图，交付可验收产物。

实现：按「方案内容」1 节 + Data Panel 落地——frontend 骨架 + 两表数据面板。

验收：验收标准条款 1-2 + 5（挂载可访问 / 面板可用 / 内存目标）。

颗粒度：子项目内功能卡（约 2 天）。

依赖：cla-plan-005（gov 数据表）、cla-plan-008（电商数据表）；电商数据未就绪时面板只展示 gov 真实数据（红线：禁 mock 假数据）

架构位置：`frontend/`（骨架）、`src/api/app.py`（挂载）

### Opportunity Stream 实时机会流

目标：完成机会流 SSE 视图，交付可验收产物。

实现：按「方案内容」2 节 Opportunity Stream 落地——SSE 端点 + 前端流式卡片。

验收：验收标准条款 3（实时上屏 / 断线重连 / 历史加载）。

颗粒度：子项目内功能卡（约 1.5 天）。

依赖：Data Panel、cla-plan-010（机会数据源）

架构位置：`src/api/app.py`（/api/stream）、frontend 机会流页

### Compliance Panel 合规审核台

目标：完成合规审核操作界面，交付可验收产物。

实现：按「方案内容」2 节 Compliance Panel 落地——审核页调用审核 API。

验收：验收标准条款 4（审核全流程可用）。

颗粒度：子项目内功能卡（约 1.5 天）。

依赖：Opportunity Stream、cla-plan-011（审核 API）

架构位置：frontend 审核页

## 转卡计划

Data Panel（1 卡）/ Opportunity Stream（1 卡）/ Compliance Panel（1 卡）

## 备注

- 三卡按依赖链出卡（Data Panel 先立骨架，后两卡复用骨架）。
- 前端纯静态部署契约（架构定稿已定）：不引入独立前端服务器，FastAPI 一体化挂载为最终形态。
- 数据面板验证必须用真实入库数据（四川药械 gov_prices 等），禁止 mock 假数据填充界面。