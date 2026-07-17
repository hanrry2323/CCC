# CCC 发展路线图

> **现行叙事**：[`VISION.md`](VISION.md) · **版本**：根目录 `VERSION`  
> **下一步产品目标**：与维护者当面同步后再写入本节「当前方向」——本文底部历史段落保留作归档。

---

## 当前方向（索引）

| 已定型 | 说明 |
|--------|------|
| Hub 为入口 | 替代第三方 Agent IDE 编排壳 |
| Loop Engineer | Engine 自动编排 / 验收 / 重试 / 进化 |
| 无穷角色 | 任务路由 + Skill/Prompt；非角色超市 |
| 控制面安全默认 | `disabled` → 显式 `enable` / `invent` |

| 开源与介绍 | 说明 |
|------------|------|
| 文档口径统一 | VISION / INTRO / README / STARTUP / USAGE |
| GitHub Release | `v0.42.1` 已发 |
| 演示资产 | Walkthrough 分镜 + 视频脚本已就位；截图/成片待维护者本地补齐 |
| 竖切蓝图 | [`vertical-qx.md`](vertical-qx.md)（CCC 底座 × QX；本阶段不拆 QX 仓） |

**下一步双轨（待拍板）**：[`NEXT-DUAL-TRACK.md`](NEXT-DUAL-TRACK.md) — 用 CCC 带动 xianyu 视频质量门 + QX 全新/原地重构决策。

**未在此预先锁定的里程碑**：安装体验、传播渠道、生态 Domain Skill 等。

---

## 历史归档（v0.19–v0.26 等）

> 以下内容为既有规划原文，版本号可能落后于 `VERSION`。以 CHANGELOG 为准。

# CCC 发展路线图（历史正文）

> **归档时状态摘录(2026-07-11)**（已过时，仅史实）:
> - **v0.21–v0.26** 等阶段见正文
> - **范式转变**摘要见下

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

## v0.24 — Engine phase 感知调度（**已完成** v0.24.1+2+3+4+5+6+7）

> **状态**: 7 个 hotfix 已落地，phase 感知 + 失败传染 + advisory lock +
> fallback quarantine + retry first backoff 全部实现。代码部分完成，
> 文档/测试同步由 v0.25.0 收尾。

### 实际改动（v0.24.x 累计）
- v0.24.1 reviewer 按变更量分级（small/medium/large）
- v0.24.2 audit 多 workspace 并行化
- v0.24.3 phases.json fcntl lock + writeback reload + audit timeout + max_workers=2 + small-class diff 非空校验 + diff stat None fail-fast
- v0.24.4 move_task 原子迁移 + reconcile 工具
- v0.24.5 reviewer per-task advisory lock + medium/large fallback 强制 quarantine + L2 通知（R-04/R-12 红线）
- v0.24.6 _acquire_lock 30s 强清 + pid mtime 校验 + phases.json commit 字段 + GET /api/* token 校验
- v0.24.7 prompt 临时文件改 ~/.ccc/prompts/ + mode 0o600 + retry=0 first backoff 60s

### 已知遗留（CHANGELOG v0.24.4:93-99，5 项 P1）
- 循环依赖检测
- max_iter=5 收敛
- PHASE_TERMINAL_FAIL 进入 blocked 状态
- 依赖 phase 不存在告警
- 重试计数器按 phase 独立

> v0.25.0 已补**回归测试**（test_phase_dependencies.py:TestV025P1Backlog 5 case），
> 实际代码实现推 v0.25+ 后续版本。

---

## v0.25 — 全链路对齐（**已完成** v0.25.0）

> **状态**: 11 commit 已落地，文档 + 测试 + 7 角色 SKILL 全面同步到 v0.24.7+ 新架构。

### 11 commit 清单
| # | commit | 范围 | 估时 |
|---|--------|------|------|
| 1 | `fix(skills/reviewer)` | R-12 红线文字防线 | 35 min |
| 2 | `docs(CLAUDE.md)` | VERSION + 红线 R- + phase 感知架构图 | 35 min |
| 3 | `docs(SKILL.md)` | VERSION + Engine 触发 + 4 文件契约 + 关键资产 | 25 min |
| 4 | `docs(skills)` 6 角色 | product/dev/tester/ops/kb/regress Engine 触发 + phase 感知 | 90 min |
| 5 | `docs(red-lines)` | R-04/07/08/09/12/14 + X7 强化 | 20 min |
| 6 | `test_advisory_lock.py` | R-04 验证 | 35 min |
| 7 | `test_fallback_quarantine.py` | R-12 验证 | 35 min |
| 8 | `test_retry_backoff.py` | v0.24.7 first backoff | 30 min |
| 9a | `test_phase_dependencies` 增量 | 5 P1 遗留契约 | 50 min |
| 9b | `test_phase_end_to_end.py` | 3 phase 链式 + 失败传染 | 50 min |
| 9c | `tests/e2e/test_pipeline_phase_aware.sh` | phase 感知 bash harness | 60 min |
| 10 | `release: v0.25.0` | CHANGELOG + roadmap + VERSION | 30 min |

### 验收
- `python3 -m pytest tests/scripts/ -q --tb=line` → 125 passed
- `bash tests/e2e/test_pipeline_phase_aware.sh` → 8 step 通过
- 11 commit 单一职责，可独立 revert

### 不在 v0.25 范围（推到 v0.26）
- Dashboard 首页（4 端点 + HTML，205min）→ v0.26 协议阶段
- STRATEGY-MAP.md 深度重写 → v0.26
- 5 项 P1 遗留的代码实现 → v0.25+ 后续

### 改动范围
- STRATEGY-MAP.md / roadmap.md / CLAUDE.md 更新
- 端到端测试：backlog → product → engine phase 调度 → dev → 验收
- 7 角色 SKILL.md 同步刷新

---

## v0.26 — CCC Board Protocol / 跨 IDE 开放协议（**已完成** v0.26.0）

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

## v0.30 — CCC Cockpit（总控台）

> **定位**: CCC Cockpit 是统一的管理入口，把所有项目/机器/服务/端口的状态和操作汇集到一个页面。
> 当前版本: `v0.1`（基础版 — infrastructure.md 解析 + 端口探测 + 三机分栏 + 快速跳转）

### 版本路线

```
v0.30.0  Cockpit v0.1  基础框架（已发布）
v0.30.1  Cockpit v0.2  知识库整合 + 服务告警（开发中）
v0.30.2  Cockpit v0.3  文件浏览器 + 看板集成
v0.30.3  Cockpit v0.4  终端体验 + UI 美化
v0.30.4  Cockpit v0.5  多 CLI 引擎 + 日志面板
v0.31.0  Cockpit Desktop  Tauri 桌面端
```

### 参考项目

Cockpit 功能设计参考了以下开源项目：

| 项目 | 星数 | 借鉴点 |
|------|------|--------|
| [claudecodeui](https://github.com/siteboon/claudecodeui) | 12,600 | 文件浏览器、终端 UI、多 CLI 引擎 |
| [cdesktop](https://github.com/cdesktop-ai/cdesktop) | 57 | Tauri 桌面端包装 |
| [CodeConductor](https://github.com/zhu1090093659/CodeConductor) | 80 | 桌面+Web 双模式 |
| [EndlessClaude](https://github.com/usualdork/EndlessClaude) | 76 | Discord 风格聊天 UI |

### v0.30.1 — 知识库整合 + 服务告警（开发中）

- 接入 HP 知识库页面（已有接口 `:8082/memories`）
- 服务离线时 Cockpit 标红 + Cockpit 页面显示告警
- 添加各项目关键指标（qb 交易状态、medio-0 封面生成数等）

### v0.30.2 — 文件浏览器 + 看板集成

- **文件浏览器**（参考 claudecodeui）：执行模式页面嵌入项目文件树，可浏览/查看代码
- **看板集成**：Cockpit 内嵌入 CCC 看板数据（从 board-server :7777 拉取）
- 可直接在 Cockpit 查看各列任务数
- 点击项目跳转到对应 Dashboard

### v0.30.3 — 终端体验 + UI 美化

- **终端体验**（参考 claudecodeui）：执行模式改为实时终端输出，不是纯文本 SSE
- 显示命令执行过程的 diff 和文件变更
- **UI 美化**：页面视觉统一（整洁卡片布局，响应式适配手机平板）
- 状态自动轮询（非刷新，前端定期拉 `/api/alive`）
- 移动端触摸优化

### v0.30.4 — 多 CLI 引擎 + 日志面板

- **多 CLI 支持**（参考 claudecodeui）：可切换 claude -p / opencode / cursor CLI
- **日志查看**：Cockpit 内查看各服务日志（tail -n 100）
- 一键部署按钮（调用各项目的 deploy 脚本）
- 版本历史追踪

### v0.31.0 — Cockpit Desktop（Tauri 桌面端）

- 用 Tauri 将 Chat Server 包装为 Mac 桌面应用（参考 cdesktop）
- 原生菜单、通知、托盘图标
- 离线缓存、自动启动

### 开发方式

所有 Cockpit 开发走 CCC 自动化流程：写 plan → phases → dev → reviewer。不入 CCC 主线版本号，Cockpit 独立版本号 `v0.1.x` 递增。

### 当前状态

- Cockpit v0.1 已发布，运行在 `:7778`，接入 `.ccc/infrastructure.md`
- 13 个端口已接入（M1 10 + feiniu 3）
- 6 个快速跳转链接
- 代码: `scripts/ccc-cockpit.py`

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

## 远期：跨 IDE 投递 + 远程集群 L1/L2（**非紧要 · 规划入库**）

> 写入日期：2026-07-17。  
> **当前紧要**仍是 Hub + 本机 Engine 多跑真任务（见 `docs/NEXT-DUAL-TRACK.md` §8.0）。

### 架构前提（已验证）

任意上游（Hub / Cursor / 脚本）只写 `backlog` → Engine 编排 → Executor。Hub 对话 ≠ Engine。

### 远程两层

| 层 | 定义 | 难度 |
|----|------|------|
| **L1 任务落点跨机** | 看板在哪台，流水线在哪台（SSH 写远程 backlog） | 低 |
| **L2 执行器跨机** | 看板在 M1，Claude/OpenCode 跑 mac2017 | 高（RemoteExecutor） |

**MiniMax**：自动化高峰期作**兜底**而非全局 P0（配额约 1–2h 抽干）。免费池需分流 + task sticky。

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
