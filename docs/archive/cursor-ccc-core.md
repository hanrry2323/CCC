# Cursor × CCC 核心开发规则（v0.51+）

## 一句话

**修平台 → 只开 CCC 仓；修业务 → Hub 下达对应项目。**

## 分流

| 意图 | 在哪做 | 怎么做 |
|------|--------|--------|
| Engine / Hub / Skill / 红线 / 登记 / 隔离 / commit-gate | **CCC** | Cursor 直接改 + commit；一次生效全舰队 |
| 业务功能、项目 SPEC、业务测试 | **业务仓** | Hub：对齐 → 定稿 → 下达；Engine 跑该仓看板 |
| 全局卫生（入口、断链、prune） | **CCC 主导** | 按 [`hygiene/PLAN-TEMPLATE.md`](hygiene/PLAN-TEMPLATE.md)；业务仓仅碰入口/登记 |
| 运维观察（doctor、runtime、Engine 控制） | **Hub** | 可选 CCC 项目聊天；**禁止**对 CCC 下达看板任务 |

## 禁止

- 禁止把 CCC 本体需求投进 CCC backlog 由 Engine 执行（**R-15**）
- 禁止在 Medio-0 / clawmed / xianyu 等仓「就地 fork」平台补丁
- 禁止 agent 自主启用 CCC 自 Loop（红线 12）

## 例外

仅当你与 Cursor **显式定「全局维护计划」** 时，才可跨仓做卫生类触碰（对齐 CLAUDE.md、清 skill、压舰队）。目的是流程更顺，不是业务功能开发。
