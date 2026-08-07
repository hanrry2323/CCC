# ARCH 体系 — 集群架构图数据规范（v1.0）

> 2026-08-08 决议（OpenCode）· 线路图页面升级为集群全景架构图。
> 关联：`docs/notes/m9-arch-roadmap-plan.md` · `VERSION` · 看板 `#/roadmap`。

## 一、目录结构

```
server/web/data/arch/
├── ARCH-SCHEMA.md        本规范
├── index.json            图库索引（项目/版本/状态/更新时间/产物路径）
├── cluster.json          集群全景 ARCH（所有项目 + 机器 + 服务 + 跨项目关联）
└── <project>.json        每项目 ARCH
server/web/legacy-chat/arch/<project>-arch.html   Archify 生成产物（静态托管）
```

## 二、每项目 ARCH（`<project>.json`）

```json
{
  "arch_version": "1.0.0",
  "project": "ccc",
  "status": "active",
  "owner": "OpenCode / 产线 Agent",
  "updated_at": "2026-08-08",
  "title": "CCC 自动化开发集群",
  "components": [
    {"id": "m1-oc", "type": "backend", "label": "M1 中枢"}
  ],
  "connections": [
    {"from": "m1-oc", "to": "github", "label": "出卡 push"}
  ]
}
```

- `arch_version`：SemVer，架构变更才 bump（图内容演进版本，独立于 CCC 仓版本）
- `status`：`active` / `frozen` / `retired`（老板口头定夺，OpenCode 标注）
- `components` / `connections` 复用 Archify architecture schema 子集（见参考库 `agent-ecosystem/archify/schemas/`）

## 三、集群全景 ARCH（`cluster.json`）

在每项目结构上增加：
- `projects`：项目级概览（id/status/关联）
- `relations`：跨项目关联线，枚举类型：
  | type | 含义 |
  |------|------|
  | `in-ccc` | 已纳入 CCC 产线（qb / medio-0） |
  | `independent` | 独立轨道（QuantHive，禁 qh 出卡） |
  | `infra` | 基础设施依赖（中继 6100/6102、HP 知识库、GitHub SSH、SMB） |
  | `dataflow` | 数据/知识流（教训回流、冷备份） |
  | `deploy` | 部署关系（HK → QuantHive） |

## 四、图库索引（`index.json`）

```json
{
  "version": 1,
  "updated_at": "2026-08-08",
  "gallery": [
    {"project": "cluster", "title": "集群全景", "arch_version": "1.0.0",
     "status": "active", "html": "/arch/cluster-arch.html"}
  ]
}
```

## 五、维护机制

- **全景图 + 跨项目关联**：OpenCode 维护（架构变更即更新 `cluster.json`）
- **每项目图**：产线 Agent 维护本项目 ARCH；出卡/验收 SOP 挂钩「架构变更 → 更新 ARCH → 跑 `scripts/gen_arch.sh` 重生成」
- **生成**：`scripts/gen_arch.sh`（ARCH → archify.mjs deliver → 更新 index + HTML）
- **版本**：ARCH `arch_version` 变更需在 CHANGELOG 记一笔；提交随 CCC 仓

## 六、验收

- `#/roadmap` 页展示全景图 + 项目列表，每项目图可展开（iframe）
- 首批 5 项目 + 全景 ARCH 齐全，版本号可见
- `gen_arch.sh` 一键重生成通过
