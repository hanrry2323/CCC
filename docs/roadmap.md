# CCC 发展路线图

> **当前状态(2026-07-09)**:
> - **v0.21 阶段**(门控修补):已发布,`v0.21.0`
> - **v0.22 阶段**(audit 角色):已发布,`v0.22.1`
> - **v0.23 阶段**(product 上游智能化):**已发布**,`v0.23.0` + `v0.23.1`
> - **v0.24 阶段**(Engine phase 感知调度):**已规划暂不实施**
> - **v0.25 阶段**(全链路对齐):**已规划暂不实施**
> - **v0.26 阶段**(CCC Board Protocol / 跨 IDE 开放协议):**已规划暂不实施**
> - **当前最新版本**:v0.23.1
>
> **范式转变**:
> 1. **v0.11**: "opencode 写 + 人工 review" 模式 (Lesson 35)
> 2. **v0.12**: bug 扫描 → 必修 → 复查 → 沉淀 4 步标准化 (Lesson 36)
> 3. **v0.15**: 真自动化开发 (opencode 写代码 + post-exec 自动 commit+push)
> 4. **v0.16**: **7 角色 + 任务看板** — 任务在 6 列流转, 7 launchd plist 周期跑
> 5. **v0.17**: **战略地图** — 任何 cloud agent 启动必读第一份文件
> 6. **v0.18**: **7 角色文档对齐 + 架构审查** — regress 角色正式加入, 全文档 6→7 角色更新; 修复 9 个架构问题
> 7. **v0.19**: **基础加固 + 扩展通路** — BoardStore/Executor/Config 三抽提取, 消除 board-server.py 代码重复, E2E 集成测试, 定义 task 文件格式共享契约
> 8. **v0.20.1**: **串行执行引擎** — 取消 7 角色定时轮询，改为单一 Engine 常驻进程，有 task 即串行执行全链路
> 9. **v0.23**: **product 上游智能化** — product 角色读代码结构再写 plan，提升 plan 质量减少下游返工

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

## v0.20.0 — Dev 体验 + 运维完备

> 见 `CHANGELOG.md` 完整条目。
>
> 新增 ops 扩展、E2E 覆盖、6 项对抗性审查修复。

## v0.20.1 — 串行执行引擎（开发中）

> **定位**: 取消 7 角色 launchd 定时轮询，替换为单一 `ccc-engine.py` 常驻守护进程串行驱动 task 全链路。
>
> **决策背景**: 老板明确指示"有任务就直接串行执行，不要定时"。
>
> **架构变更**:
> - 14 plist（CCC 7 + qxo 7） → 每 workspace 1 个 engine plist
> - 定时轮询 → 有 task 立即执行，无 task 休眠 5s
> - 7 独立进程各扫各的 → 单一 while 循环串行编排
>
> **新增文件**:
> - `scripts/ccc-engine.py` — 引擎主循环（~280 行）
> - `scripts/ccc-engine.sh` — engine launchd 入口
> - `scripts/uninstall-ccc-roles.sh` — 卸载旧角色 plist
>
> **修改文件**:
> - `scripts/_config.py` — 加 engine_poll_interval / engine_idle_sleep
> - `scripts/ccc-board.py` — 加 dev_role_launch / dev_role_check_complete
> - `scripts/install-ccc-roles.sh` — 只装 engine + board-server
> - `references/red-lines.md` — X5/X6 更新
>
> **删除文件**:
> - `scripts/roles/*.sh`（7 文件，保留目录）
>
> **验证**:
> - pytest 49 全通过
> - engine 启动 → 检测 planned task → 走完 dev→reviewer→tester→kb 全链路

---

## v0.23 — product 上游智能化（v0.23.0-dev）

> **定位**: product 角色不再盲写 plan——先读代码结构，再写 SPEC-合规的 plan。
>
> **版本依赖**: 不依赖 v0.24，可独立发版。v0.24 依赖本版本。

### 改动
- 新增 `_get_code_context()` 函数：动态获取代码文件树 + git 日志 + 入口文件
- `_call_claude_for_plan` prompt 注入代码上下文（<3KB）
- plan 模板强制写 `## 当前代码状态` 段
- product SKILL.md 更新：启动后第一步读代码

### 不做的
- engine 不改（phase 感知调度留给 v0.24）
- 不引入新角色
- 不改变 dev/reviewer/tester 行为

### 验证
- compile 无语法错误
- product 角色实际产出 plan 含代码上下文分析

---

## v0.24 — Engine phase 感知调度（已规划，暂不实施）

> **定位**: Engine 从"平铺串行 task"改为"按 phase 依赖串行"。
>
> **决策**: 当前任务量级小（3-5 task），好的 plan 本身足够应对混乱。
> 等出现"20+ task 版本级任务、大量依赖编排"场景时再做。
>
> **依赖**: 依赖 v0.23（engine 读的 phases 标记由 product 产出）

### 改动范围
- engine 主循环增加 phase 感知：读 phases.json → 按 phase 边界分组
- 依赖解析：phase 标注 `depends_on: [phase_id]` → 前 phase 未完成不启动
- 失败隔离：quarantine task → 同 phase 还有 task 则继续；无则标记 phase failed → 跳过依赖它的 phase

---

## v0.25 — 全链路对齐（已规划，暂不实施）

> **定位**: 文档 + 测试 + 7 角色 SKILL 全面同步到新架构。
>
> **依赖**: v0.23 + v0.24

### 改动范围
- STRATEGY-MAP.md / roadmap.md / CLAUDE.md 更新
- 端到端测试：backlog → product → engine phase 调度 → dev → 验收
- 7 角色 SKILL.md 同步刷新

---

## v0.26 — CCC Board Protocol / 跨 IDE 开放协议（已规划，暂不实施）

> **定位**: CCC 从"框架"变成"协议标准"。任意 IDE 工具（Trae/Cursor/Zed/VS Code/OpenCode）
> 读协议文档 → 写标准 JSONL → 看板全自动流转。CCC 成为任务编排内核，不绑定执行环境。
>
> **决策背景**: 老板希望多工具混合使用（远程临时需求、小任务用方便 IDE、agent 混用写方案
> 和执行、IDE 自动化定时扩展如纠错/定时管理等）。
>
> **依赖**: v0.23 + v0.24 + v0.25

### Agent ↔ 看板列映射（协议核心）

Protocol v1 的核心契约是：**每种 agent 只从一个列取任务，写入另一个列**。

```
IDE / 任何工具 → [backlog]   ← 我写 JSONL
                    ↓
Claude CLI (product) → [planned]   ← 写 plan + phases
                    ↓
OpenCode CLI (dev) → [in_progress]   ← 执行代码
                    ↓
                    [testing]   ← reviewer + tester 验收
                    ↓
                    [verified]
                    ↓
                    [released]   ← kb 归档
```

每步由不同的 CLI/agent 执行，看板列精确反映当前在哪个阶段。

### 改动范围

| # | 要做的事 | 工作量 |
|---|---------|--------|
| 1 | `board-task-schema.md` 重写为"CCC Board Protocol v1"（含 agent 列映射表 + 校验规则 + 多语言示例） | 小 |
| 2 | `validate_task_jsonl()` 函数，写 task 时自动校验列迁移合法性 | 小 |
| 3 | dev_role 集成 worktree 隔离（每个 task 独立 worktree 执行） | 中 |
| 4 | 正向 error feedback（IDE 写 task 失败时有明确反馈） | 中 |

### 设计原则

- CCC 保持**单节点任务编排内核**，不做多用户/权限/Web UI
- 协议级别 = 只要读 `board-task-schema.md` 就能写出合格的 task
- 不做耦合（不要求 IDE 装 plugin，不要求 agent 改行为）
- 扩展靠 IDE 侧的自动化能力（定时器、纠错脚本、事件触发）

### 颜色分层（v0.26.1）

Protocol v1 新增字段 `color_group` + `color_depth`，实现看板任务颜色分层：

```
大任务 A（color_group: "A", color_depth: 0）→ 蓝色深
  ├── A1（color_group: "A", color_depth: 1）→ 蓝色浅
  ├── A2（color_group: "A", color_depth: 1）→ 蓝色浅
大任务 B（color_group: "B", color_depth: 0）→ 绿色深
  ├── B1（color_group: "B", color_depth: 1）→ 绿色浅
  ├── B2（color_group: "B", color_depth: 1）→ 绿色浅
```

- `color_group`：分配色组（A/B/C…），同一组共享色相
- `color_depth`：层级深度（0=父任务深色，1=子任务浅色，以此类推）
- product 角色拆解时自动赋值：父任务 group 继承，depth+1
- 看板渲染根据 group 算 HSL 色相，depth 算亮度

好处：几十个 task 在板上一眼看出"这些是一个版本"、"这些是另一个版本"。

### 使用场景

```
Trae agent           → 写 task.jsonl → backlog → CCC 全自动走完
Cursor agent         → 写 task.jsonl → backlog → CCC 全自动走完
OpenCode 定时脚本    → 写纠错 task  → backlog → CCC 走 review 流程
远程零时需求（手机） → GitHub 写 issue → 同步脚本 → backlog
```

---

## v1.0 — 跨设备集群 Agent 军团（最终目标）

> CCC v1.0 = 完整的轻量自动化: 单节点可靠, 扩展通路清晰, 可嵌入任意项目。

### 核心架构（3 层）

```
┌──────────────────────────────────────┐
│  CCC Engine (串行编排)               │  ← L3: 业务编排层
├──────────────────────────────────────┤
│  7 角色函数 (ccc-board.py)          │  ← L2b: 角色逻辑层
├──────────────────────────────────────┤
│  BoardStore / Executor / Config      │  ← L2a: 抽象接口层
├──────────────────────────────────────┤
│  FileBoardStore / OpenCodeExecutor   │  ← L1: 当前实现层（可替换）
└──────────────────────────────────────┘
```

### v1.0 验收

- 单节点 Engine 流水线稳定运行 7 天无异常
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
