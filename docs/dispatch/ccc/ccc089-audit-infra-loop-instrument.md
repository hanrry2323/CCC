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
3. L3407-3408 读到空/旧 audit_text → 无业务结论特征 → L3427 `not ok and not pass特征` 成立 →
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
+        # → 不按 infra 记账，防固定节奏重复刷 infra 行（ccc081 现象）。
+        # 注意（机审席核正 2026-08-25）：第三返回值 audited=False 仅被 --audit CLI
+        # 路径消费（main.py L4575-4578「skipped」口径）；引擎 worker 主链
+        # （_run_audit_worker L3696）弃用该值——本候选在引擎路径只消除台账刷行，
+        # 冷却空转仍持续至 strikes 熔断（详见 diff 后核正说明）。
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

机审席核正（2026-08-25 · 轻级就地修正）：本节原称「两案均…仅消除『未拉起也记账+冷却』的
空转路径」，与实证不符——引擎主链 `_run_audit_worker`（L3696）将 `_run_machine_audit_after_writeback`
第三返回值弃为 `_audited`（无消费方）；案 A 在引擎路径的实效 = 停止 infra 台账刷行并**消除 ledger
观测信号**，而 problems（含「基础设施」特征）仍经 `is_retryable_failure`→`_hold_infra_failure`
按冷却续跑，直至 strikes 熔断转待分派（若生产 strikes 不累积则空转依旧，只是不再留痕）。
「未审挂起待人工跟进」口径仅存在于 `--audit` CLI 路径（L4575-4578 消费 `audited`）。
欲终结空转本体，须采案 B（pre-launch 标签 → 转待分派人工跟进）或在引擎 worker 路径补
`audited=False` 消费分支。两案均不改重试/熔断预算语义本身；落地须另行开卡并由环节②按上述
边界裁量。

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

## 机审区

**DSH 机审席 · 2026-08-25 · severity：轻**

### 独立核验证据（不引用执行体自述，全部命令复现）

- 范围核对：`git log main..HEAD` 分支独有提交仅 2 个——bd51c4083（main.py +21 插桩 /
  新增 test_ccc089_audit_infra_loop.py +215）与 ae32bf995（仅卡回写）。相对 main 的
  diffstat 中 approve-merge.sh / ccc090-093 卡等差异经 `git log HEAD..main` 实证为
  main 前移（d26c00eb2、c5d927686）的反向差，非本分支改动。白名单严守 ✓
- 零行为变更实证：`git show bd51c4083 -- server/engine/main.py` 逐行核对，7 处插桩全为
  `[ccc089-trace]` logger.info；_ledger_record 出口链块 try/except 自包裹、无分支/返回值变更 ✓
- 测试独立复跑：`pytest server/tests/test_ccc089_audit_infra_loop.py -q` → 4 passed；
  六个回归文件合计 155 passed（=新增4+回归151，与回写声称一致）；ruff All checks passed ✓
- 根因链条逐行走读核实：L2162/L2188/L2274/L2314/L2322/L2362 早退点、L3271-3285 记账出口链、
  L3407-3408 audit_text 读取、L3427 判定、L3429-3437 kind="infra" 记账、L3675/L3696 worker 链、
  L600 冷却门禁、L3719+L3790-3830 infra 分支与 strikes 熔断、L529 _hold_infra_failure、
  L4558 起 --audit CLI——机制本体（候选 b）成立：Popen 前早退 → audit.log 静态仍按
  infra 记账进冷却续审，到期即复发 ✓
- 测试夹具真实性：真实 git worktree add 失败路径（worktree_base 指向普通文件之下）、
  无 mock dispatch/记账/冷却；CCC_AUDIT_LEDGER 覆盖、冷却配置键名均与生产消费点对上 ✓
- Push 证据：`git ls-remote origin codex/ccc089-audit-infra-loop-instrument` = ae32bf995
  = 本地 HEAD（含回写提交均已推送）✓
- 机械门禁：`PYTHONPATH=. python3 server/board/docgate.py <卡>` exit=0 ✓；
  维护区四问逐项单选已填、说明非空实情；抽查属实（卡头无方案编号；diffstat 无结构/路径/
  技术栈变化；教训落于本卡论证与测试 docstring）✓

### 发现与处置（severity 三级评分 · 影响面/改动深度/红线邻近）

1. 【影响面2 · 改动深度1 · 红线邻近1 = 4分】**候选推荐 diff 行为声明不实（已就地修正）**：
   原 diff 注释称「由调用方按既有『未审』口径挂起待人工跟进」，实证引擎主链 L3696 将第三
   返回值弃为 `_audited`，「未审」口径仅 `--audit` CLI 路径（L4575-4578）消费。该候选在
   引擎路径实效 = 只消除台账刷行并削弱观测信号，problems 含「基础设施」仍进冷却续跑至
   strikes 熔断——并未终结 ccc081 空转本体（终结需案 B 或补引擎侧 audited=False 分支）。
   属交付文本缺陷而非生产行为缺陷（卡明确「供环节②裁量·落地另开卡」），已在回写区
   原位核正并在 diff 注释内标注。
2. 【影响面1 · 改动深度1 · 红线邻近1 = 3分】**行号引用偏差（已就地修正）**：根因论证第 3 步
   「L3419 读到空/旧 audit_text」实际读取在 L3407-3408；L3419 落在业务打回记账分支
   （kind="audit"）内、语义相反。机制结论不受影响。
3. 【记录不计分】节奏解释「60s 冷却 + 扫描延迟 ≈ 76s」的 16s 差值构成无独立证据；
   卡内已自标「待生产侧核实、不下定论」，诚实降级可接受。

合计 8 分中取各维最高合成：两发现均为交付文本层轻量缺陷，生产代码零行为变更、根因诊断
与复现测试经独立复现全部成立，任一维度未达高。综合 severity＝轻。

### 结论

两项轻级发现已按分流规则就地修复（修正回写区候选 diff 注释与收尾说明、更正行号引用）
并随本次提交推送，不构成打回事由。根因定位（函数+行号）、加速形态循环复现测试、
候选 diff 文本三项验收标准均达成且证据可复现。

机审：通过（被审 ae32bf995fd2）
