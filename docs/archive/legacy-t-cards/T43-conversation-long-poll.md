# 任务卡 T43 · 对话历史 HTTP 长轮询增量同步（OpenCode 执行）

> 关联：ccc-plan-001 · 依据：T29（对话大脑 /conversation）与 T41（SSE 流式）已落地，前端仍整表轮询 /conversation
> 执行体：OpenCode · 验收：Codex（严格）· 状态：已关闭 · 日期：2026-08-04 · 派发：manual · 项目：ccc
> 变更记录：2026-08-03 老板放行；Codex 决定执行体 OpenCode（工程类任务）；状态置「执行中」防 2017 Engine 抢跑；T42 查验确认单线程阻塞为本卡步骤 1 的必要修复。2026-08-04 执行完成回写（commit 6ad7f8f）。

## 目标

`GET /conversation` 支持 HTTP 长轮询增量同步：客户端带 `after` 光标挂起等待，新消息到达即返回增量，避免前端轮询整表；缺省参数行为保持向后兼容。同时完成服务端并发化（ThreadingHTTPServer），解除 SSE/长轮询挂起时阻塞全服务的 P1 问题（T42 独立复现实锤）。

## 红线（先看）

1. **向后兼容**：`GET /conversation` 不带 `after` 时行为与现版完全一致（返回全量 `{messages}`），现有对话测试必须原样通过。
2. **零硬编码**：长轮询超时默认值走 `config.env` / 环境变量（如 `CCC_WEB_LONGPOLL_TIMEOUT`），代码不出现字面量（硬规则 6）。
3. **不碰运行面**：本卡只产代码 + 测试 + 模板，不在本卡内重启 2017 服务；部署按 T22 部署卡流程另行执行。
4. **单 phase 单 commit**；显式路径提交，禁 `git add -A`（R-15 纪律）。

## 范围

`server/web/server.py`（长轮询协议 + 并发服务化）、`server/web/legacy-chat/js/api.js`（前端增量拉取）、`server/tests/test_http_api.py`（长轮询用例）、`server/config/config.env`（超时默认值配置项）。桌面壳仅保证协议兼容（缺省参数即兼容），不做强制改造。

## 步骤

1. **并发化服务端**：`HTTPServer` → `ThreadingHTTPServer`（server.py:746），否则长轮询挂起期间 /health、/board/states 全部阻塞（现行为单线程，T42 已核实）。
2. **seq 光标**：`_conversations` 为 append-only 列表，以 `len(_conversations)` 作为单调 seq（缺省 0）；`POST /conversation`（同步与 SSE done 两处落历史，server.py:572-573、610-612）写后递增。
3. **长轮询**：`GET /conversation?after=<seq>&timeout=<s>` → 用 `threading.Condition` 挂起等待：有增量立即返回 `{messages: [...新消息], seq: <最新>}`；超时返回 `{messages: [], seq: <不变>}`；连接 reset（BrokenPipe）时退出等待释放线程。
4. **唤醒机制**：历史落写处 `with cond: cond.notify_all()`，与 seq 更新同锁，保证「看到 seq 必见消息」。
5. **前端增量拉取**：`api.js` `loadHistory`/`loadSession` 首次无 `after` 拉全量，之后带 `after=seq` + `timeout` 增量轮询，不再整表重拉。
6. **测试**：补长轮询用例（超时返回空、新消息到达返回增量、after 光标正确、挂起期间 /health 不被阻塞、客户端断开不崩溃）。

## 验收标准

1. `GET /conversation` 无参返回全量（现有 `test_conversation_history_after_success` 等原样通过）。
2. `GET /conversation?after=<seq>&timeout=<s>`：无新消息超时返回 `{messages:[], seq:<不变>}`；有新消息返回增量且 `seq` 推进。
3. 长轮询挂起期间并发请求 `/health` 与 `/board/states` 正常返回（ThreadingHTTPServer 实测）。
4. 客户端连接 reset 后无线程泄漏、服务不崩溃（`lsof`/日志确认）。
5. 前端 legacy-chat 首次全量 + 之后增量轮询（代码可查，无整表重拉）。
6. 验证命令全绿：
   ```bash
   python -m py_compile server/web/server.py
   pytest server/tests/test_http_api.py -q --tb=short
   ruff check server/
   ```
7. **T42 关闭条件**：并发锁重验（双壳同时对话：一路 SSE 流式挂起时，另一路对话返回 503 busy 而非网络阻塞；/health、/board/states 正常）——Codex 复验后 T42 关闭。

## 回写要求

卡头状态更新为「已回写」；回写区填：seq 光标设计说明、ThreadingHTTPServer 切换依据、前端改造 diff 摘要、新增测试清单与结果、并发锁重验记录、push 证据（commit hash）。

## 回写区

**执行体**：OpenCode · 日期：2026-08-04

---

### 1. seq 光标设计说明

- `_conversations` 为 append-only 列表，单调 seq = `len(_conversations)`（缺省 0）；历史清空（测试隔离）后 seq 自然回 0。
- `GET /conversation` 无 `after` → `{messages: 全量, seq}`（向后兼容，仅新增 `seq` 字段，现有对话测试原样通过）。
- `GET /conversation?after=<seq>&timeout=<s>` → `server.py:_wait_conversation_increment` 在 `threading.Condition`（`_conv_cond`）上挂起：`after < len` 立即返回 `_conversations[after:]`；否则等到超时（空增量、seq 不变）或被 `notify_all()` 唤醒。
- 「看到 seq 必见消息」：两处历史写点（同步 `_handle_conversation_post` + SSE done `_handle_conversation_stream`）均在 `with _conv_cond:` 内 append + `notify_all()`，与读取同锁。
- 非法参数：`after` 非整数/负数、`timeout` 非整数 → 400（不挂起）。
- 客户端断开：等待循环每 ≤0.5s 用 `select([connection])` 探测 readable/EOF（`_client_gone`），断开即抛 `ConnectionResetError` 退出释放线程；写响应时 BrokenPipe/Reset 亦被捕获。断连不崩溃、不长期占线程。

### 2. ThreadingHTTPServer 切换依据

- `create_server`/`serve_forever`：`HTTPServer`（单线程）→ `ThreadingHTTPServer`（`server.py:848`），stdlib 一行切换。
- 依据：T42 独立复现实锤——SSE 流式挂起独占唯一线程，`/health`、`/board/states`、第二路 /conversation 均网络层超时（000），brain 并发锁（503 busy）无法触发。切换后长轮询/SSE 挂起不再阻塞其他请求。

### 3. 前端改造 diff 摘要（`api.js`）

- 新增模块级光标 `_historySeq` + 缓存 `_historyMsgs` + `_fetchHistory()`：首拉无 `after` 全量；之后 `after=<seq>&timeout=30` 增量；服务端 seq 回退（重启/清空）→ 以本次返回为准重置。
- `loadHistory`/`loadSession` 改为经 `_fetchHistory` 返回合并后的完整 `{messages}`（旧实现整表重拉 /conversation）。UI 消费契约不变。

### 4. 新增测试清单与结果（`test_http_api.py` `TestConversationLongPoll`，8 项全绿）

| 用例 | 验证点 |
|------|--------|
| `test_no_after_returns_full` | 无 after 全量 + seq 光标（向后兼容） |
| `test_after_cursor_increment` | after 增量切片正确；after 到当前 seq → 空增量 |
| `test_longpoll_timeout_returns_empty` | 超时返回 `{messages:[], seq 不变}`（实测 ≥0.8s 才返回） |
| `test_longpoll_returns_increment_on_new_message` | 挂起被 notify 唤醒，返回增量 + seq 推进 |
| `test_longpoll_hang_does_not_block_others` | 挂起期间 /health、/board/states 正常（实测 <1.5s） |
| `test_longpoll_client_disconnect_no_crash` | 长轮询中途断连 → 服务不崩溃、后续请求正常 |
| `test_invalid_after_and_timeout_400` | 非法 after/timeout → 400 不挂起 |
| `test_hang_second_conversation_503_busy_not_blocked` | T42 关闭条件：锁占用时第二路对话快速返回 503 busy（实测 <1.5s，非网络阻塞） |

结果：`pytest server/tests/` → **339 passed**（T41 基线 331 + 本卡 8）；`python -m py_compile server/web/server.py` OK；`ruff check server/` clean；`node --check js/api.js` OK。

### 5. 并发锁重验记录（T42 关闭条件）

新增 `test_hang_second_conversation_503_busy_not_blocked` 独立重验：一路对话挂起（模拟 SSE 流式占用 brain 锁）时，第二路 `POST /conversation` 实测 <1.5s 返回 **503 busy**（网络层不再阻塞，brain 并发锁真正可触发），同时 `/health`、`/board/states` 正常返回。T42 并发锁项达标，待 Codex 复验后关闭。

### 6. push 证据

代码 commit：`6ad7f8f feat(web): T43 对话历史长轮询增量同步 + ThreadingHTTPServer 并发化（...）`（本回写 commit 推送后一并 push）。

---

## 验收区（Codex 独立取证 · 严格 · 2026-08-04）

**判定：✅ 通过。** P1 单线程阻塞修复 + 长轮询增量同步达标；T42 关闭条件独立复验满足。

### 对照承诺表

| 验收标准 | 实际 | 判定 |
|----------|------|------|
| 1. 无参 GET /conversation 返回全量（向后兼容） | 实测无参返回 `{messages:[], seq:0}`；现有 history 测试原样通过 | ✅ 做到 |
| 2. after 光标：新消息返回增量 + seq 推进；超时返回空 | Codex 独立实测：`after=0&timeout=60` 挂起 → 同步对话落 2 条 → 返回 `{messages:[user+assistant], seq:2}`；超时/非法参数由 8 用例覆盖 | ✅ 做到 |
| 3. 挂起期间 /health、/board/* 正常（ThreadingHTTPServer） | Codex 独立实测：长轮询 + 对话进行中 `/health` 200 @0.002s（修复前同场景 3s 超时 000） | ✅ 做到 |
| 4. 客户端断开无线程泄漏/崩溃 | BrokenPipe/ConnectionResetError 捕获 + select 探测提前退出；测试覆盖断连用例 | ✅ 做到 |
| 5. 前端首次全量 + 之后增量（无整表重拉） | api.js 模块级 seq 光标：首拉无 after，之后 `after=seq` 增量合并，seq 回退自动重置；代码已核 | ✅ 做到 |
| 6. 验证命令全绿 | Codex 独立复跑：pytest 339 collected 0 失败、py_compile OK、ruff All checks passed | ✅ 做到 |
| 7. T42 关闭条件（503 busy 而非网络阻塞） | Codex 独立实测：对话 A 进行中，对话 B → `{"error":"brain busy, try later"}`（503 语义）；/health 正常 | ✅ 做到 |

### 备注

- seq 光标 = `len(_conversations)`（append-only），内存历史重启即失属已知边界（持久化不在本卡范围，与 T41 对话持久记忆观察项同源）。
- 2017 部署（pull + 三服务重启）由 Codex 放行，随 T42 关闭后一并执行（老板实测前置）。

### 2017 部署记录（Codex 放行执行 · 2026-08-04）

- pull → `cdee446`（T43 代码 + 卡关闭）；config.env 补 `CCC_WEB_LONGPOLL_TIMEOUT=30`。
- 三服务重启（web-server 22666 / engine 22668 / board-scheduler 22670），relay 6100/6102 健康。
- 生产实测：同步对话通；长轮询 `after=2` → 新对话落 2 条 → 返回 `{messages, seq:4}`；挂起期间 `/health` 200 @0.002s。
- 看板 48 已关闭/4 打回/0 在飞。老板可双壳实测。

## 机审区

**机审：通过**
- 说明：历史卡，无存档证据，按看板已关闭态标注

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：历史卡，无需额外同步方案状态。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：历史归档，未记录额外复用教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：历史完成，未改变项目架构。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：历史结束，不涉及线路图更新。
