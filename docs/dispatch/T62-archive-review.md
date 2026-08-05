# 任务卡 T62 · T-A5 历史归档与回顾 + /cards 兜底（Claude Code 执行）

> 关联：阶段 3（T-A5）+ T50 联调发现（/cards 缺索引返回空，需兜底）· 执行体：Claude Code · 验收：Codex · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-05
> 工作目录：请先创建独立 worktree `git -C /Users/fan/program/CCC worktree add /Users/fan/program/ccc-dev-ws-t62 -b codex/t62-archive-review origin/main`，在其中工作；分支 `codex/t62-archive-review`
> **分步提交纪律（硬）**：每块完成立即 commit+push；超时 7200s。

## 目标

历史任务归档与回顾：关闭 6 个月卡自动归档（git mv）+ 索引 archived 标记 + 回顾查询（结构化/语义双通道）+ /cards 缺索引兜底。

## 具体项

1. **归档机制**：关闭 >6 个月卡自动移入 `docs/archive/ccc-tasks/<project>/`（git mv 保留历史）；索引 `archived=true` 标记；board-scheduler 定时执行 + 手动触发（`scripts/archive-cards.sh`）。
2. **回顾查询**：结构化（按项目/时间/状态/执行体走索引，含归档卡）；语义走知识库（大脑检索已有，卡关闭时教训沉淀机制 T-A4 已衔接）。
3. **/cards 缺索引兜底**：索引文件缺失/为空时，/cards 与 /cards/search 自动回退全量扫描（不返回空），并触发一次索引重建（日志记录）。
4. 测试：归档脚本（临时目录）、索引 archived 标记、/cards 兜底（删索引后查询仍返回数据）。

## 红线

1. 只改 server/board/、server/engine/、server/web/server.py（/cards 兜底区）、scripts/、docs/、tests；**禁止改前端 js（后续卡）**。
2. 归档只 git mv，不删除；缺索引兜底不得破坏正常索引路径性能。
3. 回写前 push 成功并附证据。

## 验收标准

1. 归档脚本实测（临时目录）：过期卡移入归档 + 索引 archived 标记 + 看板/回顾不含已归档（除非显式含）。
2. /cards 缺索引：删索引后查询返回全量数据（兜底生效）+ 日志有重建记录。
3. 结构化回顾查询（含归档）实测；语义回顾走知识库说明。
4. pytest 全绿、ruff clean、push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：归档机制、兜底实现、测试记录、pytest/build、push 证据。

## 回写区

**执行体**：Claude Code（2017）· 日期：
