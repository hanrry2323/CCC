# Executor 启动提示词模板

> 标准 `claude -p` 启动 Claude 时的提示词。所有 `<...>` 占位符替换后使用。
> 模板在 `~/program/CCC/templates/executor-prompt.template.md`，新项目直接复制。

---

## ⚠️ 启动前必读：`claude -p` 的真实行为（Lesson 27）

`claude -p` / `claude --print` **不是 prompt 参数**，是**非交互打印模式开关**。真正的 prompt **必须通过 stdin 喂入**。

| 写法 | 行为 |
|---|---|
| `claude -p "hi"` | ❌ print 模式打开，但 stdin 空，打印默认开场白（"老板好。今天要做什么？"） |
| `cat /tmp/p.txt \| claude -p` | ✅ print 模式 + stdin 真有内容 |
| `claude -p < /tmp/p.txt` | ✅ 等价 |
| `claude -p "$(cat <<EOF ... EOF)"` | ✅ 等价（command substitution 当 stdin pipe） |

**快速 sanity check**（任何不确认的时候跑这条）：

```bash
echo "用一句话回答：1+1=?" | ANTHROPIC_BASE_URL=http://127.0.0.1:4000 claude -p
# 期望输出：2（或类似的简短回答）
# 不期望输出："老板好" 等默认开场白
```

> 历史上 Trae / opencode / 新会话都因为写成 `claude -p "..."` 而把 prompt 当成 silently-drops 误以为是中转站 hang。Lesson 27 沉淀这条。

**模板内所有 `claude -p` 调用都是 stdin 形式，可以直接用。**

---

## ⚠️ 前置门控（由 opencode pipeline 自动处理）

**ccc-precheck.sh / ccc-finish.sh / executor-watchdog.sh 已移除**。
这些门控目前由 opencode pipeline 自动处理：

- **前置门控**：`ccc-board.py dev_role()` 内置了 .done/PID/retry 检查
- **后置门控**：opencode-runner.sh 写 .exitcode/.done，ccc-exec-commit.sh 处理 commit
- **范围检查**：`reviewer_role()`（testing → verified）按 plan scope 做 py_compile 范围验证

---

## ⚠️ Executor 不直接 git commit（v1.2.0 新增 · T1.6 配套）

**Executor 退出后, commit 由外部脚本 `ccc-exec-commit.sh` 自动化处理**（红线 4 + 8 + 15 配套):

```bash
# Executor 退出后, Planner 跑:
ccc commit <workspace> <task>           # 处理所有待 commit phase
ccc commit <workspace> <task> --phase N # 仅指定 phase
```

**禁越界**:
- ❌ Executor 自己 `git add` + `git commit` = 触犯红线 4/8
- ❌ Planner 跳过 `ccc commit` 直接 `git commit` = 触犯红线 4/8 + 失去 commit hash 自动回写
- ✅ 唯一通路: Executor 把改动放在 working tree (无 staged), Planner 调 `ccc commit` 兜底

---

## 标准模板

```bash
ANTHROPIC_BASE_URL=http://127.0.0.1:4000 \
claude -p "$(cat <<'EOF'
你是 CCC 框架的 Executor（独立 Claude session，不是 Planner）。

启动顺序（必读）：
1. 读 ~/program/CCC/CLAUDE.md — CCC 流程、术语、红线
2. 读 <workspace>/.ccc/profile.md — 项目背景
3. 读 <workspace>/.ccc/plans/<task>.plan.md — 任务 plan
4. 读 <workspace>/.ccc/phases/<task>.phases.json — phases 初始状态

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

## 超时/失败恢复（v0.31）

如果 session 因超时、LLM 中断、系统异常终止：

1. 读 `<workspace>/.ccc/state.md` 确认当前 phase 和进度
2. `git status --short` 检查 working tree——有未提交改动则逐文件确认完整性
3. 不完整的改动 → `git checkout -- <file>` 回退到上一个已知干净状态
4. phases.json 的当前 phase 标记为 `pending`（移除部分 done 标记）
5. 重新提交 report 到 `<workspace>/.ccc/reports/<task>.report.md`，标记 phase 为 retry N
6. **不要跳过自检**——恢复后仍需全部自检 PASS 才能退出

**完成执行顺序**（Lesson 4 修复 · 必须按此顺序）：
```
Step 0（前置）：确认 working tree 干净（仅 plan 声明文件的改动）
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

# 自检 4（scope 检查 — 零容差路径集制）：改文件 ⊆ phases.json scope 集合
# 逐文件验证，不允许 scope 外任何文件
changed_files=$(git diff --name-only 2>/dev/null || true)
scope_file="<workspace>/.ccc/phases/<task>.phases.json"
if [ -n "$changed_files" ]; then
  echo "$changed_files" | python3 -c "
import json, sys
changed = set(line.strip() for line in sys.stdin if line.strip())
with open('${scope_file}') as f:
    data = json.load(f)
rows = data if isinstance(data, list) else [data]
allowed = set()
for p in rows:
    allowed |= set(p.get('scope', []) or [])
extra = changed - allowed
if extra:
    print('FATAL: extra files:', ' '.join(sorted(extra)))
    sys.exit(1)
print('PASS: all', len(changed), 'changed files in scope (' + str(len(allowed)) + ' allowed)')
" || echo "FATAL: scope check failed"
else
  echo "PASS: no changed files"
fi

# 自检 5（phase 完成验证 — 防跳阶段）：done 的 phase 必须有 commit_message
python3 -c "
import json
with open('${scope_file}') as f:
    data = json.load(f)
rows = data if isinstance(data, list) else [data]
for p in rows:
    s = p.get('status', '')
    if s == 'done' and not p.get('commit_message'):
        print('FATAL: phase', p.get('phase'), 'done but no commit_message')
        exit(1)
print('PASS: all done phases have commit_message')
" || echo "FATAL: phase completion check failed"

# 自检 6（phase 数对账）：phases.json status=done 行数 = plan phase 数
plan_phases=$(grep -cE '^## Phase|^- Phase' <workspace>/.ccc/plans/<task>.plan.md 2>/dev/null || echo 1)
done_phases=$(grep -c '"status":\s*"done"' <workspace>/.ccc/phases/<task>.phases.json 2>/dev/null || echo 0)
[ "$done_phases" -ge "$plan_phases" ] && echo "phase count OK ($done_phases ≥ $plan_phases)" || echo "FAIL"
```

**自检输出格式**（每条自检必须 echo PASS 或 FATAL）：
```
[Self-check 1/6] git status (no staged): PASS
[Self-check 2/6] phases.json: PASS
[Self-check 3/6] report.md exists: PASS
[Self-check 4/6] file scope (zero-tolerance): PASS
[Self-check 5/6] phase completion: PASS
[Self-check 6/6] phase count match: PASS
ALL SELF-CHECKS PASSED — 退出 session
```

**所有 6 条自检必须全部输出 PASS，report.md 末尾必须包含完整自检输出**。dev_role_check_complete 会在 report.md 中 grep "ALL SELF-CHECKS PASSED" —— 找不到则视同 phase 失败，不回 testing，直接退回 retry。

如果任一自检输出 FATAL 或 FAIL：**不准退出**。必须先修复（创建 report / 检查 working tree / 更新 phases.json），再重跑自检，直到全部 PASS。

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

> 调用说明/变量替换表/参数说明 → 见同目录 `executor-prompt.README.md`