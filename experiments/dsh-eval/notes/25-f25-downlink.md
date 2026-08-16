# 实验 F25 · 生产下行协议确认（WS vs SSE）

- **状态**：✅ 完成（实证：WebSocket）
- **批次**：B6 模型
- **环境**：网络探针
- **日期**：2026-08-16

## 结论

**生产下行是 WebSocket，不是 SSE**。`/api/events.mux` 与 `/api/events.host` 对普通 GET 返回 `426 Upgrade Required` + `upgrade: websocket`；带 WebSocket Upgrade 头 → `101 Switching Protocols` + 帧流（`session/subscribed` 等 server-request 推送）。报告维度六的「两条 WS 单向流」得到实证。

## 证据

- `curl /api/events.mux` → `HTTP/1.1 426 Upgrade Required` + `upgrade: websocket`
- `curl /api/events.host` → 同上 426
- 带 WS 握手头 → `101 Switching Protocols` + `Upgrade: websocket`，随后收到多条 `server-request`（session/subscribed，含 lastSeq 计数）——推流确认
- 帧样例：`session/subscribed` payload 带 sessionId + lastSeq（会话状态增量推给浏览器）

## 结论细节

- 下行 = WS 单向流（host→browser），承载会话事件推送。
- 上行 = HTTP POST JSON-RPC（报告维度六已述，本次未复测上行）。
- `session/subscribed` 推流证明浏览器持有会话状态镜像（zustand 投影），随事件增量更新。

## 风险 / 对 CCC 借鉴的影响

- 若 CCC 要程序化订阅 DSH 会话事件（如审计/看板联动），需实现 WS 客户端连 events.mux，不是 SSE。协议确认对集成方有用。
