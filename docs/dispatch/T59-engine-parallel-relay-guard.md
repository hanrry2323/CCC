# 任务卡 T59 · Engine 异步派发 + 中继稳定性兜底（Claude Code 执行）

> 关联：过夜任务发现——① Engine 串行派发（同步等执行体完成才派下一张）；② 上游中继多次波动导致执行卡死/超时 · 执行体：Claude Code · 验收：Codex · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-05
> 工作目录：`/Users/fan/program/ccc-dev-ws`；分支：`codex/t59-engine-parallel`（先 `git fetch origin main && git checkout -b codex/t59-engine-parallel origin/main`）
> **分步提交纪律（硬）**：A/B 两块各独立 commit+push；超时 7200s。

## 目标

Engine 支持多卡并行派发（异步）+ 中继探活与自动续作兜底（上游波动零丢失自动化）。

## 具体项

### A. 异步派发（真并行）

1. `run_once` 改为：扫描待分派 → 并发拉起（每卡一个后台线程执行 `_dispatch_and_collect`，fire-and-forget）→ 独立收单（线程完成时写状态）；并发上限可配置 `EXECUTOR_MAX_CONCURRENT`（默认 2）。
2. 保持五态状态机、超时（EXECUTOR_TIMEOUT_SECONDS）、打回附原因；MANUAL 挂起逻辑不变。
3. 测试：两张卡同时派发各自独立执行、收单正确、互不阻塞；超时/失败路径不回归。

### B. 中继稳定性兜底

4. **派发前探活**：Engine 每次派发前 GET 探活地址（`EXECUTOR_PROBE_URL`，缺省 http://127.0.0.1:6100/）——失败则本轮跳过该卡（保持待分派，记日志），下轮重试；连续 N 次失败记录告警。
5. **自动续作重派**：执行体因上游问题非正常结束（退出码非 0 且日志含超时/网络特征，或执行超时）→ 卡自动回「待分派」并附原因（不直接打回），下轮自动重派一次；重派仍失败才打回。
6. 配置：config.example.env 增 `EXECUTOR_MAX_CONCURRENT`、`EXECUTOR_PROBE_URL`、`EXECUTOR_RETRY_ONCE`（默认 true）。
7. 测试：探活失败跳过、自动重派一次、重派失败打回。

## 红线

1. 只改 server/engine/（main.py、dispatch.py、store.py、task.py）、server/config/、server/tests/；**禁止改 server/web/、server/board/、前端（后续卡）**。
2. 并发线程安全（状态写入加锁）；不引入第三方依赖（threading 即可）。
3. 回写前 push 成功并附证据。

## 验收标准

1. 两张卡同时待分派 → 并发拉起（日志证明两进程同时在跑）、各自收单正确；串行旧行为可配置回退。
2. 探活失败：Engine 跳过该卡保持待分派 + 日志；恢复后自动派发。
3. 上游波动：执行异常 → 自动回待分派重派一次 → 仍失败打回附原因（测试任务先行占位卡验证）。
4. pytest 全绿、ruff/py_compile clean、push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：A/B 实现、并发/探活/重派测试、占位卡验证记录、pytest/build、push 证据。

## 回写区

**执行体**：Claude Code（2017）· 日期：
