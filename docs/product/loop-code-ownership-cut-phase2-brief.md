# Phase2 brief — M1 退役原版 Claude Code

> **对齐**：[`loop-code-ownership-cut.md`](loop-code-ownership-cut.md)  
> **日期**：2026-07-21  
> **策略**：卸 CLI + 清 PATH 可见性；**保留** `~/.claude` / `~/.claude.json`；不卸 Cursor；不动 Mac2017。

---

## 目标

`command -v claude` 为空时，Desktop + sidecar + `vendor/loop-code` 仍绿。

## 本机库存（退役前）

| 项 | 路径 |
|----|------|
| wrapper | `~/.local/bin/claude` → exec `~/.npm-global/bin/claude` |
| npm 包 | `@anthropic-ai/claude-code`（记版本见 `~/Library/Logs/CCC/phase2-claude-retire.txt`） |
| URL Handler | `~/Applications/Claude Code URL Handler.app` |

## Runbook

```bash
# 1) 备份指针
mkdir -p ~/Library/Logs/CCC ~/.ccc/retired
{
  echo "date=$(date -Iseconds)"
  which -a claude || true
  npm list -g --depth=0 @anthropic-ai/claude-code 2>/dev/null || true
  head -20 ~/.local/bin/claude 2>/dev/null || true
} | tee ~/Library/Logs/CCC/phase2-claude-retire.txt

# 2) 卸 npm 全局
npm uninstall -g @anthropic-ai/claude-code

# 3) 移走 wrapper（勿无痕 rm）
mv ~/.local/bin/claude ~/.ccc/retired/claude-local-bin 2>/dev/null || true

# 4) 移走 URL Handler
mv ~/Applications/"Claude Code URL Handler.app" \
  ~/.ccc/retired/"Claude Code URL Handler.app" 2>/dev/null || true

# 5) 壳
hash -r
command -v claude   # 期望空
```

**不删**：`~/.claude`、`~/.claude.json`、Cursor、`vendor/loop-code`。

## 仓内改动

| 文件 | 改什么 |
|------|--------|
| `scripts/install-agent-sidecar-plist.sh` | PATH 去掉 `~/.local/bin` / `~/.npm-global/bin`；加 `vendor/loop-code` |
| `scripts/smoke-loop-code-no-personal-claude.sh` | 断言无个人 `claude` + sidecar health |

## 验收

```bash
command -v claude   # 空
bash scripts/install-agent-sidecar-plist.sh --start
curl -s http://127.0.0.1:7788/health   # loop-code + ~/.ccc/loop-code
bash scripts/smoke-loop-code-no-personal-claude.sh
bash scripts/smoke-desktop-agent.sh    # 可选全量
```

## 回滚

```bash
npm i -g @anthropic-ai/claude-code@<retire.txt 中版本>
mv ~/.ccc/retired/claude-local-bin ~/.local/bin/claude
mv ~/.ccc/retired/"Claude Code URL Handler.app" ~/Applications/
# 仓内 PATH：git revert 后重装 plist
```

## 不做

- 删整个 `~/.claude`
- Phase3 / Phase4
- 版本 bump（除非显式要求）
