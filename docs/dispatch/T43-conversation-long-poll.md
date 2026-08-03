# 任务卡 T43 · 对话历史 HTTP 长轮询增量同步（OpenCode 执行）

> 关联：新阶段「对话壳感知 + 增量同步」 · 依据：T29（对话大脑 /conversation）与 T41（SSE 流式）已落地，前端仍整表轮询 /conversation
> 执行体：OpenCode · 验收：Codex（严格）· 状态：执行中 · 日期：2026-08-03
> 变更记录：2026-08-03 老板放行；Codex 决定执行体 OpenCode（工程类任务）；状态置「执行中」防 2017 Engine 抢跑；T42 查验确认单线程阻塞为本卡步骤 1 的必要修复。

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

**执行体**：OpenCode · 日期：
