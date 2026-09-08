# 执行结果上报通道 · 阶段一实现报告

> 指令：`/Users/fan/.ccc/instructions/2026-09-05-result-report-p1.md`（C 项解冻，2026-09-05）
> 设计稿权威：`docs/notes/2026-09-03-ccc-result-report-channel-design.md`（稿头状态已更新为「阶段一已实施」）
> 边界（稳）：**旁路观测**——只写独立事件存储，不碰卡文件 / card_gate / 状态机 / 机审 / 合入门禁；文件链（log_dir 结果文件→引擎代写）仍是唯一事实源；上报失败不影响 wrapper 退出码与引擎收单。

## 1. 改动清单与落点

| 件 | 文件 | 说明 |
|---|---|---|
| 服务端存储/校验 | `server/web/result_report.py`（新） | thread-safe JSONL append store + schema 校验 + 鉴权 + 幂等 + 限速 |
| 服务端路由 | `server/web/server.py` | POST `/api/v1/board/result`、GET `/api/v1/board/result/events` |
| 配置白名单 | `server/config/loader.py` | `OPTIONAL_KEYS` 增 `CCC_RESULT_REPORT_TOKEN` / `_EVENTS_PATH` / `_URL` |
| 配置模板/生产 | `server/config/config.example.env`、`config.env` | 三键占位同步（token 初始化见 §3） |
| Wrapper | `scripts/dsh-executor.sh` | 尾部调用共用上报库；`_REPORT_STARTED_AT` 计时长 |
| 上报库 | `scripts/lib/result-report.sh`（新） | 与 testing wrapper 共用的旁路上报逻辑 |
| 测试 | `server/tests/test_result_report_api.py`（新） | 14 项：鉴权矩阵 / schema / 幂等 / 限速 / GET / wrapper 行为 |

## 2. 接口实现要点

### POST `/api/v1/board/result`

- **鉴权**：`Authorization: Bearer <token>`；token 唯一来源 = config.env 新键 `CCC_RESULT_REPORT_TOKEN`（服务端启动读一次，`os.environ` 覆盖）；**空值=端点关闭 → 503**；比较用 `hmac.compare_digest`；token 只进内存，不落日志/响应。
- **请求体**：≤16KB（`Content-Length` 预检，超限 413）；`work_id`(str≤200)、`event`∈4 枚举、`event_id`(缺省服务端补 uuid)、`payload`(dict 白名单)。
- **payload 白名单**：`executor_rc`(int)、`card_title`(str≤200)、`result_path`(str≤200 逻辑标识)、`duration_s`(int)、`probe_status`/`selftest_status`∈{pass,fail,unknown}、`maintenance` 四键∈{yes,no}。**未知字段 → 400+字段名**。
- **work_id 存在性**：经 board loader 索引确认卡存在（`load_dispatch_cards` 索引查询），查不到 → 404；**禁止任何路径拼接**。
- **幂等**：键=(work_id, event, event_id)；重复 → `200 {"deduped": true}`。
- **限速**：单 work_id ≤30 事件/分钟（进程内滑动窗），超限 429。
- **写入**：追加 JSONL 到 `CCC_RESULT_REPORT_EVENTS_PATH`（缺省 `~/.ccc/data/board-events.jsonl`），每行 `{ts, work_id, event, event_id, payload}`，O_APPEND。

### GET `/api/v1/board/result/events`

- 走现有会话读闸（`_gate_read`，与其余 board 读端点同 auth：需 Bearer 或 `?token=`）。
- 参数 `work_id`(可选) + `limit`(默认 50，上限 200；越界 400)。返回 `{events:[...], total}`，事件按 ts 倒序。

## 3. 配置方法

1. `server/config/config.env`（生产，gitignored）追加：
   ```ini
   CCC_RESULT_REPORT_TOKEN=<随机 32+ hex，仅服务端与 wrapper 持>
   CCC_RESULT_REPORT_EVENTS_PATH=/Users/fan/.ccc/data/board-events.jsonl
   CCC_RESULT_REPORT_URL=http://192.168.3.116:7788/api/v1/board/result
   ```
2. 重启 web-server（engine 不动）：
   ```bash
   launchctl kickstart -k gui/$(id -u)/com.ccc.web-server
   curl http://127.0.0.1:7788/health   # 200
   ```
3. token 只经 HTTP Header，禁落日志/结果文件/卡正文/本报告（红线）。

## 4. Wrapper 行为矩阵（scripts/dsh-executor.sh 尾部）

| 条件 | 行为 |
|---|---|
| token 空 或 `$LOG_DIR/.result-report-disabled` 存在 | 跳过（不发送） |
| rc=0 / rc≠0 | event=`executor_completed` / `executor_failed`；payload 仅 `executor_rc`、`duration_s`、`result_path=<work_id>-ccc-result.md` |
| HTTP 403 / 404 / 503 | 写 disabled 旗标（本会话不再试） |
| 网络失败 / 上传超时 | `log_dir/<work_id>.result-report.log` 一行备注；**不改 rc、不影响退出码** |
| 不设 disabled 旗标的 2xx | 静默成功 |

不上报：卡全文、DSH 原始输出、凭据、本机绝对路径（设计稿 §4）。

上报逻辑抽到 `scripts/lib/result-report.sh`（`ccc_result_report <work_id> <rc> <duration_s> <log_dir>`），与测试 wrapper 共用同一份代码，规避双实现漂移。

## 5. 验证结果

- `pytest server/tests/ -q`：除 `test_parallel_dispatch_concurrency`（既有时序敏感用例，隔离重跑 2.13s<1.8s 仍超，与本改动无关）外全绿；`server/tests/test_result_report_api.py` 14/14 通过。
- `.venv-hub/bin/ruff check server/` 净。
- `bash -n` 通过 wrapper 与库。
- 交付前 web-server 重启 + `/health` 200 + token 配置完成（见 §3）。

## 6. 阶段二待办（设计稿 → 前端消费）

1. **看板前端「执行中」合成视图**：读 `GET /api/v1/board/result/events`，将 API 事件与卡文件 / `runtime_state` 合成进度展示；事件只补充实时进度，不准覆盖卡文件终态（设计稿 §3.3）。
2. **事件对账报警**：API 事件与文件链（log_dir 结果 / 主仓卡）不一致时后台对账报警（设计稿 §6「事件与文件链不一致」）。
3. **token 轮换**：短期 token + 轮换流程（当前为静态 token；轮换 = 换 config.env 值 + wrapper 侧同步）。

## 7. 红线遵守确认

- 未改 `server/board/card_gate.py` / 状态机 / 机审 / engine 主循环；未改任何卡文件。
- 事件存储为独立 JSONL，只读观测，未成为第二事实源。
- commit 语义化逐笔 push（`feat(report): ...` / `test(report): ...`）。

--- 结论：阶段一完成，等待阶段二（前端合成视图）。