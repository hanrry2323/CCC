# 实验 D15 · headless 与 web 共享存储并发

- **状态**：✅ 完成（源码级 + 观测）
- **批次**：B4 会话
- **环境**：源码 + 实测观测
- **日期**：2026-08-16

## 结论

**存储层无显式文件锁，但用原子 rename 写（无 torn write）+ last-write-wins 语义**。headless 与 web 同 workspace 并发写 `session_projcache.json` 等投影缓存时，最坏是「后写覆盖先写」（缓存丢失一次投影），**不会产生损坏/半写**。投影缓存可从会话日志重放恢复，故 last-write-wins 可接受。

## 证据

- `dsh-storage-json/lib/index.js:35`：`await rename(tmp, path)`（原子替换）
- `:11-15`：「Rename is an atomic replace on POSIX... one writer per process and last-write-wins is correct」
- `:42`：fsync POSIX 目录保证 rename 后崩溃可持久

## 结论细节

- **原子性**：临时文件写全再 rename → 读方永远看到完整旧值或完整新值，无半写。
- **并发**：同文件多进程写 = last-write-wins（一个进程的更新被覆盖）。对**缓存**（投影）可接受；对**事实源**（会话 jsonl）不适用——jsonl 是 per-session 独立文件，不共享。
- 本次实验全程 headless 与 web(3080) 并存运行，web 会话正常，无可见冲突。

## 风险 / 对 CCC 借鉴的影响

- 投影缓存 last-write-wins 无碍（可从日志重建）；但多执行体写同一存储文件需清楚「缓存可丢、日志不丢」的边界。
- CCC 多席若共享状态，应区分：缓存类可 last-write-wins，事实源类必须独立文件或加锁。
