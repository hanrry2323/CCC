# 任务卡 T70 · 全项目代码 bug 检查（Cursor 测试卡 2 · M1 只读审计）

> 关联：老板 2026-08-06 指示「Cursor 做一次全部 CCC 项目检查，主要做代码 bug 检查」· 执行体：Cursor（M1 测试接手）· 验收：Codex（独立复核）· 状态：待分派 · 派发：manual · 项目：ccc · 日期：2026-08-06
> 工作目录：M1 `/Users/apple/program/CCC`；分支 `codex/cursor-t02-code-audit`（从 main 新建）
> 背景交接：`docs/cursor-code-check-handoff.md`（先读）
> **分步提交纪律（硬）**：清单分批 commit+push；禁止 `git add -A` 全量提交。

## 目标

对 CCC 全项目做一次只读代码 bug 检查，输出 ≥15 条有证据的问题清单（每条含位置/现象/证据/影响/严重级 P0-P3/修复建议），供后续修复卡使用。

## 范围与维度

- 范围：`server/`（engine/board/web/kb/config）+ `desktop/Sources/CCCDesktop/` + `server/web/legacy-chat/` 前端
- 维度：正确性（逻辑/边界/空值/竞态/异常/资源泄漏/死代码）、前后端契约一致性、健壮性（超时/重试/降级/错误提示/轮询）、双壳行为差异、安全（低优先）
- 已知问题对照：`docs/cursor-code-check-handoff.md` §三 清单优先标记「已登记」，不重复发明

## 红线

1. **只读检查，不擅自改代码**（修复走正式卡）；问题清单文档除外
2. 只检查 `/Users/apple/program/CCC`；禁止 SSH 改 2017 生产
3. 不碰 QuantHive / qb；不碰 docs/archive/
4. 不伪造证据——每条问题给真实命令输出或代码引用

## 验收标准（Codex 独立复核，不采信自述）

1. 清单 ≥15 条，条条有位置（文件:行）+ 证据 + 严重级 + 修复建议
2. 至少覆盖 server/ 与 前端 两块；desktop 有结论（查了或说明受限原因）
3. pytest 全量真实输出附上；能补 swift build/test 更好
4. 分支分步提交、工作树干净、push 成功

## 回写要求

卡头状态更新为「已回写」；回写区填：清单全文或文件路径、检查方法、pytest/swift 输出、push 证据。

## 回写区

**执行体**：Cursor（M1）· 日期：
