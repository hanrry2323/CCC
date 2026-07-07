# debt-pool

> 标题: dev 改走 opencode-pool 获得并发保护
> 创建: 2026-07-07T12:45:01Z

## 目标

## 问题
dev_role() 直接调 opencode-exec.py，绕过 opencode-pool 的 Semaphore(3)。红线 X1 形同虚设。

## 执行方案
1. opencode-pool.py 增加 CLI 单任务模式（--single --phase <id> --prompt <file> --timeout <s>）
2. dev_role() 调 pool 的单任务模式（不走 JSON 文件）
3. pool 内部 Semaphore(3) 排队
4. 验证：同时起多个 dev 看是否排队

## Phase

(由 dev 拆)

## Commit 计划

- dev 完成后自动 commit + push
