# 任务卡 ccc093 · 审计预算失配修复 + push 成功检测去误报（DSH 执行）

> 关联：ccc081 四连 900s 击杀 / ccc088 「空转」假 infra 行 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-25

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

（执行体回写时填写）
