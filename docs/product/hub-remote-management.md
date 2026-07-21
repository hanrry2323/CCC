# 双口远程：M1 对话 + 2017 Hub 编排

> **状态**：现行 · 2026-07-21（二次纠偏 · 含实现）  
> **一句话**：远程能力抄 Desktop 双连接——**对话口在 M1**，**编排口在 Mac2017**；禁止为「只记一个口」把对话壳挂到 2017。  
> **禁止**：在 Mac2017 维护第二套产品聊天 / `hub::`；也禁止以「Hub SPA + `/api/agent` 反代」作为产品主路径。

---

## 形态（与 Desktop 同构）

```text
浏览器 / Desktop
  ├─ 对话（聊对齐 / 聊方案 / discuss·engineer）
  │     → M1 sidecar :7788 → loop-code
  │     （会话权威：M1 本机 LocalSessionStore）
  └─ 编排（transfer / flow / 看板 / 运维）
        → Mac2017 Hub :7777 → Board :7775 / Engine
```

| 接口 | 机器 | 现网 | 职责 |
|------|------|------|------|
| **对话** | M1 | `http://192.168.3.140:7788` | 热路径、本机会话 SSOT；业务事实信 Hub baseline（无本机业务 cwd）；**对话 SPA 宿主** |
| **Hub** | Mac2017 | `http://192.168.3.116:7777` | transfer / flow / board / ops；threads **仅镜像**；默认落地 `#/board` |

thread id 与 Desktop 相同：`{projectId}::…`。同一 thread 能续聊，是因为打 **同一 sidecar + 同一会话契约**，不是因为页面挂在 Hub。

---

## 远程浏览器怎么记

| 用途 | URL |
|------|-----|
| 聊 | `http://192.168.3.140:7788/`（sidecar 静态壳；鉴权 `~/.ccc/agent-token` → 浏览器 localStorage） |
| 看板 / 运维 / 下达 | `http://192.168.3.116:7777/#/board`（Hub Basic Auth `ccc`/`ccc`） |

对话 SPA 配置（与 Desktop 同构）：

| 键 | 含义 | 默认 |
|----|------|------|
| Agent base | sidecar | 同机空串 / `http://192.168.3.140:7788` |
| Hub base | 编排 API | `http://192.168.3.116:7777`（环境 `CCC_HUB_URL`） |
| `ccc_agent_token` | Bearer | 与 M1 `~/.ccc/agent-token` 相同 |

Hub `:7777/#/chat` **自动跳转** M1 对话口。Hub `/api/agent/*` 默认**不挂载**；仅 `CCC_AGENT_PROXY=1` 启用作运维探针。

SPA **设置**可持久化：`ccc_agent_token`、`ccc_hub_base`、`ccc_agent_base`、`ccc_local_workspace_map`（勿把 token 写进 URL）。

---

## 同 thread 续聊（镜像面）

| 层 | 权威 |
|----|------|
| Desktop 本机文件 | `LocalSessionStore`（对话权威） |
| Hub `GET/PUT …/threads/{id}/messages` | **仅镜像**；不得用空 Hub GET 覆盖非空本机会话 |
| sidecar slot | 同 `session_id` 串行（已有锁） |

远程 SPA 与 Desktop 共用 `{project}::…`。SPA 回合结束后应 `PUT` 消息到 Hub；冷启动可读 Hub GET 续上**已同步**的历史。若 Desktop 有本地未 PUT 的内容，以 Desktop 为准——先 Desktop 或先完成 PUT。

---

## CORS / 安全（内网）

- Hub 默认 `CORS_ORIGIN_REGEX` 含 `192.168.*` / `10.*`，以便 M1 SPA Origin 调编排 API。plist **勿**用仅 localhost 的旧 regex 盖掉。
- Sidecar 听 `0.0.0.0` 仅假设 **内网**；鉴权靠 `CCC_AGENT_TOKEN`。
- 浏览器持有 agent token（localStorage）；不经 2017 注入。

---

## 成功标准

- 打开 **M1 `:7788/`** ≈ 远程用 Desktop 中栏（SSE 日志在 M1 sidecar）。
- 打开 **2017** `#/board` / `#/ops` ≈ 远程用 Desktop 左栏运维/看板。
- transfer / flow 行为与 Desktop 一致（过桥仍走 Hub；需 Hub CORS 允许 M1 Origin）。
- **不**依赖 2017 产品级 `/api/agent` 反代；**不**在 2017 跑聊天槽。

---

## 烟测（双口）

```bash
# 对话口 + 编排口
CCC_AGENT=http://192.168.3.140:7788 \
CCC_SERVER=http://192.168.3.116:7777 \
  bash scripts/smoke-dual-port-remote.sh
```

（`smoke-hub-remote-desktop.sh` 已改为转调本脚本，勿再以 2017 为 chat origin。）

---

## 废弃叙事

| 项 | 说明 |
|----|------|
| 「HTTP ≈ Remote Desktop」且入口强制 `http://192.168.3.116:7777/#/chat` | 对话壳挂错机器 |
| Hub `/api/agent/*` 反代作**产品**主路径 | 默认关闭；`CCC_AGENT_PROXY=1` 才挂 |
| `/api/remote-chat/*`、`hub::` 分区 | 已删 / 禁止 |
| 把 2017 `apps/` 路径塞进 sidecar `project_path` | 路径必须是 M1 本机 |

边界基线：[`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md) · 拓扑：[`../deploy/topology.md`](../deploy/topology.md)。
