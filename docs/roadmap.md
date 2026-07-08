# CCC 发展路线图

> **当前状态(2026-07-08)**:
> - **v0.18 阶段**(7 角色文档对齐 + 架构审查修复):已完结,`v0.18.0`
> - **v0.19 阶段**(基础加固 + 扩展通路):**开发中**
> - **v0.20+** (文档标准化 + 执行器接口):规划中
> - **当前最新版本**:v0.19.0-dev
>
> **范式转变**:
> 1. **v0.11**: "opencode 写 + 人工 review" 模式 (Lesson 35)
> 2. **v0.12**: bug 扫描 → 必修 → 复查 → 沉淀 4 步标准化 (Lesson 36)
> 3. **v0.15**: 真自动化开发 (opencode 写代码 + post-exec 自动 commit+push)
> 4. **v0.16**: **7 角色 + 任务看板** — 任务在 6 列流转, 7 launchd plist 周期跑
> 5. **v0.17**: **战略地图** — 任何 cloud agent 启动必读第一份文件
> 6. **v0.18**: **7 角色文档对齐 + 架构审查** — regress 角色正式加入, 全文档 6→7 角色更新; 修复 9 个架构问题
> 7. **v0.19**: **基础加固 + 扩展通路** — BoardStore/Executor/Config 三抽提取, 消除 board-server.py 代码重复, E2E 集成测试, 定义 task 文件格式共享契约

---

## v0.19 — 基础加固 + 扩展通路

> **定位**: 不增加功能,只增加结构。把 CCC 从"能跑"变成"扩展有通路"。

### 核心目标

1. **存储层提取**: `board.py` 的 `.jsonl` 操作独立成 `FileBoardStore` 类, `board-server.py` 消除重复代码。铺好未来换数据库的路。
2. **集中配置**: 散布在 6 个脚本里的硬编码参数集中到 `Config` 对象。
3. **执行器提取**: `dev_role()` 里的 Popen 调用提取成 `OpenCodeExecutor` 类。铺好未来换执行器的路。
4. **基础加固**: launcher 重试、日志轮转、phases.json schema 版本。
5. **E2E 测试**: 不再只有单元测试, 有一条完整的流水线集成测试。
6. **文件格式文档**: 定义 task JSONL 格式标准, 作为 CCC-QXO 共享契约的起点。

### 不做的

| 功能 | 理由 |
|------|------|
| 数据库实现 | 抽象铺好了, 等需求明确再切 |
| 容器化执行器 | 同上 |
| 事件驱动(消息队列) | 够不着, 等需要"实时触发"时再考虑 |
| SKILL.md 标准化 frontmatter | scope 已够, 建议 v0.20 单独做 |

### 交付物

| 类型 | 数量 |
|------|------|
| 新文件 | 5 (BoardStore / Config / Executor / E2E / 格式文档) |
| 改文件 | 7 |
| 净新增行 | ~275 行 (core 4 文件 2282 行 → ~2557 行, +12%) |

### 验证

`pytest tests/ -q` 全绿 + `bash tests/e2e/test_pipeline_smoke.sh` exit 0。

详细开发方案见 `~/program/CCC/.claude/plans/ccc-v019-upgrade-plan.md`。

---

## v0.20 (规划) — 文档标准化 + 执行器接口

> 待定, 初步方向:
> - SKILL.md 添加标准化 YAML frontmatter (version / model / gates / frequency)
> - Executor 接口完善 + 测试
> - 看板 UI 对接 API (纯前端, 不改后端)

---

## v1.0 — 跨设备集群 Agent 军团（最终目标）

> CCC v1.0 = 完整的轻量自动化: 单节点可靠, 扩展通路清晰, 可嵌入任意项目。

### 核心架构（3 层）

```
┌──────────────────────────────────────┐
│  7 角色 + 看板 (product/dev/...)     │  ← L3: 业务逻辑层
├──────────────────────────────────────┤
│  BoardStore / Executor / Config      │  ← L2: 抽象接口层
├──────────────────────────────────────┤
│  FileBoardStore / OpenCodeExecutor   │  ← L1: 当前实现层（可替换）
└──────────────────────────────────────┘
```

### v1.0 验收

- 单节点 7 角色流水线稳定运行 7 天无异常
- `BoardStore` / `Executor` 抽象层经过至少 1 个替换实现验证
- E2E 集成测试覆盖完整流水线
- task 文件格式文档稳定, QXO 可读写

> v1.0 明确做轻量版本, 不做分布式。集群调度是 v2.0 的事。

---

## 历史存档

### v0.5 – v0.15 演进轨迹

| 版本 | 关键产出 |
|------|----------|
| v0.5–v0.7 | 4 文件契约 + 3 角色流水线、13 红线 |
| v0.8 | OpenCode CLI 切换 + 进程管理红线 X1/X2/X3 |
| v0.9 | model provider 修复, loop/flash 中转站 |
| v0.10 | 飞轮 + 队列简化, 失败模式扫描 |
| v0.11 | 开箱即用调度, 3 钩子模板 + install-ccc-scheduler |
| v0.12 | bug fix sweep, 3 类 bug 修复模式 |
| v0.13 | 跨项目支持 qx-observer 接入 |
| v0.14 | 真正落地, 35 commit push + scheduler 装 |
| v0.15 | 真自动化开发, ccc-auto-dev + post-exec 自动 commit+push |
| v0.16 | **7 角色 + 任务看板** — 6 列流转, 7 launchd plist |
| v0.17 | **战略地图** — agent 启动必读 |
| v0.18 | **7 角色文档对齐 + 架构审查修复** |

### v0.5.0 重构关键设计决策

| 项 | 决策 | 理由 |
|---|------|------|
| CCC 形态 | SKILL 资产 | 不挑 IDE, 可移植 |
| 7 角色 | product/dev/reviewer/tester/ops/kb/regress | 工程全流程覆盖 |
| 工作目录 | 由 agent 当前目录决定 | 不绑死 IDE / 项目 |
| 模型选择 | `loop/flash` 唯一对外名 | 中转站路由 |
| CCC 启用 | 用户显式触发 | 红线 12 |
| 与 QXO 关系 | **独立发展** | 不融合, 通过文件格式共享契约互通 |

---

## 相关文件

- `SKILL.md` — 注入 prompt
- `CLAUDE.md` — 框架总纲
- `references/red-lines.md` — 12+X6 红线
- `references/board-task-schema.md` — task JSONL 格式标准（v0.19 新增）
- `docs/architecture.md` — 框架说明书
- `docs/lessons.md` — 教训沉淀
- `CHANGELOG.md` — 版本历史
