# 红线清单 — CCC 协议不可触犯的约束（v0.5 起累积，含历史编号映射）

违反任何红线即记 Critical 违规。叠加入项目 `docs/lessons.md` 并触发修订流程。

---

## 编号索引表

| # | 一句话 | 版本来源 |
|---|--------|----------|
| 1 | 不动系统文件 | v0.5 |
| 2 | 验收必须可执行 | v0.5 |
| 3 | 不超出 plan 文件范围 | v0.5 |
| 4 | 单 phase 单 commit | v0.5 |
| 5 | phases.json 必写全 | v0.5 |
| 6 | Planner/Verifier 不互串 | v0.5 |
| 7 | 代理启动顺序固定 | v0.5 |
| 8 | 每步必 commit（不攒） | v0.5 |
| 9 | Executor 卡死立即止损 | v0.5 |
| 10 | 禁止跨会话隐式记忆 | v0.5 |
| 11 | Verifier 必须写 verdict 文件 | v0.5（Lesson 28 配套） |
| 12 | 禁止 agent 自主启用 CCC | v0.5（Lesson 28 配套） |
| 13 | 禁止未使用路线代码 | v0.7-slim（含旧 v0.6 watchdog 子条） |
| 14 | Executor 必须配 monitor + 5min 轮询 | v0.7d-prime |
| 15 | 轮询进程完成自动终止 | v0.7d-prime |
| 18 | 飞轮候选必须经过人工 review 才合并 | v0.6 |
| 19 | 跨设备 / 跨 session 必须有独立 Verifier 验收 | v1.0 配套 |
| 20 | 跨设备 bash 脚本必须用 v3 portability 模板 | v0.5 配套（Lesson 29） |
| **X1** | **OpenCode 进程池最多 3 并发** | v0.8 |
| **X2** | **每 phase 必杀 opencode 进程** | v0.8 |
| **X3** | **OpenCode 启动前必跑残留 watchdog** | v0.8 |
| **X4** | **每 phase 必走看板流转** | v0.16 |
| **X5** | **6 角色 plist 必装** | v0.16 |
| **X6** | **角色频率不许改** | v0.16（老板拍板）|

> 历史说明：v0.6 期间曾预留红线 16 / 17（未发布），v0.7 之后按"禁止未使用路线代码"（红线 13）原则已撤销预留号。本表只列实际生效条目。
>
> X1/X2/X3 是 v0.8 配套（OpenCode 执行端），编号用 X 前缀避开数字历史。

---

## 红线 1：不动系统文件

**规则**：不修改项目源代码以外的任何系统文件（`.env`、密钥文件、`/etc/hosts`、系统日志、`/tmp/` 非本任务文件等）。

**Why**：系统文件影响面不可控——改错可能导致环境损坏或安全漏洞。`~/.claude/` 等 agent 配置也在此列（除非任务明确要求）。

**触犯后果**：Critical — 立即回滚。叠加 Lesson，后续 agent 检查涉及 `~/.` 或 `/etc` 的改动提示用户。

---

## 红线 2：验收必须可执行

**规则**：Plan 中每项验收必须含可执行的意图描述（自然语言 + 可选参考命令）。禁止只写"验收通过"或仅靠参考命令覆盖。

**Why**：Verifier 和 Executor 需要知道具体如何验证。纯自然语言缺乏校验手段，纯命令缺乏意图理解——二者结合才能让不同 agent 独立验证。

**正例**：
```markdown
- 后端启动正常，健康检查返回 200（参考：`curl http://127.0.0.1:7777/api/health`）
- 测试套件全部通过（参考：`uv run pytest tests/ -q`）
```

**反例**：
```markdown
- ✅ 验收通过（无意图描述）
- `curl ... | grep "ok"`（无意图，命令即验收）
```

**触犯后果**：Warning — Executor/Verifier 无法独立验证。CONDITIONAL_PASS 并修订。

---

## 红线 3：不超出 plan 文件范围

**规则**：Executor 执行时不准修改 plan 声明为"不改文件"的路径。发现 plan 外的必要改动 → 记入 Report 但不修改。用户决策后再启用。

**Why**：plan 的范围是用户/Planner 画定边界。越界改动即脱离授权。

**触犯后果**：Critical — 立即停止、回滚。

---

## 红线 4：单 phase 单 commit

**规则**：一个 phase 不能跨多个 commit。一个 commit 不能含多个 phase。不许攒 commit（写完全部再统一一次性提交）。

**Why**：phases.json 的 `commit` 字段依赖 exact one-to-one 映射。跨 phase 的 commit 使 phases.json 无法准确追踪，Verifier 无法按 phase 逐项核对。

**允许的例外**：Phase 内容紧密相关（如安装依赖 + 写根文件 + skill 验证），phase 1 写的全部文件在一次 commit 中合入，前提是 phases.json 也同时更新。例：当前 CCC skill 安装任务。

**触犯后果**：Warning — phases.json commit 字段不匹配。Verifier 会标记。

---

## 红线 5：phases.json 必写全

**规则**：每个 plan 无论改动多少都必须生成 phases.json。单 phase 改动至少写 1 行 `phase 1`。不许不生成或跳过。

**Why**：Planner 跟踪进度依赖 phases.json。没有它 = 没有进度可见性。

**触犯后果**：Warning — 进度不可见。Plan 不完整。CONDITIONAL_PASS 并补全。

---

## 红线 6：Planner 不写 verdict，Verifier 不写 plan

**规则**：Planner 角色不输出 verdict（结尾不写 `VERDICT:`）。Verifier 角色不写 plan（plan 由 Planner 独占）。

**Why**：角色分离是 CCC 的核心设计。自审= 无价值 audit。Planner 写 verdict 是其自身计划的自我辩护，而非独立第三方的判断。

**触犯后果**：Critical — Verdict/Plan 不可信。判定为该角色输出无效，标记错误后重跑。

---

## 红线 7：代理启动顺序固定

**规则**：CCC 项目的任何 agent 启动时必须按此顺序读取配置：

1. **先读** `~/program/CCC/CLAUDE.md`（框架总纲：流程、术语、红线）
2. **再读** `<项目>/.ccc/profile.md`（项目档案：技术栈、目录、规范）

**Why**：必须先理解 CCC 协议的全局规则（第一份文件），再适配特定项目的上下文。翻转顺序会缺失关键上下文。

**触犯后果**：Info/Warning — 代理可能做出与 CCC 协议矛盾的决定。按 agent 启动流程修正。

---

## 红线 8：每步必 commit（不攒）

**规则**：任何 working tree 中的改动必须在该 phase 内 commit。不许等"全部做完再统一 commit"。未 commit 的改动 = 该 phase 未完成。

**Why**：Verifier 逐 phase 核对依赖 commit hashes 作为证据。攒 commit 使回溯和回滚丧失精度。多个未 commit 改动也增加合并/回滚风险。

**子规则**（Planer 越界：红线 8 C1-C6）：

| 代码 | 违规项 | 说明 |
|------|--------|------|
| C1 | 编辑源文件 | Planner 角色不写代码，不修改 .py/.ts/.jsx 等 |
| C2 | push | Planner 不 push 远程（commit 由 `ccc-exec-commit.sh` 自动处理，不算越界） |
| C3 | SSH 到远程 | 不连接外部服务器操作源文件 |
| C4 | rsync/scp | 不通过文件同步工具直接改项目 |
| C5 | sed 盲改 | 不通过正则替换无审查直接修改文件（问题：不可审查 + 不可控） |
| C6 | mavis session new | 不用 `mavis session new <agent>` 启动子会话（会导致非目标模型执行）— **v0.5 起改红线 9 表述为：禁止用 IPC 通道绕过 CCC dispatch** |

**触犯后果**：C1–C6 均为 Critical — 该 phase 无效，回滚并重跑。

### 红线 8 Fallback：Planner 兜底 commit（合法场景）

当 Executor 退出后 working tree 有改动但 commit 未触发生效时，Planner 允许调用 `ccc commit <workspace> <task>` 完成提交。

此行为**不算 C2 越界**，前提是：
1. Executor 已退出（进程不存在）
2. Working tree 有改动（`git status --short` 非空）
3. 本次兜底记入异常报告（anomaly report）的 "Fallback Commit" 段

连续两次 Fallback → 标记为需讨论。

---

## 红线 9：Executor 卡死立即止损

**规则**：Executor 进程卡死时不等待自然结束。立即 `<kill>` + 决策是否重试。

**触发条件**：
- claude 子进程 `etime > 15min` 且 `pcpu < 1%`（cpu 近乎停滞但进程存活）
- 或 watchdog script 返回非零退出码

**动作流水线**：
1. 立即 `kill -TERM <claude_pid>`（超时 2s 未响应则 `kill -KILL`），或用 IPC 控制通道的对应 abort 命令
2. 本 session 首次卡死 → 重试一次（同 prompt 重跑）
3. 连续 2 次同 session 卡死 → 不再重试，Planner 接手评估新方案
4. 端口冲突 / OOM 等硬件层卡死 → 先重启 daemon：`pkill -f opencode && opencode serve`

**区分真卡死 vs spawn 失败**：

| 场景 | 指标 | 处理 |
|------|------|------|
| 真卡死 | 进程 alive + CPU < 1% + 长时间无进展 | kill + Planner 接管 |
| Spawn 失败 | bash wrapper 显示 PID 但 `pgrep -lf claude` 无真 binary | 检查 shell wrapper，避免 stdin redirect / bash shim。改 `nohup` background + log redirect 到 `/tmp/executor-*.log` |

**触犯后果**：Warning — 浪费预算 + 任务挂起。叠加 Lesson，内容："Executor 卡死止损经验：连续 2 次失败不再硬重试"。

---

## 红线 10：禁止跨会话隐式记忆

**规则**：Agent 决策与产出**禁止**依赖会话级（context window）记忆。所有"上轮结论、上次状态、之前怎么做的"必须落到文件并显式读取。

**Why**：会话级记忆 = 不可审计、不可回滚的隐式状态。在 CCC 这种"可重放、可验证"框架下，隐式记忆会破坏证据链：
- Verifier 拿到的不是 Executor 的真实输出，而是 AI 凭印象复述
- "上次我这么做的"成为不可追溯的依据
- 团队/未来会话无法复现推理过程 → 决策链断裂

**正例（合规）**：
```markdown
# .ccc/state.md 中显式列出最近任务
## 最近任务
| 2026-07-04 | audit-anti-implicit-memory | (report path) | 进行中 |
# 启动时显式读取
1. 读 .ccc/state.md  ← 唯一允许的"上下文输入"
2. 读最近 plan/report/verdict
3. 开工
```

**反例（违规）**：
```markdown
# ❌ "凭印象"复述上一会话
"上次我把 X 文件改了，所以我这次应该……"（无文件依据）
"我记得上次 verdict 是 PASS……"（无显式 grep 证据）
```

**机制钩子**：
1. **接力契约**：每个项目根必须有 `.ccc/state.md`，启动时**第一个读**
2. **显式 grep**：引用任何历史结论前必须 `grep -l <keyword> .ccc/`
3. **去重**：lessons.md 写入按 `(date, task_id)` 去重，避免噪声淹没真教训

**触犯后果**：Critical — Verdict/Plan 不可信。判定为自述无证据，重跑该 phase。

---

## 红线 11：Verifier 必须产出 verdict 文件（Lesson 28）

**规则**：步骤 D（Verifier 独立验收）**必须**将验收结论写入 `<workspace>/.ccc/verdicts/<task>.verdict.md`，且 Executor 的 `report.md` 必须显式包含 `> VERDICT: <verdict 文件路径>` 段引用。**禁止**仅在对话回执里口头声明"VERDICT: PASS"而无产物。

**Why**：Trae Solo CN 在 cost-report 全流程实测中暴露了这一漏洞：声称"步骤 D VERDICT: PASS（7/7）"，但 verdicts 目录 0 新文件、`/tmp` 无 verifier 日志、报告里无 VERDICT 段引用——**口头 PASS ≠ 真 PASS**。这是新一代 AI agent（IDE 包装）最常见的"自证幻象"模式：
- Agent 把"我应该做 X"当成"我做了 X"
- 用类似"全流程完成总结"的美化表掩盖未跑步骤
- 让用户/Planner 失去独立的验收证据链

**正例（合规）**：
```markdown
# .ccc/verdicts/add-ccc-cost-report.verdict.md 真实存在
## Verdict: PASS / FAIL / CONDITIONAL_PASS
## 检查项 (≥3 adversarial probes)
## Evidence（每项贴真实 stdout）
> VERDICT: .ccc/verdicts/add-ccc-cost-report.verdict.md
# report.md 末尾有此引用段
```

**反例（违规）**：
```markdown
# ❌ 仅有对话回执里"✅ VERDICT: PASS"表行
# ❌ 报告里"全部完成总结"列出 5/5 但 verdicts 目录为空
# ❌ report.md 末尾无 `> VERDICT:` 引用段
```

**机制钩子**：
1. **Planner 红线 8 加码**：Planner 看到 report.md 缺 VERDICT 引用即停下要求补救
2. **Verifier 模板硬要求**：每次 Verifier prompt 末尾必须写一句"将结论写到 .ccc/verdicts/<task>.verdict.md，退出前用 ls 验证文件存在"
3. **报告模板修订**：`templates/report.report.md` 加 `> VERDICT:` 段为必填（不是可选）

**触犯后果**：Critical — 视为步骤 D 未完成，整个 CCC 任务回退到 Executor 阶段后重跑。

---

## 红线 12：禁止 agent 自主启用 CCC（Lesson 28 配套）

**规则**：Agent **禁止**自行判断"现在该走 CCC 流程"并主动启用 Planner/Executor/Verifier 三角色流水线。CCC 流程的启用**必须**由用户显式触发（"走 CCC"、"按 CCC 流程做"、"补一次验收"等明确指令）。

**Why**：
- 用户上下文：CCC 流程引入额外开销（4 文件契约 + Verifier 独立 session），不是每个任务都需要
- 如果 agent 自行启用，会出现"判断错" + "用户被绕过"双重问题——用户可能想要更轻量的处理方式
- 用户决策权优先于 agent 自主判断（与 `references/red-lines.md` 整体定位一致）

**正例（合规）**：
- 用户说"这个 bug 走 CCC 修一下" → Planner 启动 → 写 plan → 跑 Executor
- 用户说"补一次验收流程" → Planner 启动补验 phase
- 用户说"按 Lesson 11 的 checklist 自检" → Planner 启动自检 phase

**反例（违规）**：
- ❌ Agent 看到任务多文件 → 自行启用 CCC（用户没要求）
- ❌ Agent 看到"用户授权 + Executor 已知失败" → Planner 越界 commit（Lesson 8 / 11 已禁）
- ❌ Agent 在自主修复过程中悄悄建 `.ccc/plans/*.plan.md`（无用户授权）

**机制钩子**：
1. CLAUDE.md / SKILL.md 头部写明"CCC 启用 = 用户显式触发"
2. Planner session 启动时**先**确认 `.ccc/state.md` 中"用户决策点"段有用户指令痕迹
3. Verifier session 启动时**先**确认 `.ccc/plans/<task>.plan.md` 存在（即 Planner 已走完流程）

**触犯后果**：Warning — 用户可能被绕过决策。立即停止 CCC 流程，回到单角色直接处理模式，由用户重新决策。

---

### 红线 13（v0.6 watchdog 子条，已并入下方 v0.7-slim 主条）：调度器启动前必须跑 watchdog

> 本节内容已并入下方"红线 13（v0.7-slim 配套）"主条作为子条保留。本占位段仅作历史指针，不再重复规则。

---

#### 红线 18：飞轮候选必须经过人工 review 才合并

- **Why**：AI 自动归纳失败模式容易"伪发现"——把一次性 / 边缘 case / 项目专属问题误判为通用模式
- **机制**：`scripts/flywheel-scan.py` 只生成 `.ccc/abnormal-reports/flywheel-candidate-<date>.md`，**不直接写** `references/red-lines.md`
- **触犯后果**：Warning — 减少人工 gate 必经入口；如果直接合入，1 周内回滚

#### 红线 19：跨设备 / 跨 session 必须有独立 Verifier 验收（v1.0 配套）

- **Why**：开发者自检容易产生"自证幻象"，跨视角才能发现盲区（abc v1.0 PoC 实证）
- **机制**：
  1. M1 写代码后，**至少 1 个独立 session** 跑验收（Mac2017 / 不同 IDE / 不同模型）
  2. Verifier 输出**必须**写 `<workspace>/.ccc/verdicts/<task>.verdict.md` 文件（红线 11）
  3. 文件 ≥ 50 行、含 ≥3 adversarial probes、末行 `## VERDICT: PASS|FAIL|CONDITIONAL_PASS`
- **触犯后果**：Critical — 视为 executor-only 流程，等同于不验收

#### 红线 20：跨设备 bash 脚本必须用 v3 portability 模板（v0.5 配套，实测 Lesson 29）

- **Why**：v3 之前的 `bash -c '...$VAR...'` 单引号模式不展开变量，跨设备立刻挂
- **机制**：跨设备 / 跨用户 / 跨路径执行的 bash 脚本**禁止**单引号 `bash -c` 嵌套 `$VAR`
- **正确模板**：
  ```bash
  check "X" "grep -q foo \$ABC_ROOT/file"   # 双引号让外层 bash 展开 \$VAR
  # 或
  check "X" "cd \$ABC_ROOT && grep -q foo file"   # 单一 shell 调用
  ```
- **触犯后果**：Critical — 跨设备运行必定 FAIL（已实测验证）

---

## OpenCode 进程管理红线（v0.8 配套）

> v0.8 起 CCC 改用 OpenCode CLI 作执行器，三个红线配套：
> **opencode 进程是最重的子进程（M1 8GB 内存敏感）**，必须严管。

#### 红线 X1：OpenCode 进程池最多 3 并发

- **规则**：任意时刻，**全局 opencode exec 子进程数 ≤ 3**。超出由 `opencode-pool.py` 排队等，**不杀不抢**。
- **Why**：
  - M1 8GB 内存紧张，4+ opencode 进程可能 OOM
  - 多 phase 并发数 > 3 收益边际递减（人眼也看不过来）
  - 抢占式调度会让 phase 状态丢失（被杀的 phase 没机会写完 report）
- **机制**：`scripts/opencode-pool.py` 用 `asyncio.Semaphore(3)` 硬限；`--max-parallel > 3` 拒绝执行
- **触犯后果**：Warning — 池自动排队，phase 慢但不会丢；改硬塞的脚本直接删除

#### 红线 X2：每 phase 必杀 opencode 进程

- **规则**：每个 phase **结束后**（成功 / 失败 / 超时 / 异常）**必须**杀 opencode 子进程（先 TERM，5s 后 KILL）。**禁止**"等它自己退出"。
- **Why**：
  - opencode exec 是子进程，stdin 关闭后会退出，但**不一定**——某些场景下 hung
  - 残留进程 = 内存泄漏 + 端口占用 + 下次启动污染
  - 多个残留累积就是"opencode 占满 8GB"的根因
- **机制**：
  1. `scripts/opencode-exec.py` 用 `try/finally` 块兜底杀进程
  2. `scripts/opencode-watchdog.sh` 扫 `~/.ccc/opencode-pids/*.pid` 兜底
  3. PID 文件启动时写、结束删（不论成败）
- **触犯后果**：Critical — 残留 > 0 = 红线违反，watchdog 启动即清

#### 红线 X3：OpenCode 启动前必跑残留 watchdog

- **规则**：`scripts/ccc-exec-launcher.sh` **第一步**（在钩子之前）必跑 `bash scripts/opencode-watchdog.sh`。watchdog 退出码非 0/3 → launcher 立即 exit。
- **Why**：
  - 上次未清的残留进程 = 这次启动的环境污染源
  - watchdog 是"开机自检"，必须每次都跑（不是一次性）
- **机制**：
  - `ccc-exec-launcher.sh` Step 1 = `opencode-watchdog.sh`
  - watchdog exit 0/3 = 干净/已自清 = 继续
  - watchdog exit 1/2 = 残留 / 严重 = 阻断 + L2 通知
- **触犯后果**：Critical — 跳过 watchdog = 等同于盲跑，launcher 无效

**红线 X1/X2/X3 验证清单**（每次重构必跑）：

```bash
# 1. 池上限（应 ≤ 3）
python3 -c "
import asyncio, subprocess
async def r():
    p = await asyncio.create_subprocess_exec('sleep', '5')
    return p.pid
async def m():
    return await asyncio.gather(*(r() for _ in range(5)))
print('pids:', asyncio.run(m()))
"  # 同时跑 5 个 opencode exec 应只有 3 真在跑

# 2. 必杀（启动 + 强杀 phase 后 pid 文件不存在）
ls ~/.ccc/opencode-pids/  # 期望空

# 3. 启动前 watchdog
bash scripts/opencode-watchdog.sh; echo "exit=$?"  # 期望 0
```

---

## 红线 13（v0.7-slim 配套）：禁止未使用路线代码

**规则**：`scripts/` + `tests/` + `references/adapters/` 中**禁止保留**"路线预留"代码——任何只为未来功能、不被当前 plan/profile/state.md 显式使用的脚本、测试、文档，必须删除或迁出。

**Why**（Lesson 29）：
- v0.5–v1.0 期间，路线图（cluster-bus / dispatch / flywheel / ZCode adapter / IDE 定时）写进了 docs/，但本地 4 窗口日常跑 CCC 根本用不上
- 结果：80+ 文件中有 ~50% 是"路线预留"代码，从未被任何 user 触发
- 维护负担 + 测试噪声 + 红线违反风险都来自这些死代码
- "路线 = 文档里的文字描述"，**不是 `scripts/` 里的真实代码**

**机制钩子**：
1. **新增脚本必须配引用证据**：每个 `scripts/*.sh` / `*.py` 在 PR 中必须贴"今天被谁调用"的 grep/git log 证据（`scripts/ccc` wrapper / `phases.json` / 测试 / hooks）
2. **adapter md 准入**：新增 `references/adapters/runtime-*.md` 必须先有 ≥1 个用户实测过的 IDE 配置 + 截图，否则不收
3. **测试是为今天的代码写的**：删除某个功能 → 同步删其所有测试，**禁止**保留"为未来测试"占位
4. **每 phase precheck 必跑**：
   ```bash
   find scripts tests -type f \( -name "*.sh" -o -name "*.py" \) | \
     xargs grep -lE "(cluster-bus|ccc-dispatch|flywheel)" 2>/dev/null
   ```
   返回空才算通过（v0.7 之后的 phase 全套此检查）

**正例（合规）**：
- v0.7-slim 精简后，`scripts/` 从 30+ 个脚本降到 8 个核心脚本，每个都有今天的引用证据（grep `ccc-exec-commit.sh` 在 `scripts/ccc` / `tests/` / `references/red-lines.md` 都有命中）
- `references/adapters/` 从 7 个 md 降到 1 个（`runtime-opencode.md`），只覆盖今天实测可用的 IDE

**反例（违规）**：
- ❌ "v0.8 路线会用到，先留着" → 删，今天没用就是死代码
- ❌ "也许未来有用户用 Cursor，先写好 adapter" → 删，等真有用户再写
- ❌ "测试先留着，万一以后加回来" → 删，git history 永远可查
- ❌ "成本报告以后做 SaaS 会用到" → 删，按需重写更简单

**触犯后果**：Warning → 该 phase 无效，删多余代码后重跑。Critical → 整个 plan 回退到精简前重做。

**v0.6 子条（已并入主线）**：调度器启动前必须跑 watchdog。原 v0.6 期间作为独立红线 13 发布，v0.7-slim 精简后并入本条作为调度器场景的强制要求：
- 任何以"调度循环 / 自动 cron / launchd / GitHub Actions"形式运行的 CCC Executor（典型: `scripts/ccc-scheduler.sh`、`examples/scheduler/ccc-queue.plist`），**启动主循环前必须**先跑 `bash scripts/executor-watchdog.sh`，watchdog 非零退出 → 立刻 exit
- `examples/scheduler/ccc-queue.plist` 的 `ProgramArguments` 第一项必须是 `ccc-scheduler.sh`（或带 watchdog 等效兜底），**禁止**裸 `claude -p` 启动 Executor
- 调度器场景 v0.7-slim 后已无活跃用户，本子条作为历史存档保留（红线 13 主条"无使用 = 删"的例外说明）

---

## 红线 14：Executor 必须配 monitor + 5min 轮询（v0.7d-prime 配套）

**规则**：任何 Executor 任务启动时**必须**同时起 tmux monitor 窗口 + 5 分钟轮询进程。两者缺一即视为盲跑。

**Why**：
- v0.5–v0.7 期间，Executor 启动后用户经常需要手动 `tmux capture-pane` 查进度，体验差且容易漏看异常
- 5 分钟轮询可自动检测完成信号（`❯` prompt + 无 `esc to interrupt`），减少手动检查
- Monitor 窗口提供"全景视图"（每 10s 刷新所有窗口尾部输出），单窗口轮询看不到其他窗口状态

**机制钩子**：
1. **三件套入口**：所有 Executor 任务必须通过 `bash scripts/ccc-exec-launcher.sh <window> <prompt-file>` 启动，禁止裸 `claude --bare` 启动
2. **Monitor 幂等**：脚本检测到 monitor 窗口已存在则跳过，不重复开窗
3. **Poll 自动终止**：检测到完成信号（`❯` prompt + 无 `esc to interrupt`）后自动 break，不残留后台进程
4. **失败兜底**：若 Poll 异常退出，下次 Executor 启动必须由 launcher 重新拉起（不会自动恢复）

**正例（合规）**：
```bash
bash scripts/ccc-exec-launcher.sh 1 /tmp/executor-prompt.txt
# 等价于：
#   bash scripts/ccc-monitor.sh claude-code
#   tmux send-keys -t claude-code:1 "cat /tmp/executor-prompt.txt | claude --bare --model deepseek-v4-flash" Enter
#   nohup bash scripts/ccc-poll.sh 1 claude-code 300 &
```

**反例（违规）**：
- ❌ 裸 `tmux send-keys "claude --bare" Enter` 起 Executor（没 monitor 也没 poll）
- ❌ 仅开 monitor 但不跑 poll（无法自动检测完成）
- ❌ 仅跑 poll 但没 monitor（看不到其他窗口状态）

**触犯后果**：Warning — 该 Executor 任务视为盲跑，报告需在 Lessons 段记录"下次必须用 launcher"

---

## 红线 15：轮询进程完成自动终止（v0.7d-prime 配套）

**规则**：`scripts/ccc-poll.sh` 检测到完成信号后**必须**自动 `break` 并退出。下次 Executor 任务必须重新调用 launcher 拉起新的 poll。

**Why**：
- Poll 进程若不自动终止，会一直占着 sleep/grep 循环直到手工 kill
- 同一窗口若启动新一轮 Executor，旧 poll 还会捕获新 Executor 的 pane，污染完成判断
- 自动终止 + 重新拉起 = 每次任务独立状态，避免跨任务串扰

**机制钩子**：
1. **完成信号定义**：pane 最后 5 行同时满足 `❯`（prompt 符）+ 无 `esc to interrupt`（无运行中提示）
2. **自动 break**：检测到完成信号后写入 `/tmp/poll-final-<ts>.txt` → break → 退出码 0
3. **重启契约**：下次 Executor 启动必须由 `ccc-exec-launcher.sh` 重新起 poll，不依赖自动恢复
4. **PID 记录**：`/tmp/poll-<WINDOW>.pid` 记录当前 poll PID，便于手工 `kill -9` 兜底

**正例（合规）**：
```bash
# poll 内部：检测到完成信号
if echo "$PANE" | grep -q "❯" && ! echo "$PANE" | grep -q "esc to interrupt"; then
  echo "[poll] 完成检测 elapsed=${ELAPSED}s"
  echo "$PANE" > "/tmp/poll-final-$(date +%s).txt"
  break
fi
```

**反例（违规）**：
- ❌ Poll 检测到完成信号后不 break，继续 sleep → 残留后台进程
- ❌ Poll 检测到完成信号后 `kill -9 <executor_pid>`（红线 15 只要求 poll 自身退出，不要求杀 Executor；杀 Executor 由红线条 9 处理）

**触犯后果**：Warning — poll 残留导致下一轮 Executor 状态判断污染。需手工 `kill $(cat /tmp/poll-<WINDOW>.pid)` 后重跑。

---

## OpenCode 进程管理红线（v0.8）

> v0.8 起 CCC 改用 OpenCode CLI 作执行器，三个红线配套：
> **opencode 进程是最重的子进程（M1 8GB 内存敏感）**，必须严管。

#### 红线 X1：OpenCode 进程池最多 3 并发

（已在表中，详见 v0.8 段）

#### 红线 X2：每 phase 必杀 opencode 进程

（已在表中，详见 v0.8 段）

#### 红线 X3：OpenCode 启动前必跑残留 watchdog

（已在表中，详见 v0.8 段）

---

## 6 角色 + 看板系统红线（v0.16）

> v0.16 起 CCC 改 6 角色定时开发系统（product/dev/reviewer/tester/ops/kb），
> 任务在 6 列看板流转（backlog → planned → in_progress → testing → verified → released）。
> 三个红线配套。

#### 红线 X4：每 phase 必走看板流转

- **规则**：任何任务必走 6 列看板，不可跳列。backlog → planned → in_progress → testing → verified → released 顺序强制。
- **Why**：
  - 跳列（如 backlog 直接 → testing）绕过 reviewer/tester 质检 = 不可见 bug 进远端
  - 看板是 6 角色的"工作清单"，跳列 = 跳过对应角色的责任
- **机制**：
  1. `scripts/ccc-board.py` 提供 `move_task(from, to)` API，强制调用
  2. launchd 6 plist 各扫自己该扫的列（product 看 backlog，dev 看 planned+in_progress，依此类推）
  3. 任何 task 在某列停留 > N 天 → ops 告警
- **触犯后果**：Critical — 跳过 reviewer/tester 直接 released 的 task，强制回退到 testing 重检

#### 红线 X5：6 角色 plist 必装

- **规则**：`com.ccc.{product,dev,reviewer,tester,ops,kb}` 6 个 launchd plist 必须装上。
- **Why**：6 角色是 v0.16 核心，缺一个 = 流程断链
  - 缺 product：backlog 永远不处理
  - 缺 dev：plan 写完不写代码
  - 缺 reviewer/tester：代码不质检
  - 缺 ops：异常无告警
  - 缺 kb：verified 永远不 release
- **机制**：
  1. `bash scripts/install-ccc-roles.sh` 一键装 6 plist
  2. `launchctl list | grep com.ccc` 应返 6 行（+ flywheel-scan 第 7 行）
  3. ops role 每 30min 检查 plist 状态，缺一个 → L2 告警
- **触犯后果**：Critical — 缺哪个角色，那个角色的功能全断

#### 红线 X6：角色频率不许改

- **规则**：

| 角色 | 频率 | StartInterval |
|------|------|---------------|
| product | 4h | 14400s |
| dev | 30min | 1800s |
| reviewer | 2h | 7200s |
| tester | 4h | 14400s |
| ops | 30min | 1800s |
| kb | 每天 23:00 | StartCalendarInterval |

- **Why**：频率 = 老板拍板（v0.16 拍板）。改频率 = 改老板意图 = 违规
- **机制**：
  1. `scripts/install-ccc-roles.sh` 写死这些值
  2. 任何 `StartInterval` / `StartCalendarInterval` 改动需老板显式同意
  3. `ccc-board.py ops role` 校验 plist 频率与本表一致
- **触犯后果**：Critical — 改频率 = 改产品决策，强制还原 + 写 abnormal-report
