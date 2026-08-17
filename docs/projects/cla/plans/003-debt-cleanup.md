# 方案 · 债务收尾：旧文件作废归档与 decided.json 修正（M1-1.3）

> 项目：cla · 编号：cla-plan-003 · 状态：计划中 · 作者：OpenCode · 工具：opencode
> 创建：2026-08-17 · 更新：2026-08-17
> 关联卡：待出卡
> 关联方案：无
> 里程碑：M1 · 独立底座与路径清零
> 子项目：1.3 债务收尾
> 决策源：/Users/apple/qx-map/__archive__/decisions/ClawMed-CCC-Architecture-2026-08-17.md

## 目标

按架构定稿「旧方案废除清单」完成债务收尾：`docs/dev-plan.md` 作废、`docs/OBS1~3.md` 归档、`.ccc/agent-mind/decided.json` 修正，让 M1 真正闭环。

## 背景

架构定稿明确列出旧方案废除清单：
- `docs/dev-plan.md` 作废（旧 Phase 0-3 路线被架构定稿替代），内容移入 `docs/_archive/` 供考古。
- `docs/OBS1~3.md` 归档（旧观测文档，流程已闭环），移入 `docs/_archive/obs/`。
- `.ccc/agent-mind/decided.json` 修正：旧目标 `g-scheduler-jobspec-v0` → completed；追加 `g-clawmed-sqlite-and-ui`；追加两条硬契约（禁止复制 CCC 原生逻辑 / 前端静态单页一体化挂载）。
- 历史卡足迹（`.ccc/verdicts/`、`.ccc/pids/`）只读保留，不清理。

## 方案内容

### 1. 旧文件作废归档
- `docs/dev-plan.md` → `docs/_archive/dev-plan.md`（作废标记 + 指针指向架构定稿）。
- `docs/OBS1.md`/`OBS2.md`/`OBS3.md` → `docs/_archive/obs/`。
- 全仓 grep 清理残留引用（CLAUDE.md/README 若引用 dev-plan 则改指架构定稿）。

### 2. decided.json 修正
- 旧目标标 completed；新增 `g-clawmed-sqlite-and-ui` 目标；追加两条硬契约（自研契约）。

## 验收标准

- [ ] dev-plan/OBS 全部移入 `docs/_archive/`，无原位残留
- [ ] decided.json 目标/契约与架构定稿一致（diff 可复核）
- [ ] 全仓无指向旧文件的活跃引用（grep 验证）

## 功能卡

### 债务收尾（旧文件归档 + decided.json 修正）

目标：完成 M1 债务收尾，交付可验收产物。

实现：按「方案内容」两节执行——文件归档 + 引用清理 + decided.json 修正。

验收：验收标准三条款全过（归档无残留 / decided.json 一致 / 无旧引用）。

颗粒度：子项目级（1-2 卡，约 0.5 天）。

依赖：无（可与 cla016 并行）

架构位置：`docs/`、`.ccc/agent-mind/decided.json`

## 转卡计划

债务收尾（1 卡，待出卡）

## 备注

- 本方案从原 cla-plan-002 拆出（原方案混杂 1.2+1.3 两子项目，按 xy/hp 范式拆为独立方案）。
- 历史卡足迹（verdicts/pids）保留不清理，避免破坏审计链。