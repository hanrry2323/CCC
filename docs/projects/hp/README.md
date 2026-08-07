# hp / 知识库（前缀 hp）

## 是什么

HP 个人 AI agent 中央知识库基础设施 + 教训沉淀平台。

## 路径

| 机 | 路径 |
|----|------|
| M1 | 无（仅开发预览 UI 及 CCC 任务卡） |
| Mac2017 | `/Users/fan/program/apps/hp`（SSOT 权威路径） |

## 在 CCC 怎么动

- **前缀**：`hp`（UI 名常为「hp 服务仓」；display「知识库」）→ `docs/dispatch/hp/`
- **taskable**：是
- **出卡**：`scripts/new-card.sh --project hp --title "..."`

## 线路 / 近况

- 已完成 Phase 0-3（基线/复验/collector重建/K23补档），当前重点转向监控与备份。
- 下一程意向：推进 hp 仓监控盲区修复（每日 git 状态/探活入 qx-map）与数据备份对齐。

## 禁区

- 绝对禁止在 M1 本地修改、添加、删除任何业务仓 `/Users/fan/program/apps/hp` 的代码文件，必须通过 Desktop transfer → Engine 派发执行。
- 绝对禁止在 CCC 仓新建业务深文档目录（如 `docs/projects/hp/xxx.md` 业务详文），业务/知识深文应留在 hp 仓或知识库产品侧。
- 端口与路径权威一律以 qx-map `cluster/path-authority.md` 为准，禁止在 CCC 仓复制或维护端口表副本，防双源漂移。

---

## 附 A 技术栈表

| 层次/组件 | 技术栈 | 描述 / 备注 |
|-----------|--------|-------------|
| 核心语言 | Python / TypeScript / Bash | Python 后端，TS Dashboard 前端，Bash verify 脚本 |
| 运行时服务 | BaseHTTPRequestHandler / pnpm dev | `memory-store` (:8082), `Dashboard API` (:8089), `SPA Server` (:8090) |
| 数据库存储 | PostgreSQL 18.0 + pgvector | 存储 documents 元数据 (3,533 行)、chunks (74,151 行)、memory_store (2,839 行) |
| 嵌入/LLM | Ollama (bge-m3:q4 / phi3 / qwen2.5) | 实际向量维度 1024 (bge-m3:q4 / latest)，提供本地嵌入与检索推理 |
| 契约与测试 | pytest / static verify | `tests/server` 对 Dashboard 端点 TDD，21 行纯 Bash 对 KB 静态自检 |
| 数据同步 | com.hp-kb.collector.plist | `auto-collect` 多项目 watcher 配置与 collector 守护进程，本地 scripts/ SSH 互通 |

## 附 B 目录树（深度 3）

```
hp/ (git tracked files at top-level)
├── .ccc/                 # CCC decided.json brain sync (git tracked)
├── .harness/             # Mavis agent configuration
├── docs/                 # Documentation, lessons and archives
│   ├── _archive/         # hp_scripts B-line draft (paused)
│   ├── _archive_2026-06-23/  # One-time fast snapshot archive
│   ├── audit/            # Phase 0 Baseline Report 2026-08-03
│   ├── knowledgebase/    # In-depth research papers & VERIFY.md
│   │   ├── research/     # Survey papers
│   ├── postmortems/      # Retrospectives and incident analysis
│   ├── dev-plan.md       # Development plan & SSOT
│   └── lessons.md        # Lessons learned (DATE | TASK | FAILURE | FIX)
├── scripts/              # Shared scripts and QA validation
│   ├── qa/               # Quality assurance verification
│   └── kb_entry_guard.py # Knowledgebase entry guard CLI
├── tests/                # Dashboard API & embedding unit/E2E tests
│   └── server/           # Dashboard backend testing (pytest)
├── README.md             # Project overview
├── AGENTS.md             # Workspace setup instructions
├── CLAUDE.md             # Developer guidelines
├── VERSION               # Current repo version (v0.1.2)
├── CHANGELOG.md          # Release logs
└── daily-summary.py      # Local summary generator
```

*注：运行时代码 `local/`（含 `auto-collect/`, `pipeline/`, `memory-store/`, `memory-bridge/`, `graph/`, `cluster/`, `scripts/`）按设计 untracked，部署在 hp@hp 节点上。*

## 附 C 业务线路梳理

| 阶段 / 模块 | 现状与核心产出 | 下一步规划 / 意向 |
|-------------|----------------|-------------------|
| **Phase 0 摸底与基线** | 2026-08-03 摸底基线已产出，发现 K23 未交付、Collector 停摆、文档漂移。 | 已收口，作为后续里程碑对照基准。 |
| **Phase 1 修复与对齐** | 2026-08-07 复验完成，清除根目录草稿双轨，修复路径与端口漂移，文档自检对齐。 | 已收口。 |
| **Phase 2 采集器重建** | 完成。通过 `kb-collect.py` 与 launchd `com.hp-kb.collector.plist` 重建 collector 守护，恢复数据管道。 | 持续监控采集稳定性与资源占用。 |
| **Phase 3 K23 元数据交付** | 完成。`heading_path`, `domain`, `project`, `node_type` 四列补档完成，重写 md_parser 并在前端增加 Quality 与 Search。 | 持续核算短 chunk 占比 (<15% 目标)。 |
| **Phase 4 监控盲区修复** | 待启动。当前 `daily-sync` 不含 hp git 状态，缺乏探活。 | 将 hp git state 接入 daily-sync，实现统一端口探活。 |
| **Phase 5 备份对齐** | 待启动。当前冷热与异地备份机制尚未对齐规范。 | 梳理备份策略，规范化 psql 异地备份与恢复机制。 |
