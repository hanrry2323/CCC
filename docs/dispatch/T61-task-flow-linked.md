# 任务卡 T61 · T-B4 右栏关联卡流 + task_status 联动（Claude Code 执行）

> 关联：前端四板块架构（T-B4）+ T49 对话即工作 · 执行体：Claude Code · 验收：Codex · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-05
> 工作目录：`/Users/fan/program/ccc-dev-ws`；分支：`codex/t61-task-flow-linked`（先 `git fetch origin main && git checkout -b codex/t61-task-flow-linked origin/main`）
> **分步提交纪律（硬）**：每块完成立即 commit+push；超时 7200s。与 T60 并行，文件所有权见下。

## 目标

对话右栏卡流升级：关联过滤（当前项目未关闭卡 + 本会话关联卡）+ 与 T49 task_status 事件联动（对话内任务状态变化实时反映到右栏），复用 T56 组件。

## 具体项

1. **关联过滤**：右栏默认显示「当前项目未关闭卡」+「本会话最近关联卡」（T49 task_status 关联的 thread_id），提供「全部」切换（进看板）。
2. **task_status 联动**：对话收到 task_status 事件（已创建/已派发/已回写/已验收）时，右栏即时刷新对应卡（8s 轮询保留 + 事件触发即时刷新）。
3. **统一组件**：右栏 TaskCardList 复用 T56（已接入），补齐空态（「下达任务，大脑会写卡」引导）与加载态。
4. headless 实测：关联过滤正确、task_status 事件触发右栏刷新、空态引导、零 console error。

## 红线

1. 只改 server/web/legacy-chat/（js/components/boardPanel.js、js/components/message.js、js/app.js 相关行）+ css + tests；**禁止改 consolePage.js（T60 所有权）**。
2. 复用 T56 组件；不引第三方依赖。
3. 回写前 push 成功并附证据。

## 验收标准

1. 右栏默认关联过滤（当前项目未关闭 + 会话关联）；「全部」切换正确。
2. task_status 事件到达 → 右栏即时刷新（headless 模拟事件验证）。
3. 空态引导文案（「下达任务，大脑会写卡」）在位；零 console error。
4. pytest 全绿（如涉）、push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：关联过滤实现、task_status 联动、headless 实测、push 证据。

## 回写区

**执行体**：Claude Code（2017）· 日期：
