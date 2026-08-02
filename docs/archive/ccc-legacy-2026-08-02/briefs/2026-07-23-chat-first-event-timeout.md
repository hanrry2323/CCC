# Fix: Desktop 对话 first_event_timeout 误杀

| 字段 | 值 |
|------|-----|
| brief_id | `2026-07-23-chat-first-event-timeout` |
| 现象 | 长提示后对话「断开」；账本 `first_event_timeout` / 偶发 `client_progress_stall` |
| 根因 | 首包门禁默认 60s + Desktop 客户端进展门 75s；MiniMax/loop-code 长提示首包常超过 |

## 改动

1. `CHAT_FIRST_EVENT_TIMEOUT` 默认 **60→120**（`scripts/chat_server/config.py`）
2. query 后立即 SSE `status phase=accepted`（刷 UI；**不**解除首包门禁）
3. Desktop `progressLimit` **75→150**（`APIClient.swift`），避免客户端先于 sidecar 误杀

## 部署

- sidecar：已 kickstart，`FIRST_EVENT=120`
- Desktop：已 package + 安装 `/Applications/CCCDesktop.app` 并 relaunch
