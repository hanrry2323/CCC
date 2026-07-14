# .ccc/state.md — CCC 接力索引（红线 10 强制）

> **本文件是 CCC 框架跨会话接力的唯一可信输入**——**最高接力文件**（继 CLAUDE.md / SKILL.md 之后）。
> 任何 CCC 角色 session **必须第一个读本文件**（红线 10），本文件为**项目级最高接力契约**。
> 禁止依赖 session 内隐式记忆；所有历史结论必须显式 grep `.ccc/` 内文件。

---

## Agent 身份契约

> **本节是 CCC agent 每次启动必须阅读的最高接力契约**（继 CLAUDE.md / SKILL.md 之后第一读）。

- **身份**：我是 **xianyu 项目负责人**，CCC 12 条红线条约贯穿所有任务。
- **强制启动顺序**：CLAUDE.md → SKILL.md → **state.md（本文件为最高接力契约）** → profile.md。
- **流程强制**：所有任务按 CCC `plan → phases → 执行 → report → verdict` 五段流程跑完，缺一不可。
- **红线优先级**：12 条红线 + X1-X6 + R 系列均为最高约束，违反任意一条即判 fail。

---

## 项目身份

| 字段 | 值 |
|------|----|
| 项目名 | CCC (Connect–Claude Code) |
| 路径 | `/Users/apple/program/ccc` |
| 形态 | SKILL 资产 + CCC Engine 串行执行架构 |
| 主语言 | Bash + Python 3.9+（已兼容 3.14） |
| Profile 路径 | `.ccc/profile.md` |
| 本文件路径 | `.ccc/state.md` |
| Agent 身份 | xianyu 项目负责人，CCC 12 条红线贯穿 |
| 当前版本 | **v0.24.4**（2026-07-11） |

---

## 最近任务（按完成时间倒序，最多 5 条）

| 时间 | 任务 ID | 计划 | 报告 | 验收 | 状态 |
|------|---------|------|------|------|------|
| 2026-07-14 | fix-lint-2026-07-14 | `.ccc/plans/fix-lint-2026-07-14.plan.md` | `.ccc/reports/fix-lint-2026-07-14.report.md` | ruff F401/F841/F811 全清零（21+14=35 处）+ `_audit_lint` latent tuple bug 顺手修 + 248 passed | PASS |
| 2026-07-14 | writing-agent-identity-into-state-md | `.ccc/plans/writing-agent-identity-into-state-md.plan.md` | `.ccc/reports/writing-agent-identity-into-state-md.report.md` | state.md 头部加 Agent 身份契约 + 最高接力文件地位 | PASS |
| 2026-07-12 | qb-6tasks | `.ccc/plans/qb-*.plan.md` × 6 | `git diff HEAD~1 -- scripts/ccc-board.py` | 已投递 QB backlog + 修 product_role 锁 bug | DISPATCHED |
| 2026-07-12 | v0.28.1 | — | `git log a81be00` | 任务复杂度分流 + 每周总结定时 | PASS |
| 2026-07-11 | v0.24.4 | — | [CHANGELOG §v0.24.4](../CHANGELOG.md) | board zombie 修复 + reconcile 工具 | PASS |
| 2026-07-11 | v0.24.3 | — | [CHANGELOG §v0.24.3](../CHANGELOG.md) | tag `v0.24.3` + release | PASS |
| 2026-07-10 | v0.24.2 | — | [CHANGELOG §v0.24.2](../CHANGELOG.md) | tag `v0.24.2` + release | PASS |
| 2026-07-10 | v0.24.1 | — | [CHANGELOG §v0.24.1](../CHANGELOG.md) | tag `v0.24.1` + release | PASS |
| 2026-07-10 | v0.24.0 | — | [CHANGELOG §v0.24.0](../CHANGELOG.md) | tag `v0.24.0` + release | PASS |
| 2026-07-10 | v0.23.16 | — | [CHANGELOG §v0.23.16](../CHANGELOG.md) | tag `v0.23.16` + release | PASS |
| 2026-07-09 | v0.23.15 | — | [CHANGELOG §v0.23.15](../CHANGELOG.md) | tag `v0.23.15` + release | PASS |
| 2026-07-09 | v0.23.14 | — | [CHANGELOG §v0.23.14](../CHANGELOG.md) | tag `v0.23.14` + release | PASS |
| 2026-07-09 | v0.23.13 | — | [CHANGELOG §v0.23.13](../CHANGELOG.md) | tag `v0.23.13` + release | PASS |
| 2026-07-09 | v0.23.12 | — | [CHANGELOG §v0.23.12](../CHANGELOG.md) | tag `v0.23.12` + release | PASS |
| 2026-07-09 | v0.23.11 | — | [CHANGELOG §v0.23.11](../CHANGELOG.md) | tag `v0.23.11` + release | PASS |
| 2026-07-09 | v0.23.3 | — | [CHANGELOG §v0.23.3](../CHANGELOG.md) | tag `v0.23.3` + release | PASS |
| 2026-07-09 | v0.23.2 | — | [CHANGELOG §v0.23.2](../CHANGELOG.md) | tag `v0.23.2` + release | PASS |
| 2026-07-09 | v0.23.1 | — | [CHANGELOG §v0.23.1](../CHANGELOG.md) | tag `v0.23.1` + release | PASS |
| 2026-07-09 | v0.23.0 | — | [CHANGELOG §v0.23.0](../CHANGELOG.md) | tag `v0.23.0` + release | PASS |
| 2026-07-09 | v0.22.1 | — | [CHANGELOG §v0.22.1](../CHANGELOG.md) | tag `v0.22.1` + release | PASS |

> v0.19 起，版本级任务走"commit + tag + CHANGELOG"三件套，不再为每个版本单独建 plan/report/verdict 文件。
> v0.18 及之前（含 v0.18 的 7 个子任务）的 plan/report/verdict 文件保留在 `.ccc/plans/` `.ccc/reports/` `.ccc/verdicts/`。

### 当前版本族关键 commit（v0.19 ~ v0.24.3 全集）

| 版本 | 关键 commit | 主题 |
|------|------------|------|
| v0.19.0 | `981c5e1` | 基础加固 + 扩展通路（三层抽象 + E2E + 契约） |
| v0.20.0 | `8632cb6` | Dev 体验 + 运维完备（ops 扩展 + 6 项审查修复） |
| v0.20.1 | `0592c3f` | CCC Engine 串行执行引擎（取消 7 角色定时） |
| v0.21.0 | `a9e0383` | 门控修补（reviewer LLM + tester baseline） |
| v0.22.0 | `ebf92a7` | audit 角色 + daily-auto-scan 收纳 |
| v0.22.1 | `d4866d8` | audit 修复 + 实测耗时记录 |
| v0.23.0 | `5775ec3` | product 上游智能化（读代码结构再写 plan） |
| v0.23.1 | `d652cbd` | v0.23 对抗性审查修复（A1-A7） |
| v0.23.2 | `5aeb65a` | engine 取 task 后未 update_index 修复 |
| v0.23.3 | `785ba7f` | 时间戳统一为北京时间（Asia/Shanghai） |
| v0.23.11 | `acb2b55` | 根治 fcntl 死锁 + reviewer JSON 宽松解析 |
| v0.23.12 | `d5ab36d` | audit_role per-workspace last_run key 修复 |
| v0.23.13 | `3c35afd` | board-server GET / 路由修（do_GET else 兜底吞 UI） |
| v0.23.14 | `fcb5030` | reviewer bytes/text 冲突 + engine LOG 路径冲突 |
| v0.23.15 | `1c35417` | OpenCode 模型名 (loop/code) + product 3.9 rglob 兼容 |
| v0.23.16 | `3d77f16` | reviewer G2 误判 + COLUMN_TRANSITIONS abnormal 重投通路 |
| v0.24.0 | `6b821a2` | Engine phase 感知调度（依赖解析 + 失败隔离） |
| v0.24.1 | `7705a09` | reviewer 按变更量分级（small/medium/large） |
| v0.24.2 | `9b63788` | audit 多 workspace 并行化（ThreadPoolExecutor） |
| v0.24.3 | `764be91` | 对抗性审查 P0 hotfix（8 项：写回 reload / 文件锁 / audit timeout / small reviewer 校验 / _parse_diff_size fail-fast / engine 多 phase） |
| v0.28.1 | `a81be00` | 任务复杂度分流（complexity small/medium/large）+ 每周总结定时任务 |
| fix-lint-2026-07-14 | `c4ec801` (phase 2) + `479ac6d` (phase 1) | scripts/ ruff F401/F841/F811 全面清零（21 自动 + 14 手动）+ `_audit_lint` 补 return |

---

## 当前状态（v0.28.1 closure, 2026-07-12）

**架构**：CCC Engine 串行驱动 + BoardStore / Executor / Config 三层抽象 + phase 感知调度 + **复杂度分流（small/medium/large）**。

**复杂度分流**（v0.28.1）：task 有 `complexity` 字段（small/medium/large）。product_role 根据 plan_weight 自动推断。small 任务在 Engine 中跳过 reviewer+tester 直通 kb。medium（默认）和 large 走完整 7 角色。详见 `CHANGELOG.md §v0.28.1` 或 `references/board-task-schema.md §12`。

**每周总结定时任务**（v0.28.1）：CronCreate 每周日晚 22:03 自动生成 `.ccc/reports/weekly-YYYY-MM-DD.md`。持久的，重启后仍在。

**已发布版本族**：v0.7.0 → ... → v0.28.0 → **v0.28.1**（共 34 个 release tag）

**已完成范式转变**（roadmap 标注）：
1. v0.11 — "opencode 写 + 人工 review" 模式
2. v0.12 — bug 扫描 → 必修 → 复查 → 沉淀 4 步标准化
3. v0.15 — 真自动化开发（opencode + post-exec 自动 push）
4. v0.16 — 7 角色 + 任务看板（6 列流转 + 7 launchd 周期）
5. v0.17 — 战略地图（启动必读第一份）
6. v0.18 — 7 角色文档对齐 + 架构审查（regress 角色正式加入，9 个问题修复）
7. v0.19 — 基础加固 + 扩展通路（三抽象 + E2E + 共享契约）
8. v0.20.1 — 串行执行引擎（取消 7 角色定时，Engine 常驻进程）
9. v0.23 — product 上游智能化（读代码结构再写 plan）

**已规划未实施**（按用户节奏）：
- v0.24 — Engine phase 感知调度
- v0.25 — 全链路对齐（文档/测试/角色 SKILL 同步刷新）
- v0.26 — CCC Board Protocol / 跨 IDE 开放协议（Agent ↔ 看板列映射）

**当前不启动**任何新任务，等用户拍板。

---

## Mac2017 部署链路打通（2026-07-09，会话外操作）

> 老板要 M1 开发 / Mac2017 生产分离。一次性做了 P0+P1。

**M1 → Mac2017 部署现状**（`192.168.3.116`，用户 `fan`）：

| 项目 | 部署 | 状态 | 文档 |
|---|---|---|---|
| qb（量化） |  P0-1 完成 | 8095 dashboard 跑通（降级模式）；4 个 plist 受 launchd 限制未启 | `~/program/projects/qb/DEPLOY_MAC2017.md` |
| xianyu（AI 分发） |  P0-2 完成 | admin/web/data-collector 跑着；6 个 daily-video slot 退出码 1（**ROOT 路径 bug 已修**） | `~/program/xianyu/DEPLOY_MAC2017.md` |
| qx（爬虫） |  未部署 | Mac2017 无源码，P2 任务 | `~/program/projects/qx/DEPLOY_MAC2017.md` |
| qx-observer |  早就跑 | 7777 健康 | 已有部署 |

**统一部署脚本**：`/Users/apple/program/scripts/deploy-to-mac2017.sh`（commit `d03dcac`）
- 4 项目 + dry-run + skip-rsync
- 排除 .env / venv / logs

**关键修复**：
- 5 个 qb plist 路径 `/Users/apple/` → `/Users/fan/`
- Mac2017 qb venv `uv sync --extra dashboard`
- qb .env `JWT_SECRET` + `QB_ADMIN_PASS` 轮换
- xianyu `run_daily_video.sh` ROOT 路径修

**已知缺口**（不在 P0+P1 范围，等老板拍板）：
- macOS launchd 在 SSH session 报 IO error 5 / 状态码 78 → nohup workaround
- PG 5432 跨机不可达 → Mac2017 装本地 docker pg
- xianyu 缺中文 TTS voice `Flo (中文（中国大陆）)` → 改 edge-tts

**Lessons Learned**（候选，等沉淀到 `docs/lessons.md`）：
- L-? launchd `load` 在非 GUI session 不可靠，用 `nohup` 兜底
- L-? SSH 远程 plist `Load failed: 5` 不是 plist 错，是 session 限制
- L-? 跨机部署的密钥必须在目标机重新生成，不能复用 M1 密钥
- L-? `plutil -lint` 只能验语法，验不出路径不存在；必须手工跑一次确认

---

## v0.18 ~ v0.23 任务链回放（commit + CHANGELOG 形式）

> 详细条目见 `CHANGELOG.md`。本段只记关键产出与决策。

### v0.18 任务链：✅ 已完结（2026-07-07/08，7 角色文档对齐 + 架构审查）

- 关键产出：regress 角色正式加入（v0.18-board-py + v0.18-agents + v0.18-schedule + v0.18-role-log + v0.18-product-llm + v0.18-ui + v0.18-docs）
- 关键产出：ccc-board.py 扩展 — 事件记录（timeline）+ 批量操作（--batch）+ task_id 唯一性校验
- 关键产出：opencode 默认模型 → loop/code（避免误用对话模型写代码）
- 关键产出：v0.18 架构审查修复（6 项对抗性问题）
- plan/report：`.ccc/plans/v0.18-*.plan.md` × 7 + `.ccc/reports/v0.18-*.report.md` × 7

### v0.19 任务链：✅ 已完结（2026-07-08，基础加固 + 扩展通路）

- 关键产出：`scripts/_config.py` 集中配置（消灭 6 个脚本硬编码）
- 关键产出：`scripts/_board_store.py` BoardStore 抽象 + FileBoardStore 实现（fcntl.flock + 原子写入）
- 关键产出：`scripts/_executor.py` Executor 协议 + OpenCodeExecutor 实现
- 关键产出：`references/board-task-schema.md` task JSONL 格式标准（CCC-QXO 共享契约起点）
- 关键产出：`tests/e2e/test_pipeline_smoke.sh` 完整流水线 E2E 集成测试
- 关键产出：phases.json 加 `"schema_version": "1.0"` 元数据行
- 关键产出：dev_role 读 phases 时跳过 schema_version 行
- 关键产出：看板写操作加文件锁防 race condition

### v0.20 任务链：✅ 已完结（2026-07-08，Dev 体验 + 运维完备）

- 关键产出：ops 角色扩展 — launchd 7 角色自检 + `.ccc/metrics.json` 指标收集
- 关键产出：日志清理 — ops 角色自动删除 >30 天的 role-*.log
- 关键产出：E2E 覆盖增强 — 白名单外语法错误跳过 + 白名单内语法错误拒绝（7→9 步）
- 修复 v0.19 对抗性审查 6 项：S1 (asyncio 阻塞)、S2 (重试日志覆盖)、W1 (无读锁)、W2 (schema_version 检测)、N1 (代码重复)、N5 (文档不一致)
- 修复 v0.20 对抗性审查 4 项：S3 (第二处 startswith)、S4 (opencode-exec 未复用 _executor)、W5 (冗余 import)、W6 (returncode 检查)

### v0.20.1 任务链：✅ 已完结（2026-07-08，CCC Engine 串行执行引擎）

- **架构重大变更**：14 plist（CCC 7 + qxo 7） → 每 workspace 1 个 engine plist
- **架构重大变更**：定时轮询 → 有 task 立即执行，无 task 休眠 5s
- **架构重大变更**：7 独立进程各扫各的 → 单一 while 循环串行编排
- 关键产出：`scripts/ccc-engine.py` — Engine 主循环（~280 行）
- 关键产出：`scripts/ccc-engine.sh` — Engine launchd 入口
- 关键产出：`scripts/uninstall-ccc-roles.sh` — 卸载旧角色 plist
- 关键产出：`scripts/install-ccc-roles.sh` 改为只装 Engine + board-server plist，支持 `--upgrade` 自动卸载旧角色
- 关键产出：X5 / X6 红线更新（X5 = Engine+board-server plist 必装，X6 = 取消角色定时）
- 关键产出：`scripts/roles/*.sh` 7 文件标记 deprecated（保留兼容）
- 验证：pytest 49 全通过；engine 启动 → planned task → dev→reviewer→tester→kb 全链路

### v0.21 任务链：✅ 已完结（2026-07-09，门控修补）

- 关键产出：`reviewer_role` 重写 — 调 Claude API 审查 `git diff HEAD~1` + plan `## 验收清单`
- 关键产出：`tester_role` 强制 baseline — 检测 pyproject.toml 时追加 `pytest tests/ -q --cov=src --cov-fail-under=80`
- 关键产出：`_get_git_diff()` / `_review_with_llm()` / `_py_compile_fallback()` 辅助函数
- 关键产出：LLM 审查失败时 fallback 到 py_compile 静态检查
- 关键产出：plan 模板加 `## 验收清单` 段
- 关键产出：`skills/ccc-reviewer/SKILL.md` 重写 — 5 大类审查清单 + 三级严重度
- 关键产出：红线 X7 — reviewer 必须 LLM

### v0.22 任务链：✅ 已完结（2026-07-09，audit 角色 + daily-auto-scan 收纳）

- 关键产出：`audit_role()` 新角色 — 全项目扫描 + AI 分类 + auto 直接修 / review 投 backlog
- 关键产出：`engine` 主循环加 `_audit_should_run()` 时间检查（每 2h）
- 关键产出：`FileBoardStore` 白名单 `backlog → planned` 允许（audit 投出直接到 planned）
- 关键产出：报表路径迁移 — `~/Desktop/auto-scans/` → `{workspace}/.ccc/audit-reports/`
- 关键产出：lint baselines 迁到 `~/.ccc/lint_baselines/`
- 关键产出：删除 `~/.claude/skills/daily-auto-scan/`（功能并入 audit_role）
- 关键产出：删除 `~/.claude/scheduled_tasks.json` cron `7 */2 * * *`（改 engine 触发）
- 关键产出：红线 X8 — audit 角色 2h 内只跑一次

### v0.22.1 任务链：✅ 已完结（2026-07-09，audit 修复 + 实测耗时记录）

- 修复 N1：`FileBoardStore` __init__ 兜底建 7 列 + events 目录（裸 workspace 不抛 FileNotFoundError）
- 修复 N3：审计报表加 mypy 原始输出附录（防截断误导）
- 修复 N4：`audit_role` 加全程计时（per-workspace + total duration → `audit-last-run.json` + 报表 + return dict）

### v0.23 任务链：✅ 已完结（2026-07-09，product 上游智能化）

- 关键产出：`_get_code_context()` 函数 — 动态获取当前代码结构（文件树 + git 日志 + 入口文件）
- 关键产出：`_call_claude_for_plan` prompt 注入代码上下文（<3KB）
- 关键产出：plan 模板强制写 `## 当前代码状态` 段
- 关键产出：`skills/ccc-product/SKILL.md` 加 §0 "先读代码，再写 Plan"

### v0.23.1 任务链：✅ 已完结（2026-07-09，对抗性审查修复 A1-A7）

- A1: VERSION v0.23.0-dev → v0.23.0
- A2: `_get_code_context` 截断确保代码块闭合
- A3: 删除冗余 subprocess import
- A4: roadmap.md v0.23 状态改为已发布
- A5: 入口文件过滤增强（排除 vendor/build/tests）
- A6: 模块级缓存 `_get_code_context_cache`
- A7: rglob `follow_symlinks=False`

### v0.23.2 任务链：✅ 已完结（2026-07-09，engine 取 task 后未 update_index 修复）

- 修复：`ccc-engine.py` `dev_role_launch` 成功后未调 `update_index()`，导致 index.json 与实际看板列不一致
- 教训：Lesson 37 — Engine 每次操作看板文件后必须同步 index.json

### v0.23.3 任务链：✅ 已完结（2026-07-09，时间戳统一为北京时间）

- 修复：`ccc-board.py` `now_iso()` 从 `timezone.utc` 改为 `ZoneInfo("Asia/Shanghai")`，输出后缀 `Z` → `+08:00`
- 修复：`ccc-engine.py` `now_iso()` 同样改为北京时间
- 影响：task JSONL 时间戳、engine 心跳、报表日期、事件记录等全部时间输出

---

## 待办任务（用户已承诺，未启动）

### 已投递到 QB backlog（等待 Engine 调度）

| # | 任务 ID | 复杂度 | 来源 |
|---|---------|--------|------|
| 1 | `qb-redis-nogroup-fix` | medium | 审查 — Redis 消费组自愈 |
| 2 | `qb-config-unify` | medium | 审查 — 双配置系统统一 |
| 3 | `qb-mypy-debt-phase1` | small | 审查 — mypy 债务清理 |
| 4 | `qb-backtest-smoke` | small | 审查 — 回测冒烟测试 |
| 5 | `qb-dashboard-unit-tests` | small | 审查 — 前端单元测试 |
| 6 | `qb-testnet-keys` | small | 审查 — Testnet 密钥补全 |

> 6 个 task 已写入 `~/program/projects/qb/.ccc/board/backlog/`。
> product 产出：plan × 6 + phases.json × 6 + 看板卡片 × 6。
> Engine 检测到 planned 转 in_progress 后自动串行执行。

---

## 已知约束（项目级）

- **不新增平台依赖**：CCC = SKILL 资产 + Engine 脚本，跨 IDE/跨模型
- **4 文件契约**：plans / phases / reports / verdicts 必须严格走 `.ccc/`
- **跨 IDE symlink**：
  - `~/.claude/skills/ccc-protocol` → CCC repo
  - `~/.zcode/skills/ccc-protocol` → CCC repo
  - `~/.config/skills/ccc-protocol` → CCC repo（通用）
- **不可触碰**：`/etc/*`, `~/.env`, `~/.aws/*`（红线 1）
- **commit 规则**：单 phase 单 commit + commit msg 必含 `ccc-task-id=<task> phase=N`
- **Engine + board-server plist**：必装（红线 X5）

---

## 工具链状态

| 工具 | 版本 | 状态 |
|------|------|------|
| Python | 3.9+（已兼容 3.14） | ✅ |
| Bash | 5.x | ✅ |
| Claude Code CLI | 2.1.193+ | ✅ |
| OpenCode CLI | latest（loop/flash / loop/code 双通道） | ✅ |
| ruff | 0.8.6 | ✅ |
| shellcheck | latest | ✅ |
| pytest | latest（v0.22.1 起 10 passed） | ✅ |

---

## 关键历史决策（影响后续任务）

1. **CCC 形态选择** (2026-07-06)：选 SKILL 资产而非 framework 代码库 — 跨 IDE/跨模型维护成本最低
2. **三角色边界** (2026-07-06)：Planner / Executor / Verifier 严格分离，禁止互串（红线 6）
3. **红线 11** (2026-07-06)：Verifier 必须写真 verdict 文件，口头 PASS 不算 PASS（Lesson 28）
4. **执行方式 4 选 1** (2026-07-06)：`manual` / `auto` / `loop` / `goal`（其他术语禁止）
5. **v0.7-slim 精简决策** (2026-07-07)：删除 cluster-bus / dispatch / flywheel / 成本报告 / precommit / 多 IDE adapter 等"路线预留"代码
6. **v0.7.0 closure** (2026-07-07)：v0.7-slim → v0.7a → ... → v0.7f 共 9 子任务全部 PASS / CONDITIONAL_PASS，统一收束为 `v0.7.0` umbrella release。流程层版本从 1.2.0 回落至代码层 v0.7.0
7. **v0.11 范式转变** (2026-07-07)：CCC 转入 "opencode 写 + 人工 review" 模式（Lesson 35）
8. **v0.12 bug fix 4 步法** (2026-07-07)：扫描 → 必修 → 复查 → 沉淀（Lesson 36）
9. **v0.16 7 角色系统** (2026-07-07)：product/dev/reviewer/tester/ops/kb/regress 7 角色 + 6 列任务看板 + 7 launchd plist
10. **v0.19 三抽象 + 契约** (2026-07-08)：Config / BoardStore / Executor 三层抽象 + board-task-schema.md 共享契约（CCC-QXO 解耦）
11. **v0.20.1 Engine 串行化** (2026-07-08)：取消 7 角色 launchd 定时轮询，改为单一 Engine 常驻守护进程串行执行 task 全链路（红线 X6 = 角色频率不再适用）
12. **v0.21 门控强化** (2026-07-09)：reviewer 必 LLM + tester 必 baseline（红线 X7）
13. **v0.22 audit 收纳** (2026-07-09)：daily-auto-scan skill 全部并入 CCC audit_role，外部 cron 删除（红线 X8 = audit 2h 限频）
14. **v0.23 product 智能化** (2026-07-09)：product 角色先读代码结构再写 plan，提升 plan 质量减少下游返工
15. **v0.23.3 时区统一** (2026-07-09)：所有 ISO 时间戳统一 `Asia/Shanghai +08:00`，消除 UTC Z 后缀带来的解析歧义

---

## 维护说明

- **追加任务**：在"最近任务"表头部插入，保留最多 5 条
- **去重**：lessons.md 写入按 `(date, task_id)` 去重（红线 10 机制钩子）
- **过期归档**：超过 30 天的任务可移到 `.ccc/archive/state-YYYY-MM.md`
- **禁止手动改写历史行**：只能追加新行，不能修改已完成任务的 hash
- **v0.19+ 任务记录形式**：版本级任务走"commit + tag + CHANGELOG"三件套，不为每个版本单独建 plan/report/verdict 文件（除非用户显式要求）

---

**最后更新**：2026-07-09（v0.23.3 closure — 北京时间 +08:00 已统一）
**v0.23.3 收尾**：
- `now_iso()` 全量改 `ZoneInfo("Asia/Shanghai")`，后缀 `+08:00`
- commit `785ba7f` 已合入 main
- 工作树与 origin/main 同步
- 下一版节奏等用户拍板

**下次启动必读顺序**：
1. 读本文件（state.md）
2. 读 `.ccc/profile.md`
3. 读 `CHANGELOG.md` §最近（v0.28+）
4. 才开工

**当前活跃**：
- complexity 分流已生效（v0.28.1）
- 每周总结定时任务（周日 22:03）

<!-- board-status -->
## 看板状态

> 自动更新 — 最后刷新时间：2026-07-15T00:31:39+08:00

| 列 | 任务数 |
|---|------:|
| backlog | 5 |
| planned | 1 |
| in_progress | 1 |
| testing | 0 |
| verified | 0 |
| released | 98 |
| abnormal | 0 |

<!-- /board-status -->

























































