# Hub Remote Desktop Shell

> **状态**：现行 · 2026-07-21（纠偏）  
> **一句话**：HTTP SPA ≈ **远程 Desktop（约 90% 能力）**——对话跟 M1 sidecar；编排跟 Hub。  
> **禁止**：在 Mac2017 再维护第二套产品聊天 / `hub::` 会话分区。

---

## 形态

```text
浏览器 → Hub :7777 SPA
  ├─ /api/agent/*     → 反代 M1 sidecar :7788（对话热路径，与 Desktop 相同）
  ├─ /api/desktop/*   → threads 同步面 / transfer / flow（与 Desktop 相同）
  └─ /api/board|ops   → 看板 / 运维（与 Desktop 相同）
```

| 面 | 权威 |
|----|------|
| 对话 runtime | M1 `com.ccc.agent-sidecar` → loop-code |
| 本机会话文件 | M1 Desktop `LocalSessionStore`（HTTP 经 Hub threads 镜像同步） |
| thread id | `{projectId}::…`（与 Desktop 一致） |
| 看板 / transfer | Hub on Mac2017 |

---

## 环境（2017 Hub）

| 变量 | 默认 | 说明 |
|------|------|------|
| `CCC_DESKTOP_AGENT_URL` | `http://192.168.3.140:7788` | M1 sidecar |
| `CCC_AGENT_TOKEN` | （与 M1 `~/.ccc/agent-token` 相同） | 反代注入，浏览器不持有 |
| `CCC_DESKTOP_WORKSPACE_MAP` | JSON 可选 | `{"ccc-demo":"/Users/apple/program/apps/ccc-demo"}` |

M1 sidecar 须对 2017 可达：`CCC_AGENT_HOST=0.0.0.0`（仅内网）+ token。

---

## SPA

- `#/chat`：经典对话壳；`streamChat` → `POST /api/agent/api/chat`
- 历史：`GET /api/desktop/threads/{id}`；回合结束后 `PUT …/messages`
- `project_path`：来自 workspace map（须为 **M1 本机路径**）
- 讨论/工程：`tool_mode` 与 Desktop/sidecar 一致

---

## 烟测

```bash
CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-hub-remote-desktop.sh
```

---

## 废弃

- `/api/remote-chat/*` 独立 2017 会话槽（已删）
- `hub::` thread 前缀产品叙事
