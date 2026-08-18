# 交付报告 · 底座解耦与架构升级

> 项目：mx · 编号：mx-delivery-003 · 方案：mx-plan-003 · 作者：CCC 中枢 · 交付日期：2026-08-19 · 软件版本：v0.9.0 · 对应 Git Tag：v0.9.0

## 1. 交付目标与背景

medio-0 底座解耦（行为等价重构）：把服务依赖从内部 new 改为统一注入 Arc 单例，AppState 拆子状态域，路由层复用注入服务。修复 WebSub 实时推送断链（rss/service.rs 路径引用）。这是「第一个真跑通 CCC 全流程」的方案（mx036-041 六卡经 engine 派发→回写→机审→合入完整闭环），于 2026-08-15 完成。

## 2. 交付物清单（Delivery Checklist）

- [x] **交付报告**：本报告归档 `docs/projects/mx/deliveries/mx-delivery-003.md`
- [x] **CHANGELOG**：业务仓 CHANGELOG.md（v0.9.0 阶段）
- [x] **RELEASE**：业务仓发布记录（v0.9.0）
- [x] **Git Tag**：v0.9.0 已打并 push（`git tag` 确认 v0.9.0 在）
- [x] **可复跑安装验证**：业务仓 scripts/ 提供 build/deploy/health_probe/test；`cargo test` + 前端 vitest + 冒烟全绿

## 3. 方案与卡状态对齐（Gate Checklist）

- [x] **方案状态置为「已完成」**：mx-plan-003 状态=已完成
- [x] **方案验收标准全勾**：6 条验收（WebSub 恢复/注入单例/AppState 拆分/路由复用/ImageCache config/Playback 注入 + 测试全绿）全 `[x]`
- [x] **关联任务卡全关闭**：mx036-041 全部已关闭（2026-08-15）
- [x] **项目档案近况同步**：roadmap M6 标已完成
- [x] **全局线路图挂账同步**：docs/projects/mx/roadmap.md 含 plan-003

## 4. 版本与发布信息

- 软件版本：`v0.9.0`
- 发布渠道：Mac2017 生产机（`/Users/fan/program/apps/medio-0`）
- 关联卡：mx036, mx037, mx038, mx039, mx040, mx041
- 重构性质：行为等价（无功能新增，纯架构解耦，现有测试基线全绿为回归保证）

## 5. 运维要点

- WebSub 实时推送恢复后需确认 rss feed 订阅实时性（非轮询）
- 服务注入单例化后，并发场景下 AppState 共享只读，无锁竞争
- `cargo test` + `vitest` 为合入门禁，失败即阻断

## 6. 回滚

- 行为等价重构，回滚 = revert mx036-041 六卡 commit 到合入前 main；测试基线保证无回归
- v0.9.0 tag 可 `git reset --hard v0.9.0^` 回退（需业务确认）
