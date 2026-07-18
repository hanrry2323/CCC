# Executor: loop-code（可选私有对话 CLI）

> 可选 Claude Code 兼容 CLI。仅私有自用；**不是**看板开发默认（看板仍用 OpenCode）。  
> 二进制在 `vendor/loop-code/cli`（gitignore），不进 git。

## 布局

```text
CCC/vendor/loop-code/
  cli          # 可执行文件（~160MB）
  SHA256
  VERSION
  README.md
```

安装：`bash scripts/install-executor-loop-code.sh /path/to/cli`

## 切换（对话路径）

**产品 SSOT**：Hub 方案 Agent = loop-code。  
`scripts/install-hub-plist.sh` 默认写入 `CCC_EXECUTOR=loop-code`。

优先级：`CCC_CLAUDE_BIN` > `CCC_EXECUTOR=loop-code` > PATH `claude`。

**方式 A — 显式路径：**

```bash
export CCC_CLAUDE_BIN=/Users/fan/program/CCC/vendor/loop-code/cli
```

**方式 B — 执行器名（Hub 默认）：**

```bash
export CCC_EXECUTOR=loop-code
# 解析为 <CCC_HOME>/vendor/loop-code/cli
```

### Hub launchd（Server）

```bash
bash scripts/install-hub-plist.sh --start
# 或 kickstart：
launchctl kickstart -k "gui/$(id -u)/com.ccc.chat-server"
```

验收：`bash scripts/smoke-desktop-agent.sh`（断言 `/api/desktop/config` 的 `agent_runtime=loop-code`）。

中转仍走 `ANTHROPIC_BASE_URL`（Server 本机 `http://127.0.0.1:4000`）。

## 替换

调试可临时去掉 `CCC_EXECUTOR` 回退 PATH `claude`；产品交付必须以 loop-code 为准。  
看板开发换执行器不在本文范围（见 [`overview.md`](overview.md)）。
