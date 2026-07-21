# Executor: loop-code（M1 对话方案 Agent CLI）

> Claude Code 兼容 CLI。**M1 对话面专用**：与 Desktop 深度整合为本机 sidecar 的方案 Agent。  
> **不是**看板开发执行器（看板 dev 角色仍用 OpenCode，见 [`overview.md`](overview.md)）。  
> **不再**部署到 Mac2017；Hub `/api/chat` 路由已删。

## 布局（仅 M1）

```text
CCC/vendor/loop-code/        # 仅 M1 本机；gitignore，不进 git
  cli                        # 可执行文件（arm64，~160MB）
  SHA256
  VERSION
  README.md
```

安装（M1）：`bash scripts/install-executor-loop-code.sh /path/to/cli`  
**Mac2017 上不安装**：2017 是编排消费面，对话由 M1 sidecar 完成。

## 切换（对话路径，M1 sidecar）

**产品 SSOT**：M1 Desktop sidecar 方案 Agent = loop-code。  
`scripts/ccc-agent-sidecar.sh` 默认 `CCC_EXECUTOR=loop-code`，解析为 `<CCC_HOME>/vendor/loop-code/cli`。

优先级：`CCC_CLAUDE_BIN` > `CCC_EXECUTOR=loop-code` > PATH `claude`。

**方式 A — 显式路径：**

```bash
export CCC_CLAUDE_BIN=/Users/apple/program/CCC/vendor/loop-code/cli
```

**方式 B — 执行器名（sidecar 默认）：**

```bash
export CCC_EXECUTOR=loop-code
# 解析为 <CCC_HOME>/vendor/loop-code/cli
```

### M1 sidecar launchd

```bash
bash scripts/install-agent-sidecar-plist.sh --start
# 或 kickstart：
launchctl kickstart -k "gui/$(id -u)/com.ccc.agent-sidecar"
```

验收：`curl http://127.0.0.1:7788/health`（出口应为 MiniMax；plist `ANTHROPIC_BASE_URL` 含 `minimaxi.com`）。

模型：`ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic`，`ANTHROPIC_MODEL=MiniMax-M3`（key：`~/.ccc/minimax-api-key`）。  
~~经 2017 Router `:4000` 已退役。~~

### 暂停：118.ink（opus 4.8）

**成本暂停，不作现网默认。** Desktop 对话固定 MiniMax；后续改走 **App 内模型快选**（[`../product/dev-channel.md`](../product/dev-channel.md)）。

若仍须临时切 sidecar 上游：

```bash
export CCC_AGENT_UPSTREAM_118INK=1
# CCC_AGENT_118INK_KEY=sk-…（本机 env，勿提交）
bash scripts/install-agent-sidecar-plist.sh --start
```

| env | 值 |
|-----|----|
| `CCC_AGENT_UPSTREAM_118INK` | `1` |
| `CCC_AGENT_118INK_KEY` | `sk-…` |
| `ANTHROPIC_BASE_URL` | `https://118.ink`（**勿**加 `/v1`） |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` |

**回默认 MiniMax**：`unset CCC_AGENT_UPSTREAM_118INK CCC_AGENT_118INK_KEY` 后重装 sidecar。

## 与 Mac2017 的关系

| 项 | M1 | Mac2017 |
|----|-----|---------|
| loop-code 二进制 | **有**（arm64，sidecar 用） | **无**（已删，不再需要） |
| Hub `/api/chat` | 不调用 | **已删路由**（404） |
| Engine 扇出 | 不跑 | **Claude Code**（`scripts/board/roles/product.py`） |
| dev 写码 | 不跑 | **OpenCode**（`scripts/board/roles/dev.py`） |

## 替换

调试可临时去掉 `CCC_EXECUTOR` 回退 PATH `claude`；产品交付必须以 loop-code 为准。  
看板开发换执行器不在本文范围（见 [`overview.md`](overview.md)）。
