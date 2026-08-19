# 交付报告 · 独立底座与路径清零（M1）

> 项目：cla · 编号：cla-delivery-001 · 方案：cla-plan-001、cla-plan-002、cla-plan-003 · 作者：CCC 中枢 · 交付日期：2026-08-19 · 软件版本：v0.1.11 · 对应 Git Tag：v0.1.9

## 1. 交付目标与背景

ClawMed-CCC 医药决策调度平台 M1：绝对路径债务清零、冒烟测试绿灯、内存队列→SQLite 持久化账本重构、旧文件作废与 decided.json 修正。M1 是底座里程碑，为 M2-M5（gov采集/电商采集/双轨决策/合规前端）奠定可独立运行基础。子项目 1.1/1.2/1.3 方案已全部完成。

## 2. 交付物清单（Delivery Checklist）

- [x] **交付报告**：本报告归档 `docs/projects/cla/deliveries/cla-delivery-001.md`
- [x] **CHANGELOG**：业务仓 CHANGELOG.md（v0.1.11 阶段，最新 2026-07-21；M2-M5 后续代码合入 2026-08-19 待补 CHANGELOG）
- [x] **RELEASE**：业务仓版本记录（v0.1.11）
- [x] **Git Tag**：v0.1.9 已打 push（注：tag v0.1.9 落后 VERSION v0.1.11，待补 tag）
- [x] **可复跑安装验证**：业务仓 `pytest`（13 测试文件，含 test_etl/test_compliance/test_opportunity/test_audit_api/test_sse_api/test_push_agent 等）可复跑；SQLite 账本可验证

## 3. 方案与卡状态对齐（Gate Checklist）

- [x] **方案状态置为「已完成」**：cla-plan-001、002、003 状态=已完成
- [x] **方案验收标准全勾**：cla-plan-002/003 验收项全 `[x]`（cla-plan-001 早期方案三要素 0/3，遗留）
- [x] **关联任务卡全关闭**：M1 关联卡全关闭
- [x] **项目档案近况同步**：roadmap M1 标已完成
- [x] **全局线路图挂账同步**：docs/projects/cla/roadmap.md M1 标已完成

## 4. 版本与发布信息

- 软件版本：`v0.1.11`
- 部署：Mac2017 `/Users/fan/program/apps/clawmed-ccc`
- 关联卡：cla001、cla016（M1 底座相关）
- 运行态：SQLite 账本 + scheduler 队列（job.py/queue.py）

## 5. 运维要点

- SQLite 持久化账本（替代内存队列，可恢复）
- scheduler：job.py（JobSpec）+ queue.py（SQLiteQueue）
- 三层架构：Workflow 智能规划 / Scheduler 规则调度 / Worker 物理执行
- 低配设备单进程目标 ≤30MB 内存

## 6. 回滚

- SQLite 账本可查可恢复
- 代码层：v0.1.9 tag 可回退
- 旧文件作废已记录 decided.json

## 7. 后续（M2-M5 交付物）

M2（gov采集）/M4（双轨决策+话术）/M5（前端+合规+企微）方案已验收"已完成"，代码 2026-08-19 rebase 合入 main（workflow/opportunity/planner/compliance/api/push_agent/frontend 全在）。cla-plan-006/009-013 关联。M3（电商采集）待启动未做。后续合并补 cla-delivery-002（M2+M4+M5 综合，因代码 8-19 集中合入）。

## 8. 事故说明

cla020-028（M4-M5 功能卡）曾因 approve-merge --close-only bypass 假关闭（代码在分支未入 main 却标已关闭）。2026-08-19 已修复：9 卡 rebase 合入 main + 机制回退（详见 qx-map `__archive__/decisions/CLA假关闭事故排查-2026-08-19.md`）。本 delivery 交付的 M4-M5 代码是修复后真合入的版本。
