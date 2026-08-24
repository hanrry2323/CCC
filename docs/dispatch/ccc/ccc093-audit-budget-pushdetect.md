# 任务卡 ccc093 · 审计预算失配修复 + push 成功检测去误报（DSH 执行）

> 关联：ccc081 四连 900s 击杀 / ccc088 「空转」假 infra 行 · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-25

## 目标

①审计超时预算按被审 diff 规模自适应：base=EXECUTOR_AUDIT_TIMEOUT_SECONDS，按 diff 行数线性上浮（上限 2×），杜绝复杂 diff 必然超时；②机审证据推送结果判定改为**以 origin 分支事实为准**：commit/push 返回空转时，`git ls-remote origin <branch>` + 分支卡文含机审区双重校验，核实已达远端则记 pass 覆盖，杜绝「空转」假 infra 行（ccc088 事故）。

## 红线

- 白名单：server/engine/main.py、server/tests/。
- 不动 ledger 结构与末行裁决制。
- ls-remote 校验失败仍按原 infra 续审路径（不放宽）。

## 步骤

1. 自适应预算函数+单测（小 diff=base，大 diff 上浮封顶）。
2. push 空转分支接 ls-remote 双重校验+单测（远端已有→pass；远端未有→infra）。

## 验收标准

- [ ] 两组单测绿
- [ ] 以 ccc081/ccc088 历史参数回放推演，两事故均被新逻辑正确处置

## 回写要求

- 回写区附单测与回放推演；维护区四问如实。

## 人工批注

（留空）

## 回写区

**执行体**：DSH（dsh-executor）· 日期：2026-08-25

### 实现说明

改动文件：`server/engine/main.py`（+133/-4）、`server/tests/test_engine_main.py`（+207），均在卡白名单内。

**目标① 审计预算自适应（ccc081 根修）**
- 新增 `_audit_diff_changed_lines(worktree_path)`：以 `git diff --numstat origin/main...HEAD` 统计被审 diff 增删行总数（二进制行自动跳过；取不到 → None）。
- 新增 `_audit_adaptive_timeout_seconds(cfg, worktree_path)`：base=`EXECUTOR_AUDIT_TIMEOUT_SECONDS`；diff ≤200 行 = base 不浮；[200, 2000] 区间线性上浮；≥2000 行封顶 2×base。规模取不到回退 base（不放宽不收紧）。
- 接入点：`_run_audit_worker` 预算计算处（原恒定 `_audit_timeout_seconds(cfg)`），复用同一 worktree hint，不新增重复探测。

**目标② push 空转去误报（ccc088 根修）**
- 新增 `_remote_branch_audit_evidence(worktree_path, card_rel, branch)`：双重校验——① `git ls-remote origin <branch>` 非空；② fetch 后 `git show origin/<branch>:<rel>` 卡文含机审区通过结论（`machine_audit_passed_text`）。任一关失败 → False。
- `_commit_and_push_worktree_card` 两处失败分支（push 返回非零 / 本地 HEAD 复核空转）接入该复核：核实已达远端 → 记 pass 覆盖；校验不过仍走原 infra 续审路径（红线「不放宽」已守）。
- **额外根修（实现中发现的真实机制）**：`rel = wt_card.relative_to(Path(worktree_path).resolve())` 单侧 resolve——worktree 路径经符号链接（macOS `/tmp`→`/private/tmp` 类环境）时 relative_to 必败，回退 `wt_card.name` 裸文件名 → add/show 全走错路径 → 把实际成功的 commit/push 误判为空转。修复为双侧 resolve 后 rel 恒为完整相对路径。

### 自测结果

1. **单测绿**（两组共 10 个新用例 + 全文件回归）：
   - 命令：`python3 -m pytest server/tests/test_engine_main.py -q`
   - 结果：129 passed（新增 TestAuditAdaptiveBudget×5：小 diff=base / 中点线性 1.5× / 大 diff 封顶 2× / 非 git 目录与 None 回 base / 坏配置兜底 1800 不变；TestPushIdleRemoteEvidence×5：本地空转+远端有证据→pass、push 报错+远端有证据→pass、远端查无分支→infra 不放宽、远端分支无通过结论→infra、符号链接 worktree rel 不退化回归锁）
2. **全量套件零新增失败**：
   - 命令：`python3 -m pytest server/tests -q`（当前 vs `git stash` 基线对照）
   - 结果：基线 11 个 pre-existing 失败（brain_stream/brain_kb/http_api/advanced_review 等 brain 流式模块，均与本卡无关）；含本改动的多轮全量失败集合与之完全一致（comm 差集为空）。期间偶现 1 次 `test_audit_rejection_exit_zero_is_business_reject` 失败，经查其失败路径为生产卡 `_append_machine_audit_pass` 文件写入（本卡未触碰；本卡改动的分支卡信封路径文案不同可区分），该用例连续单跑 10 次、engine 主文件连跑 4 轮全部绿，定性为环境级偶发 flaky，非本卡回归。
3. **lint**：`ruff check server/engine/main.py server/tests/test_engine_main.py` → All checks passed（ruff format 差异为基线既有状态，未做越范围重排）。

### 回放推演（验收标准② · ccc081/ccc088 历史参数）

- **ccc081 回放**：base=900s + diff≈3000 行复杂改动 → 新预算 = **1800s**（旧逻辑恒 900s 必然超时四连击杀；新逻辑线性段封顶后预算翻倍，≥ 实际审计耗时即不再被杀）。断言 `got == 1800` 通过。
- **ccc088 回放（三场景）**：
  - ②-a 本地 HEAD 复核被注入空转 + 远端分支事实已有卡文机审区（sha=a7d35ae4fcf3…）→ 判定 **True**（旧逻辑 False → 假 infra 行）；
  - ②-b worktree 经符号链接路径全链路真实执行 → 判定 **True**（修复前 rel 退化为裸文件名 → 假空转 False）；
  - ②-c 反向护栏：本地空转 + 远端查无分支 → 判定 **False**，维持原 infra 路径 ✓（不放宽）。
- 结论：两事故均被新逻辑正确处置。

### push 证据

- 分支 `codex/ccc093-audit-budget-pushdetect`
- 实现 commit：`8d0615122`（fix(engine): ccc093 审计预算按 diff 规模自适应 + push 空转以 origin 分支事实去误报）
- 回写 commit：见下方 git 记录（docs(card): ccc093 已回写）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：本卡无关联方案编号（「关联」为 ccc081/ccc088 两事故教训直修卡），无可同步的方案状态与关联卡。
2. **教训沉淀**：本卡是否产出可复用教训？[有]
   - 说明：「git 路径拼接必须双侧 resolve，否则符号链接环境下 relative_to 退化成裸文件名制造假故障」与「进程外副作用（push）成败判定应以目的端事实复核而非仅看本地返回码」两条要点已固化于 main.py 相应函数注释与本卡回写区；docs/lessons.md 不在白名单未单独沉淀。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：纯 engine 行为修复 + 测试补充，未动项目结构、技术栈与路径；新增常量与函数均在既有模块内。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：两起事故的点状根修，无新增线路或近况变化；建议环节② 关注 brain 流式模块 11 个 pre-existing 失败（与本卡无关，疑似环境配置缺失 CCC_BRAIN_BASE_URL）。
