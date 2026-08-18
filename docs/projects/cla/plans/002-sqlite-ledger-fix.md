# 方案 · SQLite 持久化队列重构（M1-1.2）

> 项目：cla · 编号：cla-plan-002 · 状态：待验收 · 作者：OpenCode · 工具：opencode
> 创建：2026-08-17 · 更新：2026-08-18
> 关联卡：cla016
> 关联方案：cla-plan-001（声明已完成，但 SQLite 重构未合入业务仓 main）
> 进度：0/1 (0%)
> 里程碑：M1 · 独立底座与路径清零
> 环境准备：Python >= 3.10, SQLite 3（M1/2017 均就绪）
> 子项目：1.2 SQLite 持久化队列重构
> 决策源：/Users/apple/qx-map/__archive__/decisions/ClawMed-CCC-Architecture-2026-08-17.md

## 目标

把 `src/scheduler/queue.py` 的 `InMemoryQueue` 重构为 SQLite 持久化 `SQLiteQueue`，任务在进程闪退/重启后不蒸发，通过 kill 进程重建验证。

## 背景（取证证据）

1. 业务仓 `clawmed-ccc`（2017）main 分支 `git log` 最新提交为路径修复（b6435d4），**无 SQLiteQueue 提交**；`src/scheduler/queue.py`（30 行）仍为纯内存 deque 队列。
2. 看板 cla001 已关闭（2026-08-17 14:29），但 `machine_audit_passed=false`，且 **cla002 卡从未出卡**（API 查询 total=0）——cla-plan-001 声明的 SQLite 部分实际未落地。
3. 架构定稿要求：`data/clawmed.db` 建 `jobs` 表，`SQLiteQueue` 取代 `InMemoryQueue`，断电/闪退后任务不蒸发。

## 方案内容

### 1. SQLite 持久化任务队列
- `data/clawmed.db` 建 `jobs` 表（id/name/payload/status/created_at）。
- `src/scheduler/queue.py`：`InMemoryQueue` → `SQLiteQueue`（enqueue 事务型 ACID 写入、dequeue 乐观锁读取、size/clear 保留）。
- `src/scheduler/job.py`：JobSpec 序列化对齐 jobs 表字段。
- `data/` 目录自动创建（os.makedirs），不提交 db 文件。

### 2. 闪退恢复验证
- 新增 `tests/test_queue_persistence.py`：入队 2 任务 → kill 进程 → 重建 Queue → 任务仍在。

## 验收标准

- [ ] `pytest tests/test_scheduler_jobspec.py tests/test_queue_persistence.py -q` 全绿
- [ ] kill 进程重建后队列任务不蒸发
- [ ] `ruff check src/scheduler/` 无错误

## 功能卡

### SQLiteQueue 落地与闪退恢复验证（cla016）

目标：完成 SQLite 持久化队列重构，交付可验收产物。

实现：按「方案内容」两节落地——jobs 表 + SQLiteQueue 重构 + JobSpec 对齐；新增持久化测试（入队→kill→重建→仍在）。

验收：验收标准三条款全过（pytest 全绿 / kill 重建不蒸发 / ruff 干净）。

颗粒度：子项目级（1 卡，约 1 天）。

依赖：无（独立于已关闭的 cla001）

架构位置：`src/scheduler/queue.py`、`src/scheduler/job.py`、`data/clawmed.db`

## 转卡计划

SQLiteQueue 落地与闪退恢复验证（cla016，已出卡，执行中）

## 备注

- cla016 卡已由 engine 派发执行中（2026-08-17），本方案状态随卡推进更新。
- cla-plan-001 的 1.3 债务收尾（旧文件作废 + decided.json 修正）已拆出独立方案 cla-plan-003。