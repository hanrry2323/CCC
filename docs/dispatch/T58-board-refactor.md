# 任务卡 T58 · T-B2 看板重构（列表默认 + 视图切换）（Claude Code 执行）

> 关联：阶段 3（T-B2，过夜任务前端链 2/2）· 执行体：Claude Code · 验收：Codex · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-04
> 工作目录：`/Users/fan/program/ccc-dev-ws`；分支：`codex/t58-board-refactor`（先 `git fetch origin main && git checkout -b codex/t58-board-refactor origin/main`）
> **分步提交纪律（硬）**：每块完成立即 commit+push；超时 7200s。

## 目标

看板重构：默认列表视图（高密度 + 分页 + 筛选搜索，复用 T56 TaskCardList）+ Kanban 列视图可选切换 + 按项目/执行体分组视图。

## 具体项

1. **列表视图（默认）**：复用 TaskCardList/cardApi（/cards 分页+搜索），高密度行 + 筛选栏（项目/状态/执行体/搜索）。
2. **看板视图（可选）**：按状态分列（Kanban），列内「加载更多」；复用 TaskCard。
3. **分组视图**：按项目/执行体分组折叠。
4. **视图切换**：顶部切换（列表/看板/分组），记忆偏好（localStorage）。
5. headless 实测三视图 + 500+ 卡虚拟滚动。

## 红线

1. 只改 server/web/legacy-chat/（pages/boardPage.js、css/、components/）+ tests；**禁止改 server/board、server/engine、server.py（T57 所有权）**。
2. 复用 T56 组件（TaskCard/TaskCardList），禁止再拼 DOM。
3. 回写前 push 成功并附证据。

## 验收标准

1. 三视图切换可用；列表默认 + 筛选搜索分页（与 /cards 一致）；Kanban 列加载更多；分组折叠。
2. 500+ 卡虚拟滚动流畅（临时数据验证）。
3. 零 console error；旧看板渲染代码清零。
4. pytest 全绿（如涉）、push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：三视图实现、headless 实测（截图/文本）、旧渲染清零清单、push 证据。

## 回写区

**执行体**：Claude Code（2017）· 日期：
