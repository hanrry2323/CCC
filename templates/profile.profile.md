# <项目简称> — 项目简介

> 供 `<项目简称>-CC` agent 读取，避免每次重复解释项目背景。
>
> 启动顺序：先读 `~/program/CCC/CLAUDE.md`（流程），再读本文件（项目）。

---

## 基本信息

| 项 | 值 |
|----|----|
| 项目路径 | `~/program/<项目>` |
| Agent | `<项目简称>-CC` |
| 主要语言 | [如 Python / TypeScript / Go] |
| 主要框架 | [如 FastAPI + React] |
| 数据库 | [如 PostgreSQL / SQLite] |
| 部署方式 | [如 Docker / launchd / k8s] |

---

## 技术栈

[详细列出关键技术组件，每项 1 行]

- **后端**：[框架、端口、入口]
- **前端**：[框架、端口、构建工具]
- **DB**：[类型、连接串、迁移工具]
- **守护/部署**：[launchd plist 路径 / cron 任务 / CI 流程]
- **AI/LLM**：[API 中转、模型名]

---

## 目录结构

```
[项目根]/
├── [顶层目录]         [一句话说明]
│   └── [子目录]        [一句话说明]
├── [顶层目录]         [一句话说明]
└── .ccc/              CCC 工作目录（plan/phases/report/verdict）
```

---

## 命名/编码/提交规范

| 项 | 规范 |
|----|------|
| 文件命名 | [snake_case / kebab-case / PascalCase] |
| 行宽 | [PEP 8 / 100 / 120] |
| Lint | [ruff / eslint / ...] |
| Test | [pytest / jest / ...] |
| Commit | [Conventional Commits / 自定义] |
| 分支 | [main / develop / ...] |

---

## 路由/模块惯例

[如果项目是 API/微服务，描述路由注册、模块拆分、tag 命名等惯例]

例：
- `app/api/__init__.py` 中所有 router 通过 `include_router(xxx, tags=["xxx"])` 注册
- tag 用小写模块名

---

## 架构原则（项目级红线）

- ❌ [不允许的事 1]
- ❌ [不允许的事 2]
- ✅ [强制要求 1]
- ✅ [强制要求 2]

---

## 关键指标（可选）

| 指标 | 数值 |
|------|:----:|
| [API 路由数] | [N] |
| [测试通过率] | [N/N] |
| [LOC] | [~Nk] |

---

## .ccc 目录说明

| 路径 | 用途 |
|------|------|
| `.ccc/profile.md` | 本文件 — 项目简介 |
| `.ccc/plans/` | plan 文件 |
| `.ccc/phases/` | 阶段进度 JSON |
| `.ccc/reports/` | 实施报告 |
| `.ccc/verdicts/` | 验收结论 |

---

## 已知陷阱 / Lessons（项目级）

- [历史踩过的坑 1]
- [历史踩过的坑 2]

---

> **维护**：项目结构或规范有变化时，同步更新本文件。所有 `<项目简称>-CC` agent 都基于本文件工作。