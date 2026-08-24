# 任务卡 ccc086 · ccc081 熔断根因核实与合规解除（DSH 执行）

> 关联：环节②交接(2026-08-25)问题2 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-25

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

（执行体回写时填写）
