# 任务卡 ccc086 · ccc081 熔断根因核实与合规解除（DSH 执行）
> 批准：老板合入批准 · 2026-08-25

> 关联：环节②交接(2026-08-25)问题2 · 执行体：DSH · 验收：DSH · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-25

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

## 机审区

**DSH 机审席 · 2026-08-25 · severity：轻**

### 范围核对（复现：worktree ccc086）

- 分支 `codex/ccc086-ccc081-breaker-adjudicated-unblock` 相对父提交仅改本卡文件：`git diff --name-only HEAD~1 HEAD` → 单文件，47+/2-，零业务代码，符合「运行面运维卡」定位。
- 主仓占位卡未被触：`git -C /Users/fan/program/CCC status --short docs/dispatch/ccc/ccc086-*.md` 为空。
- 运行面操作严格限于卡内白名单：台账、告警文件、备份目录、本卡，无外溢。
- 推送核实：`git ls-remote origin refs/heads/codex/ccc086-…` = `5c48c6afe`，与本地 HEAD 一致（status 显示 ahead 1 系 upstream 挂在 origin/main 的显示噪音，实际已推至对应 codex 远端）。

### 对抗式找茬记录（逐项命令复现）

1. **三笔强拆三源一致**：台账三个 epoch 经 `date -u -r` 逐秒换算 = 16:37:04Z / 16:52:09Z / 17:07:17Z，与 worker-events.jsonl L9/L12/L13（duration_s=900.188/900.188/900.113，exit_kind=timeout）及 engine.stderr.log L7133/L7387/L7626 三条重试行完全对应；peak_rss_mb≈1.2、peak_cpu_pct=0.0 排除资源型击杀，「均为 900s 审计超时」成立。
2. **先备份后变更**：archive-20260825/ 三件套在场（目录 mtime 02:34），`shasum -a 256` 复算与 manifest 及卡述缩写三方吻合（dd73969c…8233d7c / 113431e7…41b86ca96）；备份内容与卡述移除前后状态逐字节相符。
3. **解除现场**：force_kill_ledger.json=`{}`（2 bytes，mtime 02:34:33 后至今未再变更→重派全程无新增强拆）；alerts 目录清空。
4. **根因修复行为级验证**：config.env L76=EXECUTOR_AUDIT_TIMEOUT_SECONDS=1800（mtime 01:55）→ engine.lock pid=51218 started=02:11:55（ps 实证存活，晚于配置改动）→ 重派终局行 duration_s=584.55 exit_kind=ok，低于旧 900s 击杀线，预算修复成立。
5. **重派业务结果与打回流转**：主仓 data/audit/ledger.jsonl 尾行 ccc081 ts=18:45:17Z conclusion=不通过 kind=audit reasons=P1-F1/F2；引擎自动落信封 commit 490ac9ca5（主仓 02:45:18，仅动 ccc081 卡状态行）——「该分支自 d160509b0 后无修复提交」属实，缺陷未修归因成立。
6. **熔断未复发**：engine.stderr.log 中「派发被熔断跳过」最后一次在 L9710（解除前），L9741 起「拉起机审: work=ccc081」成功进入审计，heartbeat audit_in_flight=2。
7. **观察项 O1（非缺陷，不改判）**：卡述「当前日志段拦截 64 次」，本席复测 72 条（grep 计数，全部 work=ccc081）。定位：最后拦截在解除前 L9710，64→72 系执行体写卡时点早于日志尾部追加的快照差；其方向性声称（远小于 115+、差异系轮转）仍成立。属历史叙述数字陈旧，非验收项。
8. **观察项 O2（制卡建议，不下代）**：「ledger 出现 pass」写进运维解除卡的验收标准，而 pass 与否取决于 ccc081 自身内容缺陷（属彼卡白名单），超出本卡可控范围。执行体以 ⚠️ 如实标注并归因、拒绝伪造——正是防幻觉纪律的正确执行；若机械套用该子句打回，唯一「修复」路径是越白名单代修 ccc081 或造假，均触红线。建议后续运维卡验收谓词限定在本卡可控行为内。

### severity 判定

影响面 1（运行面两文件已备份留痕、零代码改动、主仓未触）+ 改动深度 1（分支仅本卡文档 47+/2-）+ 红线邻近 1（未触 main/验收区/已关闭，无伪造数据，禁 add -A 遵守）= 3 分 → 轻。

### 验收标准核对

- ✅ 三笔强拆逐笔核实（日志行引用）：见找茬记录 1。
- ⚠️→✅ 1800s 内完成**满足**（584.55s、exit_kind=ok 进程级、无强拆）；「出现 pass」未满足，但归因=ccc081 内容 P1-F1/F2 未修（信封 commit 与分支提交史实证），属该卡自身生命周期、本卡步骤3明令停手不循环重试；如实报告优于伪造完成，判本卡达成业务意图（熔断解除+机审链路恢复均行为级实证）。
- ✅ 操作前后备份留存：三件套+SHA256 哈希三方验证通过。

### 维护区核对（P1-b 机械判据）

四问均为合法单选 [否]/[无]/[否]/[否]，说明行各一句实情、非空非占位；声明抽查属实：git diff 证实未触任何方案/档案 README/线路图文件，证据均落本卡回写区。

机审：通过（被审 5c48c6afec69）

## 验收区

**合入批准** · 日期：2026-08-25
- 判定：通过
- ✅ 人审 diff 后合入批准（北星 W2）
