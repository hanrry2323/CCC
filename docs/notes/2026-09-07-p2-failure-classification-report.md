# P2 完成报告 · v2.0 失败分类 + 重试预算 + 待人工终态

> 日期：2026-09-07 · 指令：`/Users/fan/.ccc/instructions/2026-09-07-p2-failure-classification.md`
> 目标仓：`/Users/fan/program/CCC` · 交付头部：见本报告末尾

## 结论

P2 全部改动已落地并验证：**全量 pytest 1439 passed（基线 1425，净 +14）+ 2 skipped，ruff 净**。
`failure_class.py` 单一分类源，散乱的 `transient_probe`/关键字判断收敛为 `FailureClass` 路由。

## 改动清单（6 项全覆盖）

### 1. failure_class 枚举 + 落账
- 新建 `server/engine/failure_class.py`：`FailureClass(StrEnum)` 三值
  （`infra`/`business`/`protocol`）+ `classify_failure` 统一分类源。
- `runtime_state.write_card_state` 增 `business_reject_count` / `protocol_retry_count` /
  `awaiting_human` / `exhausted_class` 字段（sidecar `state/cards.jsonl`）。
- `audit_ledger.record_action` 增可选 `failure_class` / `exhausted_class` 字段
  （只增不改，批准真值账本语义不变）。

### 2. 失败分类 → 动作路由
- **phase2**：`process_one` 按 `classify_failure` 路由：
  - `infra` → 既有冷却（指数退避封顶 1800s），不消耗预算；
  - `business` → 打回 + 计 `business_reject_count`；
  - `protocol`（verdict 协议非法）→ 一次修复轮（30s 后重跑 cc-auditor），仍失败计
    `protocol_retry_count`。
- `audit_card`：verdict `protocol：` 前缀 fail-closed，显式标记 `protocol=True`，
  不再混入 infra 重试。
- **engine main**：`_run_auto_worker` 收单失败按 `classify_failure` 路由；散乱
  `retryable`/`transient_probe` 判断收敛。

### 3. 重试预算统一
- `business_reject_count`（business 类）与 `protocol_retry_count`（protocol 类），
  各自上限 **3 次**（`PHASE2_REJECT_MAX_STRIKES` / `PHASE2_PROTOCOL_MAX_STRIKES`，默认 3，只紧不松）。
- 任一类 ≥3 → 打回（附原因 + class 标签）→ sidecar 记 `reject_budget_exhausted` → 看板可见。
- 人工重派（`POST /tasks/<id>/transition`）清零全部计数。

### 4. 待人工结构化终态
- 预算耗尽打回卡头：`打回（REJECT 预算耗尽，待人工）` / `打回（PROTOCOL 预算耗尽，待人工）`
  ——与「打回」同一 base_state，reason 标注。
- sidecar 结构化：`awaiting_human: true` + `exhausted_class: "business"|"protocol"`。
- `redispatch-card.sh`：检测 `awaiting_human` 时额外输出「此卡预算耗尽，确认后重派将清零计数」。

### 5. infra 环境自检清单
- `run_infra_selfcheck`（只读）四项：①3456 通道连通（`/v1/models` HTTP code）
  ②worktree `.venv/bin/pytest` 存在（fallback `.venv-hub/bin/pytest`）
  ③`ANTHROPIC_BASE_URL` 归一根 ④verdict 工件目录写权限。
- `all_ok=true` → 归因执行体侧；`any_fail` → 归因基础设施侧并升级告警
  （ledger `infra_selfcheck_fail`）。

### 6. 测试
- 新增 `server/tests/test_p2_failure_class.py`（14 用例，mock 不碰真实资源）：
  分类优先级/预算上限/business+protocol 计数/phase2 修复轮/待人工终态/重派清零/engine 侧预算。

## 验证记录

| 项 | 结果 |
|---|---|
| 全量 pytest（ignore t53） | **1439 passed, 2 skipped**（基线 1425+2） |
| ruff check server/ | **All checks passed** |
| 每模块提交并 push | 5 commits，均已推 origin/main |

## 提交清单

```
4246b05fd test(p2): failure classification routing budget and human terminal paths
ea886c7a2 feat(p2): redispatch 预算清零提示 + 看板待人工结构化可见
761b9f235 feat(p2): engine 收单失败分类路由 + business 打回计 reject 预算
ae188de57 feat(p2): phase2 失败分类路由 + protocol 修复轮 + 预算耗尽待人工终态
2980a1193 feat(p2): failure_class enum + sidecar/ledger fields + budget config
```

## 红线核验

- ✅ 不改 xianyu；不改已关闭卡。
- ✅ 不动 `CardStateStore` CAS/锁语义（仅观测面字段扩展）。
- ✅ fail-closed 不放松：verdict 缺失/非法仍 REJECT，P0/P1 阻断不变。
- ✅ 预算只紧不松：上限默认 3，配置只能显式收紧（`max(1, ...)`），不放宽。
- ✅ 不绕过 test-evidence；infra 自检只读不修改环境。

## 部署

- 已推 origin/main；重启 engine + web 后 /health 200。
- head-sha 与 engine pid 见最终输出。

## 最终输出

```
P2-FAILURE-CLASS-DONE <head-sha> <新engine pid>
```
