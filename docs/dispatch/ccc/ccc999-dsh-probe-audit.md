# 任务卡 ccc999 · DSH 只读取证/审计探针（DSH 执行）

> 关联：ccc-plan-029 卡3 · 执行体：DSH headless · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-18

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 方案池：`docs/projects/ccc/plans/`（关联方案见卡头「关联」）

## 目标

DSH 首单只读取证/审计探针：验证 Engine 能经 executors.json 自动拉起 DSH headless 完成只读审计并回写。

## 任务

1. 只读审计 CCC 仓 `docs/projects/registry.yaml` 与 `docs/dispatch/` 卡命名合规性
2. 按只读取证/合规扫描契约输出（发现清单 + file:行号 + 证据命令输出 + 置信度）
3. 审计完成后回写卡头「已回写」

## 红线

- 全程只读：不写/不删/不改任何业务文件
- 不碰密钥明文，只占位引用
- 审计输出带证据（原文 + 验证命令），禁止凭记忆断言

## 验收标准

- [ ] Engine 自动拉起 DSH（无手动触发）
- [ ] DSH 输出符合审计契约（发现清单 + 证据 + 置信度）
- [ ] 卡头回写「已回写」
- [ ] 退出码 0

## 执行提示

请对 /Users/fan/program/CCC 做只读取证审计：检查 registry.yaml 项目注册是否合规、dispatch 卡命名是否遵循 prefixNNN-slug.md、有没有过时/残留。输出严格按审计契约。
