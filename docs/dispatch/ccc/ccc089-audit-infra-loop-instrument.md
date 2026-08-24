# 任务卡 ccc089 · 审计 infra 冷却重审「76s 循环」插桩定位（DSH 执行）

> 关联：环节②回函(2026-08-25)指派·环节①走卡核实 · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-25

## 目标

定位 ccc081 现象的确切记账路径：审计 infra 失败进入冷却重审后，ledger 以 ~76s 节奏重复追加 infra 行，而 audit.log 静态、无新会话启动痕迹（已排除：wrapper 本体双环境复跑健康 / 补提交支路 / 900s 超时）。产出根因结论与最小修复候选 diff（回传环节②，本卡不落生产修复）。

## 红线

- 白名单：server/engine/main.py（仅插桩日志与单测）、server/tests/。
- 生产数据只读；实验用 tmp DATA_DIR。
- 根因未实证前不得改任何重试/熔断行为。

## 范围

1. 复现：pytest 形态构造「audit infra-fail → 冷却到期 → 重审评估」，断言每轮是否在**不拉起会话**的情况下重复 record_audit(kind=infra)。
2. 候选分支（逐一证伪）：a) _run_machine_audit 在 evidence-check/补提交支路早退时仍走 infra 记账；b) 冷却到期判定与实际派发解耦，记账先于会话拉起且拉起失败静默；c) 多来源（engine+manual 工具链）对同一卡重复触发。
3. 定位后输出：根因行号、最小修复候选 diff（文本附回写区，不落盘）、回归单测。

## 步骤

1. 插桩：在候选分支各加一行 logger.info（含调用栈标记），tmp 环境复跑复现序列。
2. 记录每条 infra 行的精确产生点。
3. 输出根因报告 + 候选 diff 文本。

## 验收标准

- [ ] 复现测试落地且稳定重现 76s 型循环（加速形态）
- [ ] 根因定位到函数+行号
- [ ] 候选 diff 文本随回写区交付，生产代码零行为变更

## 回写要求

- 回写区附插桩输出节选与根因论证；维护区四问如实。

## 人工批注

（留空）

## 回写区

### 实现说明（2026-08-25 · DSH 执行体）

- 插桩：`server/engine/main.py` 新增 7 行 `[ccc089-trace]` logger（纯日志，零行为变更）——
  `_dispatch_and_collect` 拉起前早退点 ×5（L2188 熔断 / L2274 worktree重建+关联失败 / L2314 worktree创建+关联失败 / L2322 worktree过程异常 / L2362 build_command失败）、
  `_ledger_record` kind="infra" 调用栈出口链（L3271-3285）、补提交支路失败点（L3369）。
- 复现测试：新增 `server/tests/test_ccc089_audit_infra_loop.py` 4 项（真实 git worktree add 失败路径，
  不 mock dispatch/记账/冷却任何一环）：
  ① `test_infra_recorded_without_session_launch`：单轮早退仍记 infra 账，audit.log 从未创建；
  ② `test_infra_loop_repeats_each_cooldown_expiry`：加速形态（cooldown=0s）连续 4 轮，每轮恰 +1 条 infra 行；
  ③ `test_cooldown_gate_delays_then_releases`：生产默认 60s 冷却基数实证 + 到期放行即复发第 2 条；
  ④ `test_max_strikes_breaks_loop_to_todo`：熔断边界——达上限轮**先记账后转待分派**，DONE 队列清空收敛。

### 自测结果

- 新增测试：`python3 -m pytest server/tests/test_ccc089_audit_infra_loop.py -q` → **4 passed**。
- 回归：`test_engine_main / test_infra_resilience / test_audit_ledger / test_engine_audit_backfill /
  test_engine_audit_marker / test_engine_pass_ledger` → **151 passed**（插桩零行为回归）。
- lint：`ruff check server/engine/main.py server/tests/test_ccc089_audit_infra_loop.py` → All checks passed。

### Push 证据

- 分支 `codex/ccc089-audit-infra-loop-instrument`，commit `bd51c4083`，已 push 至 origin
  （远端新分支，GitHub 返回 PR 创建链接；本地 tip 与 origin tip 一致均为 bd51c4083）。

### 插桩输出节选（每条 infra 行的精确产生点）

```
INFO ccc.engine:main.py:2313 [ccc089-trace] dispatch 拉起前早退（worktree 创建+关联均失败）: work=ccc999 phase=audit
INFO ccc.engine:main.py:3277 [ccc089-trace] infra 记账: work=ccc999 source=engine reason0=基础设施：worktree 创建与关联均失败… 出口链=_run_machine_audit_after_writeback:3429 <- _run_audit_worker:3696 <- run_worker_once:87
（×4 轮重复，逐轮同型）
```

### 根因论证（函数+行号）

**结论：候选 b 证实。infra 台账记账无法区分「会话真跑后失败」与「Popen 拉起之前早退」；早退时
audit.log 全程不被触碰（静态）、无任何子进程启动痕迹，但每轮仍按 kind="infra" 记账并进入冷却续审，
冷却到期判定放行后循环复发——即 ccc081「~76s 循环」的机制本体。**

循环链条（全部实测复现，行号为当前 main.py）：

1. 卡「已回写」→ `_audit_round`（L4296-4297 冷却门禁）到期放行 → `_run_audit_worker`（L3675）。
2. `_run_machine_audit_after_writeback` → `_dispatch_and_collect`（L2162）在 `subprocess.Popen`
   **之前**的任一早退点返回 `(False, problems)`：熔断 L2188 / worktree 失败 L2274·L2314·L2322 /
   build_command L2362 —— 会话从未拉起，`{id}.audit.log` 不被创建或保持旧内容（静态）。
3. L3419 读到空/旧 audit_text → 无业务结论特征 → L3427 `not ok and not pass特征` 成立 →
   L3429-3437 `_ledger_record(kind="infra")` **追加台账行**。
4. 回 worker：reasons 含「基础设施」→ `is_retryable_failure`=True → L3795-3830 infra 分支 →
   `_hold_infra_failure`（L529）写 sidecar `infra_cooldown_until`（默认基数 60s，指数退避 2^n）。
5. 冷却期内门禁跳过；到期后回到第 1 步 → 每轮恰追加一条 infra 行。

节奏解释：60s 冷却基数 + 主循环事件感知扫描延迟（2s 粒度探测/heartbeat 兜底）≈ 观测到的 ~76s。
注：若 sidecar strikes 正常累积应呈 60→120→240…退避且第 5 次（EXECUTOR_INFRA_MAX_STRIKES 默认 5）
转待分派收敛；生产观测恒定 ~76s 提示 strikes 可能未有效累积（sidecar 丢失 / engine 重启换
log_dir / 多 DATA_DIR 并存）或观测窗口短于退避展开期——此点待生产侧核实，本卡不下定论。

候选分支证伪：

- a) 补提交/evidence-check 早退自身记账：**证伪**。evidence 通过早退 return True 不记账（L3352-3355）；
  补提交失败仅 warning 转重审不记账（L3348/L3369）。但补提交失败后继续走真重审时若 dispatch 早退，
  记账仍发生——归入 b 的机制。
- b) 冷却到期与实际派发解耦、拉起失败静默：**证实**（见上）。冷却只是延迟器，不消除根因，到期即复发。
- c) 多来源重复触发：**部分证实存在第二来源但非本现象必要条件**。`--audit` 手动 CLI（L4558 起）
  绕过冷却门禁直接审计且失败同样经 L3429 记账（source=engine）；但其为人工触发无周期性。
  engine 自动循环（b）单独即可产生全部观测现象。

### 最小修复候选 diff（文本交付 · 未落盘 · 供环节②裁量）

推荐方案（改动面最小）：会话未真正拉起的轮次不得按 infra 记账进冷却续审，防固定节奏空转刷账。

```diff
--- a/server/engine/main.py
+++ b/server/engine/main.py
@@ def _run_machine_audit_after_writeback(work, registry, cfg, log_dir, timeout, ...):
     # _claim_running_marker 前记录本轮起始时刻（新增一行）
+    t_start = time.monotonic()
     _claim_running_marker(log_dir, f"{work.id}-audit", data_dir=cfg.get("DATA_DIR"))
@@
     if not ok and not _audit_output_indicates_pass(audit_text):
+        # ccc089 候选修复：本轮 audit.log 未被任何真实会话写入（Popen 前早退）
+        # → 不按 infra 记账进冷却续审（否则以固定节奏重复刷 infra 行，ccc081 现象），
+        # 改为返回未审（audited=False），由调用方按既有「未审」口径挂起待人工跟进。
+        audit_log_fresh = (
+            (log_dir / f"{work.id}.audit.log").is_file()
+            and (log_dir / f"{work.id}.audit.log").stat().st_mtime >= t_start - 1
+        )
+        if not audit_log_fresh:
+            logger.error(
+                "机审 dispatch 拉起前早退（会话未启动），不记 infra 账防循环: work=%s reason=%s",
+                work.id, (problems or ["?"])[0][:120],
+            )
+            return False, problems or ["机审执行失败"], False
         # P1-C 修复：机审执行失败 = 基建故障（kind=infra），不参与命中判定
         _ledger_record(
             work,
```

备选方案（语义更显式）：`_dispatch_and_collect` 各拉起前早退 reasons 统一加 `pre-launch:` 前缀标签，
worker 对该标签走「转待分派人工跟进」而非无限冷却。改动点多一处常量，侵入面略大。

两案均不改重试/熔断预算语义本身，仅消除「未拉起也记账+冷却」的空转路径；落地须另行开卡。

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：环节②回函指派的定位任务卡，卡头无方案编号，无需方案同步。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：「拉起前早退不得按 infra 记账」教训已完整落于本卡根因论证与复现测试 docstring；受白名单限制未另落 docs/notes。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：仅 main.py 加纯日志插桩与新增一个测试文件，无结构/技术栈/路径变化。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：ccc081 生产修复属后续卡裁量事项，不改变线路图方向。
