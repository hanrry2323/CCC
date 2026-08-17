# 方案 · SQLite 账本落地补卡与债务收尾 (M1)
> 项目：cla · 编号：cla-plan-002 · 状态：草案 · 作者：OpenCode · 工具：opencode
> 创建：2026-08-17 · 更新：2026-08-17
> 关联卡：待出卡
> 关联方案：cla-plan-001（声明已完成，但 SQLite 重构未合入业务仓 main）
> 里程碑：M1 · 独立底座与路径清零
> 子项目：1.2 SQLite 持久化队列重构, 1.3 债务收尾
> 决策源：/Users/apple/qx-map/__archive__/decisions/ClawMed-CCC-Architecture-2026-08-17.md

## 目标

核实并落地 cla-plan-001 声明但未合入的 SQLite 持久化账本（业务仓 main 上 `src/scheduler/queue.py` 仍为 InMemoryQueue）；完成旧文件作废归档与 decided.json 修正，让 M1 真正闭环。

## 背景（取证证据）

1. 业务仓 `clawmed-ccc`（2017）main 分支 `git log` 最新提交为路径修复（b6435d4），**无 SQLiteQueue 提交**；`src/scheduler/queue.py`（30 行）仍为纯内存 deque 队列。
2. 看板 cla001 已关闭（2026-08-17 14:29），但 `machine_audit_passed=false`，且 **cla002 卡从未出卡**（API 查询 total=0）。
3. 架构定稿要求：`data/clawmed.db` 建 `jobs` 表，`SQLiteQueue` 取代 `InMemoryQueue`，断电/闪退后任务不蒸发。
4. 架构定稿「旧方案废除清单」：`docs/dev-plan.md` 作废、`docs/OBS1~3.md` 归档、`.ccc/decided.json` 修正（旧目标标 completed、追加 sqlite3 自研契约与前端静态单页契约）。

## 方案内容

### 1. SQLite 账本落地（补 1.2）
- `src/scheduler/queue.py`：`InMemoryQueue` → `SQLiteQueue`（事务 ACID 写入 + 乐观锁读取，`data/clawmed.db` 的 `jobs` 表）。
- `src/scheduler/job.py`：JobSpec 序列化对齐 jobs 表字段（id/name/payload/status/created_at）。
- 持久化验证测试：入队 2 任务 → kill 进程 → 重建 Queue → 任务仍在。

### 2. 债务收尾（1.3）
- `docs/dev-plan.md` 移入 `docs/_archive/`（作废，内容保留供考古）。
- `docs/OBS1~3.md` 移入 `docs/_archive/obs/`。
- `.ccc/decided.json` 修正：旧目标 `g-scheduler-jobspec-v0` → completed；新增 `g-clawmed-sqlite-and-ui`；追加两条硬契约（禁止复制 CCC 原生逻辑 / 前端静态单页一体化挂载）。
- 历史卡（cla-obs1-commit ~ cla-obs5-marker、docs-templates-*）保持只读保留。

## 转卡计划

按「三要素」拆 2 张卡：

### cla016 | SQLite 持久化队列落地与闪退恢复验证
* 颗粒度：1.0 天（3 文件）
* 依赖：无（独立于已关闭的 cla001）
* 架构位置：`src/scheduler/queue.py`、`src/scheduler/job.py`、`data/clawmed.db`
* 验收：`pytest tests/test_scheduler_jobspec.py` 通过；kill 进程重建后任务不蒸发（新增测试用例）；`ruff` 干净。

### cla017 | 债务收尾：旧文件作废归档 + decided.json 修正
* 颗粒度：0.5 天（文档操作）
* 依赖：无
* 架构位置：`docs/`、`.ccc/agent-mind/decided.json`
* 验收：dev-plan/OBS 移入 `docs/_archive/`；decided.json 目标/契约与架构定稿一致；全仓无残留引用。

## 备注

- 若 cla001 的关闭声明与代码事实不符属「Doc-Gate 声明不实」，本方案为事实修复路径；如老板倾向直接复核 cla001 合入状态，可先做卡复核再出卡。