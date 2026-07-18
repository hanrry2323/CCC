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

默认：PATH 上的 `claude`（不设下列变量）。

**方式 A — 显式路径：**

```bash
export CCC_CLAUDE_BIN=/Users/fan/program/CCC/vendor/loop-code/cli
```

**方式 B — 执行器名：**

```bash
export CCC_EXECUTOR=loop-code
# 解析为 <CCC_HOME>/vendor/loop-code/cli
```

优先级：`CCC_CLAUDE_BIN` > `CCC_EXECUTOR=loop-code` > PATH `claude`。

### Hub launchd（Server）

编辑 `~/Library/LaunchAgents/com.ccc.chat-server.plist` 的 `EnvironmentVariables`，增加其一后：

```bash
launchctl kickstart -k "gui/$(id -u)/com.ccc.chat-server"
```

或重跑 `bash scripts/install-hub-plist.sh --start` 后再手改环境变量。

中转仍走 `ANTHROPIC_BASE_URL`（Server 本机 `http://127.0.0.1:4000`）。

## 替换

同一对话契约可换回官方 `claude`（去掉上述环境变量即可）。  
看板开发换执行器不在本文范围（见 [`overview.md`](overview.md)）。
