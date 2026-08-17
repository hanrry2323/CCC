# 方案 · 轻量级 SPA 控制台搭建 (M5 · 对应架构定稿 M5.F 三功能卡)
> 项目：cla · 编号：cla-plan-011 · 状态：草案 · 作者：OpenCode · 工具：opencode
> 创建：2026-08-17 · 更新：2026-08-17
> 关联卡：待出卡
> 关联方案：cla-plan-009（审核 API）、cla-plan-010（推送）
> 里程碑：M5 · 前端控制台、合规审核与企微触达
> 子项目：5.3 轻量级 SPA 控制台搭建 (Vite + React)
> 决策源：/Users/apple/qx-map/__archive__/decisions/ClawMed-CCC-Architecture-2026-08-17.md

## 目标

落地轻量级前端控制台：Vite + React + Tailwind + Zustand，FastAPI 一体化挂载静态单页，目标整机内存 ≤30MB（前端 + 后端 + 任务），含数据面板/机会流/合规审核三视图（架构定稿 M5.F 三功能卡）。

## 背景

架构定稿（M5.F · 一体化决策控制台与合规前端）：
- 技术栈：Vite + React 18 + TailwindCSS + Zustand；构建产物纯静态，FastAPI `StaticFiles` 一体化挂载（低配设备不跑独立前端服务）。
- M5.F 三功能卡：
  - cla-m5-f01 Data Panel（SQLite 数据面板：gov/电商价格表 + 趋势）
  - cla-m5-f02 Opportunity Stream（实时机会流：SSE 推送新机会，websocket 备选）
  - cla-m5-f03 Compliance Panel（合规审核台：调用 cla014 审核 API，三级审核操作界面）
- 前端轻量化：无重依赖 UI 框架（纯 Tailwind 手写组件），生产构建后整体内存目标 ≤30MB。

## 方案内容

### 1. 前端工程骨架
- `frontend/`（Vite + React + Tailwind + Zustand），构建产物输出到 `src/api/static/`（FastAPI 挂载目录）。
- 页面路由：数据面板 / 机会流 / 合规审核台。

### 2. 三个视图
- Data Panel：gov_prices/ecommerce_prices 表格 + 筛选 + 简单趋势图（轻量，无 ECharts 重依赖，先用 CSS/表格表达）。
- Opportunity Stream：SSE 实时接收新机会（后端 `/api/stream`），卡片式展示。
- Compliance Panel：待审列表 → 详情 → approve/reject 操作，调 cla014 API。

### 3. FastAPI 一体化挂载
- `src/api/app.py`：FastAPI 应用 + `/api/*` 路由 + StaticFiles 挂载前端构建产物。
- SSE 端点：`/api/stream`（机会/审核事件推送）。

## 转卡计划

按架构定稿 M5.F 三功能卡对齐出卡（功能卡命名沿用 cla-m5-f01/f02/f03）：

### cla-m5-f01 | Data Panel 数据面板
* 颗粒度：2.0 天（前端工程骨架 + 数据面板）
* 依赖：--depends cla005, cla009（数据表就绪，可先 mock）
* 架构位置：`frontend/`（骨架）、`src/api/app.py`（挂载）
* 验收：构建产物被 FastAPI 挂载可访问；数据面板展示两表数据 + 筛选可用；整机内存目标 ≤30MB（观测记录）。

### cla-m5-f02 | Opportunity Stream 实时机会流
* 颗粒度：1.5 天（SSE 端点 + 前端流式卡片）
* 依赖：--depends cla011（机会数据源）
* 架构位置：`src/api/app.py`（/api/stream）、frontend 机会流页
* 验收：新机会 SSE 实时上屏；断线重连；历史机会初始加载。

### cla-m5-f03 | Compliance Panel 合规审核台
* 颗粒度：1.5 天（前端审核操作页）
* 依赖：--depends cla014（审核 API）
* 架构位置：frontend 审核页（调 cla014 API）
* 验收：待审列表/详情/审核动作全流程可用；审核状态实时刷新。

## 备注

- 三卡按依赖链出卡（f01 先立骨架，f02/f03 复用骨架）。
- 前端纯静态部署契约（架构定稿已定）：不引入独立前端服务器，FastAPI 一体化挂载为最终形态。