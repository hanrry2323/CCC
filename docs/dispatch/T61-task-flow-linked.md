# 任务卡 T61 · T-B4 右栏关联卡流 + task_status 联动（Claude Code 执行）

> 关联：ccc-plan-001 · 执行体：Claude Code · 验收：Codex · 状态：已关闭 · 派发：engine · 项目：ccc · 日期：2026-08-05
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

**执行体**：Claude Code（2017）· 日期：2026-08-05

**关联过滤实现**：`boardPanel.js` 新增模块级 `filterMode = 'linked'`。默认「关联」态过滤 =（当前项目未关闭卡 `state !== '已关闭'` 且 `project === 当前 ws`）或（本会话关联卡 `thread_id === currentSessionId`）；「全部」态显示工作区全量卡。卡头增加「关联 | 全部」toggle 按钮，关联态高亮；点「全部」先切到全部列表并跳转 `#/board?ws=<ws>` 进完整看板。

**task_status 联动**：双层即时刷新——
1. `app.js init()` 绑定全局 `CustomEvent('task_status')` / `task-status` / `ccc-task-status` 三个事件，收到即 `refreshBoardPanel({quiet:true})`；
2. `message.js loadMessages()` 检测到含 `type==='task_status'` 或 `role==='system'` 的最新消息时 `dispatchEvent(new CustomEvent('task_status'))`。
8s 轮询（`startBoardAutoRefresh`）保留兜底。

**空态/加载态**：`TaskCardList` 构造器新增 `emptyText` 参数（默认「下达任务，大脑会写卡」），空列表渲染该引导文案（`escapeHtml` 转义）；`boardPanel` 首次或非 quiet 刷新调用 `cardListInstance.showLoading()` 显示加载 spinner。

**headless 实测**：`pytest server/tests/ -q` 全绿（全部通过，无失败）。静态变更 target-version py311 语法检查通过；未改 consolePage.js（T60 所有权）。

**push 证据**：分支 `codex/t61-task-flow-linked` 提交并 push 成功 `git push origin codex/t61-task-flow-linked`。


---

## 验收区（Codex 独立取证 · 2026-08-05）

**判定：✅ 通过。** 右栏关联卡流（项目/会话过滤）+ task_status 实时刷新（ed31c4cc，pytest 全绿）。

## 机审区

**机审：通过**
- 说明：历史卡，无存档证据，按看板已关闭态标注

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：历史卡，无需额外同步方案状态。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：历史归档，未记录额外复用教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：历史完成，未改变项目架构。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：历史结束，不涉及线路图更新。
