# 034 · 前端性能根治 —— 页面切换慢 + 「API 断开」

> 方案编号：ccc-plan-034 · 日期：2026-08-17 · 状态：已实施
> 执行体：M1 主窗口直接开发（ccc taskable:false，不出卡不走 engine）· 平台自研
> 验收：验收席独立验证（本方案交付代码 + 证据，终验归 Codex）

## Context

老板反馈前端页面切换慢（计划/线路图等明显），偶发「API 断开」报错。此前多次局部优化只缓解个别页面。本次要求**根治根因，不打补丁**。

三路只读调查确认根因分三层：

1. **切换机制**：`app.js onHubRoute` 每次导航「全量卸载 + `await page.mount()` 阻塞整条切换」；无数据缓存（切回必重拉）、无 abort（快速连点新旧请求并发洪峰）、无超时（`apiGet` 无 signal，挂起请求让 mount **永久 pending → 切换卡死**）。叠加常驻全局轮询（health 30s / relay 10s / 对话长轮询死循环 / 对话右栏 5s 拉 1000 卡）永不停 → 持续压服务器。
2. **连接 + API 断开**：web-server 是 HTTP/1.0 无 keep-alive（每请求新 TCP 连接 → 连接 churn 大）；「网络中断，请重试」是 `streamChat.runOnce` 把浏览器导航/切换 abort 产生的 `TypeError: Failed to fetch`（非 AbortError）**误判为真实网络故障**弹错；服务器 ConnectionResetError 被 Python 3.14 `handle_one_request`（只 catch TimeoutError）+ do_GET/POST 无外层捕获打成 traceback 噪音。
3. **渲染**：plansPage `render()` 整页 `innerHTML` 无签名重建（60-70 卡 / 2000+ 节点），30s 定时器 + 每次交互触发，`filteredPlans()` 每 render 重复 7 次；opsPage 每 15s 拉 12 请求 + 6 区块全量重建；boardPage 已有签名+虚拟滚动兜底（剩 5s 全量重拉 211 卡 + 运行列每 5s 整列销毁重建 stream 盒 + `handleScroll` 无 rAF 节流）；roadmapPage 二级页整页 innerHTML 重建（草案池最多 37 卡）。

## 目标

- 切换即时响应：骨架秒现、数据到达增量填充、切回不重拉（M2 缓存）
- 「API 断开」不复发：浏览器导航 abort 静默、服务器 abort 静默、keep-alive 消除连接 churn
- 四页渲染从全量重建降为签名增量；服务器负载显著下降

## 关键设计决策

| # | 决策 | 做法 |
|---|------|------|
| D1 | 服务器 keep-alive | `_APIHandler` 加 `protocol_version="HTTP/1.1"` + `handle()` 内 `settimeout(30)` 空闲回收；SSE 显式 `Connection: close` |
| D2 | abort 静默 | 服务器 `handle()` 层 try/except 静默客户端断开；前端识别导航/切换 abort 走 settled |
| D3 | 数据层 | api.js 内存 TTL 缓存（10s，SWR）+ 同 key 在途去重 + 写后全清 + GET 15s 超时 + 瞬时错误 1 次重试 |
| D4 | 路由切换 | `onHubRoute` 令牌化 + `pageScopeAbort()` + 非阻塞 mount（同步骨架，数据后台填充） |
| D5 | 渲染 | 学 board 签名机制（`taskCardList.js:45-57`）推广到 plans/ops/roadmap |
| D6 | 常驻轮询 | 按可见性 + 路由门控（health/relay/长轮询/右栏） |

## 分模块改动（已实施）

### M1 · 服务端连接与日志静默（`server/web/server.py`）
- `_APIHandler` 类体加 `protocol_version = "HTTP/1.1"`（JSON/静态响应已有 Content-Length，帧完整可复用）
- 覆写 `handle()`：`settimeout(30)` + `try: super().handle() except (BrokenPipeError, ConnectionResetError, OSError, TimeoutError): self.close_connection = True`（一处覆盖 do_GET/do_POST 分发与写响应全部抛出点）
- 两处 SSE `_handle_tasks_stream` / `_proxy_chat_stream` 的 `Connection: keep-alive` → `close`（无限流无 Content-Length 不合法）；`_handle_conversation_stream` 已 close 保持；删 `_proxy_chat_stream` finally 后死代码 `_send_404()`

### M2 · 前端数据层（`legacy-chat/js/api.js`）
- 页面级请求作用域：`pageScopeAbort()/pageScopeSignal()`（切路由中断旧页全部页面级 GET）
- 内存 TTL 缓存：`CACHEABLE_PREFIXES` 白名单（plans/list、card-states、roadmap、summaries、projects 等）+ `/cards /tasks /ready_for_merge /conversation /health` 不缓存；写操作成功 `invalidateCache('/')` 全清；同 key 在途合并
- GET 统一 15s 超时（`AbortSignal.timeout` + `AbortSignal.any` 合并）；瞬时 `TypeError` 1 次 400ms 退避重试
- `streamChat.runOnce` 两处 catch 加 `_isNavAbort()`（路由切换中/页面隐藏）→ settleDone 静默，不落 `'network'` 不弹「网络中断」；`pagehide` 监听 abort 活跃流 + cancelAllStreams
- 热回滚开关 `window.__CCC_CACHE_DISABLED__`

### M3 · 路由切换架构（`app.js` + 六页）
- `onHubRoute`：`_routeGen` 令牌 + `setRouteSwitching(true)` + `pageScopeAbort()` + **非阻塞 mount**（同步渲染骨架 → 后台拉数据，不 await 网络）；保留 T46 护栏（只 abort 页面级 GET，不动流/写操作）
- 六页 mount 全改非阻塞 + `_disposed` 状态 + unmount 清理（清定时器 + 置 disposed + 清监听）；`_root`/`_disposed` 守卫防卸载后空指针（ops/roadmap/board/plans/console/dsh）
- 常驻轮询门控：health/relay 可见性门控；对话长轮询「chat 路由 + 可见」门控（光标在 `_historyCursors` 前端态，切回续拉增量不丢上下文）；对话右栏 5s→10s + 可见性门控

### M4 · 渲染根治
- **plansPage**：静态壳（shellHTML 建一次）+ `renderFlow()` 只刷列 + 列签名（`path+status+acceptance+flow 分布+卡状态`，未变复用列 DOM）+ `filteredPlans()` 每 render 只算 1 次 + 事件委托（列重建不重绑）+ 删死代码 renderColumn
- **opsPage**：`setHtml(el, html)`（字符串相等则不动 DOM）六个 render 全改 + `/roadmap/{proj}` 走 M2 缓存消 N+1 + 15s→30s 降频
- **boardPage**：`handleScroll` rAF 节流；`renderRunCol` 签名去瞬态字段（tool_calls/audit_runs）+ `_updateRunColMetrics` 增量更新徽标保留 stream 盒；5s→10s + 可见性门控
- **roadmapPage**：`_root`/`_disposed` 守卫 + 非阻塞 mount + unmount 重置 `_currentProject`（切回回总览）；无高频重建源，详情签名不做（避免过度工程）
- **ui.js**：新增 `setHtml` 幂等 innerHTML

## 验证结果（已跑）

1. `pytest server/tests/test_http_api.py` 141 项全绿（keep-alive 回归）
2. `pytest server/tests/test_plans.py` 全绿（契约测试 `test_exports_mount` 同步更新为 `export function mountPlans` 非阻塞签名）
3. 全部改动 JS `node --check` 语法通过
4. keep-alive 实证：单连接二次请求复用（HTTP/1.1 200）
5. abort 风暴实证：30 连发（含中途断开）服务器 stderr 零 traceback
6. 缓存判定独立验证 17 例全对（可缓存/不可缓存区分正确）
7. 列签名逻辑验证：数据不变签名稳定、验收变/状态流转签名精确变化
8. 非阻塞 mount 语义验证：同步返回、卸载后丢弃旧数据

## 已知遗留（非本次范围）

- `test_real_dispatch_cards` 失败：`docs/dispatch` 卡 hp009 状态为「作废（任务本身高风险…）」，`base_state()` 归一返回 `'作废'` 但测试白名单缺该态——**pre-existing 数据层债务**（stash 后仍失败，与本次前端改动无关），待后续卡状态白名单治理。

## 回滚点

- 服务器：删 `protocol_version` 一行 + 两处 SSE 头还原 + 删 `handle()` 覆写 → 完全回退 HTTP/1.0
- 缓存/超时/重试：`window.__CCC_CACHE_DISABLED__=1` 热回滚（不动码）
- 路由：还原 `onHubRoute` 函数体（git revert 单函数）
- 渲染：各页独立 revert
