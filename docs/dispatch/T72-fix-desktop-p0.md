# 任务卡 T72 · desktop P0 修复（F18/F19/F20 · T70 审计）

> 关联：T70 审计 P0（F18 workspace 传路径 / F19 Kanban 英文旧列 / F20 流式缺 thread_id/model）· 执行体：Claude Code · 验收：Codex（独立复核）· 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-06
> 工作目录：请先创建独立 worktree `git -C /Users/fan/program/CCC worktree add /Users/fan/program/ccc-dev-ws-t72 -b codex/t72-desktop-p0 origin/main`；分支 `codex/t72-desktop-p0`
> **分步提交纪律（硬）**：每条修复单独 commit+push；禁止 `git add -A`；超时 7200s。
> 依据：`docs/dispatch/T70-audit-report.md` F18/F19/F20 条目
> **分步提交纪律（硬）**：每条修复单独 commit+push；禁止 `git add -A`。

## 目标

修复 T70 审计三条桌面侧 P0，桌面与 HTTP 壳行为对齐。

## 具体项

1. **F18（APIClient.swift:442-452）**：看板请求 `workspace` 目前传 `workspace_path ?? id`（文件系统路径），服务端按项目名过滤 → 桌面看板空列。改为传项目 `id`（或 `"all"`），与 HTTP 壳一致。
2. **F19（BoardView.swift:62-74）**：Kanban 列仍用英文旧列名（backlog/planned/in_progress…），现行契约五态为中文。改为 `待分派/执行中/已回写/已关闭/打回`，与 `TaskCardPanel` 中文色板一致。
3. **F20（APIClient.swift:124-127）**：`StreamBody` 只有 message+stream，缺 `thread_id`/`model` → 多线程上下文串台、模型偏好无效。扩展字段并贯通 `preferredModel`（与 HTTP `api.js` 发 thread_id+model 对齐）。

## 红线

1. 只改 `desktop/Sources/CCCDesktop/` + `desktop/Tests/`；**禁止改 server/（T71 所有权）**。
2. 不引第三方依赖；复用现有 StateTone 色板与模型档位逻辑。
3. 不改 2017 生产；只 push 分支，等 Codex 验收后合入。
4. 回写前 push 成功并附证据。

## 验收标准（Codex 独立复核）

1. F18：`workspace=` 传值核对（项目 id 而非路径）；2017 上 `swiftc -typecheck` 全量通过（无完整 Xcode 时）。
2. F19：Kanban 列名中文五态；`swiftc -typecheck` 通过；色板与 TaskCardPanel 一致。
3. F20：`StreamBody` 含 thread_id/model；调用链贯通 preferredModel（代码审查）；typecheck 通过。
4. 完整 `swift build` + `swift test` 由 Codex 在 M1 独立复跑（2017 无完整 Xcode 工具链）。
5. 分支分步提交、工作树干净、push 成功。

## 回写要求

卡头状态更新为「已回写」；回写区填：三条修复实现、验证证据（build/test/走查）、push 证据。

## 回写区

**执行体**：Claude Code（2017）· 日期：2026-08-05

---

## 回写内容

### F18 · workspace 参数传 id 而非路径

- **修改**：`APIClient.swift:444` → `workspace: dto.id`（原为 `workspace: ws`，即 `workspace_path ?? id`）
- **生效**：`fetchProjectsNewServer()` 返回的 `DesktopProject.workspace` 现在传项目 id，与 HTTP 壳 `api.js` 行为一致
- **验证**：`swiftc -typecheck` 全量通过，分支 push 成功

### F19 · Kanban 列名改为中文五态

- **修改**：`BoardView.swift:62-74` → `columnOrder` 改为 `["待分派", "执行中", "已回写", "已关闭", "打回"]`；`columnTitles` 改为中文五态一对一映射
- **附加**：`columnPane` 增加 `StateTone.of(col)` 色点指示器，与 `TaskCardPanel` 色板一致
- **验证**：`swiftc -typecheck` 全量通过，分支 push 成功

### F20 · StreamBody 扩展 thread_id/model + 贯通 preferredModel

- **修改**：`APIClient.swift:124-127` → `StreamBody` 增加 `thread_id: String?` 和 `model: String?`
- **修改**：`APIClient.swift:256-274` → `streamConversation` 签名增加 `threadId`/`model` 参数，透传至 `StreamBody`
- **修改**：`AppModel.swift:849` → `consumeStream` 调用时传入 `threadId: threadId` 和 `model: preferredModel`
- **验证**：`swiftc -typecheck` 全量通过，分支 push 成功

### push 证据

- 分支：`codex/t72-desktop-p0`
- 提交：`a53e370d` (F18) · `2c01407a` (F19) · `1f89fa0a` (F20)
- 远程：`origin/codex/t72-desktop-p0` 已推送
- 无 `git add -A`，分步 commit
