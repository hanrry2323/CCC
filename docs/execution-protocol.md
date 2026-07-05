# Claude 执行协议

> 来源：ccg-workflow spec-impl.md + Claude Code official best-practices。

---

## 执行方式

Claude 以**自主长任务**方式执行，**不需要用户在场**。两种启动方式：

### 方式一：/codex-executor slash command

```bash
claude /codex-executor --task <task>
```

加载 plan 后使用 `/goal "按 plan.md 完成所有改动、自验通过、提交代码后结束"` + `--permission-mode auto` 开始执行。

### 方式二：非交互模式

```bash
claude -p "读取 .ccc/plans/<task>.plan.md，按其中的步骤执行。全部完成后写实施报告到 .ccc/reports/<task>.report.md" --permission-mode auto
```

Claude 运行完成后进程退出，不需要人在终端等待。

**注意**：
- `claude -p` 与 `claude --print` 等价（`-p` 是 `--print` 的简写）。`claude --help` 显示 `-p, --print` 都是合法参数。
- 标准提示词模板见 `~/program/CCC/templates/executor-prompt.template.md`，新项目直接复制。
- 加 `timeout` 兜底（按任务分级，见下文 timeout 表）。

---

## Planner 边界（重要）

**Planner 不能在自己 IPC session 里 spawn `claude -p`**（v0.5 重构表述）：
- Planner 是 IPC daemon (mavis) 内的 agent，没有独立 Claude Code CLI 终端
- `claude -p` 会 block Planner session（auto 多 phase = 1200s + 网络 = 1500s），期间 Planner 无法响应用户
- 必须**用户在另一个 Claude Code CLI 终端**跑 `claude -p "<prompt>"` 启动 Executor
- 替代方案（仅兜底）：Planner 直接执行任务（Lesson 8/11 越界兜底规则），但默认严格走 Plan → Executor → Verifier 三角色分离

---

## 长任务自主执行机制

Claude 按 plan 定义的**执行方式**字段自动驱动自己：

| Plan 中指定 | Claude 怎么做 |
|---|---|
| `manual` | 一次性执行，不进入长任务循环 |
| `auto` | 自动逐 phase 执行，每完成一个写 phases.json 然后继续 |
| `loop` | 用 `/loop` 定时轮询，每轮完成任务片段 |
| `goal` | 用 `/goal` 保持会话持续，跨多轮不中断 |

---

## Timeout 分级表（P4 修复 · 新增）

按任务规模和特性分级设 `timeout`：

| 任务类型 | 单文件 / 小改 | 多文件 / 中等 | 长任务 / 网络 |
|---|---|---|---|
| **manual** | 600s（10 分钟） | 900s（15 分钟） | — |
| **auto** | 900s | 1200s（20 分钟） | 1500s |
| **loop** | — | — | 3600s（1 小时），单次循环不超过 7 天 |
| **goal** | 1200s | 1800s（30 分钟） | 3600s+，需拆分 sub-task |

**判断规则**：
- **小改**：≤50 行改动，单文件，无网络操作
- **中等**：50-200 行，1-3 文件，可能涉及 git push
- **长任务**：> 200 行，> 3 文件，或涉及网络/外部依赖

**网络/外部依赖加成**：git push / npm install / pip install / docker pull 等网络操作，timeout **额外加 300s**（网络可能慢）。

**示例**：

```bash
# 小改 manual：600s
claude -p "..." --permission-mode auto --timeout 600

# 多文件 auto：1200s
claude -p "..." --permission-mode auto --timeout 1200

# 长任务 goal：3600s+
claude -p "..." --permission-mode auto --timeout 3600
```

---

## Plan 的读法

Plan 是自然语言。**不要逐行执行**，而是整体理解后自行规划执行顺序。

**注意**：plan 的"参考命令"是 hint，Claude 自己决定用什么命令实现（红线 2 / 红线 0）。

---

## 执行规则

1. **纯机械执行** — 所有决策已在 Plan 阶段完成，不新增、不重构、不"改进"
2. **意图驱动** — plan 中写的"做什么"，Claude 自己决定"用什么命令"
3. **逐段执行** — 按 Phase 顺序，每完成一个更新 phases.json
4. **自验门禁** — 每个 Phase 完成后按 plan 的"验收"描述验证，失败最多重试 3 次
5. **范围隔离** — 只改 plan 声明的文件，发现额外问题记入 report 但不修改
6. **单 Phase 单 commit**（P4 修复）— 每个 Phase 独立 commit，message 含 Phase 编号（`fix: xxx (phase 1/3)`）

---

## Commit 流程（P4 修复 · 强化）

每个 phase 完成后必须：

```bash
git add <只改文件>
git commit -m "type(scope): description (phase N/M)"
```

- commit message 参考 plan 的"Commit 计划"表
- commit 后把 hash 填回 phases.json 的 `commit` 字段
- 不准一个 phase 跨多个 commit
- 不准一个 commit 含多个 phase（除非是 manual 模式的单 phase）

### 每步必须 commit 兜底规则（P4 强化 · 新增）

**任何 working tree 中的改动必须在该 phase 内 commit，不准攒着等"全部做完"再 commit。**

| 场景 | 错误做法 | 正确做法 |
|---|---|---|
| 改 1 个文件 + 改 2 个文件 | 一次性 stage 3 个文件，commit "fix: 多文件" | 改 1 改完立刻 commit；改 2 改完再 commit |
| 改完 Edit 还没 push | 不 commit 就 push（不存在 push uncommitted） | Edit 完 → commit → 再 push |
| 多 phase plan | 改完所有 phase 才一次性 commit | 每 phase 改完立刻 commit，commit message 含 phase 编号 |
| 同一 phase 内多个独立改动 | 攒着最后一起 commit | 每个独立改动单独 commit |

**判断标准**：phase 内的"完成定义"包含 `git status --short` 无该 phase 改动 + phases.json `status=done`。两者同时满足才算 phase 完成。

**反例**（Lesson 3 案例）：Executor 跑完 Edit + phases in_progress 后静默退出，working tree 还有 modified 文件没 commit → phase **未完成**，即使其他步骤看起来"做了"。

---

## 文件读写路径

| 文件 | 操作 |
|------|------|
| `.ccc/plans/<task>.plan.md` | 读 |
| `.ccc/phases/<task>.phases.json` | 每完成一个 Phase 追加/更新一行 |
| `.ccc/reports/<task>.report.md` | 全部完成后写入 |

---

## 退出条件

- 全部 Phase 完成 + 自验全通过 + 所有 phase 都 commit → 写 report → 退出
- 某 Phase 重试 3 次仍失败 → 标记 phases.json failed → 写 report（包含失败记录） → 退出
- 环境故障（编译工具缺失、网络不通等）→ 退出
- **超时中断**（本次任务实测案例）→ Planner 兜底（详见 `agent.md` §Planner 越界兜底规则）：**Planner 不 commit**，告诉用户失败，让用户决定下一步。