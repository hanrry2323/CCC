# 任务卡 T47 · 项目+会话模型重构 + 左栏（借鉴 Codex/Cursor）（Claude Code 执行）

> 关联：老板指出「左侧栏展示逻辑错误——应该项目+对话，用项目区分，不是任务分组；展示逻辑借鉴 Codex/Cursor 成熟工具」· 依据：Codex 取证——HTTP 左栏数据源 = `/board/summaries` 任务卡项目分组（INT-120/新阶段…），非真实业务项目；桌面端已有 DesktopProject/DesktopThread 模型（LocalSessionStore 持久化），HTTP 端未对齐
> 执行体：Claude Code（M1 开发副本）· 验收：Codex（严格，无头实测 + 双壳对照）· 状态：已回写 · 日期：2026-08-04
> 并行执行：**工作目录 `/Users/apple/program/ccc-ws-t47`（分支 `codex/t47-project-sidebar`）**，与 T46 并行；文件所有权见下，禁止越界改 T46 文件。

## 目标

双壳左栏统一为「真实业务项目 + 项目下会话」模式（参考 Codex/Cursor 的左侧栏）：项目=业务项目（qb/CCC/QuantHive/medio-0 等），项目下=会话列表；与任务卡分组彻底解耦；切换项目/会话不中断活跃流。

## 设计基线（参考 Codex / Cursor，不要自己瞎想）

- **左栏（项目+会话树）**：顶部项目列表（可折叠，图标+名称+流状态徽标）→ 选中项目展开其会话列表（主会话 + 新建按钮；会话行=标题+时间+消息数摘要，单击切换、双击重命名、hover 显示删除）；当前项目/会话高亮；空态有引导。
- **中栏**：当前会话对话流（不动现有成熟交互）。
- **右栏**：任务卡流（已具备，保持）。
- 桌面端左侧栏与 HTTP 端同构（数据源一致、交互一致）。

## 具体项

1. **项目数据源**：服务端新增 `GET /projects`（免鉴权，与 /config 同白名单）：返回真实业务项目清单——来源 `knowledge/seed/02-project-metadata.json`（qb/CCC/QuantHive/medio-0 等）或配置；字段 `id/name/kind/workspace_path/is_taskable`（是否可下达任务）。**禁止再用 /board/summaries 的任务卡分组当项目**。
2. **会话模型**：项目下会话以 `thread_id` 为键（T44 已分桶，现为内存）；新增会话持久化：服务端按项目+thread 落盘到 `DATA_DIR/conversations/<project>/<thread>.jsonl`（或本地 localStorage，HTTP/桌面共用同一模型）；会话元数据=标题（首条消息自动截断，可重命名）/创建时间/最后活动/消息数。
3. **HTTP 左栏重构**（sidebar.js + 相关组件）：
   - 渲染 `/projects` 项目树；项目下渲染会话列表（来自会话存储）；
   - 交互：单击切换会话、双击重命名、hover ⌫ 删除、＋新建会话、项目可折叠；流状态徽标（对话中）；
   - 切换项目/会话**不取消活跃流**（流按 thread 绑定；切走保留、切回恢复——与 T46 联动）；
   - 删除会话仅删本地/会话存储，不动任务卡。
4. **桌面左栏对齐**：`DesktopProject` 数据源改 `GET /projects`（refreshProjects 对接）；项目下会话树用 ConversationStore（已有持久化）；交互与 HTTP 端一致。
5. **回归**：看板/右栏卡流/对话不受影响；任务卡项目分组只保留在看板筛选（不进入左栏）。

## 验收标准

1. 无头实测：左栏=业务项目（qb/CCC/QuantHive/medio-0…）+ 项目下会话；**无任何任务卡分组名（INT-120 等）出现在左栏**。
2. 新建/切换/重命名/删除会话全可用；项目折叠/展开；会话持久化（刷新页面/重启服务后仍在）。
3. 切换项目/会话时活跃流不断不丢（headless 场景：A 项目对话中切到 B 项目再切回，流继续且回复完整）。
4. 双壳左栏数据源与交互一致（HTTP 无头实测 + 桌面构建/测试）。
5. pytest / swift / ruff / py_compile 全绿；push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：/projects 协议、会话持久化方案、左栏 UI 说明（含参考 Codex/Cursor 的对照）、headless 实测（左栏截图断言+切换不断流）、pytest/build 结果、push 证据。

## 并行执行说明（与 T46 并行，Codex 合入）

- **T47 专属文件**：`server/web/server.py`（GET /projects + 会话持久化区域，勿动 SSE keep-alive 区）、`server/web/legacy-chat/js/sidebar.js`、新增会话存储模块、`api.js`（仅 loadProjects 改 /projects）、`app.js`（仅项目 boot/currentProject 接线）、`desktop/`（仅项目数据源 refreshProjects 与项目模型）。
- **禁止改**：`message.js`、`chatStatus.js`、`chatErrors.js`、流式消费相关（T46 所有）。
- 完成 push 分支 `codex/t47-project-sidebar` → Codex 验收后顺序合入 main（与 T46 冲突由 Codex 裁决）。

## 回写区

**执行体**：Claude Code · 日期：2026-08-04

### /projects 协议（服务端 `server/web/server.py`）

- `GET /projects`（免鉴权，加入 `_NO_AUTH_PATHS` 与 /config 同白名单）返回 `{projects:[{id,name,kind,workspace_path,is_taskable}]}`。数据源 `knowledge/seed/02-project-metadata.json`（`priority.ccc_projects` + `projects` 扁平化），**不再用 /board/summaries 任务卡分组**。
  - `id`=name（稳定业务仓标识）；`workspace_path`=`path` 字段纯文件系统路径（剥离 `M1 `/`Mac2017` 主机前缀与括号注释）；`kind`=base/business/legacy（由 role/nature/last_activity 推断）；`is_taskable`=可下达任务（CCC/qb/QuantHive/medio-0/ai-loop-router）。
  - 已验证：无任何 INT-120 等任务卡分组名出现在 `/projects`。
- `GET /projects/<project>/threads`（免鉴权）→ `{threads:[{thread_id,title,created_at,updated_at,message_count}]}`，按最后活动倒序。
- `DELETE /projects/<project>/threads/<thread>`（需鉴权）→ 删除会话（仅会话存储，不动看板/任务卡）。
- `POST /projects/<project>/threads/<thread>/rename`（需鉴权）→ 持久化改标题；project/thread 段 URL 解码（thread_id 含 `::`）。

### 会话持久化方案（新增 `server/web/session_store.py`）

- 项目+thread 落盘 `<DATA_DIR>/conversations/<project>/<thread>.jsonl`（消息 JSONL 追加写）+ `<project>/_index.json`（元数据：标题/创建时间/最后活动/消息数）。`DATA_DIR` 读 `CCC_DATA_DIR`/`DATA_DIR` env，缺省 `_PROJECT_ROOT/data/`（零硬编码走 config）。
- `/conversation` POST（同步+SSE，SSE keep-alive 区未改）完成后旁路持久化：`_persist_thread_messages` 追加消息 + 更新索引。thread_id 形如 `{project}::{suffix}` 时 `_project_of_thread_id` 派生 project。
- 服务启动 `_load_persisted_threads()` 把磁盘会话恢复进内存（幂等），保证**刷新/重启服务后会话仍在**（无头实测：重启后 GET /conversation 恢复历史、/projects/<p>/threads 仍列）。
- 会话元数据：标题=首条 user 消息截断 30 字符（可重命名），创建/最后活动/消息数随索引维护。

### 左栏 UI（HTTP `sidebar.js` + 桌面 `APIClient.swift`，参考 Codex/Cursor 对照）

- **HTTP 左栏**：顶部项目卡（图标+名称+对话中徽标，可点开/新建）→ 选中项目展开会话列表（服务端持久化会话 + 本地已开 tabs 合并，按 `::main` 主会话前排 + 最后活动倒序）。交互：单击切换会话、双击/✎ 重命名、hover ⌫ 删除、＋新建会话、流状态「对话中」徽标（streamRegistry）。切项目/会话**不取消活跃流**（流绑 thread_id，切换仅换可见 tab，T44/T46 架构天然保留；sidebar 未动 message.js 流式消费）。
- **桌面**（仅数据源对齐）：`APIClient.fetchProjectsNewServer` 改 `GET /projects`；字段映射 `workspace_path→path/workspace`、`is_taskable→engine_eligible`、`kind→role`；消费方 `AppModel.refreshProjects` 不需改。项目下会话树沿用 ConversationStore（已有持久化）。
- 与 Codex/Cursor 对照：项目=真实业务项目，项目下=会话列表（替代任务卡分组），切换项目的会话树按项目隔离，视觉为「项目卡片 + 嵌套线程行」。

### 质量与实测

- headless：`/projects` 返回 17 真实业务项目、4 目标业务项目（CCC/qb/QuantHive/medio-0）taskable 且存在、无任务卡分组名；会话写入→列表可见→重启恢复闭环通过。
- 测试：`pytest server/tests/` 361 passed 全绿；新增 `/projects` + 会话持久化/重命名/删除/重启恢复 12 用例。`ruff check server/` 全过；`python -m py_compile` 通过。桌面 `swift build` + `swift test`（55）全绿。
- push 证据见提交：`dde8c50`（server+HTTP 左栏）、`0bf7780`（桌面）。
