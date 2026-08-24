# 任务卡 ccc084 · 轨迹抽取工具固化 traj-digest（DSH 执行）

> 关联：环节②交接指令(S116-01)卡3 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-24

## 目标

将临时区取证脚本 /tmp/dsh-traj-extract.py（重启即失）固化为仓内 scripts/traj-digest.sh：对指定卡的执行轨迹一键出坑清单（并发风暴/空转/环境坑/git 工作流/测试依赖五类）。

## 红线

- 白名单：scripts/traj-digest.sh（新建）。只读消费既有轨迹数据（exec/*.log、worker-events.jsonl、engine.stderr.log），不改任何数据源。
- macOS 优先：避免 sha256sum 等 Linux 专属命令；set -euo pipefail。

## 范围

- 入参：卡号或 exec 日志路径；输出：结构化坑清单（类别/证据行/时间戳）。
- 兼容 stderr 无时间戳现状（按行序+metrics jsonl 对时策略）。

## 步骤

1. 以 /tmp/dsh-traj-extract.py 逻辑为基线重写为 bash+python 内嵌形态落仓。
2. 对 ccc076-079 四卡轨迹实跑，产出清单。

## 验收标准

- [ ] scripts/traj-digest.sh 对 ccc076-079 轨迹跑通，五类坑清单输出完整
- [ ] 清单结论与本批取证（环节②指令第二节）逐类可对齐
- [ ] bash -n 通过；重复运行幂等

## 回写要求

- 回写区附四卡跑批输出摘要与对齐说明；维护区四问如实。

## 人工批注

（留空）

## 回写区

（执行体回写时填写）
