# CCC Infrastructure — 机器 / 端口 / 服务总览

> **现行（2026-08-06）**。旧 Hub `:7777` / Board `:7775` / sidecar / hub-tunnel 已退役。  
> 权威链：`docs/INDEX.md` §0 · `.cursor/rules/location-truth.mdc`（CURSOR.md 已随 Cursor 弃用移除）  
> 老板面：M1 IDE 中枢聊意图 + 浏览器看 2017 看板/运维；中间 pull/派发自动。

---

## 机器清单

| 主机 | IP | 角色 | 说明 |
|------|-----|------|------|
| **M1** | 192.168.3.140 | 中枢节点 | git 主仓（M1）；IDE（Claude/OpenCode）开仓；**不跑** `:7788` / Engine |
| **Mac 2017** | 192.168.3.116 | 生产与执行节点 | 生产运行 + Engine 派发 + 机审 + 执行写码（engine worktree） |

---

## Mac 2017（生产）

根目录：`/Users/fan/program/CCC`

| 端口 | 服务 | 说明 |
|------|------|------|
| **7788** | `com.ccc.web-server` | HTTP：看板 / 运维 / 对话 / API |
| **6100** | ai-loop-router（Anthropic） | 大脑 + Claude Code 执行体 |
| **6102** | ai-loop-router（openai-chat） | OpenCode code 档 |

| launchd | 进程 |
|---------|------|
| `com.ccc.web-server` | `server/web/server.py` |
| `com.ccc.engine` | `server/engine/main.py`（`CCC_AUTO_PULL=1`） |
| `com.ccc.board-scheduler` | `server/board/scheduler.py` |
| `com.ccc.ai-loop-router` | 中继 6100/6102 |

日志：`/Users/fan/.ccc/logs/`（含 `engine-pipeline.json` 管道状态）。

---

## M1（中枢）

- 开仓：`/Users/apple/program/CCC`
- 看生产：浏览器 → `http://192.168.3.116:7788/#/board` · `#/ops`
- Desktop 壳：**暂缓**

---

## 自动链（人不管中间）

```text
IDE 出卡（OpenCode · 验收 Claude）→ push → 2017 自动 pull
  → OpenCode 开发 → 机械门禁（commit+diff）→ 已回写
  → Claude 机审（## 机审区）→ 老板说「验收看板」→ 终验已关闭
```
