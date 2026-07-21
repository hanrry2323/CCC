# Brief F2-1 · 编排 soak N=5 + orphan 归零

| 字段 | 值 |
|------|-----|
| brief_id | `F2-20260721-soak-orphan-zero` |
| 波次 | F2 |
| 状态 | `accepted` |
| 定稿人 | 架构 |
| 日期 | 2026-07-21 |
| 依赖 | F1 / F1-2 已合入 |
| 模型提示 | **编排窗用 Auto**；若发现需改 Engine 主循环或新增探针 → 停手升级高级并回架构 |

## 1. 目标

在 `ccc-demo` 跑连续 **N=5** 轮 epic→released（或等价 small 业务 epic），达到：**`orphan_delta=0`、无槽泄漏、无失控残留进程**。让编排面具备「短时无人值守」的最低基线。

## 2. 非目标

- 不重写 Engine 主循环 / 不引入 Temporal / LangGraph  
- 不改 transfer / flow 契约  
- 不动 Desktop（壳）  
- 不强行让真实业务仓全绿；先 `ccc-demo`  
- 不加人批步骤  

## 3. 契约变更

无。若需新增 / 调整探针输出格式，仅改 `scripts/engine/` 内部，不改外部契约。

## 4. 现状与缺口

| 已有 | 缺口 |
|------|------|
| Phase13 reliability 探针（hang / 槽 / orphan） | 长跑 N=5 是否仍 `orphan_delta=0` 未最近验证 |
| `smoke-ccc-demo-soak.sh`（N=3 已绿） | 扩到 N=5 + 失败计数器 / quarantine 路径回归 |
| `smoke-f1-backlog-failover.sh` | 与 soak 联跑未常态化 |

## 5. 分工白名单

| 面 | 参与 | 路径 | 禁止 |
|----|------|------|------|
| **编排** | **是（主责）** | `scripts/engine/` · `scripts/board/roles/` · `scripts/ccc-engine.py`（必要时）· `scripts/smoke-ccc-demo-soak.sh` · `scripts/smoke-f1-backlog-failover.sh` · `tests/scripts/` | 改 Desktop、改 Hub API 字段 |
| 过桥 | 否 | — | |
| 壳 | 否 | — | |
| 架构 | 验收 | 本 brief · `hub-shell-phase-status.md` 行更新 | 代写实现 |

## 6. 行为规格

1. 跑 `bash scripts/smoke-ccc-demo-soak.sh`（或等价）扩展到 **N=5**；若脚本硬编码 N，改为可参数化 `SOAK_N=5`。  
2. 每轮断言：`orphan_delta == 0`；槽位回收计数对齐；无残留 `opencode` / `claude` 子进程超过既定上限。  
3. 联跑 `bash tests/e2e/test_f1_backlog_failover.sh`，确认失败计数器 + quarantine 路径不回归。  
4. 若发现 drift：**先在 brief §8 记现象**，再以最小补丁修 `scripts/engine/`；禁止改契约。  
5. 通过后回写 `docs/product/hub-shell-phase-status.md` 新增一行 `F2-1 soak N=5 + orphan=0 green`。  

## 7. 验收清单

- [ ] `SOAK_N=5 bash scripts/smoke-ccc-demo-soak.sh` 绿（或等价命令）
- [ ] `orphan_delta == 0`（5 轮合计）
- [ ] `bash tests/e2e/test_f1_backlog_failover.sh` 绿
- [ ] `pytest tests/scripts/ -q` 仍绿
- [ ] `phase-status.md` 新增 F2-1 行
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
