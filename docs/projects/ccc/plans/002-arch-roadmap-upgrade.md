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

---

## 附录：原始决策全文（2026-08-08 保留原文，合并不丢内容）

# 决策：线路图升级为集群全景架构图（ARCH 体系）· 2026-08-08

> 类型：功能 + 基建 · 决策人：老板 · 记录/执行：OpenCode · 日期：2026-08-08
> 关联：CCC `docs/notes/m9-arch-roadmap-plan.md` · CCC `CHANGELOG v0.71.0` · 参考库 `agent-ecosystem/archify`

## 一、背景

- CCC 看板 `#/roadmap` 线路图页原为任务卡状态统计（六桶计数，`/board/roadmap`），无架构表达，价值低。
- 需求：升级为**集群全景架构图**——所有项目（含关联/不关联）一图尽收，每项目一张自己的图；
  开发中由 OpenCode + 产线 Agent 持续维护，成为老板 ↔ Agent 的**双向沟通界面**。

## 二、结论

- 落地 **ARCH 体系 v1.0**：每项目 `ARCH.json` + 集群 `cluster.json` + 图库 `index.json`；
  看板线路图页改造为「架构图库」；Archify 生成高质感 HTML；版本号随 CCC 仓提交发布。
- 三个决策点（老板批准按推荐）：ARCH 集中放 CCC 仓；先静态图后动态叠加；每项目图 3-8 组件精简粒度。

## 三、架构设计

1. **ARCH 数据层**（`server/web/data/arch/`）：组件/边界/关联/状态 + `arch_version`（SemVer 独立演进）。
   关联类型：`in-ccc`（纳入产线）/`independent`（独立轨道）/`infra`（基础设施依赖）/`dataflow`/`deploy`。
2. **渲染两段式**：Archify 静态主图（self-contained HTML，iframe 展示）+ 看板实时状态叠加（P4 可选）。
3. **维护机制**：OpenCode 维护全景+关联+规范；产线 Agent 维护项目 ARCH；出卡/验收 SOP 挂钩「架构变更→更新 ARCH→跑 gen_arch.py 重生成」。

## 四、版本号规则

- **提交/发布随 CCC 仓**：代码/ARCH/HTML 产物全进 CCC 仓，随 CHANGELOG+VERSION（`v0.71.0`）。
- **图独立语义版本**：`arch_version` 存 ARCH+index，架构变更才 bump——CCC 版本管提交，图版本管内容演进。

## 五、文件规划

```
server/web/data/arch/ARCH-SCHEMA.md   规范 + 维护机制
server/web/data/arch/index.json      图库索引
server/web/data/arch/cluster.json    集群全景
server/web/data/arch/<project>.json  每项目 ARCH（5 个首批）
server/web/legacy-chat/arch/*.html   Archify 产物（静态托管）
server/web/js/pages/roadmapPage.js   改造（图库导航）
server/web/server.py                 GET /board/arch
scripts/gen_arch.py                  一键生成
```

## 六、落地结果（v0.71.0 已交付）

- 6 张图生成成功：cluster/ccc/qb/medio-0/quanthive/qxmap（4 showcase + 2 standard，standard 后续可优化）。
- `/board/arch` 端点 + 前端图库页 + 静态托管均验证通过（HTTP 200）。
- Archify 运行时引用 HP 参考库（不 vendored），`gen_arch.py` 首次运行自动拉取。

## 七、验收标准（达成）

- [x] 线路图页展示全景图 + 项目列表可展开
- [x] 首批 5 项目 + 全景 ARCH 齐全、arch_version 可见
- [x] gen_arch.py 一键重生成通过
- [x] CHANGELOG/VERSION 更新至 v0.71.0

## 八、风险与边界

- 图过期风险 → SOP 挂钩 + arch_version 倒逼（P3 后续落地到出卡/机审 SOP）。
- Archify 依赖 HP 参考库 → gen_arch.py 固定路径 + 文档说明。
- standard 档两张图（cluster/qxmap）后续可手工调 pos 提升 showcase。

## 九、参考

- Archify：`reference/agent-ecosystem/archify/`（HP）· 决策：`OpenCode接管日常主力与QuantHive主导-2026-08-08.md`
