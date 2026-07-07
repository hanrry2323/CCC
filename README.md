# CCC — Connect–Claude Code

> **One skill, every IDE, every model.** A skill that turns any coding agent
> into a Plan → Execute → Verify pipeline.

---

## 含义

**C**onnect — **C**laude **C**ode

把 Claude Code 的执行能力**连接到任何 IDE 工具**：
- Trae / Cursor / Zed / VS Code / OpenCode — 都能用同一份 SKILL
- SKILL 一次性注入 prompt，不污染 agent 上下文
- 中转站路由（`ANTHROPIC_BASE_URL`）— 任务类型自动选模型

## 核心

```
CCC = 1 个 SKILL.md
      + 11 条红线
      + 4 文件契约
      + IDE 定时任务（可选）
      + 知识飞轮（可选）
```

CCC 不是 framework 代码库，**是一个 prompt 资产 + 工程纪律沉淀**。

## 关键资产清单

| 路径 | 角色 |
|------|------|
| `SKILL.md` | 唯一注入 prompt（agent 启动时自动加载） |
| `references/red-lines.md` | 13+2+X3 红线强约束（v0.8 新增 X1/X2/X3） |
| `scripts/ccc-precheck.sh` | 5 项前置门控（红线 7+10） |
| `scripts/ccc-finish.sh` | 5 项后置门控 |
| `scripts/opencode-exec.py` | **OpenCode CLI 执行器**（v0.8 替换 claude） |
| `scripts/opencode-pool.py` | **OpenCode 进程池**（max 3 并发，红线 X1） |
| `scripts/opencode-watchdog.sh` | **OpenCode 残留扫描**（红线 X2/X3） |
| `scripts/ccc-notify.sh` | **macOS 桌面通知**（升级链 L1/L2/L3） |
| `scripts/ccc-hook.sh` | **通用钩子**（pre-exec / post-exec / on-error） |
| `scripts/ccc-exec-launcher.sh` | 单 phase 启动入口（串联 watchdog→hook→opencode） |
| `scripts/ccc-exec-commit.sh` | 单 phase 单 commit（红线 4+8） |
| `scripts/ccc` | CLI wrapper |
| `scripts/ccc-init.py` + `ccc-search.py` + `ccc-status.sh` + `ccc-task-done.sh` | 基础运维 |
| `templates/` | 4 文件契约模板（plan/phases/report/verdict/executor-prompt/AGENTS） |
| `tests/scripts/` | pytest 核心测试 |
| `references/adapters/runtime-opencode.md` | **OpenCode 执行器契约**（v0.8 重写） |
| `.ccc/profile.md` + `.ccc/state.md` | 项目档案 + 接力索引（红线 7+10） |
| `docs/lessons.md` | 历史教训沉淀 |
| `docs/roadmap.md` | 路线图 |
| `CHANGELOG.md` | 版本变更 |

## 30 秒上手

```
1. 把 ~/program/CCC/ 作为 skill 加载到 IDE
2. 在项目目录下开新对话
3. 用户说："按 ccc full 跑 X 任务"
4. agent 加载 4 文件契约 + 红线，跑 Planner/Executor/Verifier
```

## 三角色

| 角色 | 谁 | 产出 |
|------|----|------|
| **Planner** | 你 + agent 对话 | `.ccc/plans/<task>.plan.md` + `phases/<task>.phases.json` |
| **Executor** | agent 自主 | `.ccc/reports/<task>.report.md` |
| **Verifier** | 独立 session | `.ccc/verdicts/<task>.verdict.md`（≥3 probes） |

严格分离：**Planner 不写 verdict，Verifier 不写 plan**。

## 关键纪律（详见 `references/red-lines.md`）

- **红线 11**: Verifier 必须写 verdict 文件（口头 PASS 不算）
- **红线 12**: 禁止 agent 自主启用 CCC（必须用户显式触发）
- **红线 X1**: OpenCode 进程池最多 3 并发（v0.8）
- **红线 X2**: 每 phase 必杀 opencode 进程（v0.8）
- **红线 X3**: OpenCode 启动前必跑残留 watchdog（v0.8）
- **Lesson 27**: `claude -p` 是 print 模式，prompt 必须走 stdin
- **Lesson 28**: Verdict 强证据红线 11 的来历

## 路由决策（用户拍板）

| 任务 | 谁处理 |
|------|-------|
| 单文件 / 调试 / 查信息 | agent 直接处理（**不**走 CCC） |
| 多文件 / 跨模块 | CCC 启用 1-2 phase |
| 多阶段 / 跨会话 | CCC 强制 + 完整 4 文件 |

## 配套

- **跨模型**：`ANTHROPIC_BASE_URL=http://127.0.0.1:4000` 走中转站路由

> v0.7-slim 已精简：知识飞轮 / IDE 定时 / 跨设备集群 / ZCode adapter 等路线预留代码移除。
> 如需做这些功能，按需从头重写更简单的版本。

## 链接

- 唯一 SKILL 资产：`~/program/CCC/SKILL.md`
- 红线清单：`~/program/CCC/references/red-lines.md`
- 教训沉淀：`~/program/CCC/docs/lessons.md`
- 模板库：`~/program/CCC/templates/`
- 当前版本：`1.1.0`

---

**测试覆盖**: 42/42 smoke tests PASS。
