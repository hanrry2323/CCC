# 10 条红线 — CCC 协议不可触犯的约束

违反任何红线即记 Critical 违规。叠加入项目 `docs/lessons.md` 并触发修订流程。

---

## 红线 1：不动系统文件

**规则**：不修改项目源代码以外的任何系统文件（`.env`、密钥文件、`/etc/hosts`、系统日志、`/tmp/` 非本任务文件等）。

**Why**：系统文件影响面不可控——改错可能导致环境损坏或安全漏洞。`~/.claude/` 和 `~/.mavis/` 等 agent 配置也在此列（除非任务明确要求）。

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

**Why**：Mavis/Planner 跟踪进度依赖 phases.json。没有它 = 没有进度可见性。

**触犯后果**：Warning — Mavis 控制台无进度显示。Plan 不完整。CONDITIONAL_PASS 并补全。

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
| C6 | mavis session new | 不用 `mavis session new <agent>` 启动子会话（会导致非目标模型执行） |

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
1. 立即 `kill -TERM <claude_pid>`（超时 2s 未响应则 `kill -KILL`），或 `mavis session abort <session_id>`
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

## 红线违反处理流程

```
发现违规
  ├─ Critical → 立即停止所有操作
  │   ├─ 回滚相关 commit
  │   ├─ 记录到项目 docs/lessons.md
  │   └─ 重启对应 phase
  ├─ Warning → 记入 Verdict 的 Warning 段
  │   ├─ CONDITIONAL_PASS + 修订 v2
  │   └─ 修订中修复
  └─ Info → 记录到 Verdict 的 Info 段
      └─ 不驱动修订，仅备查
```
