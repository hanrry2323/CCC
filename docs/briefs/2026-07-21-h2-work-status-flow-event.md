# Brief H-2 · `work_status` 后续阶段流事件补齐（hotfix）

| 字段 | 值 |
|------|-----|
| brief_id | `H2-20260721-work-status-flow-event` |
| 波次 | hotfix（F4 后） |
| 状态 | `accepted` |
| 定稿人 | 架构 |
| 日期 | 2026-07-21 |
| 来源 | F3-1/F3-2/F3-3 证据链：`flow-events.jsonl` 仅见 `work_status=planned`（fanout 时写），后续阶段（in_progress/testing/verified/released/abnormal）不落盘 |
| 模型提示 | **编排窗用 Auto**（单点 hook + 既有 precedent） |

## 1. 目标

work 卡在列间迁移时，**主动**向 `flow-events.jsonl` 追加 `work_status` 事件，**不依赖 SSE 客户端在线**。让 F3 证据链的 `work_status` 后续阶段缺口消失。

## 2. 非目标

- 不改 SSE 端点行为（`desktop.py` 既有 board-poll 合成 `work_status` 保留）  
- 不改 Desktop 右栏  
- 不改 fanout 既有 `work_status=planned` 写入（保留）  
- 不改 transfer/flow 契约字段  
- 不改列迁移规则 / 五态机  
- 不为 epic 迁移发 `work_status`（epic 用 `epic_done`，H-1 已做）  

## 3. 契约变更

| 项 | 有无 | 说明 |
|----|------|------|
| flow-events | **有（补语义）** | `docs/product/flow-events.md` 写明 `work_status` 由 `FileBoardStore.move_task` 主动追加（非仅 SSE/fanout） |
| 其它 docs | 无 | |

规则：先改 `flow-events.md`，再改 store 代码。

## 4. 现状与缺口（根因）

| 已有 | 缺口 |
|------|------|
| fanout 时 `_product_fanout.py` 写 `work_status=planned` | 后续阶段迁移（in_progress/testing/verified/released/abnormal）**不写** flow-events.jsonl |
| SSE 端点 board-poll 合成 `work_status` 推客户端 | 无客户端订阅时不落盘 |
| `FileBoardStore.move_task` 是所有列迁移的单点 chokepoint（dev/reviewer/tester/kb/engine/ccc-board-server 全经此） | move_task 不发 flow 事件 |

**根因**：`work_status` 仅由 fanout（planned）+ SSE（后续）产出；Engine 路径的列迁移不写。F3 三仓跑全程无 Desktop SSE 订阅，故 `flow-events.jsonl` 缺后续阶段。

## 5. 分工白名单

| 面 | 参与 | 路径 | 禁止 |
|----|------|------|------|
| **编排** | **是（主责）** | `scripts/_board_store.py`（`move_task` 成功后 hook）· `tests/scripts/test_work_status_flow_event.py`（新）· `docs/product/flow-events.md`（先改）· 本 brief §8 | 改 SSE 端点、改 Desktop、改 fanout 既有 planned 写入、改 transfer/flow 字段、改列迁移规则、改五态机 |
| 过桥 / 壳 | 否 | — | |
| 架构 | 验收 | 本 brief · `flow-events.md` 审阅 | 代写实现 |

## 6. 行为规格

1. **触发点**：`FileBoardStore.move_task` 成功返回 True 前（或之后，但同一锁内）。条件：`task.get("card_kind") == "work"` 且 `to_col` ∈ {`planned`, `in_progress`, `testing`, `verified`, `released`, `abnormal`} 且 `from_col != to_col`。  
2. **写入**：`flow_events.append_event("work_status", {"project_id": <pid>, "epic_id": <parent_id>, "work_id": task_id, "status": to_col, "from": from_col})`。  
3. **project_id 解析**：复用 `_product_fanout._project_id_for_workspace(self.workspace)`（若 store 有 workspace 属性；否则空串可接受）。  
4. **epic_id**：`task.get("parent_id")`（可能为空，可接受）。  
5. **幂等**：move_task 本身 from_col 校验已防同列迁移；不重复发。fanout 的 planned 写入不在 move_task 路径（fanout 直接创建），故不双写 planned。  
6. **失败不阻塞**：`append_event` 异常只 warning，不让 move_task 失败。  
7. **epic 迁移不发**：`card_kind == "epic"` 跳过（epic 用 `epic_done`，H-1 已管）。  
8. **import**：`from chat_server.services import flow_events as _fe`（precedent：`_product_fanout.py` 已如此；`_board_store.py` 同在 scripts/ 根，无新跨层）。  
9. **SSE 路径不动**：`desktop.py` board-poll 合成 `work_status` 保留（客户端在线时可能双写；JSONL 顺序 + Desktop 去重可接受，同 H-1 口径）。  

## 7. 验收清单

- [ ] `docs/product/flow-events.md` 写明 `work_status` 由 `move_task` 主动追加（§5 或新 §6）
- [ ] `_board_store.move_task` 在 work 卡迁移成功时 `append_event("work_status", …)`
- [ ] epic 迁移不发；非 flow 列（backlog 回退等）按 §6.1 条件过滤
- [ ] `append_event` 异常 warning 不阻塞 move
- [ ] 新测 `tests/scripts/test_work_status_flow_event.py` 绿（模拟 work 卡 planned→in_progress→testing→verified→released → 断言每步 `flow-events.jsonl` 含对应 `work_status`；epic 迁移不发；abnormal 也发）
- [ ] `pytest tests/scripts/ -q` 仍绿
- [ ] 白名单外无改动

## 8. 执行回贴（执行面填）

| 面 | 摘要 | 自检结果 | 完成 |
|----|------|----------|------|
| 编排 | | | |

## 9. 架构验收

| 项 | 结果 |
|----|------|
| 结论 | （待填） |
| 缺口 | |
| 验收日 | |
