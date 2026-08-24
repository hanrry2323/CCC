# CCC 稳定性代码级风险清单（2026-08-12 交叉验证扫描）

> 扫描范围：server/engine/ 全部 Python 文件 + git_sync.py、scripts/ 全部 shell 脚本、server/web/ HTTP 服务、server/board/ 看板模块（约 1.9 万行，只读扫描，未改任何代码）。
> 结论：地基（git 真相 + 原子写 + 状态机）设计扎实，但存在 5 个会实际咬人的洞——执行体超时只杀父进程、HTTP 无线程上限、归档/方案写盘不落 git、索引跨进程覆写、git_sync 与主树直写互踩。

## P0（会造成挂死 / 进程泄漏 / 数据丢失）

### 1. server/engine/main.py:2116-2155 · 泄漏（子进程族）
- 触发：执行体（OpenCode/Claude）超时或失败，`proc.kill()` 只杀 CLI 直接子进程；CLI 派生的 node/工具链/ssh 孙进程继续跑。Engine 重启后 `.running` 标记里的 child_pid 仍存活 → 卡永远「执行中」不被回收。
- 加固：`Popen(start_new_session=True)`，超时改 `os.killpg` 杀全组；收单 wait 加二次超时；`.running` 标记加最大存活时限兜底。

### 2. server/web/server.py:3000-3021 + 2557-2645 + 1879-1975 · 泄漏（线程/连接耗尽）
- 触发：`ThreadingHTTPServer` 每连接一个线程且无上限、无 daemon_threads；`/tasks/stream` 是无限 keep-alive SSE（无最大时长）；`/conversation` 长轮询 timeout 由客户端参数直接传入（`timeout = max(0, int(t_raw))` 无上限）。多个页签挂着不关 → 线程无限涨 → accept 队列填满 → 全部新请求超时（与 T43 同型事故，只是从单线程变成线程池耗尽）。
- 加固：换成有界线程池（max_workers + 信号量），SSE 设空闲超时（60s 无数据即关），长轮询服务端封顶 60s。

### 3. server/board/scheduler.py:57-63 → server/board/archive.py:97-108 · 数据不一致（归档不落 git）
- 触发：board-scheduler 每轮自动跑归档，`git mv` 后不 commit/push；随后 engine/web 的 git_sync `checkout -f` 把 dispatch 卡恢复 → 同一卡同时出现在 dispatch 与 archive → 看板双份、主树永久脏、`git pull --ff-only` 部署失败。
- 加固：归档移文件后同批 commit+push；或 scheduler 保持纯只读，归档改人工/计划卡触发。

### 4. server/board/loader.py:272-282,375 · 竞态（索引覆写丢卡）
- 触发：engine 心跳、web 看板、new-card.sh 多进程同时增量重扫，各自整体覆写 `cards.index.jsonl`；后写者基于旧索引，把对方刚入库的新卡抹掉，卡从看板消失直到下次重扫。
- 加固：索引写加跨进程 fcntl 文件锁（复用 new-card.sh `.card-lock` 模式），或按 (path,mtime) 合并增量而非整体覆写。

### 5. server/git_sync.py:145-176 + server/engine/main.py:2486-2525 · 竞态（同步与主树直写互踩）
- 触发：认领超时回收 `_clear_claim_marker` 直写主树卡文件（非原子）→ commit 前 git_sync `checkout -f` 把该改动 revert，或 untracked 清理把并发新建的卡删掉；两者同进程不同步。
- 加固：主树任何写（认领清除/机审落盘）改 tmp+rename 原子写，且 git_sync 的 force-checkout 前对「本进程刚写过、尚未 commit」的路径做保护名单或文件锁。

## P1（挂死 / 静默失败）

### 6. server/engine/main.py:160-180, 86-115, 500-510, 1292-1310, 1901-1985, 2513-2520 等 · 挂死（git 无 timeout）
- 触发：业务仓或主仓被 index.lock、网络盘挂起时，无 timeout 的 `git clean/checkout/status/log/diff/add/commit/push` 永久阻塞心跳线程。
- 加固：统一 `_git(cmd, timeout=…)` 包装（15-120s），全部 git 调用走它。

### 7. server/board/docgate.py:44-190 · 挂死（同型）
- 触发：合入批准/机审 Q3/Q4 校验里 `git rev-parse/show-ref/log/diff` 全 `check=True` 且无 timeout。
- 加固：同上，统一 timeout。

### 8. server/engine/main.py:328-372 · 静默失败（机审打回落分支卡）
- 触发：`_mark_branch_card_state` 的 git add/commit/push 全 `check=False` 且不查返回码；远端拒推/断网时打回状态没落信封 → 下轮分支信封又读回「已回写」→ 无限机审（代码注释声称修的正是这个洞，但失败路径无感知）。
- 加固：commit/push 检查 rc，失败保留脏现场 + 写 pipeline_status 告警，不假装成功。

### 9. server/web/chat_bridge.py:168-217 · 泄漏 + 单线程崩溃
- 触发：SSE 客户端断开时 generator close 不杀 claude/ssh 子进程（无 finally 清理）；ssh-loop 分支全量写 prompt 无超时；`proc.wait(timeout=10)` 的 TimeoutExpired 未捕获 → 处理线程抛异常。
- 加固：仿 brain.py `_terminate_proc`（killpg+wait 兜底）放入 finally；stdin 写与 wait 捕获 TimeoutExpired。

### 10. server/board/plans.py:279,392,629 · 数据不一致（方案写盘不落 git）
- 触发：`create_plan`/`update_plan` 只写本地文件不 commit+push（仅 convert_plan 提交）→ 方案状态/新建方案 2017 与远端永远看不到，且阻塞 deploy 的 ff-only pull。
- 加固：create/update 与 convert 同规则提交推送；文件写改 tmp+replace。

### 11. server/board/plans.py:353-407 · 竞态（编号撞号 + 锁文件删除竞态）
- 触发：两个并发 `create_plan` 的 `_next_num` 算出同号，后者覆写前者；`_release_convert_lock` unlink 锁文件后第三者建新 inode 双持锁。
- 加固：create_plan 也走 fcntl 锁；锁文件不 unlink（留空文件即可）。

### 12. scripts/worker-claim.sh:35,86 · 数据不一致（同步/推送失败静默）
- 触发：`git pull` 双 fallback 全吞错仍继续认领（基于旧视图可能双重认领）；认领 commit 后 `git push` 不查 rc，标记只留在本地。
- 加固：pull/push 失败即退出非 0；push 失败回滚本地认领写。

## P2（瞬时不一致 / 性能 / 清理）

### 13. server/engine/observer.py:446-470、server/engine/cluster.py:211 · 数据不一致（瞬时半截文件）
- 触发：observer 写 snapshot.json/报告、cluster 写 cluster.js 用非原子 write_text，web 实时读可能读到半截 JSON。
- 加固：统一 tmp+os.replace。

### 14. server/web/server.py:2440-2480 · 死代码 + 缩进错位
- 触发：`/loop/findings` 表行解析缩进异常（能跑但逻辑脆）；`_proxy_chat_stream` 2874 行 `finally: return` 后的 `_send_404()` 不可达（py_compile 已报 SyntaxWarning）。
- 加固：重排该解析块；删死代码。

### 15. server/web/server.py 全局缓存（_BOARD_CACHE/_ENRICHED_CACHE/_OPS_COLLECT_CACHE 等）· 低危竞态
- 触发：多请求并发重建缓存，dict.update 非原子 → 偶发读到半新半旧快照（CPython 下影响极小）。
- 加固：缓存写加锁或单写线程。

### 16. server/web/server.py:1610-1620、server/web/brain.py:102 · 内存增长（低危）
- 触发：`_tokens` 只在 /session 时清理；`_thread_conversations`/`_session_locks` 按 thread_id 无上限增长，长期运行会话多时膨胀。
- 加固：token 按 TTL 定时清；会话锁/历史加 LRU 上限。

### 17. scripts/card-evidence.sh:43、first-audit-evidence.sh:29、backfill-stale-audit.sh:61 · 取卡歧义
- 触发：`find | head -1` 与 lib/card-resolve.sh「多命中禁止猜」规则自相矛盾；同 ID 两文件（迁移期）时取错卡。
- 加固：统一 source lib/card-resolve.sh 的 resolve_card。

### 18. server/engine/main.py:2327-2330 · 死代码
- 触发：连续两个相同 `except Exception as e:`，后者永不可达。
- 加固：删一个。

### 19. server/web/session_store.py:161 · 低危（索引非原子）
- 触发：掉电/多进程写 `_index.json` 半截 → load 容错返回空（可恢复），但会短暂丢会话列表。
- 加固：tmp+replace。

### 20. server/board/scheduler.py:90-97（轮询 vs 事件）
- 触发：board.js 静态导出固定 60s 轮询，web API 走 20s 缓存 + sidecar，两套视图最多差 ~60s；老板对照静态文件与 7788 会看到不一致。
- 加固：可选——scheduler 仿 engine 的 dispatch 目录 mtime 事件感知；board.js 在页面标注 generated_at 快照时间。

## 已做对、无需改的部分

engine 的运行时 sidecar 追加写、pipeline_status/metrics 的原子写、brain.py 的进程组清理（`_terminate_proc`）、worktree_dirty/exec_metrics 的短超时+TTL 缓存、loader 解析失败保留旧索引、web 看板合成「git 真相+sidecar+分支信封」三源模型。

## 最佳动作（唯一建议）

把 P0 的 5 项（1/2/3/4/5）整理成 2-3 张极窄维护卡走 OpenCode 出卡修复，P1 的 6-12 随下一批合入——这是代码级加固，不是新功能，方向明确，不需要老板再选。
