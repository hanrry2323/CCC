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

**成本暂停，不作现网默认。** Desktop 上游默认 MiniMax；**App 内模型快选**（Phase17）只换请求级逻辑名，不改本 plist 出口（[`../product/dev-channel.md`](../product/dev-channel.md) · [`../product/hub-shell-phase17-model-picker.md`](../product/hub-shell-phase17-model-picker.md)）。

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

## 配置切割（Phase1–5 基线）

战略 SSOT：[`../product/loop-code-ownership-cut.md`](../product/loop-code-ownership-cut.md) · 收口 brief：[`../product/loop-code-ownership-cut-closeout-brief.md`](../product/loop-code-ownership-cut-closeout-brief.md)。

| 项 | M1 Desktop | Mac2017 Engine |
|----|------------|----------------|
| 配置家 | `CLAUDE_CONFIG_DIR=~/.ccc/loop-code` | `~/.ccc/engine-claude` |
| 二进制 | `vendor/loop-code/cli`（禁 PATH 个人 claude） | x86 原版 `claude`（不换 loop-code） |
| 人格 | `hub_voice` + 私有 `CLAUDE.md` | 无头扇出短 `CLAUDE.md` |
| VERSION | `/health` → `loop_code_version` | n/a |

## 与 Mac2017 的关系

| 项 | M1 | Mac2017 |
|----|-----|---------|
| loop-code 二进制 | **有**（arm64，sidecar 用） | **无**（已删，不再需要；x86 ≠ arm64） |
| Hub `/api/chat` | 不调用 | **已删路由**（404） |
| Engine 扇出 | 不跑 | **原版 Claude CLI x86**（`scripts/board/roles/product.py`）；不为一致换 loop-code |
| dev 写码 | 不跑 | **OpenCode**（`scripts/board/roles/dev.py`） |

## 替换

产品交付必须以 loop-code 为准；sidecar **不得**回落 PATH `claude`。  
看板开发换执行器不在本文范围（见 [`overview.md`](overview.md)）。
