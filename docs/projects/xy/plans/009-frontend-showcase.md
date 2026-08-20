# 方案 · 前端展示台（M6）

> 项目：xy · 编号：xy-plan-009 · 状态：部分执行 · 作者：OpenCode（集群架构） · 工具：OpenCode
> 批准：老板定里程碑 · 2026-08-20
> 创建：2026-08-20 · 更新：2026-08-20
> 关联卡：xy052、xy053
> 关联方案：无
> 进度：2/4 (50%)
> 里程碑：M6 · 前端展示台
> 子项目：6.1 内容库 API / 6.2 工作流 API / 6.3 预览页面 / 6.4 工作流可视化
> 环境准备：mac2017 xianyu 业务仓可写；video-pipeline 输出目录存在；admin 服务可扩展

## 目标

在现有 admin（7 页 + SQLite + 只读 API 模式）上扩展**生产展示台**：老板打开页面即可看到——每天产出的视频直接自动播放、图文内容直接阅读、任何生产任务当前走到哪个节点一目了然（类扣子工作流可视化，实时刷新）。M7 之前唯一可视化窗口，发布闭环的数据基础。

## 背景

生产链路（topic→writer→rewriter→image→tts→video 状态机，12 个 launchd 守护，worker 池 xy050）已全绿，但**产出与进度零可视化**：视频落在 `video-pipeline/output/<task>/final.mp4`，图文走 IMAGE_TEXT_PIPELINE，进度只能翻日志。admin 已有 7 个页面（topics/tasks/publish/platforms/contents/logs/failures）+ `server.py` 只读 API 模式 + SQLite，直接扩展，不重写不引重型框架。

## 方案内容

四块：

1. **内容库 API**（只读）：扫描 `video-pipeline/output/` 产出目录（视频 final.mp4 + 图文产物），组装元数据（标题/日期/时长/大小/任务号/封面），JSON 接口。
2. **工作流 API**（只读）：接入 pipeline 状态机（VIDEO_PIPELINE / IMAGE_TEXT_PIPELINE stage 定义）+ worker 池运行态，输出任务级阶段进度（当前任务、各 stage 状态：排队/进行中/完成/失败）。
3. **视频/图文预览页面**：内容列表 + HTML5 自动播放 + 图文正文渲染，每日产出自动收录。
4. **工作流可视化页面**（核心）：类扣子节点流展示（topic→route→writer→rewriter→image→tts→video），节点状态着色，自动轮询刷新，失败节点可跳日志。

## 验收标准

- [ ] 打开展示台首页，今日产出视频列表可见，点击即自动播放
- [ ] 图文内容列表可见，正文可阅读
- [ ] 任意生产任务（运行中）在工作流页显示当前阶段，节点状态实时更新（≤10s 刷新）
- [ ] 失败任务在对应节点标红，可跳转查看日志
- [ ] 全部为只读接口，不修改生产核心代码

## 功能卡

### 内容库 API

目标：只读 JSON 接口，返回视频/图文产出目录的元数据列表。

实现：`admin/api/server.py` 新增端点（沿用现有 sqlite/只读模式）：扫描 `video-pipeline/output/` 各任务目录（`final.mp4`/`script.json`/图文产物），组装 `{task_id, title, date, duration, size, type(video|article), path}`；按日期倒序。

验收：`GET /api/v1/library` 返回当日产出列表，字段完整，扫描含新任务自动收录。

颗粒度：API 端点 + 目录扫描，单模块。

依赖：无

架构位置：admin/api/server.py（只读适配层）

### 工作流 API

目标：只读 JSON 接口，返回生产任务阶段进度。

实现：接入 pipeline 状态机 stage 定义与运行态（worker 池/任务状态记录），输出 `{task_id, pipeline, stages: [{name, status}], current_stage, updated_at}`；运行中任务实时反映进度，历史任务返回终态。

验收：`GET /api/v1/workflows` 对运行中任务返回各 stage 状态，节点进度真实可查。

颗粒度：状态源接入 + API 端点，单模块。

依赖：内容库 API（同仓，先出）

架构位置：admin/api/server.py + pipeline 状态读取

### 视频/图文预览页面

目标：展示台首页：视频列表自动播放 + 图文列表正文预览。

实现：`admin/pages/` 新增展示页（沿用 common.js/api.js 轻量模式）：视频卡片列表（点击 HTML5 自动播放，封面/时长/日期），图文列表（标题+正文预览）。

验收：打开页面即见当日产出，视频可直接播放，图文可读。

颗粒度：两个列表页 + 播放交互，多文件。

依赖：内容库 API

架构位置：admin/pages/ + admin/js/

### 工作流可视化页面

目标：类扣子节点流展示生产进度（本方案核心）。

实现：`admin/pages/` 新增工作流页：按 pipeline stage 定义渲染节点流（SVG/轻量实现，不引重型框架），节点状态着色（完成=绿/进行中=蓝/排队=灰/失败=红），10s 轮询刷新，失败节点点击跳日志页。

验收：运行中任务在工作流页显示阶段流转，状态自动更新，失败可定位。

颗粒度：节点渲染 + 轮询 + 日志跳转，单页。

依赖：工作流 API

架构位置：admin/pages/ + admin/js/

## 转卡计划

内容库 API → 工作流 API → 视频/图文预览页面 → 工作流可视化页面（一张一张出，验收过关再下一张）

### 依赖链与并行关系（2026-08-20 定稿）

```
xy052 (6.1 内容库 API) ✅ 已合入（xy052 卡）
  ├── xy053 (6.2 工作流 API)      ← 依赖 xy052 合入（同改 admin/api/server.py，顺序开发）
  │     └── xy055 (6.4 工作流可视化页) ← 依赖 xy053 合入（消费 /api/v1/workflows）
  └── xy054 (6.3 视频/图文预览页面) ← 依赖 xy052 合入（消费 /api/v1/library）

并行规则：
- xy053 与 xy054 代码无交集（server.py vs admin/pages/），理论可并行
- **但 xy 业务仓 isolation.max_concurrent=1（registry.yaml）**，同仓禁止并发执行——实际全部顺序出卡：xy053 → xy054 → xy055
- xy055 必须等 xy053 合入后才能开发（消费 /api/v1/workflows）
- 每张卡独立验收：一张合入后再出下一张（禁止批量建卡）
```

## 备注

- 执行顺序 M6 优先于 M5：老板核心诉求「M7 之前能看到产出视频」，展示台先行。
- 与 M7 衔接：展示台为发布效果追踪留数据位（发布后效果数据可后续并入）。
- 工作流可视化参考扣子（Coze）交互，但实现保持轻量（SVG 节点流），不做拖拽编排——只读展示。