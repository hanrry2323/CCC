# CCC — Codex Claude Collaboration

> Mavis (MiniMax) 规划 + 监控 + 验收 → Claude 长任务自主执行。全文件桥接，零对话回合。

## 近期实战更新 (2026-07-01)

8 次 CCC 任务实战沉淀 (audit-frontend 三轮修订 + qb 卫生 + V6.5 + accept-cleanup + push + Lesson 20), 总结如下:

### 三角色模型
- Planner: qxo-CC (默认 MiniMax 模型) — 写 plan + 启 Executor/Verifier
- Executor: claude Code CLI 走 `claude -p` — 自主执行
- Verifier: 同 Executor 配置 — 独立验收
- 严格分离: Planner 不验收, Verifier 不规划, Claude 只执行

### Executor / Verifier 启动标准 (红线 9)
- 用 `claude -p "$(cat prompt)" --permission-mode bypassPermissions --max-budget-usd N`
- Executor 退出后必须调用 `ccc commit <workspace> <task>` 自动处理 commit（详见 P0.2 拆分 commit 职责）
- **绝对禁止** `mavis session new <agent>` (会 fallback minimax/MiniMax-M3 = 三角色失效, 记 Lesson 19 / 红线 8 C6 = Critical)

### 默认预算
- 调研类 (6 phases): 200 USD
- 修补类 (1-3 phases): 30-50 USD
- 简单文件操作: 20 USD
- push 类: 5-30 USD

### Plan 硬性结构 (红线 2)
- 范围 (目标/只改文件/不改文件/执行方式/Phase 数)
- 改动 N: 做什么 / 怎么做 / 验收
- Commit 计划 + 全局验收清单 (红线 1-10)

### phases.json 必写 (红线 5)
- 单 phase 至少写 1 行 phase 1
- status 字段: pending → in_progress → done (不跳阶段)
- commit 字段: 该 phase commit hash (push-only 用 "N/A")

### 必建 cron 自提醒 (async-audit)
- 每次启 Executor/Verifier 立即 `mavis cron self qxo-<task> --every 5m`
- 完成即 `mavis cron delete`

### Verifier 必做 (不信任 report 自报)
- ≥3 个 adversarial probes 强制找问题
- 每个 Check 带 Method / Evidence / Result
- 三级严重度: Critical / Warning / Info
- 结尾必 VERDICT: PASS / CONDITIONAL_PASS / FAIL 三选一

### Planner 越界 = Critical (红线 8)
- C1 Edit 源代码 / C2 push（commit 由 `ccc-exec-commit.sh` 自动处理，不算越界）/ C3 ssh / C4 rsync / C5 sed 盲改 / **C6 mavis session new**
- 兜底: Executor 卡死 → 告诉用户 + 标 failed + 写 anomaly report
- 如果 Executor 已生成文件但未 commit（working tree 非空），Planner 允许调用 `ccc commit` 完成提交，记入 anomaly report 的 Fallback 段，不算 C2 越界

### 禁止跨会话隐式记忆 (红线 10, 2026-07-04 新增)
- 决策/产出禁止依赖会话级记忆
- 所有"上次结论"必须落到 `.ccc/state.md` + plan/report/verdict
- 启动时第一个读 `.ccc/state.md`，禁止"凭印象"复述上一会话
- 详见 `references/red-lines.md` 红线 10

### 实战经验沉淀
- 修订 v2 比一次性写更有价值 (Verdict 反馈驱动精确修复)
- direct fetch 盲区 (修 dead API 不只看 service/*.ts, grep views/components/)
- barrel export 检查 (store/hook grep 要考虑桶输出)
- 报告自报不可信 (Verifier 必抓 5 False Positive 这种坑)

---

## v0.4.0 路线 — Multi-Platform Orchestration (2026-07-02)

CCC 战略方向: multi-platform LLM orchestration framework (不是任何单平台的替代品).

### 核心定位

任何"用户常用 agent" (按 LLM 偏好) 都是锁定单一 LLM 的封闭生态. 例如:
- 偏好 minimax 的用户常用 agent (Mavis 性质): 默认 minimax (不可信, 红线 9)
- 偏好 GLM 的用户常用 agent (ZCode 性质): 默认 GLM 智谱 (multi-agent 不成熟)
- 偏好 Claude 的用户常用 agent (Claude Code 性质): Anthropic Claude (中文弱)
- 偏好 GPT 的用户常用 agent (Codex 性质): OpenAI GPT
- 偏好 Claude + GLM 混用的用户常用 agent: 多模型协作

CCC 在用户常用 agent 工具集之上做整合层 (不替代任何):
- 跨平台: 按用户偏好激活的常用 agent 工具集都可调度
- 跨模型: 用 Claude 写代码 / GLM 写中文 / GPT 写英文文档 (按模型优势)
- 文件契约: Plan/Phases/Report/Verdict 4 文件跨用户 agent 一致

### 用户 killer use case (两层架构)

```
Layer 1 (单用户常用 agent 擅长)  ←→  Layer 2 (CCC 跨平台调度)
─────────────────────────────     ─────────────────────────
用户常用 agent (LLM 偏好 X) 草图 plan  →  CCC 拆 phases 写到 .ccc/phases/
用户常用 agent (LLM 偏好 Y) 中文 UI    →  每个 phase 指定 platform 字段
用户常用 agent (LLM 偏好 Z) 深度开发   →  按 phases 串行执行
← 跨用户 agent Report / Verdict 汇集 →
```

### v0.3.0-dev 已有基础设施 (按用户 agent 配置激活, 默认值可扩展)

- references/adapters/runtime-{claude-p,claude-code,zcode,mavis}.md (4 个 runtime adapter 默认值)
- references/adapters/scheduler-{mavis-cron,launchd,github-actions}.md (3 个 scheduler adapter 默认值)
- scripts/install-ccc-as-skill.sh (按用户 agent 路径自动 symlink + 6 项 check)

### v0.4.0 必加能力 (设计稿见 ADR-004)

1. phases.json schema 加 `platform` 字段 (允许任意用户自定义 agent name, 不绑定 4 平台)
2. plan 模板加 "Platform Routing" 段 (按用户 LLM 偏好路由每个 phase)
3. Report 加 "Platform Actual" 段 (记录实际 platform + cost)
4. Verifier 跨平台一致性 (同一 Verdict 可调用不同用户 agent 确认)

### 不破红线

红线 9 仍适用: 任何"用户常用 agent"里如果包含 minimax fallback, 走 Executor/Verifier 必须用 claude-p 替代 (claude-p 是唯一可信 executor 后端, 不依赖任何用户常用 agent 的 minimax 通路)

---

## 三阶段管线

```
Mavis 桌面端                Claude (free-code)              Mavis 桌面端
    │                              │                              │
    ├─ ccc-planner 出 plan ────→ ├─ 长任务自主执行 ─────────→ │
    │   .ccc/plans/<task>.plan.md   │  按 plan 的执行方式启动       │
    │                              │  每完成一个 phase             │
    │                              │  → .ccc/phases/<task>...json │
    │  ←─ 跟踪 phases ───────── │                              │
    │                              │  全部完成 → .ccc/reports/    │
    │                              │                              ├─ ccc-verifier 验收
    │                              │                              │  读 report + git diff
    │                              │                              │  → .ccc/verdicts/
```

角色严格分离：**planner 不验收，verifier 不规划，Claude 只执行**。

---

## 目录布局

```
~/program/CCC/                           ← 框架总目录（协议 + 模板）
├── CLAUDE.md                            本文件（唯一总纲）
├── templates/                           全局模板（所有项目共用）
│   ├── plan.plan.md                     Plan 模板
│   ├── phases.phases.json               阶段状态模板
│   ├── report.report.md                 实施报告模板
│   ├── verdict.verdict.md               验收报告模板
│   └── profile.profile.md               项目 profile 模板
├── docs/                                全局规范
│   ├── plan-spec.md                     Plan 格式规范
│   ├── execution-protocol.md            Claude 执行协议
│   ├── verification-spec.md             Verifier 验收协议
│   └── agent-commands.md                命令速查
├── skills/                              全局 skill 定义
│   ├── ccc-planner/SKILL.md
│   └── ccc-verifier/SKILL.md
└── projects/                            项目归档（按项目简称）
    └── <简称>/
        ├── profile.md                   项目档案存档（与 <项目>/.ccc/profile.md 内容对齐）
        └── history/                     历史 plan/report/verdict 备份

<目标项目>/.ccc/                         ← 项目私有（每个项目独立）
├── profile.md                           项目简介（agent 启动第二份要读的）
├── plans/<task>.plan.md                 当前/历史 plan
├── phases/<task>.phases.json            当前/历史 阶段状态
├── reports/<task>.report.md             当前/历史 实施报告
└── verdicts/<task>.verdict.md           当前/历史 验收结论
```

---

## Agent 命名与启动流程

**命名**：`<项目简称>-CC`（如 `qxo-CC` / `xianyu-CC`）。每个项目一个独立 agent，记忆不跨项目串扰。

**Agent 启动顺序**（任何 `<项目简称>-CC` agent 必须遵循）：

1. 读 `~/program/CCC/CLAUDE.md`（本文件）— 学流程、术语、红线
2. 读 `<项目>/.ccc/profile.md` — 学项目背景
3. 开工

**两层配置优先级**：

| 层 | 文件 | 内容 | 优先级 |
|---|---|---|---|
| Agent 级 | `~/.mavis/agents/<简称>-CC/agent.md` | 跨项目通用约束（启动顺序 / 自然语言驱动 / 不 commit / 不建 cron） | 基础 |
| 项目级 | `<项目>/.ccc/profile.md` + 框架归档 `program/CCC/projects/<简称>/profile.md` | 该项目特定约束（plan 路径 / claude -p 调用模板 / timeout） | 覆盖 agent 级 |
| 框架总纲 | `~/program/CCC/CLAUDE.md` | 流程、术语、红线（每次启动必读） | 顶层 |

**冲突规则**：项目级 > agent 级。项目档案明确写"该项目可以 X"时，覆盖 agent 级默认的"不要 X"。

这样：用户不需要每次重复解释。CCC 总目录是"协议"，项目 `.ccc/profile.md` 是"项目档案"，各管各的。

**Verifier**：独立于 planner，使用 Mavis 内置 `verifier` agent（`~/.mavis/agents/verifier`），复用 `skills/ccc-verifier/SKILL.md` 协议。Planner 不写 verdict。

---

## 新增项目流程（用户操作）

要在新项目上启用 CCC，做三件事：

1. **建项目 agent**：`mavis agent identity` + 在 `~/.mavis/agents/<简称>-CC/agent.md` 写角色
2. **建项目工作目录**：在项目根 `mkdir .ccc/{plans,phases,reports,verdicts}`
3. **复制 profile 模板**：`cp ~/program/CCC/templates/profile.profile.md <项目>/.ccc/profile.md` 并填写

之后用户每次只需说："给本项目写 plan，输出到 `.ccc/plans/<任务>.plan.md`"，agent 即可按 CLAUDE.md + profile.md 自动工作。

---

## 文件桥接协议（核心）

### 1. Plan — Planner → Claude

`templates/plan.plan.md` 定义格式。每份 plan 必须包含：
- 范围：目标、只改文件、不改文件、**执行方式**（见下）
- 改动 N：**做什么 / 怎么做 / 验收**
- 全局验收清单

**验收口径**（P3 修复）：每条验收写"自然语言意图 + 可选命令示例"。例：

> ### 验收
> - 启动后端服务，确认健康检查返回正常（参考：`curl http://127.0.0.1:7777/api/health`）
> - 跑测试套件，全部通过（参考：`uv run pytest tests/ -q`）

命令示例仅作参考，Claude 自己决定执行命令。**禁止把命令当唯一验收手段**（不可执行的描述不允许出现，但也不允许"命令即验收"）。

### 2. Phases — Claude → Planner（过程监控）

`templates/phases.phases.json` 定义阶段状态。**每个 plan 无论改动多少都生成 phases.json**（P1 修复：单 phase 改动写 1 行 phase 1）。

Claude 每完成一个 phase 追加一行 JSON。Planner 读此文件跟踪进度。

### 3. Report — Claude → Verifier（终验输入）

`templates/report.report.md` 定义格式。包含：
- 改动文件清单（含 commit hash）
- 每条验收结果（含证据输出）
- 未完成项 + 失败重试记录
- **Commit 列表**（P4 修复：每个 phase 一个 commit，message 含 phase 编号）

### 4. Verdict — Verifier（终验输出）

`templates/verdict.verdict.md` 定义格式。Verifier 独立完成：
- 读 plan + report + git diff
- 跑验收命令（每条带证据）
- 三级严重度：Critical / Warning / Info
- 结尾输出 `VERDICT: PASS` / `CONDITIONAL_PASS` / `FAIL`

**Verifier 默认不信，先查证再下结论**。Planner 不写 verdict。

---

## 执行方式（P2 修复：术语统一）

| 方式 | 何时使用 | Claude 怎么跑 |
|---|---|---|
| `manual` | 一次性、单文件、可直接验证的小改 | 一次性执行，不进入长任务循环 |
| `auto` | 简单多 phase、可逐步推进 | 自动逐 phase 执行，每完成写 phases.json |
| `loop` | 需要定时轮询、反复执行（最长 7 天） | `/loop <间隔> <指令>` 定时重复 |
| `goal` | 复杂多 phase、不中断跑完整个 plan | `/goal <条件>` 自主保持 |

Plan 中必须明确指定其一。**禁止出现其他术语**（如 "codeloop" / "手动" / "auto-loop"）。

---

## 红线

1. 不动项目源代码以外的任何系统文件
2. plan 中验收必须有可执行的描述（自然语言意图 + 可选命令示例）
3. Claude 执行时不准超出 plan 声明的文件范围（额外问题记入 report 但不修改）
4. 不准一个 phase 跨多个 commit；不准一个 commit 含多个 phase
5. phases.json 必须写全——单 phase 也要写（至少 1 行 phase 1）
6. planner 不写 verdict；verifier 不写 plan
7. agent 启动必须先读 `~/program/CCC/CLAUDE.md` 再读项目 `.ccc/profile.md`
8. **每步必须 commit**（P4 强化）：任何 working tree 中的改动必须在该 phase 内 commit，不准攒着等"全部做完"再 commit。任何未 commit 改动 = 该 phase 未完成
9. **Executor 卡死必须立即止损**（A2 新增 · Lesson 7 + Lesson 9 + Lesson 12 修复）：
   - 触发条件：`bash ~/program/CCC/scripts/executor-watchdog.sh` 返回非零，或 claude 子进程 `etime > 15min && pcpu < 1%`
   - 立即动作：caller 立即 `kill -9 <claude_pid>` 或 `mavis session abort <session_id>`，不要等自然结束
   - 决策路径：
     - 1 次卡死 → watchdog --force-kill + 重试
     - 连续 2 次同 session 卡死 → 不再尝试第 3 次，**Planner 接管**（参考 Lesson 8 越界兜底判定标准）
   - 端口冲突 / OOM 等硬件层卡死 → caller 必须重启 daemon：`pkill -f opencode && opencode serve`
   - 必须记录：`~/.mavis/memory/user.md` 加 entry + `program/CCC/projects/qxo/lessons.md` 加 Lesson
   - **扩展: spawn 失败场景（与真卡死区分, Lesson 12）**：
     - 真卡死：进程 alive + CPU < 1% + 长时间无进展 → kill + Planner 接管
     - spawn 失败：`bash wrapper PID 显示 claude -p "$PROMPT"` 但 `pgrep -lf claude` 找不到真 binary → bash shim 接管 → stdin 处理错
     - spawn 失败处理：检查 shell wrapper（避免 stdin redirect / bash shim），避免 `--add-dir` 扫大目录，必要时改 `nohup` background + log redirect 到 `/tmp/executor-*.log`
     - **判定**：`pgrep -lf claude` 显示真 binary 进程 → 真正 spawn 成功；否则 spawn 失败（即使 bash wrapper 在跑）
10. **禁止跨会话隐式记忆**（详见 `references/red-lines.md#红线-10`）：所有历史结论必须落到文件并显式读取。启动时第一个读 `.ccc/state.md`。