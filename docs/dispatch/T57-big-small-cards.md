# 任务卡 T57 · T-A4 大卡/小卡 + 项目级执行体隔离（Claude Code 执行）

> 关联：阶段 3（T-A4，过夜任务后端链 2/3）· 执行体：Claude Code · 验收：Codex · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-04
> 工作目录：`/Users/fan/program/ccc-dev-ws`；分支：`codex/t57-big-small-cards`（先 `git fetch origin main && git checkout -b codex/t57-big-small-cards origin/main`）
> **分步提交纪律（硬）**：每块完成立即 commit+push；超时 7200s。

## 目标

大卡（epic）/小卡（task）机制：类型字段 + 父卡 + 只有 task 可派发 + epic 聚合视图；执行体注册表项目级绑定（隔离）。

## 具体项

1. **类型/父卡字段**：卡头 `类型：epic|task`（缺省 task）+ `父卡：<id>`（仅 task）；loader/validate 校验（epic 无父卡、task 父卡存在且同项目）。
2. **派发规则**：`decide_work` 只有 task 可派发；epic 不派发（只拆解/聚合）。
3. **聚合视图**：线路图/看板按 epic 聚合子卡进度（已完成/总子卡）；epic 状态由子卡派生（全部关闭+目标达成→待验收）。
4. **项目级执行体隔离**：executors.json 支持按项目绑定（如 qb 卡只派 qb 执行体）；`decide_work` 加项目维度校验（缺省=当前绑定）。
5. 测试任务先行：临时目录占位卡验证 epic/task 流转。

## 红线

1. 只改 server/board/、server/engine/、server/config/、server/web/server.py（聚合接口区）、tests；**禁止改 legacy-chat 前端（T-B2 所有权）**。
2. 旧卡兼容（无类型/父卡字段按 task 处理）。
3. 回写前 push 成功并附证据。

## 验收标准

1. epic/task 卡头校验（非法组合被拦）；epic 不被派发（测试占位验证）。
2. 聚合视图：epic 子卡进度正确（含部分完成/全关）。
3. 项目级执行体：qb 卡只派 qb 绑定执行体（配置示例 + 测试）。
4. pytest 全绿、ruff clean、push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：字段/派发/聚合/隔离实现、测试任务验证、pytest/build、push 证据。

## 回写区

**执行体**：Claude Code（2017）· 日期：
