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
