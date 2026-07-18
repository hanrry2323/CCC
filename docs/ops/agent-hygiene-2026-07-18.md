# Agent 卫生报告 — 2026-07-18

> Claude Code + OpenCode 全局清理；舰队 doctor 对照。

## 做了什么

### Claude (`~/.claude`)

| 动作 | 效果 |
|------|------|
| 清 telemetry `1p_failed_events.*` | ~349MB |
| 清 `skills-disabled` | ~55MB |
| 删 stale `ccassist.db` | ~114MB |
| 删 141 个 `qx-worker-*` project 会话目录 | ~67MB |
| 空 `session-env` / 旧 shell-snapshots / bak | inode + 小文件 |
| `skills/ccc-protocol` 符号链接：整仓 → `CCC/skills` | 避免吃到 archive SKILL |
| 工作树 archive 移出仓：`~/.ccc/archive/worktrees-archive-…` | 停止 Cursor 扫到旧 skill |
| 全局 `CLAUDE.md`：取消「每步必 commit」 | 与 Hub/红线对齐 |
| CCC project 会话文件 >30d | 轻量裁剪 |

规模：约 **1.2GB → ~0.67GB**（再轻裁后可能更低）。

### OpenCode

| 动作 | 效果 |
|------|------|
| 重置 `~/.ccc/opencode_slots.json`（pytest 假占用） | Engine slot 恢复 |
| 会话 >14d 再 >7d 删除 | 历史会话减半 |
| **清空 `event` 表**（5.7GB 流式日志，单条最大 ~424MB） | 主收益 |
| 删除 `message.data` >2MB 的病理行 ×7 | 防再膨胀 |
| VACUUM | **DB 8.8GB → 275MB**；整目录 ~10GB → ~430MB |
| 旧 snapshot / log rotate / 退役 1.17.10 二进制 | 版本与缓存卫生 |
| 清 `~/.ccc/prompts` >3d | 临时 prompt |

### 舰队

`ccc-workspace-doctor`：8 仓登记，ERROR=0；WARN=`qx` Hub 可见未挂 Engine（预期）。

## 仍建议（未自动改权限）

1. **`~/.claude/settings.json`**：`additionalDirectories` 含整个 `~/program` + `Bash(**)` + `bypassPermissions` — 功能便利 vs 爆炸半径。建议日后收窄到活跃仓列表。
2. **OpenCode MCP `filesystem` → `~/program`**：交互式无 `--pure` 时仍可能跨仓；Engine 路径保持 `CCC_OPENCODE_PURE=1`。
3. **双配置**：`~/.config/opencode`（1.18）与 `~/.opencode`（legacy）并存 — 以 npm-global 1.18.1 为准。
4. **定期**：每月 `DELETE FROM event; VACUUM;` 或会话 >7d 裁剪；doctor 周检。

## 验收

```bash
du -sh ~/.claude ~/.local/share/opencode
python3 ~/program/CCC/scripts/ccc-workspace-doctor.py
opencode --version   # 期望 1.18.1
```
