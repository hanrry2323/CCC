# Plan: qx-err-structured-logging — 爬虫结构化 JSON 日志

> 撰写：ccc-product | 执行：ccc-dev（auto）

---

## 当前代码状态

代码勘探发现当前日志系统存在两个互不相交的层次：

**① `scripts/crawler_logger.py`（79 行）** — 极简 `log_crawl_result()` 函数，接受 `(worker_id, worker_name, status, records_count, …)` 参数，写入 `data/workflow.db` 的 `execution_logs` 表供 dashboard 面板读取。**不使用 `logging` 模块，不输出日志文件，无任何 JSON 结构化输出，无日志轮转**。

**② 9 个文件各自独立使用 Python `logging`** — 每个文件自写 `logging.basicConfig()` + `logging.getLogger("name")`，8 个不同 logger 名称 (`tfydd`/`nmpa`/`announcement_sync`/`snapshot_refresh`/…)，格式互不兼容。**无集中日志配置**、**无 JSON 格式化器**、**无 Python 层日志轮转**（PM2 只管理其托管进程的 stdout/stderr 文件轮转）。

- **入口/核心文件：**
  - `scripts/crawler_logger.py`（行 1-79）— 当前唯一"爬虫日志"入口，写入 SQLite（dashboard 数据源），无文件日志
  - `lib/crawler_core/base.py:115-156` — 框架方法 `log_crawl_result()`，延迟导入 `crawler_logger.log_crawl_result`，异常不阻断主流程
  - `lib/crawler_core/runner.py:175-190` — 编排器在 `finally` 中调 `crawler.log_crawl_result()`
  - `config/loader.py:54` — 已导出 `LOGS_DIR`（默认为 `QX_ROOT / "logs"`），可直接复用

- **当前结构要点：**
  - `config/loader.py` 已提供 `LOGS_DIR` 和 `QX_ROOT`，可在新模块中直接 `from config.loader import LOGS_DIR` 引用日志路径，无需额外路径发现
  - `logs/` 目录已存在（存放 PM2 stdout/stderr 文件），可在其下建子目录 `logs/crawler/` 存放 JSON 日志
  - 项目零日志依赖（仅 stdlib），`pyproject.toml` 只依赖 `requests` 和 `playwright`
  - `log_crawl_result` 的调用链有两层：`runner.py:175-190 → base.py:115-156 → crawler_logger.py:38-78`，JSON 日志在 `crawler_logger.py` 注入即可覆盖全调用路径

- **待改动点：**
  - `lib/structured_logger.py`（新建）— 每日滚动 JSONL 写入器，7 天自动清理
  - `scripts/crawler_logger.py`（行 38-78）— `log_crawl_result()` 内新增 JSON 日志输出

---

## 范围

- **目标**：为爬虫执行日志添加 JSON 结构化文件输出（`logs/crawler/YYYY-MM-DD.jsonl`），每日滚动 + 7 天自动清理。每个 `log_crawl_result` 调用同时产出 JSON 日志行（level/ts/crawler/msg/error 五字段），不改变现有 SQLite 日志路径
- **只改文件：**
  - `lib/structured_logger.py`（新建）
  - `scripts/crawler_logger.py`
- **不改文件：** `config/loader.py`（已导出 `LOGS_DIR`，不动）、`lib/crawler_core/base.py`（框架方法不动）、`lib/crawler_core/runner.py`、`crawlers/` 下所有文件（v1.0/driver/wrapper 均不动）、`workers/`、`dashboard/`、`scripts/`（除 `crawler_logger.py`）、`infra/`、所有 CCC 看板/计划文件
- **执行方式：** `auto`
- **Phase 数：** 2

---

## 改动 1：`lib/structured_logger.py` — 每日滚动 JSONL 核心模块

### 做什么

创建项目级 JSON 结构化日志模块，提供零依赖的每日滚动 JSONL 写入 + 7 天自动清理。

核心设计：
- 单入口函数 `write_log(level, crawler, msg, ts=None, error=None, **extra)`，写入 `logs/crawler/YYYY-MM-DD.jsonl`
- 每次写入时检查并清理超过 7 天的旧日志文件（调用 `_housekeeping()`）
- 使用 `threading.Lock` 保证多线程安全
- 写入失败 `print` 到 stderr，不抛异常（不拖垮业务）
- `maybe_override_log_dir()` 可通过 `QX_CRAWLER_LOG_DIR` 环境变量覆盖日志目录

JSON 行 schema（单行、`ensure_ascii=False`、紧凑）：

```json
{
  "level": "INFO",
  "ts": "2026-07-15T10:30:00",
  "crawler": "sichuan",
  "msg": "crawl completed: success (42 records, 3120ms)",
  "error": null,
  "records_count": 42,
  "duration_ms": 3120,
  "status": "success"
}
```

其中 `level`/`ts`/`crawler`/`msg`/`error` 为强制字段，`**extra` 中传入的附加字段（如 `records_count`, `duration_ms`）自动展平到 JSON 行中。

`level` 取值：`INFO` / `WARN` / `ERROR`（字符串）

### 怎么做

**`lib/structured_logger.py`**（新建，约 70 行）：

```python
"""lib/structured_logger.py — 每日滚动 JSONL 结构化日志模块。

设计：
  * 零外部依赖（仅 stdlib）
  * 每日一个 JSONL 文件（logs/crawler/YYYY-MM-DD.jsonl）
  * 7 天自动清理
  * 线程安全（threading.Lock）
  * 写入失败不抛异常（仅 stderr 告警）

用法：
    from lib.structured_logger import write_log

    write_log("INFO", "sichuan", "crawl completed", records_count=42)
    write_log("ERROR", "tfydd", "login failed", error="HTTP 502")

JSON 行字段（固定 5 字段 + extra 展平）：
  level, ts, crawler, msg, error, ...extra
"""
from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

# 项目日志目录（复用 config.loader.LOGS_DIR，无循环导入风险）
try:
    from config.loader import LOGS_DIR
except ImportError:
    LOGS_DIR = Path(__file__).resolve().parents[1] / "logs"

# 可被环境变量覆盖
_CRAWLER_LOG_DIR = Path(
    os.environ.get("QX_CRAWLER_LOG_DIR", str(LOGS_DIR / "crawler"))
)

_lock = threading.Lock()


def write_log(
    level: str,
    crawler: str,
    msg: str,
    ts: str | None = None,
    error: str | None = None,
    **extra,
) -> None:
    """追加一条 JSON 日志行到当日文件。

    Args:
        level: 日志级别（INFO / WARN / ERROR）
        crawler: 爬虫名称（如 sichuan、tfydd）
        msg: 人类可读消息
        ts: ISO 时间戳（默认自动生成 UTC now）
        error: 错误信息（无错误时 None）
        **extra: 额外字段（自动展平到 JSON 行同一层）
    """
    entry = {
        "level": level,
        "ts": ts or datetime.now(timezone.utc).isoformat(),
        "crawler": crawler,
        "msg": msg,
        "error": error,
    }
    if extra:
        entry.update(extra)

    try:
        _write_jsonl(entry)
    except Exception as e:
        print(f"[structured_logger] 写入失败: {e}", file=sys.stderr)


def _write_jsonl(entry: dict) -> None:
    """线程安全地追加 JSON 行到当日文件，附带 7 天 housekeeping。"""
    with _lock:
        today = date.today()
        log_dir = _ensure_dir(today)
        log_file = log_dir / f"{today.isoformat()}.jsonl"

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        _housekeeping()


def _ensure_dir(d: date) -> Path:
    """创建并返回日志子目录（含日期子目录便于按日清理）。"""
    p = _CRAWLER_LOG_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def _housekeeping() -> None:
    """删除超过 7 天的日志文件（仅在今日文件写入后触发）。"""
    cutoff = date.today() - timedelta(days=7)
    try:
        for f in _CRAWLER_LOG_DIR.iterdir():
            if f.suffix != ".jsonl":
                continue
            try:
                # 文件名即日期：YYYY-MM-DD.jsonl
                file_date = date.fromisoformat(f.stem)
                if file_date < cutoff:
                    f.unlink()
            except (ValueError, OSError):
                continue
    except OSError:
        pass
```

### 验收清单

- [ ] `lib/structured_logger.py` 创建成功，Python 语法合法
- [ ] `write_log("INFO", "test", "msg")` 在 `logs/crawler/<今日>.jsonl` 写入合法 JSON 行
- [ ] JSON 行含 `level`/`ts`/`crawler`/`msg`/`error` 五个字段
- [ ] `**extra` 字段展平到 JSON 行同层
- [ ] 写入失败仅 stderr 告警，不抛异常
- [ ] 日志目录 `logs/crawler/` 自动创建（不存在时）
- [ ] `threading.Lock` 保证并发写入不拆行
- [ ] `QX_CRAWLER_LOG_DIR` 环境变量可覆盖日志目录
- [ ] 7 天 housekeeping：超过 7 天的 `.jsonl` 文件被删除，7 天内文件保留

### 验收

- [语法合法]（参考：`cd ~/program/projects/qx && python3 -c "import ast; ast.parse(open('lib/structured_logger.py').read()); print('OK')"`）
- [写入正常]（参考：`cd ~/program/projects/qx && python3 -c "
from lib.structured_logger import write_log
write_log('INFO', 'test', 'hello structured log', records_count=42)
import json; p=list(LOGS_DIR.glob('crawler/*.jsonl'))[0]
line=json.loads(p.read_text().strip().split('\n')[-1])
assert line['level']=='INFO' and line['crawler']=='test' and line['msg']=='hello structured log'
assert line.get('records_count')==42
assert 'error' in line
print(f'OK: wrote to {p}')
"`）
- [写入失败不抛异常]（参考：`cd ~/program/projects/qx && python3 -c "
from lib.structured_logger import write_log
write_log('INFO', 'crash', 'boom', records_count=42)
print('write completed without exception')
"`）
- [compileall 零 error]（参考：`cd ~/program/projects/qx && python3 -m compileall -q lib/structured_logger.py && echo OK`）

---

## 改动 2：`scripts/crawler_logger.py` 集成 JSON 日志输出

### 做什么

在 `log_crawl_result()` 函数末尾追加 JSON 结构化日志输出，使每个爬虫执行结果同步写入 `logs/crawler/YYYY-MM-DD.jsonl`。

映射规则：

| JSON 字段 | 来源 | 逻辑 |
|-----------|------|------|
| `level` | `status` 映射 | `"success"` → `"INFO"`, `"partial"` → `"WARN"`, 其余 → `"ERROR"` |
| `ts` | `finished_at` | 优先用入参 `finished_at`，备选自动生成 |
| `crawler` | `worker_name` | 直接传递 |
| `msg` | 组合 | `f"crawl {status}: {records_count} records"`（含 `duration_ms` 和 `error` 时有扩展） |
| `error` | — | 仅 `status != "success"` 时填 `f"status={status}"`，否则 `None` |
| `records_count` | `records_count` | extra 展平 |
| `duration_ms` | `duration_ms` | extra 展平 |
| `status` | `status` | extra 展平任务原始状态 |
| `task_id` | `task_id` | extra 展平 |
| `task_name` | `task_name` | extra 展平 |

JSON 日志输出**不取代**现有的 SQLite 写入路径——两条路径并行，dashboard 继续从 SQLite `execution_logs` 表读取，JSON 文件供运维/监控/溯源使用。

### 怎么做

**`scripts/crawler_logger.py`**（行 1-79 改造）：

文件顶部（`from config.loader import get_db_path` 之后）新增 import：
```python
from lib.structured_logger import write_log
```

`log_crawl_result()` 函数末尾（`conn.close()` 之后 `finally` 块之外，即行 78-79 之间）追加结构化日志输出：

在原函数 `finally: conn.close()` 之后（函数结束之前）：
```python
    # === JSON 结构化日志（运维/监控/溯源）===
    if status == "success":
        _level = "INFO"
    elif status == "partial":
        _level = "WARN"
    else:
        _level = "ERROR"
    _msg = f"crawl {status}: {records_count or 0} records"
    if duration_ms is not None:
        _msg += f", {duration_ms}ms"
    _error = None if status == "success" else f"status={status}"
    try:
        write_log(
            level=_level,
            crawler=worker_name,
            msg=_msg,
            ts=finished_at,
            error=_error,
            records_count=records_count or 0,
            duration_ms=duration_ms,
            status=status,
            task_id=task_id,
            task_name=task_name or "",
        )
    except Exception:
        pass  # JSON 日志写入失败不影响主流程
```

最终 `log_crawl_result()` 整体结构变为：

```python
def log_crawl_result(...) -> None:
    log_id = f"log-{uuid.uuid4().hex[:16]}"
    if duration_ms is None:
        duration_ms = _calc_duration_ms(started_at, finished_at)

    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    try:
        conn.execute(INSERT_SQL, params)
        conn.commit()
    finally:
        conn.close()

    # === JSON 结构化日志 ===
    if status == "success":
        _level = "INFO"
    elif status == "partial":
        _level = "WARN"
    else:
        _level = "ERROR"
    _msg = f"crawl {status}: {records_count or 0} records"
    if duration_ms is not None:
        _msg += f", {duration_ms}ms"
    _error = None if status == "success" else f"status={status}"
    try:
        write_log(
            level=_level,
            crawler=worker_name,
            msg=_msg,
            ts=finished_at,
            error=_error,
            records_count=records_count or 0,
            duration_ms=duration_ms,
            status=status,
            task_id=task_id,
            task_name=task_name or "",
        )
    except Exception:
        pass
```

### 验收清单

- [ ] `scripts/crawler_logger.py` 顶部 import `from lib.structured_logger import write_log`
- [ ] `log_crawl_result()` 末尾追加 JSON 日志写入（`finally` 块之后、`return` 之前）
- [ ] `status` → `level` 映射正确：success→INFO, partial→WARN, 其他→ERROR
- [ ] JSON 日志写入失败不冒泡（try/except pass）
- [ ] 现有的 SQLite 写入路径完全保留（dashboard 不受影响）
- [ ] `python3 -m compileall -q` 零 error
- [ ] 实际调用 `log_crawl_result("test", "unit-test", "success")` 在 JSONL 文件中产生 1 行合法 JSON

### 验收

- [语法合法]（参考：`cd ~/program/projects/qx && python3 -c "import ast; ast.parse(open('scripts/crawler_logger.py').read()); print('OK')"`）
- [import 正常]（参考：`cd ~/program/projects/qx && python3 -c "
from scripts.crawler_logger import log_crawl_result
print('import OK')
"`）
- [写 JSON + SQLite 正常]（参考：`cd ~/program/projects/qx && python3 -c "
from datetime import datetime, timezone
from scripts.crawler_logger import log_crawl_result
ts = datetime.now(timezone.utc).isoformat()
log_crawl_result('w99', 'unit-test', 'success', records_count=42, started_at=ts, finished_at=ts, duration_ms=1234)
# SQLite 写入
import sqlite3
from config.loader import get_db_path
db = get_db_path('workflow')
r = sqlite3.connect(str(db)).execute('SELECT count(*) FROM execution_logs WHERE worker_id=?', ('w99',)).fetchone()
print(f'SQLite rows: {r[0]}')
# JSONL 写入
from pathlib import Path
import json
logdir = Path('logs/crawler')
if logdir.exists():
    for f in sorted(logdir.glob('*.jsonl')):
        with open(f) as fh:
            lines = fh.read().strip().split(chr(10))
            print(f'JSONL {f.name}: {len(lines)} lines')
            last = json.loads(lines[-1])
            assert last['crawler'] == 'unit-test'
            assert last['level'] == 'INFO'
            print(f'  last line level={last[\"level\"]} crawler={last[\"crawler\"]}')
"`）
- [compileall 零 error]（参考：`cd ~/program/projects/qx && python3 -m compileall -q lib/structured_logger.py scripts/crawler_logger.py && echo OK`）
- [SQLite 路径不受影响]（参考：上面验证包含 SQLite 行数检查，确保 count > 0）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | `lib/structured_logger.py` 创建 | `feat(lib): 爬虫结构化 JSON 日志模块 — 每日滚动 + 7 天清理 (phase 1/2)` |
| 2 | `scripts/crawler_logger.py` 集成 JSON 输出 | `feat(crawlers): crawler_logger.py 输出 JSON 结构化日志 (phase 2/2)` |

---

## 全局验收清单

- [ ] `lib/structured_logger.py` Python 语法合法
- [ ] `scripts/crawler_logger.py` Python 语法合法
- [ ] `python3 -m compileall -q lib/structured_logger.py scripts/crawler_logger.py` 零 error
- [ ] `write_log("INFO", "test", "msg")` 在 `logs/crawler/<日期>.jsonl` 写入合法 JSON 行（含 level/ts/crawler/msg/error）
- [ ] JSON 日志写入失败仅 stderr 告警，不抛异常
- [ ] `log_crawl_result()` 调用同时写入 SQLite 和 JSONL
- [ ] JSON level 映射正确：success→INFO, partial→WARN, 其他→ERROR
- [ ] existing SQLite `execution_logs` 表写入正常（dashboard 不受影响）
- [ ] 日志目录自动创建
- [ ] 7 天 housekeeping 有效（超过 7 天的 `.jsonl` 删除）
- [ ] `threading.Lock` 保证并发安全
- [ ] diff 范围仅限"只改文件"列表（2 文件）
- [ ] 每个 phase 对应一个 commit
- [ ] phases.json 与 plan phase 数一致（2）
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤

1. 后续可将 `lib/structured_logger.py` 推广到项目其他 8 个 `logging.getLogger` 使用方（`nmpa_to_pg`/`snapshot_refresh`/`cron_dispatcher` 等），实现全项目结构化日志统一
2. 可在 `lib/structured_logger.py` 后续版本中扩展 `debug()`/`info()`/`warn()`/`error()` 便捷方法封装
3. 可通过 `QX_CRAWLER_LOG_DIR` 将 JSON 日志指向共享卷或集中日志收集目录
4. 可考虑在 JSONL 文件中加入 `version` 字段（当前默认 `"1.0"`），方便 schema 演进
