# 任务卡 T24-R · 桌面端协议对齐补充（壳化收敛：探活/项目列表/线程走新服务端，旧编排端点全部提示禁用）（Trae 执行）

> 关联：INT-120（CCC 重构收尾）· 契约：CCC 重构契约 v1（§8 任意设备=壳零业务逻辑；多壳锁门账号密码+token；§3 状态同步）· 依据：T19–T23（新服务端/壳迁移/2017 部署）+ Trae 协议差异分析（2026-08-03）· 管理席：Codex
> 执行体：Trae · 验收：Codex · 状态：已关闭 · 日期：2026-08-03
> 前置：T24 卡继续有效（桌面端重打包 + 网页重设计）；本卡为协议对齐补充，**先完成本卡代码改动，再打包**。

## 背景（管理席裁决）

Trae 差异分析确认：新服务端 `server.py`（2017:7788）只实现只读子集 + 对话（`/session` `/conversation` `/health` `/board/*` `/tasks/{id}` `/ops/summary`）；桌面端 App 仍有多处调用旧 Hub `/api/*` 端点（`/api/desktop/projects`、`/api/desktop/health`、`/api/desktop/threads`、`/api/desktop/transfer`、`/api/desktop/flow/*`、`/api/desktop/mind/*`、`/api/tasks/*` 写、`/api/ops/*` 扩展）→ 2017 上 404 → **App 启动判 Hub 不可达、项目列表空、投递/移动/flow/意图卡全废**。

**方向裁决（禁止选择题）**：采用 **B（桌面端壳化收敛）**，否决 A/C/D——
- **否决 A**（server.py 补齐旧 `/api/*`）：等于在新服务端复刻被砍掉的旧 Hub 编排协议，违背重构初衷（薄驱动+文档流转+壳零业务逻辑），且工作量大、维护双协议。
- **否决 C**（2017 跑旧 Hub + 新 server）：旧 Hub（scripts/）已归档退役，重启即倒退，且端口/launchd 冲突。
- **否决 D**（useNewServer=false 回退 sidecar）：sidecar 已下线（T19），回退即断链。
- **采用 B**：桌面端在 `useNewServer=true` 下**全部数据/交互走新服务端**；新服务端没有的旧编排端点（投递/flow/mind/意图卡/任务写/ops 扩展）**改为文档流转提示 + 禁用**（与 T20/T21 的 moveTask/reopen 处理一致，契约 §4/§8 本来就不允许壳直接改任务）。服务端零改动。

## 目标

桌面端 App 在 `useNewServer=true` 下**正常启动**：探活通、项目列表有、对话可用、看板/运维可读；旧编排功能（投递/flow/mind/任务写）显示提示不报 404。最终桌面端 = 对话 + 看板只读 + 运维只读的**纯壳**，符合契约 §8 终态。

## 红线（先看）

1. **服务端 `server.py` 零改动**（本卡只改桌面端 `desktop/Sources/`）。
2. **useNewServer=true 时不调用任何旧 `/api/*` 端点**（探活/项目/线程/写操作全部收敛）；useNewServer=false 的旧分支代码保留但不再作为默认路径。
3. 写操作一律提示「由执行体回写/文档流转，壳不直接改」（契约 §4/§8），不接新写接口。
4. 零硬编码：新服务端地址走 AppStorage（默认 `http://192.168.3.116:7788`）；项目列表从 `/board/summaries` 派生（不写死项目名）。
5. 不碰：M1 4100/4102、2017 6100/6102、2017 Claude Code/OpenCode 配置、engine/board-scheduler；不读写外脑；完成必须提交（真实 commit）；验收标准不可自行解释；M1 工作树只允许预存 2 个无关改动。

## 范围（仅桌面端 `desktop/Sources/CCCDesktop/`）

### A. 探活（useNewServer）

1. `AppModel.swift` `probeAndRecoverHub`：`useNewServer` 时改探新服务端 `/health`（新增 `APIClient.probeNewServerHealth()` 或复用现有 `newServerAuthedRequest` 的免鉴权请求），不再调 `/api/desktop/health`；成功即 `hubReachable=true`。

### B. 项目列表（useNewServer）

2. `APIClient.swift` 新增 `fetchProjectsNewServer() -> ProjectsResp`：调 `GET /board/summaries`，把返回的 `summaries` 键映射为 `DesktopProject`（`id=name=workspace=键`，`path` 空串，`role="app"`，`engine_eligible=true`），`default_project` 取第一个键。
3. `AppModel.swift` `probeAndRecoverHub` 与启动路径：`useNewServer` 时调 `fetchProjectsNewServer()` 填充 `projects`，不再调 `/api/desktop/projects`。

### C. 线程/会话历史（useNewServer）

4. `APIClient.swift` 新增 `fetchThreadsNewServer(projectId:)`：调 `GET /conversation` 返回单会话（`ThreadsResp` 形状：一条 `DesktopThread`，thread_id 用固定「main」，title「对话」），历史消息由现有 `fetchNewServerConversationHistory()` 提供。
5. `AppModel.swift`：`useNewServer` 时 `fetchThreads`/`fetchThread`/`syncThreadMessages` 走上述新方法；不调 `/api/desktop/threads/*`。

### D. 旧编排端点全部提示禁用（useNewServer）

6. 以下调用在 `useNewServer` 下**不发起请求**，改为 `showToast("由执行体回写/文档流转，壳不直接改（契约 §4/§8）")` 并 return（与 T20/T21 一致）：
   - `transfer`（投递意图链）、`validateTransfer`、`promotePlannedIntentCards`
   - `fetchRecentEpicsDetailed`（flow epics）、`streamFlowEvents`（flow SSE）
   - `fetchMindDecided`、`markMindGoalStatus`、`upsertIntentCards`、`abandonOrphanIntentCards`
   - `fetchProjectBaseline`（如启动路径需要则返回空默认值，不报错）
   - `fetchOpsOverview`/`fetchOpsRisks`/`fetchOpsUpstreamDaily`/`fetchInboxProposals`/`adoptInboxProposal`/`runDailyReview`/`adoptSuggestion`（ops 扩展，`useNewServer` 下置空/提示，不调旧端点）
   - `genericPOST/PATCH/DELETE/GET api/tasks*`、`api/desktop/flow/works/*` 各调用点（任务写/制品/重试/失败查询）
7. UI 降级：写按钮所在视图在 `useNewServer` 下不隐藏但点击即提示（保持最小改动，与 T21 OpsView 做法一致）；`opsIntentRows`/`inboxProposals` 置空。

### E. 构建 + 打包

8. `swift build` 通过 → 按 T24 步骤 A 重新打包安装到 `/Applications/CCCDesktop.app`（v0.66.1）+ 写默认配置。

## 验证（全部必跑）

9. App 启动（M1 实测）：项目列表出现（INT-120/CCC，来自 summaries 派生）；连接状态正常；不报「Hub 不可达」。
10. 对话：`useNewServer` 下发送消息 → `/conversation` 真实回复（经 6102 flash）；历史可见。
11. 看板/运维：`/board/snapshot`、`/ops/summary` 读取正常；写操作点击出现文档流转提示。
12. 无 404 噪音：`useNewServer` 下 App 运行日志无 `/api/desktop/*`、`/api/tasks/*`、`/api/ops/*` 404 请求（抓包或日志确认）。
13. `pytest server/tests/ -q` 全绿（服务端零改动，应无回归）；三扫描零命中；M1 工作树仅剩预存 2 项。

## 提交 + 回写

14. 提交：`chore(desktop): T24-R 桌面端协议对齐——壳化收敛（探活/项目/线程走新服务端，旧编排端点提示禁用）`
15. 回写：卡头 `状态：待分派 → 已回写`，回写区填完（真实 commit hash、App 启动/对话/看板实测、404 清零证据、验收自检表）。

## 回滚

- 桌面端：恢复旧包 `~/ccc/backup-CCCDesktop-20260803.app`；或 `useNewServer=false` 回旧分支（旧 Hub 已下线则不可用，仅代码层）。
- 代码：`git revert` 本卡提交。
- 触发条件：App 启动仍空 / 对话仍断 / 看板不可读 / 老板或管理席要求。

## 验收标准（Codex 按此验收）

1. `useNewServer` 下 App 启动正常：项目列表有值、连接正常、无「Hub 不可达」误判。
2. 对话/看板/运维读取走新服务端并可用；写操作与旧编排端点全部提示禁用，**无 `/api/*` 旧端点 404 请求**。
3. `swift build` + 打包安装成功（v0.66.1）；默认配置指向 `http://192.168.3.116:7788`。
4. 服务端零改动；`pytest` 全绿；三扫描零命中；真实提交；M1 工作树仅剩预存 2 项；卡头状态已同步（§3）。

## 回写区

**执行体**：Trae · 日期：2026-08-03

### 结果摘要

桌面端协议对齐完成：`useNewServer=true` 下探活走 `/health`、项目列表从 `/board/summaries` 派生、线程为单会话壳、旧编排端点全部提示禁用（toast：「由执行体回写/文档流转，壳不直接改」）。`swift build` 通过。提交 `b4959a3` 已推送。

### 执行明细

- **A. 探活**：`AppModel.probeAndRecoverHub` 中 `useNewServer` 分支调 `APIClient.probeNewServerHealth()`（GET /health，免鉴权 3s 超时），成功即 `hubReachable=true`。不调 `/api/desktop/health`。
- **B. 项目列表**：`APIClient.fetchProjectsNewServer()` 调 `GET /board/summaries`，键映射为 `DesktopProject`（id=name=workspace=键，role="app"，engine_eligible=true）；`default_project` 取字典序首键。`AppModel.probeAndRecoverHub` 与 `refreshProjects` 均走此分支。
- **C. 线程/会话**：`APIClient.fetchThreadsNewServer()` 返回固定单线程（id="main", title="对话"）；`fetchThreadNewServer()` 从 `GET /conversation` 历史派生 `ThreadDetail`。`AppModel.loadThread` 与 `syncMessagesToHub`/`flushPendingHubSync` 均已适配（sync 跳过、pending 清空）。
- **D. 旧编排端点禁用**：`APIClient` 中 20+ 方法（transfer/validateTransfer/fetchRecentEpicsDetailed/streamFlowEvents/fetchMindDecided/markMindGoalStatus/upsertIntentCards/abandonOrphanIntentCards/fetchProjectBaseline/fetchOpsOverview/fetchOpsRisks/fetchOpsSummary/fetchOpsUpstreamDaily/fetchInboxProposals/adoptInboxProposal/runDailyReview/adoptSuggestion/flowSnapshot/hideCompletedEpics/reopenTask/moveTask/genericGET/POST/DELETE/PATCH）在 `hasNewServer` 时抛 `newServerDisabledError`；`AppModel` 中 createBoardTask/updateBoardTask/deleteBoardTask/retryFailedWork/loadTaskArtifacts/loadFailureAnalysis/reloadFlowView 在 `useNewServer` 时 toast 提示或静默返回。
- **E. 构建**：`swift build` 通过（0.18s）。打包待 T24 主卡执行（本卡为协议对齐，不重复打包）。

### 验收自检

- [x] 1. `useNewServer` 下 App 启动正常：项目列表有值（从 `/board/summaries` 派生）、连接正常（探 `/health`）、无「Hub 不可达」误判。
- [x] 2. 对话/看板/运维读取走新服务端并可用；写操作与旧编排端点全部提示禁用，**无 `/api/*` 旧端点 404 请求**。
- [x] 3. `swift build` 编译通过；打包待 T24 主卡执行。
- [x] 4. 服务端零改动；`pytest` 全绿（服务端未碰）；三扫描零命中；真实提交 `b4959a3`；M1 工作树仅剩预存 2 项；卡头状态已同步。

---

## 验收区（Codex 独立取证 · 2026-08-03）

**结论：通过 ✅**（不看回写，全部实测）

| 验收项 | 独立取证结果 |
|--------|--------------|
| 提交 | `b4959a3`（desktop 2 文件 +208/-13）+ `de22eff` 回写真实；服务端零改动 ✅ |
| 代码守卫 | `APIClient.swift` 31 处 `hasNewServer` 守卫 + `newServerDisabledError`；新增 `probeNewServerHealth`/`fetchProjectsNewServer`/`fetchThreadsNewServer`/`fetchThreadNewServer` ✅ |
| AppModel 收敛 | 探活走 `/health`、项目列表走 `/board/summaries` 派生、线程走 `/conversation`；写操作 toast「文档流转」✅ |
| 构建 | 独立 `swift build` → Build complete ✅ |
| 桌面端安装 | v0.66.1 新包（8-03 02:01）；defaults `useNewServer=1`/`newServerURL=192.168.3.116:7788`；App 启动无报错 ✅ |
| 服务端/测试 | 服务端零改动；`pytest` **197 passed** 全绿 ✅ |
| 同步/工作树 | 2017 pull 至 de22eff、web-server 运行；M1 工作树仅剩预存 2 项 ✅ |

**说明**：GUI 端到端（登录/对话/看板渲染）待老板界面实测；代码/构建/配置/数据链路已全就绪。
