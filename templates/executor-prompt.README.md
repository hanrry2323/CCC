# Executor Prompt 模板使用说明

> 从 `executor-prompt.template.md` 剥离的使用文档。
> 模板本身是 prompt 内容，不包含这些调用方说明。

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
| `-p` / `--print` | ✅ | **非交互打印模式开关**（prompt 通过 stdin 喂入，**不是**跟在这个 flag 后） |
| `< /tmp/executor-prompt.txt` | ✅ | prompt 内容来源（bash heredoc / 文件 / pipeline 都行） |
| `--permission-mode bypassPermissions` | 推荐 | 跳过弹窗，自动审批 |

**注意**：
- `claude -p` 与 `claude --print` 等价（`-p` 是 `--print` 的简写）。`claude --help` 显示 `-p, --print` 都是合法参数。
- 提示词开头明确说"你不是 Planner"，避免 Claude 误把 Planner 当 Executor。
- 把红线写在 prompt 末尾提醒，Claude 容易回看。
- 超时按 `docs/execution-protocol.md` §Timeout 分级表 设置。

---

## 启动前必读：`claude -p` 的真实行为（Lesson 27）

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
