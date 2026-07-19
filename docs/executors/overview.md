# 执行器总览 — 对话 vs 看板

> 第二步契约。架构对齐 2026-07-19：M1 = 对话脑；Mac2017 = 编排手。慢体验另议。

## 两路互不混淆

```text
M1 对话 / 对齐（Desktop + sidecar）
  → loop-code cli (arm64, M1 本机 vendor/loop-code/)
  → ai-loop-router :4000 (Mac2017)

Engine 看板开发（Mac2017）
  → product 扇出 = Claude Code
  → dev 写码 = OpenCode CLI
  → ai-loop-router :4002
```

| 路径 | 默认执行器 | 如何切换 |
|------|------------|----------|
| M1 对话（sidecar `:7788`） | **loop-code**（arm64） | `CCC_CLAUDE_BIN` 或 `CCC_EXECUTOR=loop-code` → [`loop-code.md`](loop-code.md) |
| Engine product 扇出（2017） | **Claude Code** | `scripts/board/roles/product.py` → `_product_session`；不可换 OpenCode |
| Engine dev 写码（2017） | **OpenCode** | 本步不切换；仍走 [`OpenCodeExecutor`](../../scripts/_executor.py) |

## 解析入口

统一：[`scripts/_claude_cli.py`](../../scripts/_claude_cli.py) → `resolve_claude_cli()`  
M1 sidecar：[`scripts/ccc-agent-sidecar.sh`](../../scripts/ccc-agent-sidecar.sh) 默认 `CCC_EXECUTOR=loop-code`  
Hub（2017）：不再需要对话 CLI（`/api/chat` 已删）。

## Server 上客户端指向

| 工具 | Server（2017）应指向 |
|------|----------------------|
| OpenCode（dev 写码） | `provider.loop.options.baseURL=http://127.0.0.1:4002/v1` |
| Claude Code（product 扇出） | `ANTHROPIC_BASE_URL=http://127.0.0.1:4000` |

勿再指向 Client（M1）IP；中转迁走后会导致 OpenCode 长时间挂起。

## M1 上客户端指向

| 工具 | M1 应指向 |
|------|----------|
| sidecar loop-code | `ANTHROPIC_BASE_URL=http://192.168.3.116:4000`（plist 默认） |

## 冒烟

```bash
# M1 对话
bash scripts/smoke-desktop-agent.sh
bash scripts/smoke-desktop-stable.sh

# 2017 编排
bash scripts/smoke-executor-stack.sh
SMOKE_CLAUDE_P=1 bash scripts/smoke-executor-stack.sh
```
