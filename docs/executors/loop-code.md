# Executor: loop-code（可选私有）

> 可选 Claude Code 兼容 CLI。仅私有自用；**不**作为对外唯一地基。  
> 二进制在 `vendor/loop-code/`（gitignore），不进 git。

## 布局

```text
CCC/vendor/loop-code/
  cli          # 可执行文件（~160MB）
  SHA256
  VERSION
  README.md
```

安装：`bash scripts/install-executor-loop-code.sh /path/to/cli`

## 使用

```bash
export CCC_EXECUTOR=loop-code
export CCC_LOOP_CODE_BIN="$PWD/vendor/loop-code/cli"
# 或 PATH 优先
```

中转仍走服务端 `ANTHROPIC_BASE_URL`（Server 本机 `127.0.0.1:4000`；客户端 LAN IP）。

## 替换

同一契约可换官方 `claude`、OpenCode 等；见产品拓扑 `docs/deploy/topology.md`。
