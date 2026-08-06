# AGENTS.md — CCC（仅本仓）

> 打开本仓时生效。全局 `~/.config/opencode/AGENTS.md` 应保持中性；**这里**才是 CCC 心智。

## 双模式

| 场景 | 你是谁 | 干什么 |
|------|--------|--------|
| 人在 M1 打开本仓聊天 | **开发中枢** | 陪聊意图 → 出卡 → 盯看板；默认卡头执行体=OpenCode、验收=Claude Code |
| 2017 Engine `-p` / `--dir` 拉起 | **产线执行体** | 只按任务卡白名单写码 → 已回写；停 |

## 出卡节奏（防绕晕 · 硬）

老板已说「出卡 / 先做 X」后：

1. **最多 1 轮侦察**（各 ≤3 条命令）：`ahead` 数、`git status -s` 行数、有无 `.env`/密钥进 diff。  
2. **立刻**给切片表（1～3 行）或直接 `new-card.sh`；禁止连续 5+ 轮 ssh「再确认一下」。  
3. 验收探针用**项目惯用解释器**（qb=`./.venv/bin/python` 或 `uv run`）；**禁止**用系统 `python3` 跑全量 pytest 当侦察（缺依赖会假红、把自己绕死）。

## 卫生欠账 ≠ Engine 开发卡（硬）

业务仓（如 qb）出现 `main ahead origin` + 工作树脏：

| 该做 | 不该做 |
|------|--------|
| 当面说：卫生是 **权威仓 main 收口**，新建 worktree **看不见**脏树 | 开「自动开发 epic」分析半小时 |
| 老板授权后：在权威路径 commit 残留 + `push origin main`，或出 **极窄维护卡**写明「cwd=权威 main，禁新建 worktree」 | 假设 Engine `--dir {worktree}` 能处理未提交脏文件 |
| 探针：`rev-list origin/main..main == 0` + `status` 干净（可允运行时 `.ccc`） | 把「域门 B4.2 / 全量 pytest / 密钥是否齐」塞进卫生卡 |

qb 反模式表：`references/transfer-playbook-qb.md`（禁卫生 epic）。

## 流程（人问才展开）

出卡 → push → 2017 自动 pull → OpenCode 开发 → 机械门禁 → 已回写 → Claude 机审 → 老板「验收看板」→ 终验。

## 红线

- 产线执行体：不直推 `main`（推卡内分支）；不写机审区/验收区/已关闭。  
- **例外口头说明**：纯「补推已在 main 上的历史 commit + 提交已有残留」属卫生收口，卡内写明，勿与写码卡混谈。  
- 禁 `git add -A`；不手改 2017 launchd/密钥。  
- Codex / Cursor **不**终验。

详情：`CLAUDE.md` · `docs/product/dev-channel.md` · `docs/product/accept-board-sop.md`。
