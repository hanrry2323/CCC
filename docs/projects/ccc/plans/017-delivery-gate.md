# 方案 · 交付流程建设（Delivery Gate 机制）

> 项目：ccc · 编号：ccc-plan-017 · 状态：部分执行 · 作者：OpenCode · 工具：OpenCode
> 创建：2026-08-10 · 更新：2026-08-10
> 关联卡：ccc054 · ccc055（转卡后回填）
> 关联方案：无（2026-08-10 复盘遗留）

## 目标

补齐「项目交付收尾 SOP」——从单卡级完成钩子升级到**方案级交付门禁（Delivery Gate）**，并给 validate-plans.sh 加方案级收尾校验。

## 背景

2026-08-10 复盘（多 Agent 核实）确认真实遗留：
- onboarding.md **无 §7 项目交付收尾**，只有单卡级 Doc-Gate；docs/releases/ 只有 CCC 平台自身版本，无业务项目交付流程。
- **validate-plans.sh 无方案级收尾校验**：方案「关联卡全关但状态未标已完成/验收未勾」不报错（13/18 方案卡全关未收尾即此漏洞）。
- CLW 作为第一个交付实例等 SOP 定稿后走示范。

## 方案内容

1. **卡1（§7 Delivery Gate + delivery-template）**：onboarding.md 增 §7「项目交付收尾」——交付物清单（交付报告/CHANGELOG/RELEASE/git tag/可复跑安装验证）、方案置「已完成」、验收全勾、档案近况+roadmap 同步；新增 `docs/projects/_template/delivery-template.md`。
2. **卡2（validate-plans.sh 方案级收尾校验）**：validate-plans.sh 增加方案级校验——关联卡全关但方案状态未推进（应为已完成/作废）或验收未勾 → 报错。

## 验收标准

- [ ] §7 落地：onboarding 含交付收尾章节 + delivery-template，交付物清单可勾选。
- [ ] validate-plans.sh 方案级校验生效：构造「卡全关未标完成」方案 → 报错。
- [ ] 现有 13 个「卡全关未收尾」方案在 §7 定稿后逐一收尾（或由 §7 执行流程覆盖）。

## 转卡计划

```ccc-plan
title: 交付流程建设（Delivery Gate 机制）
project: ccc
slices:
  - title: onboarding §7 项目交付收尾（Delivery Gate）+ delivery-template
    slug: delivery-gate-sop
    acceptance:
      - docs/projects/onboarding.md 新增 §7「项目交付收尾（Delivery Gate）」：交付物清单（交付报告/CHANGELOG/RELEASE/git tag/可复跑安装验证）、方案置已完成、验收全勾、档案近况+roadmap 同步
      - 新增 docs/projects/_template/delivery-template.md（交付报告模板，含交付物勾选/验收/版本/安装验证）
      - 引用关系：卡级 Doc-Gate（§6）与方案级 Delivery Gate（§7）分层说明清晰
    whitelist:
      - docs/projects/onboarding.md
      - docs/projects/_template/**
    executor: OpenCode
  - title: validate-plans.sh 方案级收尾校验
    slug: validate-plans-delivery-gate
    acceptance:
      - validate-plans.sh 增加方案级收尾校验：方案关联卡全部关闭但方案状态仍为草案/已确认/部分执行（未推进）→ 报错
      - 方案「已完成」但验收未勾选 → 报错
      - 现有方案库跑一遍：列出所有「卡全关未收尾」方案供后续收尾
      - validate-plans.sh 测试覆盖新校验
    whitelist:
      - scripts/validate-plans.sh
      - server/tests/**
      - docs/projects/**/plans/*
    executor: OpenCode
```

## 备注

- 2026-08-10 已直接修复的教训相关：kb-seed 误加 L33/L34 撤销、lessons.md Lesson 55（clw006 教训）、clw-plan-001 验收勾选。
- CLW 交付收尾示范见 ccc-plan-018。
