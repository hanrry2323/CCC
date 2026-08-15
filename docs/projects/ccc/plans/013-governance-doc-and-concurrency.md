# 方案 · M1/2017 执行分工文档统一 + 2017 并发闸门

> 项目：ccc · 编号：ccc-plan-013 · 状态：已完成 · 作者：OpenCode · 工具：OpenCode
> 创建：2026-08-10 · 更新：2026-08-10
> 关联卡：ccc040 ccc041
> 关联方案：无（2026-08-10 看板漂移治理延续）

## 目标

1. **文档统一**：消除「M1=写源 vs 2017=默认开发」的文档分裂，把分工声明对齐为现状真相。
2. **2017 并发闸门**：给 Engine 执行派发加并发上限（≤3 worktree，配置化），压住 2017 高负载（load 5-11），落实「单机 ≤3 窗口」原则。

## 背景

2026-08-10 看板漂移根因探查（四 Agent）确认真相：**执行体在 2017 worktree 写码**（2017 有 engine + 10 个 dev worktree；M1 零 worktree），状态真值只在 2017 `:7788/cards` API 合成。查询线路硬规则已落地（qx-map AGENTS.md + board-live.md + workflow.md）。

遗留两处治理缺口：
- **文档分裂**：`docs/deploy/topology.md:8`「M1 = git 写源」+ `docs/projects/ccc/README.md:11`「M1（写源）」与 `server/config/executors.example.json:13`「2017 默认开发（6102）」、`docs/architecture.md:11`「2017 单端 :7788」互相矛盾。
- **2017 高负载**：load 5-11，生产机与开发 worktree 同机，需并发闸门防 OOM/抢资源。

**方向（老板 2026-08-10 拍板）**：保持「2017=执行写码节点，M1=中枢出卡/验收/合入/看板 + 轻量开发」；业务仓卡（qb 等本体在 2017）维持 2017 执行。不做「写码归位 M1」（收益小于成本：M1 8GB 扛不住并发、需新增 SSH 跳板、推倒已跑通流程）。

## 方案内容

1. **卡1（ccc040）文档统一**：改 `docs/deploy/topology.md` + `docs/projects/ccc/README.md`（+ 涉及处），分工声明统一为：2017=执行写码节点（engine worktree）+ 生产 :7788；M1=中枢出卡/验收/合入/看板 + 轻量开发；业务仓本体机器写码。全仓 grep 无残留矛盾表述。
2. **卡2（ccc041）并发闸门**：Engine 派发逻辑加并发上限（默认 ≤3，config 可调）；超限进等待队列不重复派发；并发数可观测；单测覆盖。

## 验收标准

- [x] 卡1：topology.md 与 ccc/README.md 分工表述与现状/executors 一致，全仓无「M1=写源」残留矛盾。
- [x] 卡2：并发闸门生效（默认 ≤3），超限排队不重复派发，配置可调，engine 测试全绿，并发数有观测。
- [x] 两张卡 `swift/pytest` 相应门禁过；Doc-Gate 四问回写齐全。

## 转卡计划

```ccc-plan
title: M1/2017 执行分工文档统一 + 2017 并发闸门
project: ccc
slices:
  - title: 统一 M1/2017 分工文档声明（2017=执行写码节点，M1=中枢）
    slug: governance-doc-alignment
    acceptance:
      - docs/deploy/topology.md 与 docs/projects/ccc/README.md 的「M1=写源/开发副本」表述改为现状真相：2017=执行写码节点（engine worktree）+ 生产 :7788；M1=中枢出卡/验收/合入/看板 + 轻量开发；业务仓（qb 等）本体机器写码
      - 分工声明与 server/config/executors.example.json「2017 默认开发」、docs/architecture.md「2017 单端 :7788」一致，无互相矛盾
      - 全仓 grep「M1 = git 写源 / M1（写源）」等表述无残留（历史归档 docs/archive 除外，须标注已过时）
    whitelist:
      - docs/deploy/topology.md
      - docs/projects/ccc/README.md
      - docs/architecture.md
      - docs/projects/onboarding.md
    executor: OpenCode
  - title: 2017 Engine 执行并发上限（≤3 worktree，配置化）
    slug: engine-executor-concurrency-cap
    acceptance:
      - Engine 派发增加并发闸门：同时执行中的 worktree/执行体数 ≤ 上限（默认 3，config.env 可调）
      - 超限时新卡进入等待，不重复派发、不超开 worktree；等待行为可观测（日志记录排队）
      - 并发数有观测指标（日志/统计），quarantine/fallback 既有逻辑不回归
      - 单测覆盖并发上限判定（含边界），现有 engine 相关测试全绿
    whitelist:
      - server/engine/**
      - server/config/**
      - server/tests/**
    executor: OpenCode
```

## 备注

- **依赖**：与 ccc-plan-012（SwiftUI 组件升级）无冲突，可并行；卡号从 ccc040 起（ccc039 已被 engine-dispatch-guard 占用）。
- **查询线路硬规则**（2026-08-10 已直接落地，不在此卡）：qx-map AGENTS.md「看板快照（一眼看板 · 硬）」段 + workflow.md + board-live.md，判状态唯一线路 = board-live.md + `:7788/cards`（含 `/cards/search` 单卡查询）。
- **巡检**：本方案转卡后并入 ccc033-038 的巡检跟踪，直至关闭。
