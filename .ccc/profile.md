# CCC Profile — CCC (Connect–Claude Code) 本体项目

> 本档案由 Planner 在 CCC 项目首次接入时生成。后续任务启动时 **强制先读本文件**
> （红线 7：启动顺序固定，profile.md 第一）。

## 项目元信息

- **项目根**: `/Users/apple/program/CCC`
- **仓库**: CCC 本体（SKILL 资产型框架）
- **分支**: main
- **当前版本**: 见 `VERSION` 文件（1.1.0）
- **语言/技术栈**: Bash (90% scripts) + Python 3.11+ (cluster bus / dispatcher / search)

## 项目定位

CCC 是一个 **SKILL 资产**，不是传统 framework 代码库。
核心交付物是 `SKILL.md`（唯一注入 prompt），把 Claude Code 的执行能力
**连接**到任意 IDE（Trae / Cursor / Zed / VS Code / OpenCode）。

## 关键资产清单

| 路径 | 角色 |
|------|------|
| `SKILL.md` | 唯一注入 prompt（agent 启动时自动加载） |
| `references/red-lines.md` | 13 红线强约束（v0.7 新增红线 13） |
| `scripts/ccc-precheck.sh` | 5 项前置门控（红线 7+10） |
| `scripts/ccc-finish.sh` | 5 项后置门控 |
| `scripts/executor-watchdog.sh` | Executor 健康检查（红线 9） |
| `scripts/ccc-exec-commit.sh` | 单 phase 单 commit（红线 4+8） |
| `scripts/ccc` | CLI wrapper |
| `scripts/ccc-init.py` + `ccc-search.py` + `ccc-status.sh` + `ccc-task-done.sh` | 基础运维 |
| `templates/` | 4 文件契约模板（plan/phases/report/verdict/executor-prompt/AGENTS） |
| `tests/scripts/` | 8 个 pytest 核心测试 |
| `references/adapters/runtime-opencode.md` | opencode 适配器（其他 IDE 适配器已精简） |
| `.ccc/profile.md` + `.ccc/state.md` | 项目档案 + 接力索引（红线 7+10） |
| `docs/lessons.md` | 历史教训沉淀（含 lesson 30：验收数字规则） |
| `docs/roadmap.md` | 路线图（v0.5 → v1.0） |
| `CHANGELOG.md` | 版本变更 |

## 4 文件契约路径

```
.ccc/
├── profile.md              # 本文件
├── plans/<task>.plan.md
├── phases/<task>.phases.json
├── reports/<task>.report.md
├── verdicts/<task>.verdict.md  # 红线 11 强证据
└── abnormal-reports/
```

## 已知约束

- **绝不动**: `/etc/*`, `~/.env`, `~/.aws/*`（红线 1）
- **必须走 .ccc/**: 任何任务产出物（plan/report/verdict）必须在 `.ccc/` 内
- **commit 规则**: 单 phase 单 commit（红线 4 + 8）
- **Executor 卡死**: 立即 `kill -9 <pid>` + Planner 接管（红线 9）
- **planner/verifier 隔离**: 角色不可越界（红线 6）

## 工具链版本

- Python 3.11+
- Bash 5.x (zsh 5.9 实测可用)
- Claude Code CLI 2.1.193+

## 工程纪律（适用本项目）

1. 不写假报告 — VERDICT 段必须引用真 verdict.md
2. 不口头 PASS — verdict.md 真文件存在才算 PASS（红线 11）
3. 不跨会话隐式记忆 — 必落文件（红线 10）
4. 不自主启用 CCC — 用户显式触发（红线 12）