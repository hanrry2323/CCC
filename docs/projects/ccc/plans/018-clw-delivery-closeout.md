# 方案 · CLW 交付收尾示范（首个 Delivery Gate 实例）

> 项目：ccc · 编号：ccc-plan-018 · 状态：已完成 · 作者：OpenCode · 工具：OpenCode
> 创建：2026-08-10 · 更新：2026-08-10
>  关联卡：已归档（原引用 ccc056 随 8-24 治理归档，见 docs/archive 与 RETIRED 记录）
> 关联方案：ccc-plan-017（交付流程 §7 定稿后执行）
> 进度：0/1 (0%)

## 目标

按 §7 Delivery Gate 流程，把 CLW（clwarp）作为**第一个交付示范实例**完整收尾——交付报告、版本标记、可复跑安装验证、方案/档案/roadmap 同步。

## 背景

2026-08-10 复盘确认 CLW 是「代码全链闭环但交付流程未定型」的典型：
- clw001-007 全链已合入关闭，clw-plan-001 验收已勾（本会话已修），clwarp 基建（main/默认分支/远端干净）就绪。
- **缺交付物**：无交付报告、无 CHANGELOG/RELEASE、git tag 为 0、roadmap 无 clw 业务线路段、方案交付视角未收尾。

## 方案内容

1. **卡1（CLW 交付收尾示范）**：按 §7 交付流程执行 CLW 首个实例——产出交付报告、CHANGELOG/RELEASE、git tag v0.1.0、可复跑安装验证（dmg→/Applications→启动冒烟）、roadmap 增 clw 业务线路段、clw-plan-001 交付收尾标记。

## 验收标准

- [x] 交付报告（delivery-template 格式）产出，交付物清单全勾。
- [x] CHANGELOG + RELEASE + git tag v0.1.0（clwarp 业务仓）。
- [x] 可复跑安装验证：dmg 打包 → /Applications 安装 → 启动冒烟。
- [x] roadmap.md 含 clw 业务线路段；clw-plan-001 交付收尾。

## 转卡计划

```ccc-plan
title: CLW 交付收尾示范（首个 Delivery Gate 实例）
project: ccc
slices:
  - title: CLW 交付收尾示范（报告/CHANGELOG/tag/安装验证/roadmap）
    slug: clw-delivery-closeout
    acceptance:
      - 按 docs/projects/_template/delivery-template.md 产出 CLW 交付报告，交付物清单全勾
      - clwarp 业务仓产出 CHANGELOG + RELEASE + git tag v0.1.0
      - 可复跑安装验证：dmg 打包 → /Applications 安装 → 启动冒烟通过（记录验证步骤）
      - docs/roadmap.md 增「业务线路（clw）」段，反映 clw001-007 已交付
      - clw-plan-001 标交付收尾完成（结合 §7 流程）
    whitelist:
      - docs/projects/clw/**
      - docs/roadmap.md
      - docs/releases/**
    executor: OpenCode
```

## 备注

- 依赖 ccc-plan-017 §7 定稿（或与其并行，卡内按 §7 草案执行后回填）。
- 2026-08-10 已直接修复：clw-plan-001 验收勾选、clwarp 孤儿分支清理。
