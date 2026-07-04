# Runtime: claude -p (默认)

CCC Executor/Verifier 默认运行时。通过 `claude -p` 以非交互模式启动 Claude。

---

## 何时使用

- Executor 需要完全自主执行（无人工介入）
- Verifier 需要独立验收
- 任何需要 `free-code` 模型的 CCC 任务

## 安装

确保 `claude` CLI 已安装。通过中转站时设置 `ANTHROPIC_BASE_URL`：

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:4000
```

## 使用

```bash
# 创建 prompt 文件
cat > /tmp/<task>-executor.txt << 'PROMPT'
[Executor prompt 内容 — 包含 SKILL.md context + task spec]
PROMPT

# 启动 Executor
claude -p "$(cat /tmp/<task>-executor.txt)" \
  --permission-mode bypassPermissions \
  --max-budget-usd N

# 启动 Verifier（同上，但 prompt 要求 ≥3 adversarial probes）
claude -p "$(cat /tmp/<task>-verifier.txt)" \
  --permission-mode bypassPermissions \
  --max-budget-usd N
```

## 参数说明

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `-p` | prompt string（非交互式执行） | 从文件读取 |
| `--permission-mode` | 工具调用权限 | `bypassPermissions`（跳过每次确认） |
| `--max-budget-usd` | 最大预算 | 调研类 200，修补类 30-50，简单操作 20，push 5-30 |

## 预算参考

| 任务类型 | Phase 数 | 推荐预算 |
|----------|---------|----------|
| 调研 / 审计 | 6 phase | 200 USD |
| 修复 / 重构 | 1-3 phase | 30-50 USD |
| 简单文件操作 | 1 phase | 20 USD |
| Push / 部署 | 1 phase | 5-30 USD |

## 多 prompt 文件

复杂任务建议将 prompt 拆成多个文件：
- `/tmp/<task>-context.txt` — SKILL.md 方法 + 项目 profile
- `/tmp/<task>-plan.txt` — plan.md 全量内容
- `/tmp/<task>-executor.txt` — 最终拼接的 Executor prompt

## 注意事项

- `mavis session new` 会 fallback 到非 Claude 模型 → **绝对禁止**。始终用 `claude -p`
- 如果提示 "permission denied"，检查 claude binary 路径
- Subprocess 卡死处理见 `references/red-lines.md` 红线 9

---

## qxo 执行模式（替代 mavis cron）

> 当运行时环境为 qxo（Claude Code CLI，无 mavis daemon）时，适配以下方案。

### 完成通知

不用 mavis cron。用 Bash 工具的 `run_in_background` 机制：

```bash
# ❌ 错误：bash & 后台 + 等万能通知
claude -p "$(cat /tmp/prompt.txt)" ... > /tmp/executor.log 2>&1 &

# ✅ 正确：Bash 的 run_in_background 管理生命周期
# Bash 命令不带 &，用 --max-budget-usd 做上限
# claude 完成 → Bash 退出 → 系统通知
ANTHROPIC_BASE_URL=http://127.0.0.1:4000 \
claude -p "$(cat /tmp/prompt.txt)" \
  --permission-mode bypassPermissions \
  --max-budget-usd N
```

### 预算管理

不一次性给全部 budget。每个 phase 独立分配，避免"半路超预算停"：

| Phase 类型 | 预算 | 说明 |
|-----------|------|------|
| 单文件修复 | 5 USD | 改 ≤10 行 |
| 多文件修改 | 10 USD | 改 1-3 个文件 |
| 调研/审计 | 50 USD | 只读不写 |
| 新功能开发 | 20-30 USD | 按 complexity 定 |

### 自动验收链

executor 写 report.md → 自动启 verifier。用 Bash 链式调用来实现：

```bash
# Executor
claude -p "$EXECUTOR_PROMPT" ... --max-budget-usd 10 \
  && \
# Verifier（executor 成功后自动启）
claude -p "$VERIFIER_PROMPT" ... --max-budget-usd 5
```

### qxo 发单流程

```
qxo 厂长
  └── 写 plan.md + phases.json
       └── Bash run_in_background
            └── claude -p executor
                 ├── Phase 1 → commit
                 ├── Phase 2 → commit
                 ├── 写 report.md
                 └── exit 0 → 通知 qxo
                      └── qxo 读 report.md 写 verdict.md
```
