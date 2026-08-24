# T70 全项目代码 bug 检查报告（Cursor · 2026-08-05）

> 分支：`codex/cursor-t02-code-audit` · 基线 main `0862c47` · 只读审计（未改 `server/`/`desktop/` 业务代码）  
> 对照：`docs/cursor-code-check-handoff.md` §三 已知问题标「已登记」  
> 方法：代码走读 + 本地复现脚本 + pytest 全量 + `swift build`

## 验证证据摘要

### pytest（本机 M1 · `.venv-hub/bin/python`）

```text
$ .venv-hub/bin/python -m pytest server/tests --tb=no
7 failed, 484 passed in 13.50s
```

失败 7 例全部在 `server/tests/test_engine_main.py`，日志均为本机无中继：

```text
探活失败: URL http://127.0.0.1:6100/ … Connection refused
探活失败，跳过该卡（保持待分派）
```

**判定**：中继相关用例失败属环境正常（M1 不跑 6100）；非本次新引入回归。其余 **484 passed**。

### desktop

```text
$ cd desktop && swift build
Build complete! (SWIFT_EXIT:0)
```

`swift test` 未单独跑（无强制要求）；Swift 源码级缺陷见下表 D 组。

---

## 〇、已登记（交接文档 §三 · 不重复发明）

| 编号 | 引用 | 状态 | 位置备忘 |
|------|------|------|----------|
| K1 | 交接 §三 #1 | 已登记 | 网络根因未修；前端 T68 `bootloader.js` 已兜底 |
| K2 | 交接 §三 #2 | 已登记 | `server/web/legacy-chat/js/auth.js:156`「未登录」；退出按钮仍挂载 |
| K3 | 交接 §三 #3 | 已登记 | 大脑/看板卡数口径待核（数字随 T70 已变，问题类型仍在） |
| K4 | 交接 §三 #4 | 已登记 | `deploy/release.sh:220` DATA_DIR fallback=`$REPO_PATH/data` |
| K5 | 交接 §三 #5 | 已登记 | Nginx 模板在仓、2017 未装；brew formula 归因证据偏弱 |

---

## 一、新发现问题清单（≥15）

### A. server/engine · board

| 编号 | 位置 | 现象 | 证据 | 影响 | 严重级 | 修复建议 |
|------|------|------|------|------|--------|----------|
| F01 | `server/engine/store.py:216-225`（`_STATE_PAIR_RE` @36） | `save_work` 声明只改卡头 `>` 行，实际全文首个「状态：」即替换；卡头缺状态时会改正文 | 本地复现：卡头无「状态」、正文 `- 状态：已关闭 才算完成` → 变成 `- 状态：执行中` | 正文被改写；Engine 误以为状态已回写 | **P0** | 仅在 `>` 元数据行内替换；找不到卡头状态则 fail 不写 |
| F02 | `server/board/loader.py:145-147` | 任一任务卡非 UTF-8 → `read_text` 抛错，整次扫描失败 | `_is_task_card` 无 try/except；`scan_dispatch_files` 直接调用 | 看板/Engine 列表空或崩溃 | **P0** | 单文件捕获 `UnicodeDecodeError`/`OSError`，跳过并打日志 |
| F03 | `server/engine/store.py:113-115` | 非法/未知状态被强制当成「待分派」进入派发 | `if st is None: st = State.TODO`；与 `_state_from_str` 文档「应跳过」相反 | 畸形卡可能被自动拉起 | **P1** | `st is None` 时 `continue` |
| F04 | `server/engine/main.py:298` + `337-338` | 只扫 `TODO`；worker 未捕获异常时卡留在「执行中」永不回收 | `pending = store.list_work(state=State.TODO)`；`except` 仅 `logger.exception` | 崩溃/杀进程后死信；看板撒谎 | **P1** | 启动/循环回收无 PID 的 RUNNING→打回或待分派；worker except 必须 transition |
| F05 | `server/engine/store.py:112-118` | Engine `list_work` 不过滤 `archived` | 索引含 archived；loader 有过滤（`loader.py:359-360`），store 无 | 归档卡可能再被派发 | **P1** | `if entry.get("archived"): continue` |
| F06 | `server/engine/cluster.py:189-195` | cluster 输出路径与 HTTP 静态白名单不一致 | `DATA_DIR/cluster.js` 或 fallback `server/server/web/data/cluster.js`；白名单要 `server/web/data/cluster.js`（`server.py:231`） | 运维/集群页读到空或过期数据 | **P1** | 写入路径与 `_STATIC_WHITELIST` 对齐 |
| F07 | `server/board/loader.py:347-357` | 增量解析失败静默丢卡并覆写索引 | `except Exception: continue` 后 `save_index_file(updated_entries)` | 卡从看板消失无提示 | **P1** | 失败保留旧索引项 + 打 error |
| F08 | `server/engine/main.py:351-357` | 并行派发在获 semaphore 前就把卡写成「执行中」 | 先 `transition(RUNNING)+save` 再 `Thread.start`；worker 内才 `with semaphore` | 看板虚高「执行中」；加剧 F04 死信面 | **P2** | 获锁后再标执行中，或增加「排队」态 |
| F09 | `deploy/release.sh:285` | 生产 `git checkout <commit>` 可停在 detached HEAD | `git checkout "$TARGET"`；T48 审计 #9 已观测下次 pull 失败 | 后续部署/pull 需手修 | **P2** | checkout 后 `git checkout main && git merge --ff-only` 或明确文档 |

### B. server/web · kb · 前端

| 编号 | 位置 | 现象 | 证据 | 影响 | 严重级 | 修复建议 |
|------|------|------|------|------|--------|----------|
| F10 | `server/web/server.py:1310-1316` vs `1327` | `GET /projects/*/threads` 在 `_check_auth()` 之前返回；且不在 `_NO_AUTH_PATHS` | 路由顺序：threads 处理 → return；auth 检查在后 | `CCC_WEB_AUTH_REQUIRED=1` 时会话元数据可未授权读取 | **P1** | 挪到 auth 之后；或显式列入白名单并文档化 |
| F11 | `server/web/legacy-chat/js/api.js:371-387` | SSE 网络中断返回 `'network'` 但不 `settleError`；注释声称已 settle 为假 | `catch` → `return 'network'`；重试后无 `if (!settled) settleError(...)` | 该 tab 永久卡在 streaming（发送锁死）直至硬刷新 | **P0** | 重试结束后若未 settled → `settleError('网络中断')` |
| F12 | `server/web/legacy-chat/js/api.js:368-369` + `server.py:936-950` | EOF 无 `done` 时前端 `settleDone`（当成功）；服务端不持久化 | 客户端 EOF→settleDone；服务端仅 `finished_error is False` 才 persist | 当面看得到回复，刷新/他端丢失 | **P1** | EOF 无 done → settleError/incomplete；或服务端落盘 partial |
| F13 | `server/web/legacy-chat/js/app.js:478-496` + `api.js` `_fetchWithAuth` | 长轮询 abort 未传入 `fetch` signal | `currentPollAbort.abort()` 后 `loadSession`/`apiGet` 不接 AbortSignal | 切会话后旧 30s 请求仍在；重叠轮询/串台风险 | **P1** | 全链路传递 AbortSignal；结果校验当前 sid |
| F14 | `server/web/legacy-chat/js/components/boardPanel.js:118-121` + `api.js:208-210` | 任务跟踪仍调已禁用的 `pollTaskUntil`（直接 throw） | `pollTaskUntil` → `throw new Error('轮询已禁用')`；调用方无 `.catch` | 未处理 Promise 拒绝；列变更 toast 死 | **P1** | 改用 `/board` 或 `/tasks/{id}` 轮询，或删除跟踪入口 |
| F15 | `server/web/server.py:466-475` vs `274-280` | `GET /tasks/{id}` 详情恒 `card_kind:"work"`，快照侧能区分 epic | `_find_task_detail` 写死 work；`_item_to_board_task` 按 `item.type` | 详情弹层 epic 类型错误 | **P2** | 复用 `_item_to_board_task` 字段 |
| F16 | `server/web/session_store.py:162-177` | 会话索引 load→mutate→write 无锁 | `touch_thread`/`_write_index` 全文件覆写；`ThreadingHTTPServer` 并发 | 丢会话条目/错误计数 | **P1** | 每项目 Lock 或文件锁 |
| F17 | `server/kb/search.py:255-268` + `indexer.py:265-271` | 损坏 `documents.json` 或空引擎被进程级缓存；brain 静默无 KB | `get_engine` 首次缓存；`json.loads` 无降级；brain 捕获后空上下文 | 检索长期空结果无用户可见告警 | **P2** | load 失败触发 rebuild；按 index_dir 分键；health 暴露 degraded |

### C. desktop（已 `swift build` 通过；缺陷为源码级）

| 编号 | 位置 | 现象 | 证据 | 影响 | 严重级 | 修复建议 |
|------|------|------|------|------|--------|----------|
| F18 | `desktop/.../APIClient.swift:442-452` + `AppModel.swift:1346-1355` | 看板 `workspace` 传文件系统路径，服务端按**项目名**过滤 | Desktop: `workspace_path ?? id`；Server: `i.project == workspace`（`server.py:315`）；HTTP 壳传项目 id | 桌面看板空列，HTTP 正常——双壳不一致 | **P0** | `workspace=` 传 `project.id` / `"all"` |
| F19 | `desktop/.../BoardView.swift:62-74` | Kanban 仍用英文旧列名（backlog/in_progress…） | `columnOrder = ["backlog",…]`；契约五态为中文；`TaskCardPanel` 已中文 | Kanban 模式对现行 API 基本空转 | **P0** | 列改为 `待分派/执行中/已回写/已关闭/打回` |
| F20 | `desktop/.../APIClient.swift:124-127` | 流式对话 body 只有 `message`+`stream`，缺 `thread_id`/`model` | HTTP `api.js:263-269` 发 thread_id+model；Desktop `StreamBody` 无字段 | 多线程上下文串台；模型偏好无效 | **P0** | 扩展 StreamBody 并贯通 preferredModel |
| F21 | `desktop/.../AppModel.swift:1543-1545` | `isThreadStreaming`/`streamStatus` 桩函数恒 false/空 | 真实状态在 `streamChatTasks`/`threadStreamStatus`，UI 读桩 | 侧栏/取消/streaming 指示永不亮 | **P1** | 桩改为查真实 map |

---

## 二、覆盖与优先级建议

| 区域 | 覆盖 | 代表编号 |
|------|------|----------|
| server/engine+board | 已查 | F01–F09 |
| server/web+kb+前端 | 已查 | F10–F17 |
| desktop | 已查（swift build OK） | F18–F21 |
| 已登记 | 对照 §三 | K1–K5 |

**建议修复序**：F01/F02/F11/F18/F19/F20（P0）→ F03–F07/F10/F12–F14/F16/F21（P1）→ 其余 P2 + K 组联调卡。

---

## 三、统计

- 新发现：**21** 条（F01–F21）  
- 已登记引用：**5** 条（K1–K5）  
- P0：6 · P1：11 · P2：4  
- 未改业务代码；本报告 + T70 回写为唯一写项  
