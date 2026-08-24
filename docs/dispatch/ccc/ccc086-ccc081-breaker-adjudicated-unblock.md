# 任务卡 ccc086 · ccc081 熔断根因核实与合规解除（DSH 执行）

> 关联：环节②交接(2026-08-25)问题2 · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-25

## 目标

按既有人工核查流程解除 ccc081 自动派发熔断并恢复其机审，前提=根因已修复且证据齐全。

## 已知事实（出卡人预取证，回写时须复核）

- 三笔强拆记录均为机审审计会话 900s 超时击杀（ledger ts 16:37/16:52/17:07Z），根因=审计预算与 V6 复杂 diff 不匹配。
- 预算已裁决调至 EXECUTOR_AUDIT_TIMEOUT_SECONDS=1800 且引擎 02:11 重启生效。
- 熔断现场：alerts/auto-dispatch-blocked-ccc081.txt 在场；force_kill_ledger.json 含 ccc081=3；熔断拦截已发生 115+ 次。

## 步骤

1. 复核三笔强拆：对照 worker-events/engine 日志确认每次均为 900s 审计超时（非资源/互拆）。
2. 备份 force_kill_ledger.json 至 ~/.ccc/logs/archive-20260825/ 后移除 ccc081 键；删除 alerts/auto-dispatch-blocked-ccc081.txt。
3. 触发/等待 ccc081 机审重派，观察其在 1800s 预算内完成；若再超时，停止并回报（不得循环重试）。

## 验收标准

- [ ] 三笔强拆原因逐笔核实（日志行引用）
- [ ] 解除后 ccc081 机审在 1800s 内完成且 ledger 出现 pass
- [ ] 操作前后 ledger/告警文件备份留存

## 回写要求

- 回写区附核实证据、解除操作输出、重派结果；维护区四问如实。

## 人工批注

（留空）

## 回写区

- 改动清单（2026-08-25 · DSH 执行体）：本卡为运行面运维卡，零业务代码改动；操作对象限卡内步骤指定的熔断现场两文件 + 备份目录 + 本卡文件：
  - `~/.ccc/data/force_kill_ledger.json`：移除 ccc081 键（移除前 `{"ccc081": [1787589424.994001, 1787590329.865786, 1787591237.496275]}` → 移除后 `{}`；python json 原子 tmp+rename 写回）。
  - `~/.ccc/logs/alerts/auto-dispatch-blocked-ccc081.txt`：已删除（原内容「ccc081 近24h被强制击杀 3 次（阈值 3）…人工核查后删除本文件即可恢复自动派发」，133 字节）。
  - `~/.ccc/logs/archive-20260825/`：新增备份三件——`force_kill_ledger.json.pre-unblock`、`auto-dispatch-blocked-ccc081.txt.pre-unblock`、`SHA256.pre-unblock.txt`（ledger sha256 `dd73969c…8233d7c`、告警 sha256 `113431e7…41b86ca96`）。
  - 本卡：卡头 待分派→已回写 + 本回写区/维护区。

- 步骤1 三笔强拆逐笔核实（台账 ts ↔ worker-events.jsonl ↔ engine.stderr 三源一致；均为 audit 阶段 900s 审计超时击杀，非资源/互拆——peak_rss_mb≈1.2、peak_cpu_pct=0.0）：
  1. 台账 `1787589424.994001` = 2026-08-24T16:37:04Z ← worker-events L9：`phase=audit duration_s=900.188 exit_kind=timeout problem="执行超时（900s 已 kill）"`。
  2. 台账 `1787590329.865786` = 2026-08-24T16:52:09Z ← worker-events L12：同上，`duration_s=900.188`。
  3. 台账 `1787591237.496275` = 2026-08-24T17:07:17Z ← worker-events L13：同上，`duration_s=900.113`。
  - 引擎侧佐证：`engine.stderr.log` 行 7133/7387/7626 三条「失败回待分派重试: work=ccc081 retry=1/3 problems=['执行超时（900s 已 kill）']」，行 7633 起转「派发被熔断跳过」（当前日志段拦截 64 次，与卡述 115+ 次的差异系日志轮转所致）。

- 根因修复生效核验：
  - 预算：生产 `/Users/fan/program/CCC/server/config/config.env:76` = `EXECUTOR_AUDIT_TIMEOUT_SECONDS=1800`（mtime 2026-08-25 01:55）；代码取值链 `server/engine/main.py:595 _audit_timeout_seconds=max(60, cfg值 or 1800)`。
  - 重启：`~/.ccc/data/engine.lock` = `pid=51218 started=2026-08-25 02:11:55`（ps 实证 PID 51218 存活），晚于 config 改动 → 1800s 预算在运行引擎内生效。

- 步骤2 解除操作输出（2026-08-25 02:34 先备份后变更）：
  ```
  removed ccc081 timestamps: [1787589424.994001, 1787590329.865786, 1787591237.496275]
  ledger now: {}
  rm ~/.ccc/logs/alerts/auto-dispatch-blocked-ccc081.txt  → alerts 目录清空
  ```

- 步骤3 重派观察（解除后 ~2 分钟引擎即拉起机审，无需人工触发）：
  - 02:36 起 `ccc081-audit.running` 在场（pid=89705，dsh-auditor.sh 审 worktree 分支副本）。worker-events 终局行：`{"ts":"2026-08-24T18:45:17Z","work_id":"ccc081","phase":"audit","duration_s":584.55,"exit_kind":"ok"}` —— 会话 **584.55s 自行完成**，低于旧 900s 击杀线与新 1800s 预算；全程 force_kill_ledger 保持 `{}` 无新增强拆。→ 熔断根因（预算与 V6 复杂 diff 不匹配）获行为级验证修复，机审链路恢复。
  - 机审业务结论：**不通过**（severity=重维持：P1-F1 `[：:]` 多字节括号 C locale 漏认规范信封；P1-F2 无右锚伪信封基线前推 rc=0 静默放行。分支自 d160509b0 后无修复提交，缺陷未修属实）。`data/audit/ledger.jsonl` 新增行 `conclusion=不通过 kind=audit`；引擎按重度打回自动流转（分支信封 commit `490ac9ca5`「机审打回，状态落分支信封」）。ccc081 回到开发修复循环——属该卡自身生命周期，越出本卡范围，本卡按步骤3「不得循环重试」就此停手。

- 验收标准逐条对照：
  - ✅ 三笔强拆原因逐笔核实（日志行引用）：见上三源对照。
  - ⚠️ 解除后机审在 1800s 内完成 **满足**（584.55s、无强拆）；「ledger 出现 pass」**不满足**（结论=不通过，无 pass 行）。不通过原因是卡内容 P1-F1/F2 未修复（分支无修复提交），非熔断/预算问题；如实报告，不伪造完成。
  - ✅ 操作前后 ledger/告警文件备份留存：`~/.ccc/logs/archive-20260825/` 三件套 + SHA256。

- 分支：`codex/ccc086-ccc081-breaker-adjudicated-unblock`（worktree ccc086）；本回写为分支最新一笔；未触 main、未写机审区/验收区。

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。

1. **方案同步**：[否]
   - 说明：本卡系环节②交接的熔断解除运维卡，无关联方案编号，不推进方案。
2. **教训沉淀**：[无]
   - 说明：核实/解除/重派证据均已落本卡回写区；「解除熔断≠机审必然通过，未修复缺陷会即时再吃不通过」属既有流程语义，无需另立笔记。
3. **档案/README**：[否]
   - 说明：仅操作运行面指定两文件与备份目录，未触及 docs/projects/ccc/README.md 等项目档案。
4. **线路图**：[否]
   - 说明：一次性熔断解除运维动作，不改变任何线路图意向或排期。
