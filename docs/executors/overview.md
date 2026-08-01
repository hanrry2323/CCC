# 执行器总览 — 对话 vs 看板

> 架构对齐 2026-08-01：**CCC Relay 已拆出 CCC 仓**，使用独立项目 `~/program/ai-loop-router`（端口 4100/4102）。  
> **槽位口径**：`loop-code` = 对话槽**槽位名**;OpenCode = 写码槽默认件;**ai-loop-router = 唯一模型调度网关**(三档 tier: flash/Pro/code)。定位 SSOT：[`loop-engineer-authority.md`](../product/loop-engineer-authority.md)「CCC Relay」+「三层架构与 loop-code 槽位化」。

## 两路互不混淆

```text
M1 对话 / 对齐（Desktop + sidecar → 本机 ai-loop-router :4100）
  → 对话槽 loop-code（现填 vendor cli · arm64）
  → ai-loop-router（三档 flash/Pro/code）→ upstreams.json 异构上游
  → fail-open: `CCC_RELAY_DIRECT_URL` / `~/.ccc/relay-direct.url`

Engine 看板开发（Mac2017 → M1 ai-loop-router :4100/:4102）
  → product 扇出 = Claude → M1 ai-loop-router :4100 → flash/Pro
  → dev 写码 = OpenCode → M1 ai-loop-router :4102 → code
  → fail-open: 同上直连文件（绝不 block；MiniMax-M3 已退役）
```

| 路径 | 默认执行器 | 模型调度 | 如何切换 |
|------|------------|----------|----------|
| M1 对话（sidecar `:7788`） | **loop-code**（arm64） | **本机 ai-loop-router** `:4100`（`flash`） | `CCC_ANTHROPIC_BASE_URL` 改其他；fail-open → relay-direct.url |
| Engine product 扇出（2017） | **Claude** → relay → flash/Pro | **M1 ai-loop-router** `:4100` | `AGENT_PLANNER_BASE_URL` env |
| Engine dev 写码（2017） | **OpenCode** → relay **M1** `:4102` | **M1 ai-loop-router** | `OPENCODE_MODEL=loop/flash` |

## 解析入口

统一：[`scripts/_claude_cli.py`](../../scripts/_claude_cli.py) → `resolve_claude_cli()` / `resolve_anthropic_model()`  
M1 sidecar：[`scripts/ccc-agent-sidecar.sh`](../../scripts/ccc-agent-sidecar.sh) 默认 `CCC_EXECUTOR=loop-code`  
Hub（2017）：不再需要对话 CLI（`/api/chat` 已删）。

## Server 上客户端指向

| 工具 | Server（2017）应指向 |
|------|----------------------|
| OpenCode（dev 写码） | **M1 ai-loop-router `:4102`**（`OPENCODE_MODEL=loop/flash`）；探活失败自动切 `~/.config/opencode/opencode.direct.json` 直连 |
| Claude（product / reviewer） | **M1 ai-loop-router** `AGENT_PLANNER_BASE_URL=http://192.168.3.140:4100`；fail-open → `CCC_RELAY_DIRECT_URL` / `~/.ccc/relay-direct.url` |
| Engine 环境 | Engine 启动时自动设 `AGENT_PLANNER_BASE_URL`，无需手动配置 |

## M1 上客户端指向

| 工具 | M1 应指向 |
|------|----------|
| sidecar loop-code | **本机 ai-loop-router** `http://127.0.0.1:4100`（主路径，flash）；fail-open → `CCC_RELAY_DIRECT_URL` / `~/.ccc/relay-direct.url` |

## 冒烟

```bash
# M1 对话
bash scripts/smoke-desktop-agent.sh
bash scripts/smoke-desktop-stable.sh

# 2017 编排
bash scripts/smoke-executor-stack.sh
SMOKE_CLAUDE_P=1 bash scripts/smoke-executor-stack.sh
```