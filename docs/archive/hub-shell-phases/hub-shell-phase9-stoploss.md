# Hub-Shell Phase9 — abnormal 止损最小可见

> 日期：2026-07-20 · 对齐 [`hub-shell-roadmap.md`](hub-shell-roadmap.md) §3.1

## 目标

人不加人批，但 **看得见、能点开**：存在 abnormal / `user_stage=failed` 时无需翻日志。

## 实现

| 面 | 行为 |
|----|------|
| Hub `flow/snapshot` | work `abnormal` 或 epic `split_status=failed\|blocked` → `user_stage=failed` + 止损 headline |
| Desktop 右栏 | 红条文案 + **开运维** / **看板** / 忽略 |
| Desktop toast | 同一 epic 首次进入 failed 时弹一次 |
| Ops `/api/ops/risks` | 既有 `board_abnormal` 聚合（不新造通知中心） |

## 验收清单

- [x] 单测：`test_snapshot_failed_stage_from_abnormal_and_split`（API 字段非空）
- [x] Client 契约：`tests/scripts/test_phase9_stoploss_client_contract.py`（`stopLossHint` 字符串规则）
- [x] Live API：`scripts/smoke-hub-shell-phase9.sh`（种 abnormal → snapshot `user_stage=failed`）
- [x] Desktop：`stopLossHint` + toast（手工：选有 abnormal 的项目应见右栏红条）
- [x] roadmap §3.1 已勾「止损最小可见」

## 不做

逐步人批、通知中心、推送渠道。
