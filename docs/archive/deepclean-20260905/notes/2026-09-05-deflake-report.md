# 2026-09-05 并发派发测试 deflake 报告

## 范围

本次只处理候选一 `TestParallelAndRelayGuard` 的两个测试：

- `test_parallel_dispatch_concurrency`
- `test_cross_round_slot_fill_no_batch_join`

未修改 `server/` 生产模块、配置、launchd 服务、任务卡或 `xianyu` 业务代码。

## 抖动根因

原测试使用真实 `sleep 1` 子进程，并以固定 wall-clock 阈值（`<1.8s`、`<0.8s`）推断并发和 `wait=False` 非阻塞。2017 机器负载、Python/子进程调度和引擎线程时序会改变这些耗时，即使并发语义正确也可能误报。

在改写后的定向验证中还复现并消除了一个测试自身的收单竞态：释放首个 worker 后，下一轮调用可能恰好落在 worker 子线程已退出但尚未完成 DONE 状态转移的窗口，孤儿回收会把卡重新置为待分派。测试现在先等待 `DONE` 且派发池无存活线程，再进入下一轮，等待的是状态事件而不是任意 sleep。

## 同步机制

新增测试专用 `parallel_worker.py`（写入 `tmp_path`）：

1. 子进程启动后写 `{work_id}.started` 标记；
2. 未发现 `release-{work_id}` 文件前保持等待；
3. 测试观察 started 标记后显式创建 release 文件；
4. `_wait_for_started` 和 `_wait_for_done_and_idle` 使用 `time.monotonic()` 作为有界故障保护，并在超时错误中报告缺失事件和 RUNNING 卡，不以耗时阈值证明业务语义。

并发测试要求两张卡的 started 标记同时出现后才能 release；若实现串行，第二张卡无法越过屏障。跨轮测试在 `MAX=1` 下验证槽满不派发、首卡释放并完成收单后下一轮补派第二卡。

## 验证结果

- 两个目标用例连续运行 20 次：**20/20 通过**。
- `server/tests/test_engine_main.py -q`：**通过**。
- `python3 -m pytest server/tests/ -q`：连续 3 次**通过**；三次输出均到达 `[100%]`，每次运行前后 git 状态快照完全相同。
- `.venv-hub/bin/ruff check server/`：**通过**。
- `git diff --check`：**通过**。

## git 状态快照

全量运行前（3 次均相同）：

```text
 M server/tests/test_engine_main.py
```

全量运行后（3 次均相同）：

```text
 M server/tests/test_engine_main.py
```

前后差异为空；真实 `docs/dispatch/` 未出现变化。测试改动随后已提交并推送，当前报告为本次收口文档。

## 提交

- 测试改动：`0eca439531fe8b7296ed520fbe85c0ca228b6575`
- 提交信息：`test(engine): deflake parallel dispatch tests`

## 声明

本次未改生产代码；改动仅限测试文件及本报告。
