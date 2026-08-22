# CCC P3 架构级排期方案（2026-08-22 · Part 3 P3）

> 范围：sidecar 生命周期契约 / Worker 跨节点路由 / role-skills 注入一致性。
> 定位：体量大，本轮不实现，交付带优先级+预估工作量的排期，下一轮单独排。
> 依据：ENGINEERING-CANON §三 根因修复清单 + ccc-plan-020。

## 优先级与排期

| 项 | 优先级 | 预估工作量 | 依赖 | 建议排期 | 关键风险 | 验收前置 |
|----|--------|-----------|------|---------|---------|---------|
| **sidecar 生命周期契约** | P0（clw019 根因仍在） | M（1-2 天） | 无 | 下一轮第一批 | 不动则打回卡残留继续挂死 | 收敛器入 run_once 循环；终态由磁盘卡权威 |
| **Worker 跨节点真路由** | P1 | L（3-5 天） | sidecar 契约（认领协议复用 git 信道） | 下一轮第二批 | 跨节点 merge 风险；需双机 ledger 已同步 | 决策/执行寻址对齐；REMOTE 决策态；机审适配 remote 卡 |
| **role-skills 注入一致性** | P1 | M（1-2 天） | 无 | 与 sidecar 并行 | skill 三处不同步 → 注入错版 | 收进 CCC 仓 + 一键下发/校验；注入点出卡→派发 |

## 每项细化

### 1. sidecar 生命周期契约（P0 · 1-2 天）

- **问题**：`~/.ccc/logs/exec/state/cards.jsonl` 只写不清；Engine 全程 0 次 clear；机审打回写「待分派」但磁盘卡不动 → 挂死；看板被 sidecar 覆盖失真。
- **方案**（ENGINEERING-CANON §三-1）：
  1. 定义契约：sidecar = 在途执行态；终态由磁盘卡 + 分支信封唯一权威。
  2. `_run_auto_worker`/`_run_audit_worker` 每个出口显式收口（成功/打回/重试/跳过四分支明确写 or clear）。
  3. 收敛器入 `run_once` 循环（sync-runtime-state.py 逻辑搬进 Engine）。
  4. `_fail_retry_or_reject` 拆「不可自愈 → 立即 clear」路径。
- **验收**：clw019 场景回归；打回卡无残留；看板状态与磁盘一致。
- **测试**：现有 test_engine_runtime_contract.py 已覆盖部分；补出口收口单测。

### 2. Worker 跨节点真路由（P1 · 3-5 天 · 依赖 sidecar）

- **问题**：Engine 唯一通道是 `subprocess.Popen` 本机；W9 靠「手动 GUI + manual」补丁绕开；`worker_id` 决策/执行路径语义相反（RC4）。
- **方案**（ccc-plan-020）：Worker 模型（host/transport/worker_status）；`decide_work` 认 worker_id + REMOTE 决策态；认领协议 v1（git 信道 lock marker）；机审适配 remote。
- **前置**：双机 ledger 同步已上线（sync-audit-ledger.py）；还需节点心智对齐（qx-map bootstrap）。
- **风险**：跨节点 rebase/merge 需严格走 CLA 处置标准；回滚路径要定义。
- **验收**：远程卡从派发→执行→回写→机审全链路闭环；W9 不再靠 manual。

### 3. role-skills 注入一致性（P1 · 1-2 天 · 可与 sidecar 并行）

- **问题**：skill 三处不同步（M1/2017/252 手工 scp）；出卡时烘死（改 yaml 存量卡不更新）；无「节点×skill×版本」校验。
- **方案**：skill 收进 CCC 仓 `server/config/claude-skills/`；一键下发/校验脚本；注入点从出卡改派发时动态 + 校验目标节点 skill 存在。
- **验收**：三节点 skill 版本一致；新卡注入用最新；漂移可检出。
- **测试**：skill 清单哈希校验单测。

## 执行顺序建议

```
下一轮第一批：sidecar 契约（P0）+ role-skills（并行）
   ↓
下一轮第二批：Worker 路由（依赖 sidecar 的认领协议）
```

## 与已完成项的关系

- 双机 ledger 同步（sync-audit-ledger.py）已上线 → Worker 跨节点 merge 的 provenance 前置已满足。
- 机审真值单源化（loader ledger 派生）已上线 → remote 卡机审适配可复用。
