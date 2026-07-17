# CCC Hub 端口 · 账密 · 运维（权威）

> 更新日期：2026-07-16  
> 产品入口：**唯一** `http://<host>:7777`  
> 账密：**用户名 `ccc` / 密码 `ccc`**

---

## 1. 一句话

浏览器只记 **`:7777`**，登录 **`ccc` / `ccc`**。看板与控制台都在同一个 Hub 里（`#/board`、`#/console`）。Board 进程只在本机 **`:7775`** 提供 API，由 Hub 反代。

---

## 2. 端口

| 端口 | 服务 | 绑定 | 说明 |
|------|------|------|------|
| **7777** | **CCC Hub** | `0.0.0.0` | UI + Chat SSE + Board 反代 |
| **7775** | Board API | `127.0.0.1` | 仅本机；勿对局域网直接开 |
| 7776 | Engine stats（若启用） | 本机 | 与 Hub 无关 |
| 7778 | Cockpit（可选） | 本机 | 旧总控；外链已指向 Hub |
| ~~8084~~ | 废弃 | — | 旧 Chat；不应再监听 |
| ~~18084~~ | 测试临时口 | — | pytest 残留应杀掉 |

### Hub 路由

```
http://192.168.3.140:7777/#/chat
http://192.168.3.140:7777/#/board
http://192.168.3.140:7777/#/console
```

---

## 3. 账密

| 项 | 值 |
|----|-----|
| 用户名 | `ccc`（`CCC_CHAT_USER`） |
| 密码 | `ccc`（`CCC_CHAT_PASS`） |

- 仓库 plist `scripts/com.ccc.chat-server.plist` 已写入上述默认值。
- 前端会清掉旧长口令缓存（`ccc_hub_auth_v2`）；若浏览器仍 401，清 `localStorage` 的 `ccc_chat_pass` 后刷新。
- 禁止口令：空、`claude2026`、`password`、`admin`、`123456`、`changeme`。

---

## 4. 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `CCC_CHAT_PORT` | `7777` | Hub |
| `CCC_CHAT_HOST` | `0.0.0.0` | LAN |
| `CCC_CHAT_USER` | `ccc` | Basic Auth 用户 |
| `CCC_CHAT_PASS` | `ccc` | Basic Auth 密码 |
| `CCC_CHAT_IDLE_TIMEOUT` | `600` | 对话空闲超时（秒；有输出则重置） |
| `CCC_CHAT_MAX_TIMEOUT` | `1800` | 单轮对话硬上限（秒） |
| `CCC_BOARD_URL` | `http://127.0.0.1:7775` | Hub→Board |
| `BOARD_PORT` | `7775` | Board API |
| `BOARD_HOST` | `127.0.0.1` | Board 仅本机 |

---

## 5. 开发 vs 常驻（重要）

**改前端 / 调 Hub UI — 只用前台，不要装 launchd：**

```bash
bash scripts/ccc-hub-dev.sh          # Board:7775 + Hub:7777，Ctrl-C 即停
bash scripts/ccc-hub-dev.sh stop
python3 scripts/verify-ccc-hub.py    # 自检（需先 hub-dev）
```

`ccc-hub-dev.sh` **不改** `control.json`、**不装** KeepAlive、**不启** Engine。

**需要开机常驻 UI（仍无 Engine）：**

```bash
bash scripts/install-board-plist.sh   # 仅 stage
bash scripts/install-hub-plist.sh     # 仅 stage
bash scripts/ccc-autostart-guard.sh ui --start
```

**全流水线（Engine）：**

```bash
bash scripts/ccc-autostart-guard.sh enable --start
```

**停一切常驻：**

```bash
bash scripts/ccc-autostart-guard.sh disable
```

> 禁止再把「打开还是旧皮」的修复写成无脑 `install-*-plist.sh` 并 load——那会 KeepAlive 复活后台。

日志（常驻时）：
- Hub：`/tmp/ccc-chat-server.log` / `.err`
- Board：`~/.ccc/logs/ccc-board.{out,err}.log`
- 前台开发：`~/.ccc/logs/hub-dev-*.log`

---

## 6. 架构

```mermaid
flowchart LR
  User[浏览器] -->|Basic ccc:ccc| Hub["Hub :7777"]
  Hub -->|SSE| Claude[claude CLI]
  Hub -->|proxy| API["Board :7775"]
  API --> Disk[".ccc/board/"]
  Engine[CCC Engine] --> Disk
```

旧 `ccc-board-ui/index.html`、`board.html` 仅重定向到 Hub；`dashboard.html` 已删除。

---

## 7. 相关文档

| 文档 | 内容 |
|------|------|
| 本文 | 端口 / 账密 / 运维权威 |
| `ccc-frontend-unification-plan.md` | 前端统一方案（已落地） |
| `chat-ccc-integration.md` | Chat↔Board↔Engine 对接 |
| `.ccc/infrastructure.md` | 机器总览（含 Hub 行） |

---

## 10. 对话列表：清理测试 + Claude 历史

### 清理测试对话
- 侧栏「清理」按钮，或 `POST /api/history/cleanup-tests?project=ccc`
- 会把 `ch*/sc*/sp*/ex*/ss*` 及常见 e2e 标题移到 `.ccc/chat/_trash/`
- 测试进程请设 `CCC_CHAT_DIR` 到临时目录，避免再污染

### 对接 Claude Code 历史
- 侧栏来源：`全部` / `Hub` / `Claude`
- Claude 会话来自 `~/.claude/history.jsonl` + `~/.claude/projects/<escaped-cwd>/*.jsonl`
- 点击 Claude 会话可读完整 transcript；继续发消息时走 `claude --resume <uuid>`
- Claude 历史只读展示（不在 Hub 内删除 Claude 本地文件）


常见原因（2026-07-16 已踩）：

1. **launchd 被挪走 / control=disabled**：Hub 未在跑，浏览器仍展示旧缓存。
2. **修复（开发）**：
   ```bash
   bash scripts/ccc-hub-dev.sh
   # 另开终端：
   python3 scripts/verify-ccc-hub.py
   ```
3. **修复（要常驻 UI，仍不要 Engine）**：
   ```bash
   bash scripts/ccc-autostart-guard.sh ui --start
   ```
4. **浏览器**：硬刷新（Cmd+Shift+R）；或清该站缓存后再开 `http://<IP>:7777`（账密 ccc/ccc）。
5. **辨认新 UI**：顶栏有 `CCC Hub` +「对话 / 看板 / 控制台」；暖色纸感。旧皮是冷黑 `#0b1120` / GitHub 深色，已不再由 Board 提供。
6. **归档目录** `.claude/worktrees-archive-*` 里仍有历史 board.html，勿当生产入口打开。
