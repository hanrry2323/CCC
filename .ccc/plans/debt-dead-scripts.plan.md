# debt-dead-scripts

> 标题: 清理 5 个死脚本（零引用）
> 创建: 2026-07-07T12:45:02Z

## 目标

## 问题
scripts/ 下有 5 个文件已零引用（v0.7 遗留）：
- ccc-precheck.sh
- ccc-finish.sh
- ccc-queue.sh
- ccc-auto-dev.sh
- ccc-poll.sh

## 执行方案
1. grep -rn 确认确实无引用（排除 CHANGELOG）
2. mv 到 .archived-2026-07-07/ 保留历史
3. 更新 README 资产清单

## Phase

(由 dev 拆)

## Commit 计划

- dev 完成后自动 commit + push
