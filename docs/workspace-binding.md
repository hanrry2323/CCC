# 项目绑定与接入 — Workspace Binding

> **SSOT**：Hub 对话 Agent / 看板 / Engine 与「哪个文件夹」的绑定规则。  
> 版本对齐：v0.42.3+ · 相关实现：`scripts/chat_server/`、`scripts/ccc-init.py`、`scripts/_workspace_registry.py`

---

## 1. 一句话

Hub 里选哪个项目，Claude 就 **`cwd` 到哪个仓库根**；读 **`{该仓}/CLAUDE.md`**（再叠全局 `~/.claude/CLAUDE.md`）；看板写 **`{该仓}/.ccc/board/`**。  
**不是**永远读 CCC 编排仓。

---

## 2. 三层注册（勿混）

| 层 | 数据源 | 作用 |
|----|--------|------|
| **Hub 项目列表** | Board `discover_workspaces()`：扫 `~/program/`（及 `projects/`）下含 `.ccc/board` 的目录；可用 `CCC_WORKSPACES` 显式追加 | 对话下拉框能选到 |
| **对话 Agent** | Hub `currentProject` → `path` → Claude `cwd` + 注入该仓 `CLAUDE.md` | 认知与工具隔离 |
| **Engine 消费名单** | `~/.ccc/workspaces.json`（Hub **首次下达**幂等登记） | Engine 才会扫该仓队列 |

```text
~/program/foo/.ccc/board   ──发现──► Hub 可选「foo」
Hub 选 foo 发消息          ──cwd──► /…/foo + 注入 foo/CLAUDE.md
Hub「下达并开工」          ──登记──► ~/.ccc/workspaces.json
Engine enable              ──消费──► 仅登记仓 + CCC（默认不全盘 invent）
```

路径须在 **`~/program/` 下**（或 CCC 本体），否则 Board 安全策略不会列入 Hub。

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

## 5. 运维对照

| 你想… | 改 / 查 |
|--------|---------|
| 这个项目对话「知道」什么 | `{项目}/CLAUDE.md` |
| 所有项目都带的个人偏好 | `~/.claude/CLAUDE.md` |
| Hub 选不到该项目 | 是否有 `.ccc/board`？是否在 `~/program/`？刷新 `/api/projects` |
| Engine 不跑该项目 | `~/.ccc/workspaces.json` 有无登记；控制面是否 `enable` |
| 任务写到哪 | Hub 当前选中项目的 `.ccc/board/` |
| 防串仓执行 | OpenCode `--dir` = 任务仓；勿在 CCC 仓 commit 业务代码 |

---

## 6. 相关代码

| 文件 | 职责 |
|------|------|
| `scripts/ccc-board-server.py` `discover_workspaces` | Hub/Board 项目发现 |
| `scripts/chat_server/routers/projects.py` | Hub 项目 API |
| `scripts/chat_server/services/claude_client.py` | 注入 CLAUDE.md + cwd |
| `scripts/chat_server/routers/chat.py` | 首轮注入 / 续聊跳过 |
| `scripts/_workspace_registry.py` | Engine 登记 |
| `scripts/ccc-init.py` | 新项目一键初始化 |

上手总览仍见 [`GETTING-STARTED.md`](GETTING-STARTED.md)。
