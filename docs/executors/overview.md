# 执行器总览 — 对话 vs 看板

> 第二步契约。Server = Mac2017。慢体验另议。

## 两路互不混淆

```text
Hub 对话 / 对齐
  → Claude 兼容 CLI（默认 PATH `claude`）
  → ai-loop-router :4000

Engine 看板开发（dev）
  → OpenCode CLI
  → ai-loop-router :4002
```

| 路径 | 默认执行器 | 如何切换 |
|------|------------|----------|
| Hub 对话 | 官方 `claude` | `CCC_CLAUDE_BIN` 或 `CCC_EXECUTOR=loop-code` → [`loop-code.md`](loop-code.md) |
| Engine 开发 | OpenCode | 本步不切换；仍走 [`OpenCodeExecutor`](../../scripts/_executor.py) |

## 解析入口

统一：[`scripts/_claude_cli.py`](../../scripts/_claude_cli.py) → `resolve_claude_cli()`  
Hub：[`scripts/chat_server/config.py`](../../scripts/chat_server/config.py) `require_claude_bin()`

## Server 上客户端指向

| 工具 | Server（2017）应指向 |
|------|----------------------|
| Claude / Hub | `ANTHROPIC_BASE_URL=http://127.0.0.1:4000` |
| OpenCode | `provider.loop.options.baseURL=http://127.0.0.1:4002/v1` |

勿再指向 Client（M1）IP；中转迁走后会导致 OpenCode 长时间挂起。

## 冒烟

```bash
bash scripts/smoke-executor-stack.sh
# 可选短对话：
SMOKE_CLAUDE_P=1 bash scripts/smoke-executor-stack.sh
```
