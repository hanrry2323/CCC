# Runtime: Claude Code (交互模式下加载 skill)

Claude Code 交互模式（无 `-p`）下的 CCC skill 加载方式。适用于开发者手动运行 CCC 任务。

---

## 何时使用

- 开发者已在 `claude` 交互式 session 中
- 需要手动运行 CCC 流程（非全自动 Executor）
- 调试 CCC 任务时查看分步输出

## 安装

创建 symlink 使 Claude Code 发现 CCC skill：

```bash
ln -sfn ~/program/CCC ~/.claude/skills/ccc-protocol
```

Claude Code 启动时会扫描 `~/.claude/skills/` 并加载找到的 skill。

## 使用

在 Clcode Code session 中键入：

```
/ccc-protocol
```

加载后，CCC 协议的 Procedure 和 Output contract 等上下文进入 session。

也可直接引用 SKILL.md：

```
@SKILL.md
```

## 与 claude -p 对比

| 方面 | claude -p | claude (交互) |
|------|-----------|---------------|
| 执行方式 | 全自动非交互 | 半自动，需人工确认 |
| 适用 | Executor / Verifier 批量任务 | 手动调试 / 小任务 |
| Permission | `bypassPermissions` | 默认确认模式 |
| Budget | 高（200 USD） | 无上限（交互式） |
