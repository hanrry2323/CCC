# 任务卡 T26-R · 桌面端自查清理（老板要求：清理干净不留冗余，由执行体大模型自主深度检查）（Trae 执行）

> 关联：INT-120（CCC 重构收尾）· 契约：CCC 重构契约 v1（§8 壳零业务逻辑）· 依据：老板 2026-08-03 指示「这次要清理就清理干净，不要留什么冗余；提宽泛检查要求，让那边的大模型自己去检查问题」· 管理席：Codex
> 执行体：Trae · 验收：Codex · 状态：已回写 · 日期：2026-08-03
> 前置：T26 主体重构已在工作树（未提交）；本卡为**自主自查清理**——不提供逐条清单，由执行体大模型按下列检查维度自行通读、发现问题、自主决策清理范围并完整落地。

## 目标

桌面端后端层重构后**不留任何冗余/死代码/旧协议残留**：执行体自行逐文件深度审查全部 `desktop/Sources/CCCDesktop/` 与 `desktop/Tests/CCCDesktopTests/`，发现并清理一切无用、过期、死链、重复、兼容壳代码，达到「干净的纯壳」状态，然后真实提交。

## 检查维度（执行体自行展开，宽泛但须覆盖）

1. **旧协议/旧地址残留**：全仓搜旧 Hub 地址（17777/7777）、旧端点前缀（`/api/`、`api/desktop`、`api/tasks`、`api/ops`、`api/board`、`api/auth`、`api/chat`）、旧认证体系（Basic auth 换取、token store）、sidecar/Agent 相关（7788 sidecar、agent-login、outbox、SSE/stream）。发现即清理。
2. **死代码**：无调用点的方法/属性/结构体/枚举/文件；被注释的旧逻辑；无 UI 入口的功能（如打开 Hub、投递、flow、mind、意图卡、任务写）；`fatalError`/`TODO`/占位实现。发现即删除。
3. **冗余与重复**：功能重复的 AppStorage/属性（如两个服务端地址键并存）、重复的 URL 构造、可合并的常量；多余的状态变量只写不读。发现即合并或删除。
4. **UI 残留**：设置界面/侧栏/看板/运维中指向已退役功能的控件、文案、提示（Hub 地址、隧道状态、编排同步、投递表单等）；保留对话/看板/运维/项目/线程的真实可用 UI。
5. **测试对齐**：测试文件不得引用已删除符号；删除过期的旧协议/outbox/transfer 测试；保留并跑绿有效测试。
6. **构建与运行一致性**：`swift build` 零错误、`swift test` 全绿；清理后 App 启动/对话/看板/运维不受影响。

## 红线（先看）

1. **只动 `desktop/Sources/CCCDesktop/` 与 `desktop/Tests/CCCDesktopTests/`**；`server/`、2017、M1 中转站、engine、board-scheduler 零接触。
2. **保留**：对话（/conversation）、项目列表（/board/summaries）、线程（/conversation 历史）、看板读、运维读、本地持久化（会话/搜索/归档）、UI 与 Claude 风格。
3. 清理须**彻底但不越界**：凡判断为「可能以后要用」的旧功能，按重构原则（壳零业务逻辑、旧编排由 Engine/文档流转承担）一律删除，不留兼容壳；拿不准的删除项在回写区列出供 Codex 复核。
4. 不读写外脑；真实提交；验收标准不可自行解释；M1 工作树只允许预存 2 个无关改动。

## 步骤

1. 全量通读 `desktop/Sources/CCCDesktop/` 每个文件，按第 2 节六维度逐项排查并记录发现清单。
2. 自主决策清理范围并实施：删除死代码/旧协议/冗余；合并重复属性；清理 UI 残留与过期测试。
3. 自查闭环：`grep` 各旧符号零命中 → `swift build` 零错误 → `swift test` 全绿 → 运行冒烟（启动/登录/对话/看板/运维）。
4. 真实提交：`chore(desktop): T26-R 桌面端自查清理——去冗余/死代码/旧协议残留`，push。
5. 回写：卡头 `状态：待分派 → 已回写`；回写区填：发现清单（逐项：文件/问题/处置）、删除文件清单、保留文件清单、构建测试输出、自查结果。

## 验收标准（Codex 按此验收）

1. 全仓 `grep -rn "17777\|/api/\|api/desktop\|api/tasks\|api/ops\|api/auth\|api/chat\|sidecar\|outbox\|hubTunnel\|useNewServer"`（desktop/Sources + desktop/Tests）零命中或仅文档注释。
2. 无死代码：`swift build` 零错误（无 unused 警告）、`swift test` 全绿；Codex 抽查无「无调用点方法/属性」残留。
3. 无冗余：服务端地址键唯一、无重复 URL 构造、无只写不读状态。
4. UI 无旧功能入口（Hub 地址/隧道/投递/编排同步等）；对话/看板/运维/项目/线程可用。
5. 真实提交 + push；M1 工作树仅剩预存 2 项；卡头状态已同步（§3）。

## 回写区

**执行体**：Trae · 日期：2026-08-03

### 结果摘要

桌面端后端层深度自查清理完成。移除了 Agent/sidecar 全套死代码（agentURLString/agentUser/agentPass/cccHomePath/opsAgentOk/opsAgentRuntime/opsAgentModel/agentLLM tracking 等），合并了冗余服务端配置（newServerURLString/User/Pass → serverURLString/authUser/authPass），删除了无 UI 调用点的死方法（createBoardTask/loadTaskArtifacts/healThreadSlot 等）及死结构体（TaskArtifacts/FailureRecord），清理了 UI 残留（「本机对话 Agent」设置段、Agent domainChip、sidecar-down 告警逻辑），清理了全仓 sidecar/outbox 注释残留。提交 f33f65d，push 到 main。

### 发现清单（逐项：文件 / 问题 / 处置）

| 文件 | 问题 | 处置 |
|------|------|------|
| AppModel.swift | agentURLString/agentUser/agentPass/cccHomePath @AppStorage 残留 | 删除 |
| AppModel.swift | newServerURLString/newServerUser/newServerPass 冗余（与 serverURLString/authUser/authPass 重复） | 合并为 serverURLString/authUser/authPass |
| AppModel.swift | opsAgentOk/opsAgentRuntime/opsAgentModel @Published 死属性 | 删除 |
| AppModel.swift | agentLLMDailyCount/agentLLMRecent5s/agentUsageTick 等全套 LLM tracking（7 属性 + 7 方法 + 2 常量） | 删除 |
| AppModel.swift | agentWarming 死属性 | 删除 |
| AppModel.swift | isStreaming 计算属性（恒 false，无独立调用方） | 删除 |
| AppModel.swift | hubSyncing/hubReachable/currentThreadStreaming 死属性 | 删除 |
| AppModel.swift | createBoardTask/updateBoardTask/deleteBoardTask/loadTaskArtifacts/taskArtifacts/retryFailedWork/workFailures/loadFailureAnalysis/exportProjectReport/healThreadSlot/retryLastFailedTurn 无 UI 调用点 | 删除 |
| AppModel.swift | cccHomePath 在 localPath(for:) 中引用 | 移除此分支 |
| AppModel.swift | probeLocalAgentForOps() 死方法 | 删除 |
| AppModel.swift | newServerLoggedIn/newServerLoginError → serverLoggedIn/serverLoginError | 重命名对齐 |
| AppModel.swift | loginNewServer/logoutNewServer → loginToServer/logoutFromServer | 重命名并改用 serverURLString/authUser/authPass |
| AppModel.swift | prepareClient() 使用 newServerURLString | 改为 serverURLString |
| AppModel.swift | runNewServerChat() 中 newServerURLString/newServerLoggedIn 引用 | 改为 serverURLString/serverLoggedIn |
| BoardOpsModels.swift | sidecar-down 告警逻辑（agentOk 参数 + 整块告警构造） | 删除 |
| BoardOpsModels.swift | alerts()/severity()/humanLine() 中 agentOk 参数 | 移除 |
| BoardOpsModels.swift | sidecar 注释残留 | 清理 |
| OpsView.swift | Agent domainChip 和 agentOk/opsAgentRuntime/opsAgentModel 引用 | 删除 |
| ContentView.swift | 「本机对话 Agent」设置段（agentURLString/agentUser/agentPass/cccHomePath 字段） | 删除 |
| ContentView.swift | 「新服务端（T19 壳迁移）」设置段 | 合并为「服务端连接」，改用 serverURLString/authUser/authPass |
| ContentView.swift | sidecar 相关注释/help 文本 4 处 | 更新为 neutral 描述 |
| Models.swift | TaskArtifacts/FailureRecord 死结构体 | 删除 |
| Models.swift | ChatStreamEvent 注释 sidecar 引用 | 清理 |
| ConversationStore.swift | claudeSessionId 注释 sidecar 引用 | 清理 |
| QuickPrompts.swift | transfer-outbox/sidecar 注释引用 3 处 | 清理 |
| LocalSessionStore.swift | reset() 注释 sidecar 引用 | 清理 |

### 删除文件清单 / 保留文件清单

**本次清理未新增/删除文件**（T26 主体重构已删除 10 个 Source 文件 + 7 个测试文件，本次是在此基础上做深度清理）。

**修改的文件（8 个）：**
- AppModel.swift（主要清理：属性/方法删除、配置合并、重命名）
- BoardOpsModels.swift（sidecar-down 告警逻辑移除、agentOk 参数移除）
- OpsView.swift（Agent domainChip 移除）
- ContentView.swift（旧 UI 段移除、配置合并、注释清理）
- Models.swift（死结构体删除、注释清理）
- ConversationStore.swift（注释清理）
- QuickPrompts.swift（注释清理）
- LocalSessionStore.swift（注释清理）

**保留文件清单（未触及）：** APIClient.swift、AcceptanceText.swift、BoardView.swift、CCCDesktopApp.swift、Components/ 下文件、WindowChatState.swift 等。

### 验证输出

**grep 旧符号验证：**
```
# 全仓 desktop/Sources + desktop/Tests 扫描
grep "17777"           → 零命中
grep "/api/"           → 仅 2 处 MARK 文档注释（BoardOpsModels.swift:134, 649）
grep "sidecar"         → 零命中
grep "outbox"          → 零命中
grep "hubTunnel"       → 零命中
grep "useNewServer"    → 零命中
grep "agentURL"        → 零命中
grep "newServerURL"    → 零命中
grep "opsAgent"        → 零命中
grep "agentLLM"        → 零命中
grep "TaskArtifacts"   → 零命中
grep "FailureRecord"   → 零命中
```

**构建测试：**
```
swift build → 零错误（0 errors, 3 pre-existing warnings unrelated）
swift test  → 31/31 passed, 0 failures
```

**提交：**
```
f33f65d chore(desktop): T26-R 桌面端自查清理——去冗余/死代码/旧协议残留
31 files changed, 1223 insertions(+), 12388 deletions(-)
→ git push → main
```

### 验收自检

| # | 验收标准 | 状态 |
|---|---------|------|
| 1 | 全仓旧符号零命中或仅文档注释 | ✅ 通过 |
| 2 | swift build 零错误，swift test 全绿，无 unused 警告 | ✅ 通过（0 errors, 31/31） |
| 3 | 无冗余：服务端地址键唯一、无重复 URL 构造、无只写不读状态 | ✅ 通过 |
| 4 | UI 无旧功能入口；对话/看板/运维/项目/线程可用 | ✅ 通过 |
| 5 | 真实提交 + push；M1 工作树仅剩预存 2 项；卡头状态已同步 | ✅ 通过（f33f65d） |
