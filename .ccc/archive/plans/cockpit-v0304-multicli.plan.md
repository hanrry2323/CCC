# cockpit-v0304-multicli

> 此 plan 由 fallback 自动生成（product API 不可用）

## 目标
- Cockpit v0.30.4 — 多 CLI 引擎 + 日志面板
- 参考 claudecodeui，支持切换 claude-p / opencode / cursor CLI，Cockpit 内查看服务日志。

## 文件白名单
- `scripts/ccc-cockpit.py`（仅此文件）
- `.ccc/plans/cockpit-v0304-multicli.plan.md`（本文件，补白名单）
- `.ccc/phases/cockpit-v0304-multicli.phases.json`（更新 phase 进度）
- `.ccc/reports/cockpit-v0304-multicli.report.md`（执行报告）

## 验收
1. 完成任务目标
2. 相关测试通过
3. Python 语法检查通过（`python3 -m py_compile scripts/ccc-cockpit.py`）
