# 方案 · CCC 流程架构改造——子项目层 + 完整开发流程（轻度重构）

> 项目：ccc · 编号：ccc-plan-032 · 状态：已完成 · 作者：Claude Code（W1） · 工具：Claude Code
> 创建：2026-08-16 · 更新：2026-08-16
> 关联卡：无（平台自研红线：ccc 禁出卡，M1 主窗口直接开发 + 异席机审）
> 关联方案：ccc-plan-027（里程碑×方案×功能卡模型，其中「无中间层」定义被本方案覆盖）
> 里程碑：平台流程架构
> 决策源：/Users/apple/qx-map/__archive__/decisions/CCC流程架构改造-子项目层-2026-08-16.md

## 目标

以「里程碑 → 子项目 → 计划（逐步投入）→ 开发卡（三要素）」为正确模型改造三层流程——**架构上轻度**（不加新文件类型、不重做数据层），但**开发流程端到端完整**（质量门禁 + 交付承接补齐）。

## 背景

HP 项目落库暴露三层流程粒度缺陷：缺「里程碑→方案」分解单元 → 方案=整个里程碑一次全投（原 hp-plan-004 一个方案塞 M2 全部 7 个子项目，42 分钟后作废收回）。十路子 Agent 调查确认根因：027 删除中间层基于「方案拆卡粒度已足够」的错误假设（对 mx 成立、对 HP 不成立）。

## 方案内容（P0-P7 已实施）

| 阶段 | 内容 | 落地文件 |
|------|------|---------|
| P0 数据层 | Milestone.subprojects 结构化字段 + 解析/序列化（修吞 `- 子节点：` bug）+ 按子项目聚合进度 | server/board/roadmap.py |
| P1 方案层 | 功能卡三要素（颗粒度/依赖/架构位置）+ convert_plan 按子集转卡（slices）+ 依赖透传 --depends + 依赖硬约束 | server/board/plans.py、plan-template.md、new-card.sh（已有 --depends） |
| P2 校验 | validate-plans.sh 三要素存在性 + 依赖悬空 + 环境准备声明 | scripts/validate-plans.sh |
| P3 前端 | 线路图页右里程碑/左子项目列表 + 下钻 + 激活按钮；/plans/convert 收 slices | roadmapPage.js、shell.css、server.py |
| P4 质量门禁 | 测试/编译门禁失败=硬打回；密钥扫描门禁（approve-merge）；人审定义成文 | server/engine/main.py、approve-merge.sh、merge-executor-instruction.md |
| P5 交付承接 | 环境准备门禁联动（convert_plan）+ hp 部署/回滚参考脚本 | plans.py、docs/projects/hp/scripts-reference/ |
| P6 迁移 | hp M2-M5 22 子项目→22 方案 + roadmap 子项目结构化；mx M6 状态修复 + mx-plan-003 验收勾选 + mx-plan-004 三要素 | docs/projects/hp/、docs/projects/mx/ |
| P7 文档 | PRIME-DIRECTIVE §2.1 子项目概念 + onboarding §3.5 + DOC-PROTOCOL codex 前缀消歧 + 本方案 + 决策档 | 各文档 |

## 验收标准

- [x] roadmap 解析/序列化往返不丢子项目；单测覆盖（test_board_roadmap.py 34 绿）
- [x] 方案含三要素可转卡；slices 按子集只转指定功能卡；不传 slices 全转（旧方案兼容）
- [x] 依赖硬约束：依赖不在本批/非已有关卡拒绝出卡；同批依赖透传写卡头「> 依赖：」
- [x] validate-plans.sh：子项目方案缺三要素 FAIL、缺环境准备 FAIL、依赖悬空 FAIL、旧方案 WARN；全量校验通过（0 错误）
- [x] 线路图页右里程碑/左子项目列表 + 激活按钮 + 下钻方案（roadmapPage.js 换栏）
- [x] 质量门禁：测试/编译失败硬打回（engine 门禁）；approve-merge 密钥扫描命中阻断；人审定义成文
- [x] 环境准备门禁：convert_plan 拒绝缺环境准备的子项目方案
- [x] 迁移：hp 22 方案 + roadmap 子项目结构化 + mx M6 修复 + mx-plan-003/004 收尾，全量 validate 通过
- [x] 全量 pytest（server/tests/）通过

## 备注

- **明确不纳入**（后续立项）：统一告警通道（属 HP M3，子项目模型落地后重立项）；分支卫生批量清理（远端 codex 分支已归零，剩每周五 fetch --prune 三端统一 + 2017 机 ~144 本地分支 prune）。
- **风险对策**：序列化吞子节点（P0 先修 + 往返测试）；027 冲突（决策档 + PRIME-DIRECTIVE 修订覆盖）；依赖门禁只对依赖/架构位置硬约束、颗粒度只查存在性。
- **执行模型**：平台自研红线（ccc taskable:false），M1 主窗口直接开发 + 异席机审，未走卡/engine。
