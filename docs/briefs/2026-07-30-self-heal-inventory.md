# CCC 编排自愈盘点（2026-07-30）

> 代码路径为准；权威见 `docs/product/loop-engineer-authority.md`「编排自愈硬指标」。  
> 实测：Mac2017 `apps/{hp,qb,xianyu,medio-0,qx-observer}` failures/quarantines + `~/.ccc/repair-queue.jsonl`（29 pending epic_optimize 积压）。

## 分层图

```
L1 Engine（2017 tick）
  auto_heal_workspace          pending_no_fanout 有限重扇出 + 沉底孤儿 running
  hang.py                      no_progress salvage → killpg → 耗尽 quarantine
  _retry_abnormal_failures     should_auto_refeed ≤2；耗尽 → enqueue_epic_optimize
  short_path / fail_loop       budget 耗尽 → quarantine + L3b 入队
       ↓
L2 Hub board_repair
  clear_blockers               **先** reopen_recoverable → 再 archive exhaust/failed
  failure_pack                 optimize_hint + transfer_lessons + seed planned 意图卡
  status.repair_queue          暴露本机 pending（Engine 写 ~/.ccc/repair-queue.jsonl）
  POST /repair-queue/claim     sidecar 领取 → inject_block（L3b 强制）
       ↓
L3 Desktop / sidecar（M1）
  hub_voice + lens 注入         板堵强制 hub_repair；修板后必须再投链
  repair-queue claim（隧道）   注入 post-exhaust SOP（禁只藏卡）
  outbox → Hub transfer        gate 绿进代办 + wake
       ↓
L3b Agent 优化意图链
  failure_pack.optimize_hint → 改卡 → **自动投 ccc-transfer**（禁 invent / 禁等人点）
       ↓
L4 人
  仅红灯 / 改意图 / supersede；禁止当修板工
```

## 每层触发条件

| 层 | 触发 | 动作 | 不做 |
|----|------|------|------|
| L1 hang | idle≥300s / CPU hang | salvage→kill→≤1 relaunch；耗尽 quarantine+`hang_detected` | 无限 relaunch；加 MAX_CONCURRENT 代替收尸 |
| L1 refeed | abnormal + 非 exhaust 关键字 | reopen→planned ≤2 | epic / permanent / 耗尽关键字 |
| L1 auto_heal | tick | pending 重扇出；沉底 stuck running | 每 tick `clear_blockers`（防误藏） |
| L2 clear | Agent/`hub_repair` | 可恢复 reopen（含 ui_hidden）→ 藏不可恢复 + purge 幽灵轨 + wake | 先藏还可重试卡 |
| L2 failure_pack | exhausted / Agent | 桶+hint+lessons+回流 planned | 写 backlog / invent |
| L2 claim | sidecar 每轮 | pending→injected + SOP 块 | 静默丢队列 |
| L3/L3b | 板红 / claim 注入 | repair→optimize→**自动投链** | 「请用户复制」；只归档结案 |
| L4 | 意图变更 / 红灯 | 人改目标 | 日常清板 |

## 失败桶（field-backed · `_failure_buckets`）

| 桶 | 样例（2017） | exhaust？ | 处方要点 |
|----|--------------|-----------|----------|
| hang | `hang auto-restart 耗尽` | 是（耗尽标记） | 缩小 1 work / 短探针 |
| acceptance_fail | `acceptance-gate: acceptance_empty_bullets` / `acceptance_cmd_failed` + budget | budget 才 exhaust | 修探针；认 `### 验收` |
| phase_unresolvable | hp `phase graph unresolvable` | 是 | 单 phase；禁 product regen |
| fail_loop_exhausted | medio reviewer/tester loop | 是 | 改 plan；读 review_fail |
| stale_inflight | qb `in_progress 滞留 2.0h` | 是 | 缩小卡面 |
| dirty_block | Author: / docs/reports 假脏 | 否（噪音） | 门禁后 reopen；禁卫生 epic |
| reviewer_timeout | `reviewer 未产出 verdict` | 否（瞬态） | reopen / 短路径审 |
| product_timeout | qb `product async timeout after 1200s` | 否（首击） | 缩小扇出 |
| timeout | 其它 timeout | 否 | 先 reopen |

**硬对齐**：`is_exhaust_reason` ↔ `should_auto_refeed` 耗尽关键字；禁止「凡 acceptance_fail 即 exhaust」。

## 缺口（本轮前）→ 处置

| 缺口 | 证据 | 处置（v0.65.3） |
|------|------|----------------|
| `acceptance_empty_bullets` 落 other | qb repair-queue buckets=other | classify 认 `acceptance-gate` / empty |
| `is_exhaust_reason` 过宽 | 凡 hang/acceptance_fail→不可 reopen | 仅耗尽标记才 exhaust |
| repair-queue 29 条无人消费 | 2017 pending；sidecar 不读 | Hub claim + sidecar 并行注入 |
| status 无队列可见性 | Agent 不知 L3b 待办 | `status.repair_queue` |
| 假红桶无处方 | dirty / reviewer / product | 新桶 + optimize_hint |
| 清障当结案 | SOP 有文、注入弱 | hub_voice + sidecar 板务强制再投链 |

## 测过 / 漏测 → 补测

| 已有 | 覆盖 | 本轮补 |
|------|------|--------|
| `test_board_repair` | clear 先 reopen、archive 证据 | + exhaust/transient 分流 |
| `test_post_exhaust_optimize` | buckets、failure_pack reflow、queue dedupe | 保留；与新 is_exhaust 对齐 |
| `test_gate_*` / salvage / pipeline_efficiency | 门禁与产线 | 未改逻辑；回归跑 |
| **漏** field 桶 / exhaust 对齐 / claim 注入 | — | `test_self_heal_buckets` · `test_repair_queue_claim` |

## 红线（不变）

- `invent_hard_disabled` 不绕；不对 orch 写业务 epic  
- 清障 ≠ 解决问题；耗尽必须优化意图链并自动投  
- 业务仓 main 由 Engine/DoD 提交；Cursor 不做逐卡合入闸  
