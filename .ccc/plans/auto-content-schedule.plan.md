# Plan: auto-content-schedule — 发布排期系统：定时发布 + 草稿暂存 + 排期表

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

### 核心源码分析
- **`src/xianyu/storage/models.py`**（75 行）— 5 个 SQLAlchemy ORM 模型（Topic/Article/PublishLog/Cookie/DailyStat）。Article 有 `status` 列（draft/generated/published/failed），但无独立的排期/定时发布机制
- **`admin/api/seed_data.py`**（225 行）— 同步 sqlite3 建表 + seed 注入，5 张表硬编码在 `_INIT_DB_SQL`。**无 schedules 表**。`init_db()` 含 G3.5 ALTER TABLE 迁移逻辑（`_add_column_if_missing`）
- **`admin/api/server.py`**（1083 行）— FastAPI + 22 端点，使用 raw `sqlite3.connect` 直接读写 `data/xianyu.db`（**不导入** `src/xianyu/`）。`lifespan` 内调 `init_db(DB_PATH)` 建表
- **`src/xianyu/orchestrator/pipeline.py`**（319 行）— `run_pipeline()` 端到端内容生成+发布，写入 `articles` + `publish_logs`。发布触发紧随生成，**无延迟/定时发布能力**
- **`src/xianyu/orchestrator/state_machine.py`**（487 行）— 纯函数 Task 状态机，5 状态 5 事件 + 退避重试。但 `Task` dataclass 对应的 `tasks` 表**未在数据库中实现**
- **`src/xianyu/main.py`**（29 行）— 仅 init DB + `asyncio.Event().wait()` 永远阻塞，调度由外部 openclaw 接管
- **`src/xianyu/cli.py`**（143 行）— Typer CLI，`run/agent/worker/status` 四个命令。`run` 当前为 deprecation 提示（v2 起调度由 openclaw 接管）
- **`src/xianyu/core/pipeline.py`**（103 行）— 双轨管道定义：`video`（6 阶段，含 tts/video）和 `image_text`（4 阶段，跳过 tts/video）

### 当前结构要点
1. **无排期表**：发布触发时机 = pipeline 完成瞬间。`publish_logs.next_retry_at` 仅用于失败重试时间戳，不做主动调度
2. **Article 状态已含 draft/generated/published/failed**：存在草稿概念，但无 "scheduled（已排期待发）" 状态
3. **Admin API 与 ORM 两条数据路径**：Admin API 用 raw sqlite3（`query()`）；pipeline 用 async SQLAlchemy（`SessionLocal()`）。新表须两面兼顾
4. **调度机制空缺**：整个项目无定时触发器。现有定时类任务（cookie 扫描/日报）通过外部 openclaw cron 驱动

### 待改动点
- `src/xianyu/storage/models.py`：新增 `Schedule` ORM 模型（schedules 表，字段：topic/platform/pipeline/status/scheduled_at/结果字段）
- `admin/api/seed_data.py`：`_INIT_DB_SQL` 追加 `schedules` 表 DDL + `init_db()` 中迁移逻辑 + seed 数据
- `admin/api/server.py`：新增 5 个 schedule CRUD 端点（列表/创建/更新/删除/立即发布）
- `src/xianyu/orchestrator/scheduler.py`：**NEW** — 排期守护，轮询 due schedules，调 `run_pipeline()`
- `src/xianyu/cli.py`：追加 `schedule` 命令组 + `schedule daemon` 子命令
- `tests/test_scheduler.py`：**NEW** — scheduler 单元测试

---

## 范围

- **目标**：实现发布排期系统 —— 允许用户在 admin 前端设定 topic + platform + 发布时间，后台守护按时执行 pipeline
- **只改文件**：
  - `src/xianyu/storage/models.py`
  - `admin/api/seed_data.py`
  - `admin/api/server.py`
  - `src/xianyu/orchestrator/scheduler.py`（NEW）
  - `src/xianyu/cli.py`
  - `tests/test_scheduler.py`（NEW）
- **不改文件**：`src/xianyu/video/`、`src/xianyu/content/`（video/tts/bgm/image/writer 等）、`src/xianyu/bridge/`、`src/xianyu/main.py`、`src/xianyu/core/`、任何配置/.env/依赖文件
- **执行方式**：`manual`
- **Phase 数**：2

---

## 改动 1（Phase 1）：Schedule ORM 模型 + Admin API CRUD

### 做什么

新增 `schedules` 数据库表及其 ORM 模型，并在 Admin API 中提供完整的 CRUD 端点。用户通过前端可以：创建排期（指定 topic/platform/pipeline/scheduled_at）、浏览排期列表、修改排期（改时间/话题/平台）、取消排期、手动立即触发排期。

排期状态机：`draft`（草稿）→ `scheduled`（已排期）→ `publishing`（发布中）→ `published`（已发布）/ `failed`（失败）/ `cancelled`（已取消）。

### 怎么做

**`src/xianyu/storage/models.py`**：

1. 在 `DailyStat` 类之后（第 64-74 行）、`__all__`（如有）之前追加 `Schedule` ORM 模型：

```python
class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(255))
    platform: Mapped[str] = mapped_column(String(32))
    pipeline: Mapped[str] = mapped_column(String(32), default="video")
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft/scheduled/publishing/published/failed/cancelled
    scheduled_at: Mapped[datetime] = mapped_column(DateTime)
    title: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    video_path: Mapped[str] = mapped_column(String(512), default="")
    article_id: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**`admin/api/seed_data.py`**：

2. `_INIT_DB_SQL`（第 145-193 行）追加 `schedules` 表 DDL 块

```sql
CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic VARCHAR(255),
    platform VARCHAR(32),
    pipeline VARCHAR(32) DEFAULT 'video',
    status VARCHAR(32) DEFAULT 'draft',
    scheduled_at DATETIME,
    title VARCHAR(255) DEFAULT '',
    content TEXT DEFAULT '',
    video_path VARCHAR(512) DEFAULT '',
    article_id INTEGER DEFAULT 0,
    error TEXT DEFAULT '',
    created_at DATETIME,
    updated_at DATETIME
);
```

3. `init_db()`（第 196-212 行）函数内追加迁移检测：对 schedules 表做 `_add_column_if_missing`（虽然不是必须的，但保持模式一致，以备未来加字段）

4. `seed_if_empty()` 函数内（第 84 行），counts 检测中添加 `"schedules"` 键，并在注入逻辑末尾追加 2-3 条样例行演示用

**`admin/api/server.py`**：

5. 新增 5 个 schedule CRUD 端点（追加在 `/api/runs/{task_id}` 之后，第 788 行附近）。遵循已有风格：raw sqlite3 `query()` + Pydantic 风格检查（用参数校验而非引入 pydantic）

   - `GET /api/schedules` — 排期列表。支持可选参数 `?status=scheduled` 和 `?date=2026-07-15` 过滤。按 scheduled_at ASC 排序

   - `POST /api/schedules` — 创建排期。Body: `{topic, platform, pipeline, scheduled_at}`。验证：topic 非空、platform 在已知范围内（可选检测 list）、scheduled_at 可解析。status 默认为 `scheduled`。返回新建的 schedule

   - `PUT /api/schedules/{id}` — 更新排期。Body: 同创建，所有字段可选。不可修改已处于 publishing/published 状态的排期（返回 409）

   - `DELETE /api/schedules/{id}` — 删除/取消排期。实际做软删除：SET status='cancelled'。不可取消 publishing/published 状态的排期（返回 409）

   - `POST /api/schedules/{id}/publish` — 手动触发排期立即发布。将 status 设为 `publishing`，在 `background_tasks` 中调 `_run_xianyu_task`（复用现有 subprocess 路径）。注意：目前 `_run_xianyu_task` 硬编码了 cmd 为 `run <topic>`，需要同时传递 platform/pipeline 参数

### Schedule 状态状态机

```
draft (用户暂存)
  │
  ▼ (用户提交排期)
scheduled (等待定时触发 / 手动发布)
  │
  ├─ 手动取消 → cancelled
  │
  ▼ (定时到达 / 用户手动触发)
publishing (管道执行中)
  │
  ├─ 成功 → published (终态)
  └─ 失败 → failed (终态，含 error 信息)
```

### 验收清单

- [ ] `Schedule` ORM 模型导入无报错，`Base.metadata.create_all` 在已有库上幂等执行
- [ ] Admin API 启动后 `schedules` 表存在（sqlite3 客户端可查）
- [ ] `POST /api/schedules` 创建成功，返回新建排期 JSON
- [ ] `GET /api/schedules` 返回列表，支持 `?status=` 和 `?date=` 过滤
- [ ] `PUT /api/schedules/{id}` 更新成功；对 publishing 状态的返回 409
- [ ] `DELETE /api/schedules/{id}` 软删除成功（status=cancelled）；对 publishing 状态的返回 409
- [ ] `POST /api/schedules/{id}/publish` 将 status→publishing，并触发后台任务
- [ ] `_add_column_if_missing` 兼容老库升级（无 schedules 表时 CREATE，有表但有新字段时 ALTER）

### 验收

- [模型导入]（参考：`cd ~/program/xianyu && uv run python3 -c "from src.xianyu.storage.models import Schedule; print('OK')"`）
- [表创建]（参考：`sqlite3 ~/program/xianyu/data/xianyu.db ".schema schedules"`）
- [CRUD 端点]（参考：`curl -s http://127.0.0.1:8765/api/schedules | python3 -c "import sys,json; print(json.load(sys.stdin))"` 返回预期结构）

---

## 改动 2（Phase 2）：Scheduler 守护 + CLI 命令 + 测试

### 做什么

实现排期守护进程，定时轮询 `schedules` 表中 `status='scheduled' AND scheduled_at <= now` 的条目，调用 `run_pipeline()` 执行发布，完成后更新状态。

同时追加 Typer CLI 命令 `xianyu schedule daemon` 启动守护，以及 `xianyu schedule list/create/cancel` 等快捷管理命令（供运维直接操作，不依赖 admin API）。

### 怎么做

**`src/xianyu/orchestrator/scheduler.py`**（NEW）：

```python
"""
排期守护：轮询 schedules 表，到期执行 pipeline。
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import select

from ..core.pipeline import PipelineResult, get_pipeline
from ..orchestrator.pipeline import run_pipeline
from ..storage.database import SessionLocal
from ..storage.models import Schedule

POLL_INTERVAL: int = 60  # 轮询间隔（秒）


class ScheduleDaemon:
    """schedules 表轮询守护。"""

    def __init__(self, poll_interval: int = POLL_INTERVAL) -> None:
        self._poll_interval = poll_interval

    async def run(self) -> None:
        """主循环。"""
        logger.info("[schedule_daemon] 启动，poll_interval={}s", self._poll_interval)
        while True:
            try:
                await self._tick()
            except Exception as exc:
                logger.error("[schedule_daemon] tick 异常: {}", exc)
            await asyncio.sleep(self._poll_interval)

    async def _tick(self) -> None:
        """单次轮询：找出并执行到期的排期。"""
        now = datetime.now(UTC)
        async with SessionLocal() as session:
            result = await session.execute(
                select(Schedule).where(
                    Schedule.status == "scheduled",
                    Schedule.scheduled_at <= now,
                )
            )
            dues = result.scalars().all()
            if not dues:
                return
            logger.info("[schedule_daemon] 本轮 {} 条到期排期", len(dues))
            for sched in dues:
                sched.status = "publishing"
            await session.commit()

        # 异步执行每个到期排期（不阻塞轮询）
        for sched in dues:
            asyncio.create_task(self._execute(sched.id, sched.topic, sched.platform, sched.pipeline))

    async def _execute(self, sched_id: int, topic: str, platform: str, pipeline_name: str) -> None:
        """执行单个排期。"""
        logger.info("[schedule_daemon] 执行 schedule={} topic={!r} platform={} pipeline={}",
                     sched_id, topic, platform, pipeline_name)
        result: PipelineResult
        try:
            result = await run_pipeline(topic, platform=platform, pipeline=pipeline_name)
        except Exception as exc:
            logger.error("[schedule_daemon] schedule={} 异常: {}", sched_id, exc)
            async with SessionLocal() as session:
                sched = await session.get(Schedule, sched_id)
                if sched:
                    sched.status = "failed"
                    sched.error = str(exc)[:1000]
                await session.commit()
            return

        async with SessionLocal() as session:
            sched = await session.get(Schedule, sched_id)
            if sched is None:
                logger.warning("[schedule_daemon] schedule={} 已不存在", sched_id)
                return
            if result.success:
                sched.status = "published"
                sched.title = result.stage_outputs.get("writer", {}).get("title", topic)
                logger.info("[schedule_daemon] schedule={} → published", sched_id)
            else:
                sched.status = "failed"
                sched.error = result.error[:1000]
                logger.warning("[schedule_daemon] schedule={} → failed: {}", sched_id, result.error)
            await session.commit()
```

1. 核心方法：
   - `run()` — `while True` 循环，每 60s 调 `_tick()`
   - `_tick()` — 查出 `status='scheduled' AND scheduled_at<=now` 的所有条目，mark `publishing`，`asyncio.create_task` 异步执行
   - `_execute(sched_id, topic, platform, pipeline)` — 调 `run_pipeline()`，成功时 status→published，失败时 status→failed+error

2. 错误处理：
   - `_tick()` 内异常只 log 不中断循环
   - `_execute()` 内异常捕获，写 error 到 schedule 记录
   - 空 tick（无到期排期）只打一条 DEBUG 级别日志或不打日志

**`src/xianyu/cli.py`**：

3. 新增 `schedule` 命令组（追加在 status 命令之后，第 87-138 行之后）：
   ```python
   schedule_app = typer.Typer(help="发布排期管理")
   app.add_typer(schedule_app, name="schedule")
   ```

4. `schedule list` — 列出排期。可选 `--status` 和 `--platform` 过滤
   ```python
   @schedule_app.command()
   def list(status: str = "", platform: str = ""):
       """列出排期。"""
   ```

5. `schedule create` — 创建排期。参数：`topic`, `--platform`（默认 bilibili）, `--pipeline`（默认 video）, `--at`（ISO 时间）
   ```python
   @schedule_app.command()
   def create(topic: str, platform: str = "bilibili", pipeline: str = "video", at: str = typer.Option(...)):
       """创建发布排期。"""
   ```

6. `schedule cancel` — 取消指定排期（按 ID）

7. **关键**：`schedule daemon` — 启动排期守护
   ```python
   @schedule_app.command()
   def daemon(poll_interval: int = 60):
       """启动排期守护进程。"""
       asyncio.run(ScheduleDaemon(poll_interval=poll_interval).run())
   ```

**`tests/test_scheduler.py`**（NEW）：

8. 测试
   - `test_schedule_daemon_tick_empty()`：无到期排期时 tick 无操作
   - `test_schedule_daemon_tick_fires()`：模拟 1 条到期排期，验证 status→publishing
   - `test_schedule_daemon_execute_success()`：mock `run_pipeline` 成功，验证 status→published
   - `test_schedule_daemon_execute_failure()`：mock `run_pipeline` 失败，验证 status→failed+error
   - `test_schedule_daemon_execute_exception()`：mock `run_pipeline` 抛异常，验证 status→failed
   - `test_schedule_daemon_tick_no_op`：非到期排期（scheduled_at 在未来）不被触发

### 验收清单

- [ ] `ScheduleDaemon` 在空表上运行不抛异常
- [ ] 到期排期被正确触发：status→publishing→published/failed
- [ ] 未到期排期（scheduled_at 在未来）不被触发
- [ ] `run_pipeline()` 异常时排期标记 failed 并记录 error 内容
- [ ] `schedule daemon` CLI 命令启动守护
- [ ] `schedule list/create/cancel` CLI 命令可用
- [ ] 新增测试全部通过
- [ ] 回归测试全部通过

### 验收

- [守护启动不报错]（参考：`cd ~/program/xianyu && uv run timeout 3 xianyu schedule daemon` 正常启动无 traceback）
- [触发正确]（参考：mock DB 中插一条 `scheduled_at` 为过去的 `scheduled` 记录，运行一次 _tick，检查 status 变更）
- [测试通过]（参考：`cd ~/program/xianyu && uv run python3 -m pytest tests/test_scheduler.py -q --tb=short`）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | `models.py` 新增 Schedule ORM + `seed_data.py` schedules DDL + `server.py` 5 个 CRUD 端点 | `feat(schedule): add schedules table + ORM model + admin CRUD endpoints (phase 1/2)` |
| 2 | `scheduler.py` 排期守护 + `cli.py` schedule 命令组 + 测试 | `feat(schedule): add ScheduleDaemon + CLI commands + tests (phase 2/2)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误
- [ ] 全部测试通过
- [ ] diff 范围仅限"只改文件"列表
- [ ] 每个 phase 对应一个 commit
- [ ] phases.json 与 plan phase 数一致（2）
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤

1. 交付后可创建 launchd plist 将 `xianyu schedule daemon` 注册为常驻服务（类似现有 12 个守护模式）
2. 前端排期管理页面（排期日历/甘特图）为独立前端任务，不在本范围
3. 未来可扩展：多账号轮询、排期冲突检测、批量排期导入
