# 任务卡 T53 · 控制台/线路图修复 + 后台任务进程实时展示（Claude Code 执行）

> 关联：阶段 3（控制台/线路图修复，老板 2026-08-04）· 执行体：Claude Code · 验收：Codex · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-04
> 工作目录：`/Users/fan/program/ccc-dev-ws`（2017 开发 worktree）；请先 `git fetch origin main && git checkout -b codex/t53-console-roadmap-fix origin/main`

## 目标

修复控制台/线路图两个已知问题（假"执行中"状态污染 + 线路图按项目聚合乱），并新增「后台任务进程」实时展示（执行中任务/日志尾部/进度指示），让观察窗具备实时查看后台任务的条件。

## 具体项

### A. 真实状态语义（消灭假"执行中"）

1. 卡头新增可选字段 `派发：manual|engine`（缺省 engine）：
   - `server/board/loader.py` 解析（BoardItem 增字段，缺省 engine）；
   - `server/engine/dispatch.py` `decide_work`：`派发=manual` 的卡**不派发、保持待分派**（日志说明"manual 卡由管理席派发"）；FileBoardStore 兼容。
2. 现有管理卡 T48/T49/T50 改为 `状态：待分派 + 派发：manual`（去掉假"执行中"，恢复真实队列语义）。

### B. 线路图/看板按项目聚合

3. 卡头新增可选字段 `项目：<前缀>`（衔接 T-A1 命名规则）：
   - loader 解析（BoardItem.project 优先用该字段）；
   - `server/board/queries.py` 线路图/看板按项目字段聚合（roadmap_by_project 等）；
   - 旧卡兼容：无 `项目` 字段 → 用 `关联` 首段（冒号/空格前）推导，推导不出归「未分类」。
4. 前端 `roadmapPage.js` 按新的按项目数据渲染（修正「INT-12047」「阶段 3 P12」等乱分组）。

### C. 后台任务进程实时展示

5. 后端新增 `GET /tasks/running`（免登录白名单，与 /projects 同组）：返回执行中任务列表——work_id/标题/执行体/开始时间/已用时/**日志尾部 5 行**（读 `EXECUTOR_LOG_DIR/<work_id>.log`）/最近活动时间。
6. 控制台重构（`consolePage.js`）：
   - 状态计数真实（待分派=队列数，执行中=真实在跑）；
   - 新增「后台任务进程」面板：执行中任务卡片（ID/标题/执行体/已用时/日志尾 5 行/活动指示 + indeterminate 进度条）；空态"当前无后台任务"；
   - **8 秒轮询** /tasks/running（简单可靠；SSE 实时推送后置 T49）。
7. 测试补齐：loader 字段解析、manual 不派发、/tasks/running（含日志尾部）、控制台渲染。

## 红线

1. 只在 `ccc-dev-ws` 工作（分支 codex/t53-console-roadmap-fix）；**禁止改 2017 运行副本**。
2. 只改：server/board/loader.py、queries.py、server/engine/dispatch.py、server/web/server.py、server/web/legacy-chat/js/pages/consolePage.js、roadmapPage.js、docs/dispatch/T48/T49/T50 卡头、server/tests/。
3. 零新依赖；API 向后兼容（/tasks/running 为新增，不破坏现有）。
4. commit 拆分合理（A/B/C 可分开提交），回写前 push 分支成功并附证据。

## 验收标准

1. T48/T49/T50 显示为「待分派（manual 队列）」，控制台不再显示假"执行中"。
2. 线路图按项目分组正确（无乱码分组）；旧卡归「未分类」或正确项目。
3. 面板功能由单测 + headless 渲染验证（空态/数据态）；**Codex 验收时跑一条 T9x-test 真实任务，实测面板实时显示**（执行中 + 已用时 + 日志尾部 + 进度指示，任务完成后面板清空）。
4. pytest 全绿、ruff/py_compile clean、push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：A/B/C 实现说明、T9x-test 实测（面板截图/文本）、测试结果、push 证据。

## 回写区

**执行体**：Claude Code（2017）· 日期：
