# Phase1 brief — loop-code 配置切割（可执行）

> **对齐**：[`loop-code-ownership-cut.md`](loop-code-ownership-cut.md)  
> **范围**：仅 Phase1（文档已另文；本文管本轮代码）  
> **日期**：2026-07-21

---

## 目标

Desktop 热路径读写私有配置家；缺 loop-code 则失败，绝不静默用个人 `claude`。

## 改动清单

| 文件 | 改什么 |
|------|--------|
| `scripts/install-agent-sidecar-plist.sh` | plist `CLAUDE_CONFIG_DIR=${HOME}/.ccc/loop-code`；安装时 seed 目录 + 短 `CLAUDE.md` |
| `scripts/ccc-agent-sidecar.sh` | 前台同样 export `CLAUDE_CONFIG_DIR` |
| `scripts/ccc-agent-sidecar.py` | setdefault config dir；startup ensure dir；`/health` 增 `config_dir` |
| `scripts/_claude_cli.py` | `resolve_claude_cli(..., executor_strict=)` 或等价：sidecar 禁 PATH 回落 |
| `scripts/chat_server/config.py` | `CLAUDE_ENV` 白名单（非 `**os.environ`） |
| `scripts/smoke-desktop-agent.sh` | 断言 runtime + config_dir |
| `scripts/tests/test_claude_cli.py` | 严格模式单测 |

## 种子 `CLAUDE.md`（短版口径）

与 [`desktop-agent-identity.md`](desktop-agent-identity.md) 一致：Desktop 对话面产品搭档；定稿 epic；Engine 在 2017；禁止中转站/:4000 说法。

## 不做

- 卸载个人 Claude Code  
- 删/迁整个 `~/.claude`  
- 2017 换 loop-code 或 engine `CLAUDE_CONFIG_DIR`  
- 版本 bump（除非显式要求）  
- MCP/plugins UI

## 验收

```bash
bash scripts/install-agent-sidecar-plist.sh --start
curl -s http://127.0.0.1:7788/health
# 期望：agent_runtime=loop-code；config_dir 含 .ccc/loop-code

bash scripts/smoke-desktop-agent.sh

# 缺 cli：临时移走 vendor/loop-code/cli → chat/resolve 明确失败，不落到 PATH claude
```

## 回滚

重装旧 plist（无 `CLAUDE_CONFIG_DIR`）；`executor_strict` 关闭；私有目录可留。
