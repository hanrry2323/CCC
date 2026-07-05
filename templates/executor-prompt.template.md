# Executor 启动提示词模板

> 标准 `claude -p` 启动 Claude 时的提示词。所有 `<...>` 占位符替换后使用。
> 模板在 `~/program/CCC/templates/executor-prompt.template.md`，新项目直接复制。

---

## 标准模板

```bash
# Pre-launch watchdog — 检测 hang claude 进程 / stuck mavis session / 低内存
# Lesson 7 + Lesson 9 修复：避免新任务被旧的卡死状态污染
# 退出码：0=健康可启动 / 1=warning 让 caller 决定 / 2=严重建议放弃 / 3=已自动清理
bash ~/program/CCC/scripts/executor-watchdog.sh || {
  echo "[caller] watchdog returned $?, decide: continue / --force-kill / 放弃"
  exit $?
}

ANTHROPIC_BASE_URL=http://127.0.0.1:4000 \
claude -p "$(cat <<'EOF'
你是 CCC 框架的 Executor（独立 Claude session，不是 Planner）。

启动顺序（必读）：
1. 读 ~/program/CCC/CLAUDE.md — CCC 流程、术语、红线
2. 读 <workspace>/.ccc/profile.md — 项目背景
3. 读 <workspace>/.ccc/plans/<task>.plan.md — 任务 plan
4. 读 <workspace>/.ccc/phases/<task>.phases.json — phases 初始状态
5. **确认前置 watchdog 已通过**：如果收到 `[watchdog] warning` 警告但继续启动，
   必须在你的 report.md 顶部写"watchdog warning acknowledged"段，
   并在第一条改动前 echo `WATCHDOG_WARNING_ACKNOWLEDGED` 确认你已经看过这个警告。

按 plan 执行。完成后：
- 写实施报告到 <workspace>/.ccc/reports/<task>.report.md
- 更新 phases.json，把完成的 phase 标记为 done（多 phase 逐个追加），commit_message 填写 plan 的"Commit 计划"表对应消息
- **不执行 git commit**——commit 由外部脚本 `ccc-exec-commit.sh` 自动处理

**完成定义**（必须全部满足才能退出 session · Lesson 3 + Lesson 4 修复）：
1. **report.md 已写入并含全部验收结果**（前置 · Lesson 4 修复：先写报告再做事，避免"主工作做完就退"导致漏报告）
2. **working tree 已就绪**（`git status --short` 显示仅 plan 范围文件改动，无已暂存内容）
3. `phases.json` 对应 phase `status = done`，`commit_message` 字段已填写
4. **退出前自检**（见下方）全部 PASS

> **commit 由外部处理**：Executor 不执行 `git commit`，退出后 Planner 调用 `ccc-exec-commit.sh` 自动完成。
> 所有改动只需在 working tree 中存在即可，不要暂存或提交。

**完成执行顺序**（Lesson 4 修复 · 必须按此顺序）：
```
Step 0（前置 · Lesson 9 修复）：Caller 已跑 `executor-watchdog.sh`，如果返回 warning 必须在 report.md 顶部标注并 echo 确认
Step 1：先创建空的 report.md 框架（含验收表格骨架）
Step 2：执行 plan 的所有改动（不包含 commit——commit 由外部完成）
Step 3：填实 report.md（每条验收命令的证据输出）
Step 4：更新 phases.json status=done
Step 5：跑退出前自检
Step 6：自检通过 → 才准退出
```

**退出前必跑自检**（必须全部 PASS 才准退出 session）：
```bash
# 自检 1：working tree 仅改动 plan 范围文件（无已暂存内容）
git status --short  # 期望仅 plan 声明文件为未暂存修改，无 staged 内容

# 自检 2：phases.json 已 done
grep '"status"' <workspace>/.ccc/phases/<task>.phases.json  # 期望 "done"

# 自检 3：report.md 已存在且非空
ls <workspace>/.ccc/reports/<task>.report.md  # 期望文件存在
test -s <workspace>/.ccc/reports/<task>.report.md && echo "report non-empty"  # 期望 "report non-empty"

# 自检 4（plan 范围检查 · Lesson 13）：改文件 ⊆ phases.json scope 集合
# 统计 changed_files ≤ sum(scope) 而非 grep plan 文本（避免 plan 格式误报）
plan_scope_count=$(python3 -c "
import json
p = '<workspace>/.ccc/phases/<task>.phases.json'
try:
    d = json.load(open(p))
    files = set()
    for ph in d.get('phases', []):
        s = ph.get('scope') or ph.get('expected_files', [])
        files |= set(s)
    print(len(files))
except: print('0')
")
changed_files=$(git diff --name-only 2>/dev/null | wc -l | tr -d ' ')
count_safe=$(( plan_scope_count + 5 ))  # 容差：phases.json 可能缺失少数路径
[ "$changed_files" -le "$count_safe" ] && echo "file count OK ($changed_files ≤ scope ${plan_scope_count}, capped ${count_safe})" || echo "FAIL"

# 自检 5（phase 数对账）：phases.json status=done 行数 = plan phase 数
plan_phases=$(grep -cE '^## Phase|^- Phase' <workspace>/.ccc/plans/<task>.plan.md 2>/dev/null || echo 1)
done_phases=$(grep -c '"status":\s*"done"' <workspace>/.ccc/phases/<task>.phases.json 2>/dev/null || echo 0)
[ "$done_phases" -ge "$plan_phases" ] && echo "phase count OK ($done_phases ≥ $plan_phases)" || echo "FAIL"
```

**自检输出格式**（每条自检必须 echo PASS 或 FAIL）：
```
[Self-check 1/5] git status (no staged): PASS
[Self-check 2/5] phases.json: PASS
[Self-check 3/5] report.md exists: PASS
[Self-check 4/5] file count scope: PASS
[Self-check 5/5] phase count match: PASS
ALL SELF-CHECKS PASSED — 退出 session
```

如果任一自检 FAIL：**不准退出**。必须先修复（创建 report / 检查 working tree / 更新 phases.json），再重跑自检，直到全部 PASS。

红线（不要违反）：
- 不动 plan 范围外的文件（额外问题记入 report 但不修改）
- 不写 verdict（那是 Verifier 的活）
- 每个 phase 的改动在 working tree 中保持独立（外部脚本按 phase 逐条 commit）
- 不跳阶段更新 phases.json（pending → done 必须经过 in_progress）
- plan 里的"参考命令"是 hint，自己决定用什么命令实现
- **report.md 必须 Step 1 创建（前置）**，不能 Step 4 写
- **未跑自检 + 自检全 PASS = 不准退出 session**
EOF
)" --permission-mode bypassPermissions --max-budget-usd 10
```

---

## 变量替换表

| 占位符 | 替换为 |
|---|---|
| `<workspace>` | 项目根绝对路径（如 `/Users/apple/program/qx-observer`） |
| `<task>` | 任务简称（如 `migrate-agents-md-to-ccc`） |

---

## 参数说明

| 参数 | 必填 | 说明 |
|---|---|---|
| `-p "<prompt>"` | ✅ | 非交互模式启动，prompt 是自然语言指令 |
| `--permission-mode bypassPermissions` | 推荐 | 跳过弹窗，自动审批 |

**注意**：
- `claude -p` 与 `claude --print` 等价（`-p` 是 `--print` 的简写）。`claude --help` 显示 `-p, --print` 都是合法参数。
- 提示词开头明确说"你不是 Planner"，避免 Claude 误把 Planner 当 Executor。
- 把红线写在 prompt 末尾提醒，Claude 容易回看。
- 超时按 `~/program/CCC/docs/execution-protocol.md` §Timeout 分级表 设置。

---

## 调用示例

```bash
# qxo 项目 migrate-agents-md-to-ccc 任务
ANTHROPIC_BASE_URL=http://127.0.0.1:4000 \
claude -p "$(cat <<'EOF'
你是 CCC 框架的 Executor（独立 Claude session，不是 Planner）。

启动顺序（必读）：
1. 读 ~/program/CCC/CLAUDE.md — CCC 流程、术语、红线
2. 读 /Users/apple/program/qx-observer/.ccc/profile.md — 项目背景
3. 读 /Users/apple/program/qx-observer/.ccc/plans/migrate-agents-md-to-ccc.plan.md — 任务 plan
4. 读 /Users/apple/program/qx-observer/.ccc/phases/migrate-agents-md-to-ccc.phases.json — phases 初始状态

按 plan 执行。完成后：
- 写实施报告到 /Users/apple/program/qx-observer/.ccc/reports/migrate-agents-md-to-ccc.report.md
- 更新 phases.json，把 phase 1 标记为 done，commit_message 填写计划消息
- **不执行 git commit**——commit 由外部脚本处理

红线（不要违反）：
- 不动 plan 范围外的文件
- 不写 verdict（那是 Verifier 的活）
- 不跳阶段更新 phases.json（红线 5）
- plan 里的"参考命令"是 hint，自己决定用什么命令实现
EOF
)" --permission-mode bypassPermissions --max-budget-usd 10
```

---

## 配套资源

| 资源 | 文件 |
|---|---|
| 框架总纲 | `~/program/CCC/CLAUDE.md` |
| Plan 格式规范 | `~/program/CCC/docs/plan-spec.md` |
| Plan 模板 | `~/program/CCC/templates/plan.plan.md` |
| 项目档案 | `<workspace>/.ccc/profile.md` |
| Timeout 分级表 | `~/program/CCC/docs/execution-protocol.md` §Timeout 分级表 |
| Executor 红线清单 | `~/program/CCC/CLAUDE.md` §红线 |