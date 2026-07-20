# Skill 清查与分级（本机 · 2026-07-18）

> 只标注、不自动删除。清理项见文末「建议清理」；执行前请确认。
> Hub「转任务」卡片扫描：`CCC/skills` → `~/.claude/skills` → `~/.agents/skills`（见 `scripts/_skills_catalog.py`）。

## 常用（日常高价值）

| Skill | 位置 | 说明 |
|-------|------|------|
| `ccc-protocol` | Cursor 薄封装 / CCC 根 `SKILL.md` | Hub/协议入口；**不是**转任务 chips |
| `codebase-memory` | `~/.claude/skills` | 代码知识图 / 架构问答 |
| `planning-with-files` | `~/.claude/skills` | 文件化多步规划 |
| `daily-snapshot` | `~/.claude/skills` | 今日变更扫描 |
| `test-verify` | `~/.claude/skills` | 标准化 test/lint/build |
| Cursor: `canvas`, `babysit`, `split-to-prs`, `create-skill/rule/hook` | `~/.cursor/skills-cursor` | IDE 内置（Hub 不扫描） |

## 可用专项（场景型）

| Skill | 位置 | 说明 |
|-------|------|------|
| `hmap` | Claude | 项目健康仪表盘 |
| `hp-kb-operations` / `hp-kb-verify` | Claude | HP 知识库运维/校验 |
| `opencontext-*`（5） | Claude | OpenContext 工作流 |
| `qx-models` | `~/.agents/skills` | Claude Code 换模型 |
| `cli-hub-meta-skill` | `~/.agents/skills` | 发现 agent-native CLI |
| `ui-ux-pro-max` | `~/.opencode/skills` | OpenCode UI/UX（Hub 不扫描） |

## 不适合当「任务 Skill」（Engine 角色）

以下 7 个是 CCC Engine 阶段定义，**默认不应出现在转任务偏好 chips**（Hub 已按 `hub_visible=false` 隐藏，可选手动显示）：

`ccc-product`, `ccc-dev`, `ccc-reviewer`, `ccc-tester`, `ccc-ops`, `ccc-kb`, `ccc-regress`

源：`~/program/CCC/skills/ccc-*`。

## 建议清理（需你确认后再执行）

运行只读预览：

```bash
python3 scripts/ccc-skill-cleanup.py --dry-run
# 确认后：
python3 scripts/ccc-skill-cleanup.py --apply --broken-links
# 可选：
python3 scripts/ccc-skill-cleanup.py --apply --worktree-prune
python3 scripts/ccc-skill-cleanup.py --apply --archive
```

| # | 项 | 证据 | 建议 |
|---|-----|------|------|
| 1 | `~/.config/opencode/skills/` 下 ~19 个视频 symlink | 目标 `~/.claude/skills/hyperframes*` 已删 | 删断链，或改链到 `~/.zcode/skills/…` |
| 2 | `~/.copilot/skills/` 同类断链 | 同上 | 删断链 |
| 3 | CCC ghost git worktrees（3） | `git worktree list` 目录缺失 | `git worktree prune` |
| 4 | `~/.ccc/archive/worktrees-archive-*` | ~7.5MB 快照 | 不需要可删 |
| 5 | Claude `ccc-protocol` 链到 `CCC/skills`（无顶层 SKILL.md） | 与 Cursor 薄封装不一致 | 做成薄封装 + 修 install 脚本 |
| 6 | ZCode/Mavis/Trae 整仓 `ccc-protocol` → `~/program/CCC` | 易扫进噪声 | 改为薄封装（可选） |

## Hub 展示规则（实现后）

| tier | hub_visible | 示例 |
|------|-------------|------|
| `common` | true | codebase-memory, planning-with-files, … |
| `specialized` | true | hmap, opencontext-*, qx-models, … |
| `engine` | false（默认） | ccc-* 七角色 |
