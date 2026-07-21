# Brief F1-2 · 投递三态零谎报

| 字段 | 值 |
|------|-----|
| brief_id | `F1-20260721-transfer-delivery-honesty` |
| 波次 | F1 |
| 状态 | `accepted` |
| 定稿人 | 架构 |
| 日期 | 2026-07-21 |
| 依赖 | F1 断线恢复已合入（`F1-20260721-disconnect-recovery`） |
| 模型提示 | **壳窗用 Auto**；若要动 hub-api 字段则停手升级高级并回架构 |

## 1. 目标

投递态（`draft` / `queued` / `delivering` / `delivered` / `accepted` / `failed`）与真实过桥结果一致：**不把失败显示成已受理，不把仅 HTTP 成功、无 `epic_id` 显示成已投递，不在 Hub 断线时显示已投递。**

## 2. 非目标

- 不改 transfer 请求/响应字段表（无契约破坏）  
- 不重做 outbox / Hub recover（F1 已做）  
- 不动编排面  
- 不新增多人审步骤  

## 3. 契约变更

| 项 | 有无 | 说明 |
|----|------|------|
| hub-api-v1 | 无字段变更 | 对齐 §1 三态 + `queued` 机状态 |
| 其它 docs | 按需 | 若 UI 文案与 `TransferDeliveryPhase` 不一致，只改 Desktop 或在 `desktop-connection.md` 加一行「态→文案」 |

## 4. 现状与缺口

| 已有 | 缺口 |
|------|------|
| `TransferDeliveryPhase` + 右栏/表单展示 | 审计所有 `setTransferDelivery` 路径：空 `epic_id`、超时、5xx、用户取消、flush 部分失败 |
| `applyTransferSuccess` 已拒空 epic | 确认 UI 无旁路把「转任务按钮成功动画」当成 accepted |
| outbox queued 文案 | Hub 恢复后态迁移是否每笔都更新；多 thread 互不污染 |

## 5. 分工白名单

| 面 | 参与 | 路径 | 禁止 |
|----|------|------|------|
| 壳 | 是 | `desktop/Sources/CCCDesktop/AppModel.swift` · `Models.swift` · `ContentView.swift`（仅投递态展示） | sidecar、Engine |
| 过桥 | 否（默认） | — | |
| 编排 | 否 | — | |

## 6. 行为规格

1. 仅当 `epic_id` 非空才进入 `delivered`。  
2. `accepted` 仅当 flow/snapshot（或既有 `applyTransferSuccess` 内已定义的受理信号）确认；禁止 transfer HTTP 200 直接跳 `accepted`（若现状已跳，改为 delivered，受理仍走原路径）。  
3. Hub 不可达或入 outbox → 必须 `queued`（或 `failed` 若超次），禁止 `delivered`。  
4. `failed` 须可见短因（既有 error/toast 即可）。  
5. 同 `thread_id` 态以最后一次权威事件为准；禁止他 thread 覆盖。  

## 7. 验收清单

- [ ] 代码审阅：所有 `setTransferDelivery` 符合 §6  
- [ ] Hub down 转任务 → UI `待投递`，非已投递/已受理  
- [ ] 空 epic / 失败路径 → `failed` 或回 `queued`，非 `accepted`  
- [ ] Hub 恢复 flush 成功 → `delivered`/`accepted` 与 F1 toast 不矛盾  
- [ ] 白名单外无改动  

## 8. 执行回贴（执行面填）

| 面 | 摘要 | 自检结果 | 完成 |
|----|------|----------|------|
| 壳 | 去掉 bindFlow 后无条件 `accepted`；仅 `epic_id`→`delivered`，`engine_wake`/`flowConfirms`/`applySnapshot`→`accepted`；flush 仅成功计数；态按 thread；状态栏分色 | 审阅全部 `setTransferDelivery` 符合 §6；`swift build` 绿 | ✅ |

## 9. 架构验收

| 项 | 结果 |
|----|------|
| 结论 | **通过** `578e7fe` |
| 缺口 | 无 |
| 验收日 | 2026-07-21 |

**审阅：** `applyTransferSuccess` 返回 Bool；空 epic → `failed` + 出队（防毒丸）；`delivered` 仅 epic_id 非空；`accepted` 仅 `engine_wake.ok` 或 `flowConfirmsOrchestrationAccepted`；`setTransferDelivery` 守空 thread；UI 颜色区分 failed/accepted；a11y label 已加。
