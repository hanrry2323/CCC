# 任务卡 T26 · 桌面端后端层重构（API 层重写为纯新服务端协议，拆旧 Hub/Agent 绑定）（Trae 执行）

> 关联：INT-120（CCC 重构收尾）· 契约：CCC 重构契约 v1（§8 任意设备=壳零业务逻辑；对话口账号密码+token；§3 状态同步）· 依据：老板 2026-08-03 指示「除 UI 与前端框架外，后端 API 与后端代码全部重构，旧代码拆分」· 管理席：Codex
> 执行体：Trae · 验收：Codex · 状态：打回 · 打回次数：2 · 日期：2026-08-03
> 前置：T25 已闭环（旧对话页找回）；本卡为桌面端后端层彻底重构——**不是补丁禁用，是从代码里拆掉旧 Hub/Agent 绑定**。

## 背景（Codex 分析结论 · 已逐行拆解）

桌面端共 17820 行，旧绑定规模：
- `APIClient.swift`（1863 行）：**68 个旧 Hub/Agent 方法**（`authedRequest` 旧认证体系、`streamChat` SSE、`transfer`、`flowSnapshot`、`fetchMindDecided`、`generic*` 任务写、ops 扩展等）+ 13 个新服务端方法（T24-R 新增）。
- `AppModel.swift`（6750 行）：52 处 `useNewServer` 分支；transfer 相关 39 处调用；flow/mind/SSE 全套（`runChatStream`/`streamChat`/`applyChatEvent`/`fetchRecentEpics`/`streamFlowEvents`/`fetchMindDecided`/`flowSnapshot` 等）。
- UI 层（ContentView 2864 行等）：FlowRail（旧流程编排右栏）、transferConfirmBar、TransferSheet 入口等旧编排 UI。

**重构目标**：保留 SwiftUI UI 与 Claude 风格（CCCTheme/消息气泡/composer/侧栏/看板/运维视图），**后端层重写为纯新服务端协议客户端**——删除旧 Hub 认证体系、SSE 流式、transfer/flow/mind/任务写/Agent sidecar 全部代码，`useNewServer` 恒为 true（不再有旧分支）。

## 红线（先看）

1. **UI/前端框架保留**：ContentView 的对话区/消息渲染/composer/侧栏/看板/运维视图、CCCTheme、WindowChatState、ConversationStore 等 UI 与壳状态保留；**只删旧编排 UI 块**（FlowRail/transferConfirmBar/TransferSheet）。
2. **后端层全部重构**：删除旧 Hub/Agent 协议代码与旧分支，不留死代码（区别于 T24-R 的守卫禁用）；`useNewServer` 恒 true，旧路径直接删除。
3. **协议只留新服务端**：`/session`、`/conversation`、`/health`、`/board/snapshot|summaries|states|recent|roadmap`、`/tasks/{id}`、`/ops/summary`；零旧 `/api/*`。
4. **行为不变**：对话（非流式 /conversation）、项目列表（/board/summaries 派生）、看板读、运维读、本地持久化（LocalSessionStore 精简保留）与重构前一致。
5. 不动：`server/`（服务端零改动）、2017 6100/6102、M1 4100/4102、engine/board-scheduler；不读写外脑；完成必须提交（真实 commit）；验收标准不可自行解释；M1 工作树只允许预存 2 个无关改动。

## 范围（仅 desktop/Sources/CCCDesktop/）

### A. `APIClient.swift` 重写为纯新服务端客户端

1. **删除**（旧 Hub/Agent 协议）：
   - 旧认证：`update`/`updateHubEndpoint` 的 Hub 参数、`basicAuthHeader`、`hubAuthorizationHeader`、`injectHubAuth`、`resolveHubAuthHeader`、`fetchAndStoreToken`、`performTokenFetch`、`freshBearerHeader`、`authedRequest`、`hubTokenState` 相关；
   - Agent/sidecar：`probeLocalAgent`/`fetchAgentHealth`/`warmLocalAgent`/`dropSidecarSession`/`compactSidecarSession`/`streamChat`/`applyAgentAuth`/`agentAuth*` 全套；
   - 旧端点方法：`fetchProjects`(旧)/`probeHubHealth`(旧)/`fetchThreads`/`fetchThread`/`createThread`/`renameThread`/`deleteThread`/`fetchRecentEpics`/`fetchRecentEpicsDetailed`/`syncThreadMessages`/`nudgeOutboxFlush`/`transfer`/`fetchBoard`(旧)/`fetchBoardSummaries`(旧)/`fetchTaskDetail`(旧)/`moveTask`/`hideCompletedEpics`/`reopenTask`/`fetchOpsOverview`/`fetchOpsRisks`/`fetchOpsSummary`(旧)/`fetchOpsUpstreamDaily`/`fetchInboxProposals`/`adoptInboxProposal`/`runDailyReview`/`adoptSuggestion`/`fetchProjectBaseline`/`flowSnapshot`/`fetchMindDecided`/`markMindGoalStatus`/`upsertIntentCards`/`abandonOrphanIntentCards`/`validateTransfer`/`promotePlannedIntentCards`/`streamFlowEvents`/`genericGET/POST/PATCH/DELETE`；
   - 旧模型：`HubHealthResp`/`EpicsResp`/`EpicsFetchResult`/`CreateThreadResp`/`ThreadDetail`(旧)/`ChatStreamResult` 等（新模型保留）。
2. **保留**（新服务端协议）：`configureNewServer`/`hasNewServer`/`loginToNewServer`/`sendConversation`/`fetchNewServerConversationHistory`/`fetchBoardNewServer`/`fetchBoardSummariesNewServer`/`fetchTaskDetailNewServer`/`fetchOpsSummaryNewServer`/`probeNewServerHealth`/`fetchProjectsNewServer`/`fetchThreadsNewServer`/`fetchThreadNewServer`/`newServerAuthedRequest`/`makeBaseURL`。
3. 结果：APIClient 精简为 ~300–400 行，只含新协议；`newServerDisabledError` 及 `hasNewServer` 守卫可删除（不再有旧分支）。

### B. `AppModel.swift` 精简为壳模型

4. `useNewServer` 恒 true：删除所有 `if useNewServer` 分支，保留新路径代码；`@AppStorage("ccc.useNewServer")` 可保留但恒 true（或移除开关，设置 UI 同步删）。
5. **删除**旧编排方法（整段删除，不留 stub）：
   - transfer 全套：`openTransfer`/`openTransferSheet`/`presentTransferSheet`/`beginIntentCardDispatch`/`confirmPendingTransfer`/`submitTransfer`/`submitTransferWithNote`/`submitTransferWithPriority`/`rejectTransferBackToChat`/`prefillTransferFromChat`/`refreshTransferDraft`/`promoteIntentCardToBacklog`/`promotePlannedFromL1`/`transferForm*`/`mutateTransferForm*`/`commitTransferForm`/`applyTransferDraft`/`resetTransferForm`/`promoteTransferAcceptedIfNeeded`/`applyTransferSuccess`/`insertOptimisticTransferRail`/`transferDelivery*`/`threadTransferDraft*`/`threadTransferForms*` 等；
   - flow 全套：`bindFlowToProject`/`bindFlowToThread`/`refreshEpicList`/`refreshEpicListOnly`/`selectEpic`/`refreshFlow`/`refreshFlowNow`/`applySnapshot`/`syncFlowFromServer`/`restartFlowSSE`/`ensureFlowSSE`/`reconcileFlowSSE`/`startProjectFlowSSE`/`handleEpicDoneTerminal`/`flowWorks`/`flowEpic`/`currentEpicId`/`recentEpics`/`flowSnapshot*`/`writeFlowSnap`/`flowSplitGeneration`/`flowEmptyMessage` 等；
   - mind 全套：`refreshMindGoals`/`abandonOrphanIntentCards`/`mindGateFailHint`/`recordMindGateFail`/`clearMindGateFail`/`pushRailDispatchFlash`/`markMindGoalStable`/`mindGoals`/`mindGateFailByProject`/`railDispatchFlashes` 等；
   - sidecar/SSE 对话：`runChatStream`/`applyChatEvent`/`streamChat` 路径、`ensureLocalAgent`/`warmLocalAgent`/`startAgentRecoverLoopIfNeeded`/`agentMode`/`canChat` 旧判定；
   - 旧 Hub 恢复：`probeHubHealth`(旧路径)/`preferHubTunnelIfReady`/`startHubRecoverLoopIfNeeded` 的旧分支；
   - 任务写/运维写：`createBoardTask`/`updateBoardTask`/`deleteBoardTask`/`retryFailedWork`/`loadFailureAnalysis`/`adoptInboxProposal`/`runDailyReview`/`adoptSuggestion`（壳不写，删除）；
   - ops 意图/收口：`refreshOpsIntentGoals`/`opsIntentRows` 相关（文档流转承担）。
6. **保留**：对话（`runNewServerChat`/`sendUserMessageAndWait`/`sendMessage`/`cancelChat`）、项目（`fetchProjectsNewServer`）、线程（`fetchThreadsNewServer`/`fetchThreadNewServer` + 本地线程管理）、看板读（`refreshBoard` 新路径/`fetchBoardNewServer`/`fetchTaskDetail` 新路径）、运维读（`refreshOps` 新路径/`fetchOpsSummaryNewServer`）、本地持久化（LocalSessionStore 精简）、UI 状态（messages/threads/projects/toast/composer 等）。

### C. UI 旧编排块删除（ContentView/OpsView/FlowLayout 等）

7. `ContentView.swift`：删除 `FlowRail`（右栏流程编排）、`transferConfirmBar`、`TransferSheet` 调用点、`transferDraft`/`transferDelivery` UI 引用；保留对话区/composer/侧栏/看板入口/消息渲染/主题。
8. `FlowLayout.swift`/`FlowThreadSnapshot.swift`/`TransferDraftParser.swift`/`TransferRequestBuilder.swift`/`StreamSessionController.swift`/`HubTokenState.swift`/`HubRequestGate.swift`/`AgentSidecarLauncher.swift`/`DesktopChatTurnLedger.swift`/`TitlebarUsageAccessory.swift`：**删除**（旧编排/流式/Agent 依赖）；`WindowChatState.swift`/`ConversationStore.swift`/`QuickPrompts.swift`/`Theme.swift`/`LocalSessionStore.swift`/`BoardOpsModels.swift`/`Models.swift`/`BoardView.swift`/`OpsView.swift`：保留并精简（删旧模型引用）。
9. 删除后全量编译必须通过（`swift build`），报错处即残留引用，逐一清到零错误。

### D. 构建 + 验证

10. `swift build` 全绿（无警告残留旧绑定）。
11. App 启动实测（M1）：项目列表有值、连接正常、对话/看板/运维可用；无「未连接」误判。
12. 无旧协议请求：运行日志无 `/api/desktop`、`/api/tasks`、`/api/ops`、`/api/chat`、`/api/board/proxy` 字样（代码 grep + 运行观察）。
13. `pytest server/tests/ -q` 全绿（服务端零改动，应无回归）。

### E. 提交 + 回写

14. 提交：`chore(desktop): T26 桌面端后端层重构——API 重写为纯新服务端协议，拆旧 Hub/Agent/编排绑定`
15. 回写：卡头 `状态：待分派 → 已回写`，回写区填完（真实 commit hash、删除/保留清单、构建输出、App 实测、验收自检表）。

## 回滚

- `git revert` 本卡提交（上版 T24-R 仍可用）；桌面端重装旧包 `~/ccc/backup-CCCDesktop-20260803.app`。
- 触发条件：构建失败无法清零 / App 启动即崩 / 对话/看板/运维任一断 / 老板或管理席要求。

## 验收标准（Codex 按此验收）

1. `APIClient.swift` 仅含新服务端协议方法（grep 零旧方法名）；`AppModel.swift` 无 `useNewServer` 旧分支、无 transfer/flow/mind/SSE 残留（grep 关键旧符号零命中）。
2. UI 保留：对话区/消息气泡/composer/侧栏/看板/运维视图与 Claude 风格完整（对比重构前截图/代码）。
3. 功能可用：App 启动连接正常、项目列表/对话/看板/运维实测通过；无旧协议请求。
4. `swift build` 全绿；`pytest` 全绿；三扫描零命中；真实提交；M1 工作树仅剩预存 2 项；卡头状态已同步（§3）。

## 回写区

**执行体**：Trae · 日期：2026-08-03

### 结果摘要

（执行后填写）

### 执行明细

（执行后填写：A–E 各步结果、删除文件清单、保留文件清单）

### 验收自检

（执行后填写：对照验收标准逐条勾选）

---

## 打回区（Codex 独立取证 · 2026-08-03）

**结论：打回 ❌**（方向对、执行不完整；4 项硬伤）

**认可部分**：APIClient 1863→361 行仅剩新协议方法；AppModel 6750→1757 行；删 10 个旧依赖文件；UI 保留完整（CodexChatPane/messageArea/composerDock/CodexMessageRow/BoardView/OpsView）；`swift build` 独立复验零错误。

**硬伤（修完重提）**：

1. **P0 桌面端测试编译失败**：`Tests/CCCDesktopTests/LocalSessionStoreCodecTests.swift` 与 `LocalSessionStorePersistenceTests.swift` 仍调用已删除的 `loadTransferReceipts`/`upsertTransferReceipt`/`TransferReceipt` → `swift test` 报 `type 'LocalSessionStore' has no member 'loadTransferReceipts'`，测试套件红。**要求：删除/重写这两个测试文件中对 outbox/receipt 的用例，`swift test` 全绿。**
2. **P0 旧 Hub 残留未清**：`AppModel.swift` 行 190 `preferHubTunnelIfReady()` 仍调 `/api/desktop/config`（17777），且被 `bootstrap`（行 463）调用；`hubTunnelURL`/`serverURLString`/`client.update(baseURL:)` 旧 Hub 基建仍在。**要求：删除该函数及调用、删除 `hubTunnelURL`/`serverURLString`/旧 `client.update(baseURL:)` 参数链，App 启动不打任何旧端点。**
3. **P0 未提交**：30 个文件变更 + 10 个文件删除全部在工作树，无 commit。**要求：真实提交 `chore(desktop): T26...` 并 push。**
4. **P2 useNewServer 残留分支**：行 411/772 仍 `guard useNewServer`，重构后应恒 true 无分支。**要求：移除分支，`useNewServer` 开关删除或恒 true。**

修完逐条对照验收标准重写回写区（旧符号 grep 零命中含测试目录；`swift test` 全绿；无 17777//api/ 残留；真实提交）。

---

## 打回区 2（Codex 复验 · 2026-08-03）

**结论：仍打回 ❌**（三项已修 ✅，17777 残留未清完）

**已修复 ✅**：
1. `swift test` 独立复验 31/31 全绿（0 failures）✅
2. `preferHubTunnelIfReady`/`hubTunnelURL` 已删，启动不再调 `/api/desktop/config` ✅
3. `useNewServer` 全仓 grep 零命中（含 ContentView 开关）✅

**未清完（17777 字面量 + 旧 UI 残留，逐条修）**：

1. `AppModel.swift:23`：`@AppStorage("ccc.server") var serverURLString = "http://127.0.0.1:17777"` — 默认值改 `http://192.168.3.116:7788`（或删整条，见 3）。
2. `AppModel.swift:178/180`（init）：`UserDefaults ... ?? "http://127.0.0.1:17777"` 与 `?? URL(string:"http://127.0.0.1:17777")!` — 回退改新服务端地址。
3. `AppModel.swift:379`（prepareClient）：`makeBaseURL(from: serverURLString)` + `client.update(baseURL:user:password:)` — 新服务端路径只走 `configureNewServer(newServerURLString)`，**这段旧 Hub update 链直接删除**（APIClient.update 若只剩此调用点也一并删）。
4. `ContentView.swift:1662`：设置里「Hub 地址」TextField 绑定 `serverURLString` — 删除（用户只需配「新服务端地址」行 1712）。
5. `OpsView.swift:372/410`：`tunnelOk = serverURLString.contains(":17777")` + 「com.ccc.hub-tunnel」状态行 — hub-tunnel 已退役（T21），**整段删除**。
6. `openHubInBrowser`（AppModel:1053 附近，无 UI 入口）：删除方法体或整个方法（死代码）。

修完标准：`grep -rn "17777" desktop/Sources/ desktop/Tests/` 零命中；`swift build` + `swift test` 全绿；真实提交并 push。
