# tst · CCC 管线自检专用项目

> 2026-08-23 老板拍板启用（指令 A 第 1 步），替代此前「隔离目录出卡」的测试方式——**一切管线测试/自检走真实看板 + Engine 全自动派发**。

## 1. 是什么

CCC 平台的管线自检专用项目：承载冒烟/E2E/链路验证类任务卡，是「Engine 唯一调度面 + 任务卡唯一流转载体」纪律的安全试验田。

## 2. 路径

- M1：无（已退役）
- 2017：`/Users/fan/program/apps/ccc-tst`（origin = 本地裸仓 `/Users/fan/program/apps/ccc-tst.git`，零外部依赖）
- 业务 worktree 根：`/Users/fan/program/apps/.ccc-wt/tst`（max_concurrent=1）

## 3. 在 CCC 怎么动

- 出卡前缀：`tst`（registry `taskable: true`、`forbidden: false`、`status: active`）
- 出卡方式：方案确认后 `scripts/plan-to-cards.sh`；单卡冒烟可 `new-card.sh`
- 执行体/验收：DSH（与全平台一致）；Engine 全自动派发，管理席只碰出卡与审核合入两个人审闸口

## 4. 基准文件（核心导航）

| 项 | 位置 |
|----|------|
| 项目档案 | docs/projects/tst/README.md（本文） |
| 方案池 | docs/projects/tst/plans/ |
| 看板 | http://192.168.3.116:7788/#/board（项目筛选 tst） |
| 管线权威 | docs/projects/onboarding.md · docs/CCC-PRIME-DIRECTIVE.md · server/engine/main.py |
| 测试仓入口 | /Users/fan/program/apps/ccc-tst（AGENTS.md · README.md） |

## 5. 线路 / 近况

- 2026-08-23：启用；首张自检卡 tst-001（管线冒烟）作为看板可见性+状态流转验证。

## 6. 禁区

- **禁止承载真实业务数据/逻辑**——本仓不是业务仓；
- 卡内容最小化且可标识（标题/slug 含 smoke/e2e 字样）；
- 禁止把 tst 卡用作绕过门禁的通道（approve-merge 校验/机审 ledger/维护区四问一个不落）；
- 禁止把 tst 卡当生产交付证据；
- 测试产物随卡关闭归档，不在 main 长期堆积。
