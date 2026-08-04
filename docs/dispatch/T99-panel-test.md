# 任务卡 T99-panel-test · 后台任务进程面板验证（占位）

> 关联：T53 验收（面板实时展示验证）· 执行体：Claude Code · 验收：Codex · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-04

## 目标

验证控制台「后台任务进程」面板实时显示执行中任务。占位任务：向 `/tmp/ccc-panel-test.txt` 写入 `panel-ok` 后结束（exit 0）。

## 红线

只写该占位文件，不改任何代码；验收后删除。

## 验收标准

1. 卡状态待分派→执行中→已回写（Engine 自动派发）。
2. `/tmp/ccc-panel-test.txt` 内容 = panel-ok。
3. 执行中期间 `/tasks/running` 返回该任务（含日志尾部）；完成后为空。

## 回写区

**执行体**：Claude Code（2017）· 日期：
