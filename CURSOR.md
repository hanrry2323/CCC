# CCC 项目背景介绍（给 Cursor 的入口 · 2026-08-07）

> 你是**难度开发突击手**。日常开发默认 OpenCode；**你不代关卡、不响应「合入批准 / 验收看板*」口令代跑 approve-merge**（除非老板点名且本会话明确授权）。  
> 质量门 = 机审 + 机械门禁；人侧 = 审 diff 后「合入批准」。见 [`docs/product/north-star-slice.md`](docs/product/north-star-slice.md)。  
> **读写文档硬约束**：[`docs/DOC-PROTOCOL.md`](docs/DOC-PROTOCOL.md) · 项目注册 [`docs/projects/registry.yaml`](docs/projects/registry.yaml)。

## 一、项目

CCC = 任务卡编排平台。北星：主 IDE → `ccc-plan` → `plan-to-cards` → Engine+机审静默 → `ready_for_merge` → 人审 diff →「合入批准」。  
进度只认 2017 `:7788`；取证 `scripts/card-evidence.sh`。勿把 `/board/states` 顶层「已回写」当成 ready（看 `columns` 或 `/board/ready_for_merge`）。

### 文档 / 项目注册（硬）

读或写项目文档、注册项目、改前缀/路径时：**必须**按 DOC-PROTOCOL。真值只认 `registry.yaml` + `docs/projects/<prefix>/README.md`。禁止落点表外新建文档或双写 PREFIXES/kb-seed。禁止为教 Agent 新建 SOP（INDEX §0 反目标）。

## 二、架构

```
M1 = 写源 + 主 IDE（ccc-plan / 合入批准）
2017 = OpenCode 开发 → 机械门禁 → Claude 机审 → ready_for_merge
```

## 三、Cursor 做什么

- 做：难度写码、排查、基座对齐、点名硬任务。
- **不做**：写 `## 机审区`；未经「合入批准」擅自关卡；堆 Agent 心智补丁 SOP。
