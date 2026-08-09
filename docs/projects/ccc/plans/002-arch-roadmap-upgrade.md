# 方案 · 线路图升级为集群全景架构图（ARCH 体系 v1.0）

> 项目：ccc · 编号：ccc-plan-002 · 状态：已完成 · 作者：老板 · 工具：OpenCode
> 创建：2026-08-08 · 更新：2026-08-08
> 关联卡：无
> 关联方案：无
> 迁移自：docs/notes/m9-arch-roadmap-plan.md（合并自 qx-map decisions/线路图升级为集群全景架构图-2026-08-08.md）

## 结论

CCC 看板 `#/roadmap` 由「卡状态统计」升级为「集群全景架构图库」：
每项目一张 Archify 架构图（含全景），开发中持续维护，成为老板 ↔ Agent 双向沟通界面。

## 交付清单

- ARCH 体系：`server/web/data/arch/`（schema/cluster/5 项目/index）
- 看板改造：`roadmapPage.js` 图库导航 + `server.py /board/arch` + shell.css 样式
- 生成器：`scripts/gen_arch.py`（ARCH → Archify HTML，运行时取 HP 参考库）
- 产物：6 张 HTML（cluster/ccc/qb/medio-0/quanthive/qxmap，4 showcase + 2 standard）
- 版本：`arch_version=1.0.0`；CHANGELOG/VERSION = v0.71.0

## 后续（P3/P4 挂账）

- 出卡/机审 SOP 挂钩「架构变更→更新 ARCH→重生成」（落地到流程文档）
- cluster/qxmap 两张 standard 图优化到 showcase
- P4 实时状态注入（看板五态叠加到图上）
- 其余项目图随开发逐步补齐
