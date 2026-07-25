# 执行器总览 — 对话 vs 看板

> 架构对齐 2026-07-20 → 2026-07-25 翻转：**CCC Relay 中转站回归**(推翻 v0.52 退役口径);**三层 + 双槽 + Relay 协议转换**。  
> **槽位口径**：`loop-code` = 对话槽**槽位名**;OpenCode = 写码槽默认件;**CCC Relay = 编排面唯一模型调度网关**(三档 tier: flash/Pro/code)。定位 SSOT：[`loop-engineer-authority.md`](../product/loop-engineer-authority.md)「CCC Relay」+「三层架构与 loop-code 槽位化」。

## 两路互不混淆

```text
M1 对话 / 对齐（Desktop + sidecar → 本机 relay :4000/:4002）
  → 对话槽 loop-code（现填 vendor cli · arm64）
  → CCC Relay M1 (com.ccc.relay.m1)  →  MiniMax Anthropic / OpenAI 异构上游
  → fail-open: relay down 时 sidecar 直连 MiniMax

Engine 看板开发（Mac2017 → 本机 relay :4000/:4002）
  → product 扇出 = Claude → CCC Relay 2017 (com.ccc.relay.2017) → MiniMax
  → dev 写码 = OpenCode → CCC Relay 2017 :4002 → 讯飞/智谱
  → fail-open: relay down 时各客户端直连兜底(绝不 block)
```

| 路径 | 默认执行器 | 模型调度 | 如何切换 |
|------|------------|----------|----------|
| M1 对话（sidecar `:7788`） | **loop-code**（arm64） | **本机 relay** `:4000` | `CCC_RELAY_FAIL_OPEN=1` 切直连 |
| M1 relay（`:4000`/`:4002`） | **CCC Relay M1**（v4.3.0） | — | `com.ccc.relay.m1` plist;三档 flash/Pro/code |
| Engine product 扇出（2017） | **Claude** → relay → MiniMax | **本机 relay** `:4000` | `AGENT_PLANNER_BASE_URL` env |
| Engine dev 写码（2017） | **OpenCode** → relay `:4002` | **本机 relay** | `OPENCODE_MODEL=loop/code` |
| 2017 relay（`:4000`/`:4002`） | **CCC Relay 2017** | — | `com.ccc.relay.2017` plist |

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
