# Brief F1 · 断线恢复（手感）

| 字段 | 值 |
|------|-----|
| brief_id | `F1-20260721-disconnect-recovery` |
| 波次 | F1 |
| 状态 | `accepted` |
| 定稿人 | 架构 |
| 日期 | 2026-07-21 |

## 1. 目标

Hub 短暂不可达时：**对话不中断、状态不谎报、转任务进 outbox**；Hub 恢复后：**自动探活并完成 outbox 投递 + 右栏 snapshot/SSE 对齐**，用户不必只靠点「重试」。

一句话：**断线可聊可排队；恢复自动收口，且文案诚实。**

## 2. 非目标

- 不重做 Phase5b 脚本契约（`smoke-hub-outage-outbox.sh` 已绿，可作回归基线）
- 不改 transfer 字段语义 / 不 bump Hub API 大版本
- 不动 Engine / board/roles（编排面）
- 不把「逐步人批」加进恢复路径
- 不解决 sidecar 整机宕机（已有 agent recover loop；本 brief 只盯 **Hub 断 / 恢复**）

## 3. 契约变更

| 项 | 有无 | 说明 |
|----|------|------|
| transfer-gate | 无 | |
| flow-events | 无（行为对齐既有：重连先 snapshot 再 SSE） | 若改客户端行为，在 `desktop-connection.md` 写清 SLA |
| hub-api-v1 | 无字段变更 | `queued`→恢复→`delivered`/`accepted` 口径不变 |
| 其它 docs | **有** | 必改：`docs/product/desktop-connection.md`（Hub 自动恢复 SLA）；可选一句链到本 brief |

规则：先改 docs，再改 Desktop 代码。

## 4. 现状与缺口（架构结论）

| 已有 | 缺口（本 brief 要补） |
|------|----------------------|
| 可聊 ⊥ Hub（sidecar）；文案「Hub 暂不可达（可聊）」 | Hub 宕后 **无对称 auto-recover loop**（sidecar 有 `startAgentRecoverLoop`，Hub 主要靠手动 `reconnect()`） |
| transfer 失败 → `transfer-outbox.json`；`flushTransferOutbox` 在 `refreshProjects` 成功路径 | Hub 恢复后若用户不点重试，**outbox 可能一直挂 queued** |
| flow SSE 断线有 backoff 重连 | 恢复后须保证 **snapshot 兜底 + boundEpic 不串**（已有逻辑，验收时手测） |
| `smoke-hub-outage-outbox.sh`（脚本模拟 outbox flush） | 缺 **Desktop 手感验收清单**（自动探活 + toast + 投递态） |

## 5. 分工白名单

| 面 | 参与 | 允许改动的路径 | 禁止 |
|----|------|----------------|------|
| **壳** | **是（主责）** | `desktop/Sources/CCCDesktop/AppModel.swift` · 相关 UI（`ContentView.swift` 等，仅连接/投递态文案） · 必要时 `LocalSessionStore.swift` | 改 sidecar 协议；改编排脚本 |
| **过桥** | **按需** | 仅当发现 Hub 探活/SSE 重连缺字段时：`scripts/chat_server/` 最小补丁 + 对应测 | 无关路由大改 |
| **编排** | **否** | — | |
| **架构** | 验收 | 本 brief · `desktop-connection.md` 审阅 | 代写实现 |

并行：契约文档先合；壳实现可与过桥串行（默认无过桥活）。

## 6. 行为规格（执行面照此实现）

### 6.1 Hub 不可达

1. `canChat == true`（sidecar 健康）时，界面 **不得** 呈现全局「未连接 / 不可用」以致误导不能聊。  
2. 状态栏 / stack：保留「本机 Agent · Hub 暂不可达（可聊）」类口径。  
3. 转任务：入 outbox，投递态 = `queued`（「待投递」）；toast 可保留「已排队待投递」。  
4. 对话继续：本机会话 SSOT 不变。

### 6.2 Hub 恢复（本 brief 核心增量）

1. Hub 不可达期间启动 **轻量探活循环**（建议间隔 3–5s，成功即停；与 `HubRequestGate` 共存，勿打爆）。  
2. 探活成功 → `hubReachable=true` → 依次：`flushPendingHubSync` → `flushTransferOutbox` → 当前项目 `refreshFlow` / snapshot（或等价 `bindFlowToCurrentThread`）。  
3. 若本轮 flush 投出 ≥1 笔 transfer：toast **「Hub 已恢复 · 排队任务已投递」**（或等价短句）；投递态走向 `delivered` / `accepted`（既有 `applyTransferSuccess`）。  
4. 若 outbox 空：toast 可选短句「Hub 已恢复」或仅更新状态栏（避免吵）。  
5. 手动「重试 / 重新连接」仍可用，且与自动探活 **幂等**（不双投；依赖 `client_request_id`）。

### 6.3 指标（流畅基线对齐）

| 指标 | 目标 |
|------|------|
| Hub 断 ≥10s | 仍可聊；非「未连接」误报 |
| Hub 恢复后自动探活 | ≤5s 内检测到（探活周期上限） |
| 恢复后 outbox | 无需用户再点一次即可 flush（或点一次与自动等效） |
| 右栏 | 恢复后 snapshot 与 `boundEpicId` 一致，不串他 epic |

## 7. 验收清单（架构照单勾）

- [ ] `docs/product/desktop-connection.md` 已写明 Hub 自动恢复 SLA（探活间隔、flush 顺序、文案）
- [ ] Hub down：sidecar 健康时可继续发消息；状态非全局「未连接」
- [ ] Hub down：转任务 → `queued` + outbox 落盘（`~/Library/Application Support/CCCDesktop/transfer-outbox.json`）
- [ ] Hub up（不点重试或仅依赖自动探活）：outbox 清空或成功项出队；出现 delivered/accepted 或成功 toast
- [ ] 恢复后右栏：snapshot/SSE 正常；`boundEpic` 不串轨
- [ ] 回归：`CCC_SERVER=… CCC_AGENT=… bash scripts/smoke-hub-outage-outbox.sh` 仍绿（若环境可达）
- [ ] 白名单外无改动；不对 orch 投 backlog

### 建议手测步骤（壳自检后回贴）

1. Desktop 开业务项目会话，确认可聊。  
2. 停 2017 Hub（或断到 `:7777`），确认仍可聊 + 状态「Hub 暂不可达」。  
3. 定稿转任务 → 见「待投递」/ outbox 有项。  
4. 恢复 Hub，**先等 ≤5s 不点重试**，观察是否自动恢复并投递。  
5. 看右栏是否对齐；再跑 Phase5b smoke（可选）。

## 8. 执行回贴（执行面填）

| 面 | 摘要 | 自检结果 | 完成 |
|----|------|----------|------|
| 壳 | | | |
| 过桥 | | | |
| 编排 | — | — | 不参与 |

## 9. 架构验收

| 项 | 结果 |
|----|------|
| 结论 | （待填：通过 / 打回） |
| 缺口 | |
| 验收日 | |

## 派发说明（给人看）

- **主对话窗**：架构（本 brief）。  
- **壳窗**：打开本文件，只改 §5 白名单路径；做完填 §8。  
- **过桥窗**：默认不开；壳若发现 Hub 侧 blocker 再开，并回贴。  
- **编排窗**：本轮关闭。
