# 执行器总览 — 对话 vs 看板

> 架构对齐 2026-07-20：模型**直连上游**；ai-loop-router 已退役。

## 两路互不混淆

```text
M1 对话 / 对齐（Desktop + sidecar）
  → loop-code cli (arm64)
  → MiniMax Anthropic（https://api.minimaxi.com/anthropic）

Engine 看板开发（Mac2017）
  → product 扇出 = Claude → MiniMax
  → dev 写码 = OpenCode → 讯飞 xfyun/code
```

| 路径 | 默认执行器 | 如何切换 |
|------|------------|----------|
| M1 对话（sidecar `:7788`） | **loop-code**（arm64） | `CCC_CLAUDE_BIN` 或 `CCC_EXECUTOR=loop-code` → [`loop-code.md`](loop-code.md) |
| Engine product 扇出（2017） | **Claude** → MiniMax | `scripts/board/roles/product.py`；不可换 OpenCode |
| Engine dev 写码（2017） | **OpenCode** → 讯飞 | [`OpenCodeExecutor`](../../scripts/_executor.py) |

## 解析入口

统一：[`scripts/_claude_cli.py`](../../scripts/_claude_cli.py) → `resolve_claude_cli()` / `resolve_anthropic_model()`  
M1 sidecar：[`scripts/ccc-agent-sidecar.sh`](../../scripts/ccc-agent-sidecar.sh) 默认 `CCC_EXECUTOR=loop-code`  
Hub（2017）：不再需要对话 CLI（`/api/chat` 已删）。

## Server 上客户端指向

| 工具 | Server（2017）应指向 |
|------|----------------------|
| OpenCode（dev 写码） | `~/.config/opencode/opencode.json` → `xfyun/code`（讯飞直连） |
| Claude（product / reviewer） | `ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic` |

~~勿再配置 `:4000` / `:4002`。~~

## M1 上客户端指向

| 工具 | M1 应指向 |
|------|----------|
| sidecar loop-code | MiniMax 直连（`install-agent-sidecar-plist.sh` 默认） |

## 冒烟

```bash
# M1 对话
bash scripts/smoke-desktop-agent.sh
bash scripts/smoke-desktop-stable.sh

# 2017 编排
bash scripts/smoke-executor-stack.sh
SMOKE_CLAUDE_P=1 bash scripts/smoke-executor-stack.sh
```
