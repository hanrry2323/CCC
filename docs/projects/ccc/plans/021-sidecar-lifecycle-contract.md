# 方案 · sidecar 生命周期契约 + Engine 收口（A 轨平台根治 · clw019 挂死根因）

> 项目：ccc · 编号：ccc-plan-021 · 状态：作废 · 作者：OpenCode（M1 平台自研） · 工具：OpenCode
> 创建：2026-08-11 · 更新：2026-08-11
> 关联方案：ccc-plan-020（集群 Worker 池）
> 依据：ENGINEERING-CANON §三-1（sidecar 状态生命周期契约）· 红线 6（平台不自我开发，M1 直接开发）

## 目标

根治 sidecar 状态「只写不清」导致的三类事故：
1. **manual/未登记卡挂死**（clw019：机审打回→sidecar 残留待分派→看板失真→挂 7 小时）
2. **看板被 sidecar 覆盖显示失真**（打回卡磁盘态 vs sidecar 态双源漂移无收口）
3. **孤儿读逻辑**（1407 行读 `state=="已回写"` 但从未有代码写该值）

原则：**sidecar = 在途执行态；终态由磁盘卡 + 分支信封唯一权威。** 不解决此契约，0.4.0 集群 Worker 会在「认领/收单」上重演同样的双源漂移。

## 现状分析（已核实）

### sidecar 写入点（全部）
| 位置 | 写什么 | 何时 |
|------|--------|------|
| `_hold_infra_failure` (229) | state=work.state + infra_count + cooldown | infra 失败冷却 |
| infra 打回 (2333) | state=REJECTED + infra_count | infra 连续失败熔断 |
| `_run_auto_worker` 成功 (2284) | infra_count=0（**不写 state**） | 执行成功 |
| `_run_audit_worker` 成功 (2386) | infra_count=0（**不写 state**） | 机审通过 |

### sidecar 清除点
**0 次**（`clear_card_state` 从未被调用）→ 双源漂移无收口。

### 孤儿逻辑
`_dispatch_and_collect` (1407) 读 `rt.get("state") == "已回写"`，但全仓无代码写 `state="已回写"` → 永远走 fallback 读日志 `ok:true`。读侧与写侧字段不一致。

### 挂死机制（clw019 实证链路）
1. manual 卡（执行体=W9/manual）→ `decide_work` 返回 MANUAL → 挂起等人接单（2622），**不写 sidecar**
2. 机审打回 → `_fail_retry_or_reject` → 磁盘卡改待分派 + retry 递增
3. 若曾 infra → sidecar 残留 `state=打回 + infra_count`（229/2333），**无 clear**
4. `_audit_round` 读 sidecar（2654）→ `_audit_marker_alive`（-audit.running）残留 → 卡被跳过不机审 → 无限挂死
5. 看板合成视图用 sidecar 覆盖磁盘 → 显示与磁盘卡不一致（失真）

## 方案内容

### 一、sidecar 生命周期契约（四象限）

**一句话契约**：sidecar 记录**引擎在途决策态**（冷却/重试预算/在途标记），**不记录流程终态**（已回写/打回/已关闭由磁盘卡+分支信封权威）。每笔 sidecar 写入必有对应 clear，或随轮收敛。

| 状态（write） | 谁写 | 何时写 | 谁 clear | 何时 clear |
|--------------|------|--------|---------|-----------|
| **infra 冷却**（state + cooldown_until + infra_count） | Engine `_hold_infra_failure` | infra 失败，记冷却时间 | Engine 冷却到期自动判定（`_infra_cooldown_active` 不落 clear，只读） | 无需 clear；冷却到期即失效（按 ts+until 判定） |
| **infra 熔断**（state=REJECTED + infra_count） | Engine infra 打回 | infra 连续失败超限 | Engine 收口（本次改造） | 打回即写终态，**随轮 clear sidecar**（终态只留磁盘） |
| **业务打回**（retry_count + reason） | Engine `_fail_retry_or_reject` | 业务不通过，回待分派重试 | Engine 收口（本次改造） | 打回/重试出口统一 clear sidecar 流程态 |
| **执行成功**（infra_count=0） | Engine 收单成功 | 执行/机审通过 | Engine 收口（本次改造） | 成功即 clear（无在途态残留） |
| **在途标记**（`{id}.running` / `{id}-audit.running` marker） | `_claim_running_marker` | 派发/机审占用 | `_clear_running_marker`（finally） | worker 结束；**死 marker 由 `cleanup_dead_markers` 清** |
| **manual 挂起**（不写 sidecar，只写磁盘 RUNNING） | — | manual 卡 | — | 接单/回收（`reclaim_orphaned_running`） |

**铁律**：
- **成功/终态出口必须 clear**：`_run_auto_worker`/`_run_audit_worker` 的 collected（成功）、REJECTED（打回）、清 retry 的出口，一律 `clear_card_state` + 更新磁盘卡
- **sidecar 不再存流程终态**：只存 infra 冷却（临时）+ 重试预算（计数）；已回写/打回/已关闭唯一权威 = 磁盘卡
- **孤儿读修复**：1407 行删掉读 `state=="已回写"` 分支（改用日志 ok:true 或磁盘卡态），读侧与写侧字段对齐

### 二、Engine 收口改造（_run_auto_worker / _run_audit_worker 四分支显式收口）

**`_run_auto_worker`** 每个出口显式写 or clear：

| 出口 | 现状 | 改造 |
|------|------|------|
| 成功（ok） | 只清 infra_count | **clear_card_state**（无在途残留） |
| 空回写打回（REJECTED） | 磁盘打回，sidecar 不写 | **write 终态 + clear sidecar 流程态**（磁盘权威） |
| infra 冷却（retryable） | `_hold_infra_failure` 写冷却 | 保持（冷却临时态）；**清 retry_count 残留** |
| infra 熔断（REJECTED） | write state=REJECTED | **clear sidecar**（终态磁盘权威）+ 保留 reason |
| 业务重试（`_fail_retry_or_reject`） | 磁盘待分派+retry++ | **write retry_count + clear 流程态** |
| 业务打回（retry 用尽） | 磁盘打回 | **clear sidecar** |
| worker 异常 | `_fail_retry_or_reject` | 同业务出口 |

**`_run_audit_worker`** 同样四分支：
| 出口 | 现状 | 改造 |
|------|------|------|
| 机审通过/跳过 | 只清 infra_count | **clear_card_state** |
| 机审业务打回/重试 | `_fail_retry_or_reject` | **clear 流程态**（磁盘权威） |
| infra 冷却续审 | `_hold_infra_failure` | 保持冷却；清 retry 残留 |
| 机审异常 | `_fail_retry_or_reject` | 同业务出口 |

**`_fail_retry_or_reject` 拆「不可自愈 → 立即 clear」**：
```python
def _fail_retry_or_reject(work, store, problems, cfg, log_dir=None):
    max_r = max_retries_from_cfg(cfg)
    reasons = ...
    if work.retry_count < max_r:
        work.retry_count += 1
        work.transition(State.TODO, problems=reasons)
        store.save_work(work)
        # 可自愈：写重试预算，清 sidecar 流程态
        if log_dir:
            write_card_state(log_dir, work.id, retry_count=work.retry_count)
            clear_card_state(log_dir, work.id)   # 只留 retry_count 记录
        return True
    work.transition(State.REJECTED, problems=reasons)
    store.save_work(work)
    # 不可自愈（manual/未登记/重试用尽）：立即 clear sidecar，磁盘终态权威
    if log_dir:
        clear_card_state(log_dir, work.id)
    return False
```
> 拆出专门路径：**manual/未登记卡打回 → 立即 clear sidecar**（避免 clw019 式残留）。判定：`work.executor` 含 manual/W 号 或 `decide_work == MANUAL` → 打回即 clear，不再留 sidecar。

### 三、收敛器入 run_once（sync-runtime-state 逻辑搬进 Engine）

现状：`sync-runtime-state.py` 是独立脚本（人工/外部调度），未入 run_once 循环 → 依赖人工。

改造：`run_once` 开头（git_sync 后）调 `_converge_runtime_state(store, log_dir, registry)`：
- 遍历磁盘卡终态（已回写/打回/已关闭）+ sidecar 残留对比：
  - sidecar 有 state 但磁盘卡已是终态且非 infra 冷却 → clear
  - sidecar retry_count 与磁盘卡 retry 不一致 → 对齐
  - 孤儿记录（id 不对应任何卡）→ clear
- 收敛器幂等，每轮跑，无副作用

### 四、观测与自证

- 新增单测：`test_engine_runtime_contract.py`
  - 成功出口 → sidecar 清空（read_card_state 无该卡或无 state）
  - 业务打回 → sidecar 无流程态残留，磁盘卡 REJECTED
  - manual 卡打回 → sidecar 立即 clear
  - infra 冷却 → sidecar 保留 cooldown，到期失效
  - 收敛器：构造孤儿记录 → run_once 后清除
  - 孤儿读修复：_dispatch_and_collect 不再读 state=="已回写"

## 验收标准

- [ ] `_run_auto_worker`/`_run_audit_worker` 四分支（成功/打回/重试/跳过）显式写 or clear sidecar，无「只写不清」出口
- [ ] `_fail_retry_or_reject` 拆不可自愈路径：manual/未登记卡打回即 clear sidecar
- [ ] 收敛器入 run_once：孤儿 sidecar 记录自动清除，无人工依赖
- [ ] 孤儿读逻辑修复（1407 行不再读不存在的 state=="已回写"）
- [ ] 单测全绿（新增 6+ 用例 + 存量 engine 测试不回归）
- [ ] 实况：构造 clw019 式挂死（manual 打回 + marker 残留）→ 收敛后卡可正常流转

## 备注

- 本方案为 A 轨平台根治第一项，M1 直接开发（红线 6），不走卡
- 异席机审：开发（M1 OpenCode）与机审（验收席）不同源
- 后续 A 轨项：Worker 模型+认领协议（ccc-plan-020 落地）、role-skills 一致性、观测正则修复——本契约是其前置地基
- 与 B 轨错峰：本改造期间 B 轨只出不依赖状态机的卡（纯文档/前端组件）
