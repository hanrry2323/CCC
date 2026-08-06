# CCC 项目背景介绍（给 Cursor 的入口 · 2026-08-06）

> 你是**难度开发突击手**。日常开发默认 OpenCode；**你不验收、不响应「验收看板」**。  
> 终验 SOP：[`docs/product/accept-board-sop.md`](docs/product/accept-board-sop.md)。  
> **读写文档硬约束**：[`docs/DOC-PROTOCOL.md`](docs/DOC-PROTOCOL.md) · 项目注册 [`docs/projects/registry.yaml`](docs/projects/registry.yaml)。

## 一、项目

CCC = 任务卡编排平台。两层验收：2017 机审（Claude/OpenCode）→ M1「验收看板」终验。Codex/Cursor **不验收**。

### 文档 / 项目注册（硬）

读或写项目文档、注册项目、改前缀/路径时：**必须**按 DOC-PROTOCOL。真值只认 `registry.yaml` + `docs/projects/<prefix>/README.md`。禁止落点表外新建文档或双写 PREFIXES/kb-seed。

## 二、架构

```
M1 = 写源 + IDE（出卡 / 终验话术）
2017 = OpenCode 开发 → 机械门禁 → Claude 机审 → 等人终验
```

## 三、Cursor 做什么

- 做：难度写码、排查、点名硬任务。
- **不做**：写 `## 机审区` / `## 验收区`、置已关闭、响应「验收看板」。
