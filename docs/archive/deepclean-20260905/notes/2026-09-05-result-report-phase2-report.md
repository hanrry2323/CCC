# 执行结果上报通道 · 阶段二实现报告

> 指令：`/Users/fan/.ccc/instructions/2026-09-05-result-report-p2.md`
> 设计稿：`docs/notes/2026-09-03-ccc-result-report-channel-design.md`（状态：阶段一+二已实施 2026-09-05）
> 本阶段边界：**事件只补充展示；卡文件/运行时状态机仍是唯一真值；终态事件不复活卡**。

## 1. 后端合成规则

新增 `GET /api/v1/board/executing`，复用现有会话读闸。服务端先读取当前看板卡（含既有运行时合成结果），再读取事件 JSONL，按 `work_id` 关联：

| 卡源 A | 事件源 B | 输出 |
|---|---|---|
| 基础态=执行中 | 有事件 | 返回卡条目，`source=card+event`，附最近事件、事件时间 |
| 基础态=执行中 | 无事件 | 仍返回卡条目，`source=card-only`；事件缺失不是错误 |
| 终态（已回写/已关闭/打回/作废） | 仍有事件 | 不返回；计入 `suppressed_terminal_events`，事件不改变卡状态 |
| 不存在的 `work_id` | 有事件 | 丢弃，不造卡；按唯一 work_id 计入 `orphan_work_ids` |

事件按 `ts` 取每张卡的最近一条；坏行/非对象记录跳过，不使端点失败。响应顶层含：

- `generated_at`：服务端生成时间；
- `items` / `count`：仅当前基础态为执行中的卡；每条含 `id`、`title`、`executor`、`state`、`claim_at`（若模型提供）、`event`、`event_ts`、`source`；
- `reconciliation`：`suppressed_terminal_events`、`orphan_work_ids`、`last_event_ts`。

实现落点：`server/board/executing.py`、`server/web/server.py`。未修改状态机、card gate、机审、收单逻辑或卡文件。

## 2. 前端执行中实时区块

看板页 `server/web/legacy-chat/js/pages/boardPage.js` 新增「执行中实时」区块：

- 调用 `GET /api/v1/board/executing`，使用现有 `apiGet`，因此自动携带会话 token；
- 页面可见时每 15 秒轮询；卸载时清理计时器；
- 每条显示卡号、标题、执行体、事件徽标（`started` / `completed` / `failed` / `suspended`）及相对时间；
- 显示来源 `卡+事件` 或 `卡`；顶部显示终态抑制/孤儿对账数字；
- 401 或网络失败不阻塞看板，保留最近一次成功数据并把该区块置灰，提示「实时事件不可用（降级）」；
- 无事件或无执行中卡分别显示明确空态。

样式复用现有 CSS 变量，新增样式位于 `server/web/legacy-chat/css/shell.css`，未引入依赖。

## 3. 测试与检查

新增 `server/tests/test_executing_view.py`，覆盖：

1. A 有 B：事件徽标、来源、时间与 `generated_at`；
2. A 无 B：卡仍出现且为 `card-only`；
3. 终态抑制：终态卡不出现在视图且计数增加；
4. 孤儿丢弃：不造卡且计数增加；
5. 最近事件选择与坏记录容错。

已执行：

- `python3 -m pytest -q server/tests/test_executing_view.py` → **4 passed**；
- `node --check server/web/legacy-chat/js/pages/boardPage.js` → **通过**；
- `python3 -m py_compile server/board/executing.py server/web/server.py` → **通过**；
- 前端未配置 headless 截图能力，本报告不虚报截图路径。

全量结果：`python3 -m pytest -q server/tests/` 共 1 失败 / 其余全绿。失败项 = 既有测试 `test_unconfigured_token_returns_503`（实际 401，期望 503）。根因 = 工作树中预先存在的 `server/config/config.env` token 改动（本会话进场前即 `M`，把 `CCC_RESULT_REPORT_TOKEN` 从空值填成生产值）：该测试依赖「token 为空=端点关闭→503」，本地配置不再为空故得到 401。**该改动非本阶段所改、未纳入提交**（token 属秘密，不进 git）。其余全部通过，含本阶段新增 `server/tests/test_executing_view.py` 4 项。

## 4. 手测记录

建议在 2017 web-server 重启后执行：

1. 带有效会话 token 打开看板页，确认「执行中实时」区块出现；
2. 观察 15 秒轮询，卡源无事件时显示 `来源: 卡`；
3. 向既有阶段一 POST 入口上报 `executor_started`，刷新区块确认出现 `started` 与相对时间、来源变为 `卡+事件`；
4. 将卡推进终态后保留事件，再观察该卡从实时区块消失且对账终态抑制数增加；
5. 停止 web-server 或使请求返回 401，确认区块置灰并显示「实时事件不可用（降级）」，看板其他列仍可用；
6. 重启服务：`/health` 应为 200；不带会话 token 请求新端点应为 401。

本轮未执行生产 web-server 重启，也未生成 headless 截图；因此不声明运行面已部署验证。

## 5. 提交记录

- `6e465ff92` — `feat(report): add executing board synthesis view`
- `19a49df91` — `feat(board): live executing panel with event badges (phase2)`

## 6. 红线确认

- 事件为旁路观测，不覆盖卡状态；
- 终态优先，终态事件不复活任何状态；
- 未改状态机、card_gate、机审、收单逻辑、POST 上报契约或卡文件；
- 每个模块独立 commit 并已 push；
- 生产配置 `server/config/config.env` 的未提交 token 改动为进场前既有变更，未纳入本阶段提交。
