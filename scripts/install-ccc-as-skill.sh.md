# `install-ccc-as-skill.sh` — 装到 `~/.claude/skills/`

> 把 CCC 工程（特别是 `SKILL.md`）作为 SKILL 安装到目标 IDE 的 skills 目录。

## 用途

跨 IDE 装 SKILL 一次到位。脚本同时支持：
- Claude Code (`~/.claude/skills/ccc-protocol`)
- Cursor (`~/.claude/skills/ccc-protocol`，与 Claude Code 共用)
- Zed (`~/.config/zed/skills/`)
- 其他 (可 `--target <dir>` 手动指定)

## 用法

```bash
bash scripts/install-ccc-as-skill.sh                # 自动检测 IDE
bash scripts/install-ccc-as-skill.sh --target ~/custom/skills
bash scripts/install-ccc-as-skill.sh --check        # 验证安装
```

## Exit codes

- 0: 装好 / 验证 PASS
- 1: 已存在 (with `--force` 会覆盖)
- 2: 目标不可写

## Algorithm

1. 检测 IDE：哪个 `~/.claude/skills/`, `~/.config/zed/` 等存在
2. 创建 `ccc-protocol/` 子目录
3. symlink 当前 CCC 工程（或 cp SKILL.md + 关键子目录）
4. 验证 `SKILL.md` frontmatter 完整

## 为什么 symlink 而不是 cp

- 用户在 CCC 主工程上开发的 commit 立即对 IDE 可见
- 避免双向同步问题（CCC 改了但 IDE 不更新）

## Example

```bash
# 标准 install
bash scripts/install-ccc-as-skill.sh
# → ~/.claude/skills/ccc-protocol -> ~/program/CCC (symlink)

# 验证现有 install
bash scripts/install-ccc-as-skill.sh --check
# → 6 项 OK + 4 文件存在性检查
```

## 关联

- `SKILL.md` (要被 install 的)
- `references/adapters/runtime-claude-p.md`
- `examples/cluster/` (skill consumer 用)
