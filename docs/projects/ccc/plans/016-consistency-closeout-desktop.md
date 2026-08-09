# 方案 · 三层一致性收尾 + Desktop App 重建安装

> 项目：ccc · 编号：ccc-plan-016 · 状态：已确认 · 作者：OpenCode · 工具：OpenCode
> 创建：2026-08-10 · 更新：2026-08-10
> 关联卡：ccc047 · ccc048 · ccc049 · ccc053（转卡后回填）
> 关联方案：无（2026-08-10 复盘新增）

## 目标

1. **三层一致性收尾**：路线图 ↔ 方案 ↔ 卡的漂移/断链清理（方案状态、roadmap、orphan 卡、作废方案引用）。
2. **Desktop App 重建安装**：ccc033-038 桌面源码已合入但 `.app` 未重建（M1 上仍是 8/5 旧版）。

## 背景

2026-08-10 复盘（Agent C）确认三层一致性滞后：
- 13/18 方案「卡全关但方案未标已完成」（含 ccc-plan-001/003/004/007/010/011/012/013）。
- 17 卡卡头仍指向作废的 ccc-plan-005，未迁移到后继方案。
- ccc021 双归属（005 作废 + 010 关联）。
- 6 张 orphan 卡未入方案关联卡：ccc016、ccc039、clw006、qb001、hp018、xy027。
- roadmap：hp/mx 段停在 08-07 状态，缺 clw/qb 业务线路段，M8 仍标 ⏳。
- Desktop：desktop 编译问题已修（swiftLanguageMode v5），但 `/Applications/CCCDesktop.app` 是 8/5 版，SwiftUI 6 卡改动未生效。

## 方案内容

1. **卡1 方案状态收尾**：13 个卡全关方案推进状态（已完成/作废），方案「关联卡」字段补全 orphan 卡。
2. **卡2 roadmap 与引用清理**：roadmap 补 hp/mx 状态、增 clw/qb 业务线路段、M8 更新；17 卡迁出作废 plan-005、解决 ccc021 双归属。
3. **卡3 Desktop App 重建安装**：用修复后代码重建 CCCDesktop.app + 安装 + 冒烟（macOS15 / Textual / Charts / 质感）。
4. **卡4 旧卡收尾标注补填**：为已关闭但缺标注的旧卡补 ## 验收区 / ## 机审区 / ## 维护区 四问，使所有已关闭卡四区齐全。

## 验收标准

- [ ] 卡1：13 个方案状态与看板一致（卡全关→已完成/作废）；orphan 卡入方案关联卡。
- [ ] 卡2：roadmap 反映真实状态、含全部业务前缀线路段；无卡指向作废方案；ccc021 归属唯一。
- [ ] 卡3：CCCDesktop.app 重建安装成功，启动冒烟通过（含 Markdown 渲染/图表/质感）。

## 转卡计划

```ccc-plan
title: 三层一致性收尾 + Desktop App 重建安装
project: ccc
slices:
  - title: 方案状态收尾 + orphan 卡关联登记
    slug: plan-status-closeout
    acceptance:
      - 13 个「卡全关未标已完成」方案推进状态（已完成/作废），与看板一致
      - orphan 卡（ccc016/ccc039/clw006/qb001/hp018/xy027）登记进对应方案「关联卡」字段（或卡头关联修正）
      - 方案「关联卡」字段与卡头「关联」字段双向一致（validate 通过）
    whitelist:
      - docs/projects/**/plans/*.md
      - docs/dispatch/**
    executor: OpenCode
  - title: roadmap 更新与作废方案引用清理
    slug: roadmap-orphan-cleanup
    acceptance:
      - roadmap.md 反映真实卡状态（hp/mx 段补全、M8 更新、增 clw/qb 业务线路段）
      - 17 张卡头指向作废 ccc-plan-005 的迁移到后继方案；ccc021 双归属唯一化
      - 三层一致性校验（roadmap↔plans↔cards）无断链
    whitelist:
      - docs/roadmap.md
      - docs/dispatch/**
      - docs/projects/ccc/plans/**
    executor: OpenCode
  - title: Desktop App 重建安装与冒烟
    slug: desktop-rebuild-install
    acceptance:
      - 用修复后的 Package.swift（swiftLanguageMode v5）重建 CCCDesktop.app
      - 安装到 /Applications 并替换 8/5 旧版
      - 启动冒烟：Markdown 渲染（Textual）、OpsView 图表（Charts）、质感效果正常
      - swift build 与 desktop 测试全绿
    whitelist:
      - desktop/**
    executor: OpenCode
  - title: 旧卡收尾标注补填（验收区/机审区/维护区）
    slug: legacy-card-closeout-backfill
    acceptance:
      - 对已关闭但缺标注的历史卡（T 卡 + 早期 ccc 卡 + 其他前缀旧卡）补齐收尾标注：
        - ## 验收区（合入批准 · 日期 · 判定通过）——缺的补写
        - ## 机审区（机审：通过 · 来源按现有证据）——缺且有证据的补写；无证据的注明「历史卡，无存档证据，按看板已关闭态标注」
        - ## 维护区 四问——缺失的按实情勾选（历史卡一般 [否]/[无] + 一句实情说明），不做无依据声明
      - 补填后 validate 通过；批量脚本（如可用）产出变更清单供人审
      - 不改变卡状态（保持已关闭），不编造证据
    whitelist:
      - docs/dispatch/**
    executor: OpenCode
```

## 备注

- desktop 编译修复（v5 mode）已直接落地并验证（2026-08-10）。
- 复盘相关登记见 hp-kb `/codex/topics/ccc/backlog-3-items-pending-2026-08-10`。
