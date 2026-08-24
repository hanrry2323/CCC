# 任务卡 cla016 · SQLite 持久化队列落地与闪退恢复验证（OpenCode 执行）

> 关联：cla-plan-002 (M1 补卡) · 执行体：OpenCode · 验收：Claude Code · 状态：已关闭· 派发：engine · 项目：cla · 日期：2026-08-17




## 基准文件（先看）

- 方案池：`docs/projects/cla/plans/`（关联方案见卡头「关联」）

## 目标

落地 SQLite 持久化任务队列（`SQLiteQueue` 取代 `InMemoryQueue`），使任务在进程闪退/重启后不蒸发，并通过 kill 进程重建测试验证。

## 实现

### 功能背景
cla-plan-001 声明完成但代码从未合入 main（取证：业务仓 `git log main` 最新提交 b6435d4 仅为测试路径修复；`src/scheduler/queue.py` 仍为 30 行 InMemoryQueue；看板 cla002 从未出卡）。本卡承接 M1-1.2 SQLite 持久化队列重构。

### 开发要求
1. 在 `data/clawmed.db` 建 `jobs` 表：
   ```sql
   CREATE TABLE IF NOT EXISTS jobs (
       id TEXT PRIMARY KEY,
       name TEXT NOT NULL,
       payload TEXT,
       status TEXT NOT NULL DEFAULT 'pending',
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   ```
2. 重构 `src/scheduler/queue.py`：`InMemoryQueue` → `SQLiteQueue`，`enqueue` 用事务型 ACID 写入，`dequeue` 用乐观锁读取（同一行同一时刻只允许被一个 worker 取走）。
3. `src/scheduler/job.py`：JobSpec 与 jobs 表字段序列化对齐（id/name/payload/status/created_at），保留现有接口兼容（size/clear）。
4. 新增持久化测试：入队 2 任务 → 手动 kill 后端进程 → 重新实例化 Queue → 2 任务仍在（闪退不蒸发）。

### 关键代码思路
- SQLite 连接用 `sqlite3` 标准库，`check_same_thread=False` + 锁保护，适配 Scheduler 线程模型。
- `dequeue` 用 `BEGIN IMMEDIATE` + `SELECT ... WHERE status='pending' LIMIT 1` → `UPDATE status='running'`，保证乐观锁语义。
- `data/` 目录不存在时自动创建（os.makedirs）。

## 红线（先看）

1. 禁止触碰 `src/crawlers/`、`tests/test_obs1_smoke.py`、`tests/test_obs2_smoke.py`（历史卡已闭合范围）
2. 禁止引入 sqlite3 之外的第三方存储依赖
3. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src/scheduler/queue.py`（重构）
- `src/scheduler/job.py`（序列化对齐）
- `tests/test_scheduler_jobspec.py`（扩展）+ 新增 `tests/test_queue_persistence.py`
- `data/clawmed.db`（运行时生成，不提交）

## 步骤

1. Read 卡全文 + `docs/projects/cla/plans/002-sqlite-ledger-fix-and-debt-cleanup.md` + 业务仓 `src/scheduler/queue.py`/`job.py` 现状
2. 在派发 worktree 内实现 SQLiteQueue + JobSpec 对齐 + 持久化测试
3. 跑 `python3 -m pytest tests/test_scheduler_jobspec.py tests/test_queue_persistence.py -q` 全绿
4. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
5. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `python3 -m pytest tests/test_scheduler_jobspec.py tests/test_queue_persistence.py -q` 100% 通过
2. 持久化测试：入队 2 任务 → kill 进程 → 重建 Queue → 队列仍有 2 任务
3. `python3 -m ruff check src/scheduler/` 无错误
4. `InMemoryQueue` 类在 `queue.py` 中移除（或标记 deprecated），`from collections import deque` 不再被队列使用

## 门禁

> 可选机械门禁（2026-08-16 起测试/编译失败 = 硬打回）。转卡时由中枢按卡声明注入命令；声明了命令但失败 → 卡打回。
测试：python3 -m pytest tests/test_scheduler_jobspec.py tests/test_queue_persistence.py -q
编译：
lint：python3 -m ruff check src/scheduler/
范围：false

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]
   - 说明：cla-plan-002 子项目 1.2 由「未落地」推进为「已完成」，关联方案与 roadmap M1 状态同步更新。
2. **教训沉淀**：本卡是否产出可复用教训？[有]
   - 说明：记录「声明已完成但代码未合入」的卡-代码漂移教训 → 业务仓 docs/lessons.md 或 CCC docs/notes/2026-08-17-cla-lessons.md。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[是]
   - 说明：新增 `data/clawmed.db` 持久化文件与 `src/scheduler/queue.py` 存储层变更，业务仓 CLAUDE.md 结构需补一行数据目录说明。
4. **线路图**：项目近况/下一步是否变化？[是]
   - 说明：M1 1.2 闭环后 M1 完成，roadmap M1 状态由「进行中」→「已完成」，下一步进入 M2 gov 采集（cla-plan-003）。

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

## 执行提示

- 项目：cla（）

- 项目仓（只读参考）：/Users/fan/program/apps/clawmed-ccc（Mac2017）——禁止在主仓目录切换卡分支或直接开发

- 代码工作区：由 CCC Engine 派发时注入独立 worktree（见派发提示中的具体路径），所有代码改动必须在注入的 worktree 内完成；禁止回退到主仓目录

- 关联方案摘要：目标：核实并落地 cla-plan-001 声明但未合入的 SQLite 持久化账本（业务仓 main 上 `src/scheduler/queue.py` 仍为 InMemoryQueue）；完成旧文件作废归档与 decided.json 修正，让 M1 真正闭环。

- 开发技能与命令：
  - [domains::projects::常用命令] 常用命令 - 运行测试： 全量 - 单模块测试： - 代码检查：
  - [domains::projects::常用命令] 常用命令 - 运行测试： - 单模块测试： - 代码检查： - 编译检查： - 出卡： - 看板：
  - [domains::projects::常用命令] 常用命令 - 编译检查： - 运行测试： - 后端单测： - 前端测试： - 端到端测试： - 构建： - 代码检查：

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：cla（）

- 审查重点：代码实现质量、边界条件、异常处理、架构隐患

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背/安全漏洞）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

  - 主观标准（美观/体验/设计品味）不判——记录建议即可，不得作为打回原因

  - **打回原因必须可执行**：格式「问题 → 文件:行号 + 唯一最佳动作」；禁止「体验不好/不规范」等不可执行表述（防死循环）

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

- **完成钩子（Doc-Gate）**：核对卡 `## 维护区` 四问是否已逐项勾选并填说明。

  - 维护区缺失或仍为占位说明（如「说明：」空白/复制模板）→ 输出「机审：不通过（维护区未完成）」并以非零退出，

    打回原因注明缺失项；执行体补维护区后重试。

  - 核对 [是]/[有] 声明引用工件真实存在且与卡改动一致。若存在声明不实，输出「机审：不通过（维护区声明不实）」并以非零退出。
