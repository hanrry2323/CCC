# Brief H-1 · `epic_done` 流事件补齐（hotfix）

| 字段 | 值 |
|------|-----|
| brief_id | `H1-20260721-epic-done-flow-event` |
| 波次 | hotfix（F3 后） |
| 状态 | `accepted` |
| 定稿人 | 架构 |
| 日期 | 2026-07-21 |
| 来源 | F3-1/F3-2/F3-3 证据链：`flow-events.jsonl` 仅见 `epic_created/fanout/work_status=planned`，缺 `epic_done` |
| 模型提示 | **编排窗用 Auto**；若需改 SSE 端点或 Desktop → 停手升级高级并回架构 |

## 1. 目标

Engine 在 epic `split_status` 转入 `done` 时，**主动**向 `flow-events.jsonl` 追加 `epic_done` 事件，**不依赖 SSE 客户端在线**。让 F3 证据链的 `epic_done` 缺口消失。

## 2. 非目标

- 不改 SSE 端点行为（`desktop.py` 既有 `epic_done` 推送保留）  
- 不改 Desktop 右栏（壳不参与）  
- 不补 `work_status` 后续阶段（in_progress/testing/verified/released）—— 候选 H-2，另开  
- 不改 transfer/flow 契约字段  
- 不改 epic 五态机  

## 3. 契约变更

| 项 | 有无 | 说明 |
|----|------|------|
| flow-events | **有（补语义）** | `docs/product/flow-events.md` 写明 `epic_done` 由 Engine 主动追加（非仅 SSE） |
| 其它 docs | 无 | |

规则：先改 `flow-events.md`，再改 Engine 代码。

## 4. 现状与缺口（根因）

| 已有 | 缺口 |
|------|------|
| SSE 端点 `desktop.py:727-740` 在客户端订阅时推 `epic_done` 并 `append_event` | **无客户端订阅时，`epic_done` 永不落 `flow-events.jsonl`** |
| Engine `gates.py:_refresh_parent_epic` 调 `refresh_epic_lifecycle` 把 `split_status` 写盘为 `done` | Engine 侧 **不调** `flow_events.append_event("epic_done", …)` |
| `_product_fanout.py` 在 fanout 时 `append_event("fanout"/"work_status")` | 无对称的终态事件写入 |

**根因**：`epic_done` 仅由 SSE 路径产出；Engine 路径不写。F3 三仓跑全程无 Desktop SSE 订阅，故 `flow-events.jsonl` 缺终态事件。

## 5. 分工白名单

| 面 | 参与 | 路径 | 禁止 |
|----|------|------|------|
| **编排** | **是（主责）** | `scripts/engine/gates.py`（`_refresh_parent_epic` 或等价）· `scripts/_product_fanout.py`（若更合适放 `refresh_epic_lifecycle`）· `tests/scripts/test_epic_done_flow_event.py`（新）· `docs/product/flow-events.md`（先改）· 本 brief §8 | 改 SSE 端点、改 Desktop、改 transfer/flow 字段、改 epic 五态机 |
| 过桥 / 壳 | 否 | — | |
| 架构 | 验收 | 本 brief · `flow-events.md` 审阅 | 代写实现 |

## 6. 行为规格

1. **触发点**：epic `split_status` 由非 `done` 转为 `done`（即 `refresh_epic_lifecycle` 检测到 `raw_ss != "done"` 且 `new == "done"`）。  
2. **写入**：`flow_events.append_event("epic_done", {"project_id": <pid>, "epic_id": <eid>, "split_status": "done"})`。  
3. **幂等**：仅在转换时写一次；若同一 tick 多次调用，以 `raw_ss != "done"` 守门。  
4. **不依赖 SSE**：Engine 主循环 tick 内直接 `append_event`，不经过 `desktop.py`。  
5. **失败不阻塞**：`append_event` 异常只记日志，不让 kb 门禁失败。  
6. **project_id 解析**：复用 `_product_fanout._project_id_for_workspace(store.workspace)` 既有口径。  
7. **SSE 路径不动**：`desktop.py` 既有 SSE 推送 + `append_event` 保留（客户端在线时会双写一条；可接受，因 JSONL 顺序号 / Desktop `last_terminal_stage` 去重）。若想避免双写，可在 SSE 路径改为只推 SSE 不 `append_event`（因 Engine 已写）——**本 brief 不强制**，由执行面判断；若改需在 §8 注明。  

## 7. 验收清单

- [x] `docs/product/flow-events.md` 写明 `epic_done` 由 Engine 主动追加
- [x] `gates.py` 或 `_product_fanout.py` 在 epic → done 转换时 `append_event("epic_done", …)`
- [x] 转换只写一次（`raw_ss != "done"` 守门）
- [x] `append_event` 异常不阻塞 kb 门禁
- [x] 新测 `tests/scripts/test_epic_done_flow_event.py` 绿（模拟 epic 子卡全 released → 断言 `flow-events.jsonl` 含 `epic_done`）
- [x] `pytest tests/scripts/ -q` 仍绿
- [x] 白名单外无改动

## 8. 执行回贴（执行面填）

| 面 | 摘要 | 自检结果 | 完成 |
|----|------|----------|------|
| 编排 | 先改 `flow-events.md` §实现备注 H-1；在 `_product_fanout.refresh_epic_lifecycle` 于 `raw_ss != "done"` 且 `new == "done"` 时 `append_event("epic_done", {project_id, epic_id, split_status})`；异常仅 warning。未改 `gates.py`（已调 `refresh_epic_lifecycle`，一处写入即可）。SSE 路径不动（可双写）。 | `test_epic_done_flow_event.py` 3 passed；既有 fanout/五态测绿；全量 `tests/scripts/` 绿；未改 desktop/SSE/五态机 | ✅ |

## 9. 架构验收

| 项 | 结果 |
|----|------|
| 结论 | **通过** `461f021` |
| 缺口 | 无；候选 H-2（`work_status` 后续阶段流事件）留待用户新指令 |
| 验收日 | 2026-07-21 |

**审阅：** `flow-events.md` 先改（§5 H-1 + `epic_done` 行加 `project_id?`）；`_product_fanout.refresh_epic_lifecycle` 在 `new=="done" and raw_ss!="done"` 时 `append_event("epic_done", {epic_id, split_status, project_id})`；异常 warning 不阻塞；守门幂等；未改 `gates.py`（一处写入即可，合理）；SSE 不动；3 测绿；白名单内。
