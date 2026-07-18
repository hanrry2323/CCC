# 项目绑定与接入 — Workspace Binding

> **SSOT**：Hub 对话 Agent / 看板 / Engine 与「哪个文件夹」的绑定规则。  
> 版本对齐：v0.51.0+ · 相关实现：`scripts/chat_server/`、`scripts/ccc-init.py`、`scripts/_workspace_registry.py`、`scripts/ccc-workspace-doctor.py`

---

## 1. 一句话

Hub 里选哪个项目，Claude 就 **`cwd` 到哪个仓库根**；读 **`{该仓}/CLAUDE.md`**（再叠全局 `~/.claude/CLAUDE.md`）；看板写 **`{该仓}/.ccc/board/`**。  
**不是**永远读 CCC 编排仓。  
**v0.51**：CCC = **orch**（Hub 可聊/运维，**不可下达**）；Engine **只**消费 `role=app` 且 `engine=true` 的登记仓。

---

## 2. 三层注册（勿混）

| 层 | 数据源 | 作用 |
|----|--------|------|
| **Hub 项目列表** | Board `discover_workspaces()`：扫 `~/program/`（及 `projects/`）下含 `.ccc/board` 的目录；可用 `CCC_WORKSPACES` 显式追加 | 对话下拉框能选到；API 标 `role` / `engine_eligible` |
| **对话 Agent** | Hub `currentProject` → `path` → Claude `cwd` + 注入该仓 `CLAUDE.md` | 认知与工具隔离（含选 CCC 聊运维） |
| **Engine 消费名单** | `~/.ccc/workspaces.json` 中 **engine-eligible** 条目（Hub 向 **业务仓** 首次下达幂等登记） | Engine 才会扫该仓队列；**跳过 orch** |

```text
~/program/foo/.ccc/board   ──发现──► Hub 可选「foo」
Hub 选 foo 发消息          ──cwd──► /…/foo + 注入 foo/CLAUDE.md
Hub「下达并开工」→ foo     ──登记──► ~/.ccc/workspaces.json (role=app)
Engine enable              ──消费──► 仅 engine-eligible apps（不跑 CCC orch）
Hub「下达」→ CCC           ──拒绝──► 400（请用 Cursor 改 CCC）
```

路径须在 **`~/program/` 下**（或 CCC 本体），否则 Board 安全策略不会列入 Hub。

舰队上限：**≤10 apps**；orch（CCC）额外登记 1，不占 app 名额。
---

## 3. 对话 Agent 读什么

| 时机 | 内容 |
|------|------|
| 新会话首轮 | `{项目根}/CLAUDE.md` + `~/.claude/CLAUDE.md`（合计截断约 4000 字） |
| 续聊 | **不再**重注整份上下文（Claude `--resume`） |
| 工具 / 附件 | 关在 `{项目根}`（cwd jail）；附件落 `{项目根}/.ccc/chat-uploads/` |
| 会话历史 | 按项目 path 隔离（`~/.claude/projects/<转义路径>/`） |

项目专属纪律写在 **该仓** `CLAUDE.md` / `.ccc/profile.md` / `.ccc/state.md`。  
全局 `~/.claude/CLAUDE.md` 会进**所有**项目——注意认知串味。

---

## 4. 一键接入（推荐）

```bash
# 已有仓或空目录均可（目录须已存在）
mkdir -p ~/program/myapp   # 若全新

python3 ~/program/CCC/scripts/ccc-init.py ~/program/myapp
# 可选：立刻写入 Engine 登记表（也可等 Hub 首次下达自动登记）
python3 ~/program/CCC/scripts/ccc-init.py ~/program/myapp --register

# 编辑该仓认知（必做）
$EDITOR ~/program/myapp/CLAUDE.md
$EDITOR ~/program/myapp/.ccc/profile.md
```

`ccc-init` 会：

1. 写 `AGENTS.md`、`.ccc/profile.md`（模板）
2. **创建七列看板** `.ccc/board/{backlog,planned,…}`（Hub 发现条件）
3. 种子 `.ccc/state.md`（若不存在）
4. 种子根目录 `CLAUDE.md`（若不存在；项目对话主认知）
5. `--register` → `~/.ccc/workspaces.json`

然后：打开 Hub → 刷新项目列表 → 选该项目 → 对齐 / 定稿 / 转任务。  
要自动跑队列：`bash ~/program/CCC/scripts/ccc-autostart-guard.sh enable --start`。

---

## 5. Board 可见 ≠ Engine 登记

| 现象 | 含义 | 处理 |
|------|------|------|
| Hub 下拉有项目，Engine 不跑 | 仅 Board 发现，未进 `workspaces.json` | Hub **下达**一次，或 `ccc-workspace-doctor.py register <path>` |
| Engine 扫到死路径 | pytest/tmp 污染登记表 | `ccc-workspace-doctor.py prune --apply` |
| 想暂停某仓自动化 | 仍可对话 | `unregister <path\|name>`（不删 `.ccc/`） |

**舰队规模（对内）**：建议登记仓 **≤10**（含 CCC）。超过后 doctor 报 ERROR；扩容前先归档冷仓。

周检：

```bash
python3 ~/program/CCC/scripts/ccc-workspace-doctor.py
# 期望 ERROR=0；WARN 仅「有意未登记」时可接受

# 改舰队后：同步 Claude / OpenCode 根目录白名单
python3 ~/program/CCC/scripts/ccc-sync-agent-roots.py
```

---

## 6. 运维对照

| 你想… | 改 / 查 |
|--------|---------|
| 这个项目对话「知道」什么 | `{项目}/CLAUDE.md` |
| 所有项目都带的个人偏好 | `~/.claude/CLAUDE.md` |
| Hub 选不到该项目 | 是否有 `.ccc/board`？是否在 `~/program/`？刷新 `/api/projects` |
| Engine 不跑该项目 | `~/.ccc/workspaces.json` 有无登记；控制面是否 `enable` |
| 舰队卫生 | `ccc-workspace-doctor.py`；Hub `#/ops` Diff 工作区 |
| 任务写到哪 | Hub 当前选中项目的 `.ccc/board/` |
| 防串仓执行 | OpenCode `--dir` = 任务仓；勿在 CCC 仓 commit 业务代码 |

---

## 7. 相关代码

| 文件 | 职责 |
|------|------|
| `scripts/ccc-board-server.py` `discover_workspaces` | Hub/Board 项目发现 |
| `scripts/chat_server/routers/projects.py` | Hub 项目 API |
| `scripts/chat_server/services/claude_client.py` | 注入 CLAUDE.md + cwd；委托持续会话 |
| `scripts/chat_server/services/claude_session.py` | `ClaudeSDKClient` 持续会话（非每轮 `claude -p`） |
| `scripts/chat_server/routers/chat.py` | 首轮注入 / 续聊跳过；持久化 `claude_session_id` |
| `scripts/_workspace_registry.py` | Engine 登记 / prune / 拒 ephemeral |
| `scripts/ccc-workspace-doctor.py` | 舰队卫生 CLI |
| `scripts/ccc-init.py` | 新项目一键初始化 |

上手总览仍见 [`GETTING-STARTED.md`](GETTING-STARTED.md)。  
多仓里程碑：[`milestones/m1-ten-workspaces.md`](milestones/m1-ten-workspaces.md)。
