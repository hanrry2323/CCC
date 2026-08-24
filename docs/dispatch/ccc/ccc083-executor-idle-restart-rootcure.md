# 任务卡 ccc083 · 执行体重启空转根治——B3 取证与防旋修复（DSH 执行）

> 关联：环节②交接指令(S116-01)卡2 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-24

## 目标

对「71 分钟 13 个短命执行体会话（7–16 步无编辑即断，llm_retry 最高 5 次/会话）」取证根治：核实 B3 假设（watchdog 对 LLM 失败的重派发循环）是否有直接日志证据；定位重派发循环并修复（重试退避/熔断/短命会话防旋）；会话寿命与编辑命中率纳入探针指标。

## 红线

- 白名单：scripts/watchdog-ccc.sh、scripts/kickstart-ccc.sh、server/engine/main.py（派发/重试段）、~/.dsh/run-executor.sh（只读参考）、server/tests/。
- 取证阶段只读：watchdog.log、engine.stderr.log、exec/*.log、worker-events.jsonl、engine-metrics.jsonl。
- B3 无法实证时必须显式标「推断」，不得当结论。

## 范围

- 取证：时间线对齐（会话起止 × watchdog kickstart 时刻 × LLM retry 记录），产出直接证据或排除。
- 修复方向（按取证结果择一或组合）：kickstart 前置 LLM 健康探针；短命会话计数熔断（N 分钟内 M 个短会话→暂停派发+告警）；重试指数退避。
- 探针：worker-events 增加会话寿命/编辑命中字段。

## 步骤

1. 全量取证并对时，先出证据段落。
2. 实施修复。
3. 自测：单测覆盖新熔断/退避逻辑；bash -n / py_compile。

## 验收标准

- [ ] 取证段有直接证据或明确「推断」标注
- [ ] 修复落地且有回归单测
- [ ] 探针字段可在 worker-events.jsonl 观察到

## 回写要求

- 回写区附证据时间线摘要与修复说明；维护区四问如实。

## 人工批注

（留空）

## 回写区

（执行体回写时填写）
