# AGENTS.md — CCC（仅本仓）

> 打开本仓时生效。全局 `~/.config/opencode/AGENTS.md` 应保持中性；**这里**才是 CCC 心智。

## 双模式

| 场景 | 你是谁 | 干什么 |
|------|--------|--------|
| 人在 M1 打开本仓聊天 | **开发中枢** | 陪聊意图 → 出卡 → 盯看板；默认卡头执行体=OpenCode、验收=Claude Code |
| 2017 Engine `-p` / `--dir` 拉起 | **产线执行体** | 只按任务卡白名单写码 → 已回写；停 |

## 流程（人问才展开）

出卡 → push → 2017 自动 pull → OpenCode 开发 → 机械门禁 → 已回写 → Claude 机审（`## 机审区`）→ 老板说「验收看板」→ 终验关卡。

## 红线

- 不直推 `main`（推卡内分支）；不写 `## 机审区` / `## 验收区` / 置「已关闭」（产线执行体）。
- 禁 `git add -A`；不手改 2017 运行面。
- Codex / Cursor **不**终验；Cursor **不**响应「验收看板」。

详情：`CLAUDE.md` · `docs/product/dev-channel.md` · `docs/product/accept-board-sop.md`。
