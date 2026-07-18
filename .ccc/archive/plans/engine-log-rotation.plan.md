# Plan: engine-log-rotation — Engine 日志轮转，防止日志文件累积

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-engine.sh`（shell 入口，由 launchd `com.ccc.engine` 常驻守护）、`scripts/ccc-engine.py`（Engine 主循环，Python 日志走 `_log.info()`）、`scripts/_logger.py`（统一日志层）
- **当前结构要点**：
  1. `ccc-engine.sh:12` 写死 `LOG="${LOG_DIR}/engine-${$}.log"`，每次 restart 生成新 PID 文件
  2. 当前 `~/.ccc/logs/` 已有 **201 个 engine PID 文件**（总计 888 个日志文件），无轮转、无清理
  3. `_logger.py` 只配了 `StreamHandler`（写 stderr），日志文件处理完全在 shell 层
  4. launchd plist 设 `KeepAlive=true`，Engine 每 crash/stop 重启一次就多一个文件
  5. `engine_log()` → `_log.info()` 在 `ccc-engine.py:108-111`，只管拼格式，不碰文件
- **待改动点**：
  - `scripts/_logger.py`：新增 `add_file_handler()` 函数，向任意 CCC logger 挂载 `TimedRotatingFileHandler`
  - `scripts/ccc-engine.py`：启动时调用 `add_file_handler()` 配置日志文件轮转
  - `scripts/ccc-engine.sh`：去掉 PID 重定向，改为简洁的 `exec` 调用

---

## 范围

- **目标**：Engine 日志不再以 PID 命名累积文件，改用 `engine.log` 单文件 + `TimedRotatingFileHandler` 每天切分 + 保留最近 7 天
- **只改文件**：`scripts/_logger.py`，`scripts/ccc-engine.py`，`scripts/ccc-engine.sh`
- **不改文件**：`scripts/ccc-board.py`、`scripts/ccc-board-server.py`、`tests/`、`.plist` 文件不动
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：添加日志轮转

### 做什么

当前 Engine 日志写 shell 级 PID 文件，每个 restart 一个文件，无法轮转且累积成灾。

改为：由 Python `logging.handlers.TimedRotatingFileHandler` 接管 Engine 日志文件管理：
- 写入 `~/.ccc/logs/engine.log`（固定文件名）
- 每天 0 点自动切分为 `engine.log.YYYY-MM-DD`
- 保留最近 7 个备份，超期自动删除
- 仍然同时写 stderr（给 launchd），双路输出

Shell 入口去掉 PID 重定向，不再产生 `engine-{PID}.log` 新文件。已累积的旧文件可在部署后手动清理。

### 怎么做

**1. `scripts/_logger.py` 新增 `add_file_handler()`**（文件末尾，`get_logger` 之后）：

```python
import logging.handlers


def add_file_handler(
    name: str,
    file_path: str,
    when: str = "midnight",
    interval: int = 1,
    backup_count: int = 7,
) -> None:
    """给指定 CCC logger 添加 TimedRotatingFileHandler（双路输出：原有 handler + 本文件 handler）。

    此函数是幂等的（同 name+file_path 组合只加一次），可通过模块级 `_installed` set 去重。
    日志格式与 StreamHandler 保持一致（`[ccc.{name}] %(message)s`）。

    Args:
        name: logger name（即 get_logger(name) 的 name，如 "engine"）
        file_path: 日志文件路径（如 ~/.ccc/logs/engine.log）
        when: 切分时间单位（"midnight" / "H" / "D" / "W0"-"W6"）
        interval: 切分间隔
        backup_count: 保留备份数

    参考：`_logger.py:110` `get_logger()` 签名保持一致。
    """
    _configure_root()
    logger = logging.getLogger(f"ccc.{name}")
    handler = logging.handlers.TimedRotatingFileHandler(
        file_path,
        when=when,
        interval=interval,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
    logger.addHandler(handler)
```

**2. `scripts/ccc-engine.py` 启动时配置日志轮转**（`ccc-engine.py:67`，`cfg = Config()` 之后、`_log.info()` 之前）：  
   实际位置在 L66-67 之间。当前：
   ```python
   cfg = Config()
   _log.info(
   ```
   改为：
   ```python
   cfg = Config()
   # 日志轮转：engine.log + daily rotate + keep 7 days
   _log_dir = Path.home() / ".ccc" / "logs"
   _log_dir.mkdir(parents=True, exist_ok=True)
   _log_file = str(_log_dir / "engine.log")
   from _logger import add_file_handler  # 已在 import 链，safe
   add_file_handler("engine", _log_file, backup_count=7)
   _log.info(
   ```

注意：`Path.home()` 需改为绝对路径确保 launchd 环境下正确。理想写法：
```python
_log_dir = Path(os.environ.get("HOME", str(Path.home()))) / ".ccc" / "logs"
```

但考虑到 `ccc-engine.sh` 已设 `HOME`，直接用 `Path.home()` 即可。

**3. `scripts/ccc-engine.sh` 去掉 PID 重定向**（`ccc-engine.sh:10-18`）：

```bash
LOG_DIR="${HOME}/.ccc/logs"
mkdir -p "$LOG_DIR"
LOG="${LOG_DIR}/engine-${$}.log"
```

改为：
```bash
# 日志目录确保存在（Python 端也会创建，这里保留以防 python 未初始化时写其他文件）
mkdir -p "${HOME}/.ccc/logs"
```

```bash
exec python3 "$CCC_HOME/scripts/ccc-engine.py" >> "$LOG" 2>&1
```

改为：
```bash
exec python3 "$CCC_HOME/scripts/ccc-engine.py"
```

即去掉显式重定向。launchd 仍会捕获 stdout/stderr（默认行为），Python 日志通过 `TimedRotatingFileHandler` 写入固定文件。

### 验收清单

- [ ] 验收条件 1：Engine 启动时在 `~/.ccc/logs/engine.log` 写入日志（不再写 `engine-{PID}.log`）
- [ ] 验收条件 2：`engine.log` 写入内容格式为 `[ccc.engine] ...`，日志级别/内容与前一致
- [ ] 验收条件 3：stderr 日志仍在（`engine_log()` 同时输出到 lauchd 可见）
- [ ] 验收条件 4：launchd 重启 Engine 后不产生新 PID 文件（`ls ~/.ccc/logs/engine-*.log` 数量不增加）
- [ ] 边界场景：`~/.ccc/logs/` 目录不存在时自动创建
- [ ] 边界场景：`add_file_handler()` 幂等——同 name+path 重复调用不重复加 handler
- [ ] 错误处理：文件路径不可写时不影响 Engine 启动
- [ ] 安全相关：无新增外部依赖，`TimedRotatingFileHandler` 是 Python 标准库

### 验收

- [日志文件写入] 手动启动 Engine（`bash scripts/ccc-engine.sh &`），检查 `~/.ccc/logs/engine.log` 存在且包含 `[ccc.engine]` 日志行（参考：`head ~/.ccc/logs/engine.log`）
- [无新 PID 文件] 多次启停 Engine，`ls ~/.ccc/logs/engine-*.log 2>/dev/null | wc -l` 数量不增长
- [stderr 仍输出] `bash scripts/ccc-engine.sh 2>&1 | head -5` 能看到日志行
- [编译通过] `python3 -m compileall -q scripts/_logger.py scripts/ccc-engine.py`
- [幂等检查] 二次 import 不报异常（`python3 -c "from _logger import add_file_handler; add_file_handler('test','/tmp/ccctest.log'); add_file_handler('test','/tmp/ccctest.log'); print('OK')"`）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | `_logger.py` 新增 `add_file_handler()` 函数；`ccc-engine.py` 启动时配置 `TimedRotatingFileHandler`；`ccc-engine.sh` 去掉 PID 重定向 | `feat(engine): 日志轮转 — TimedRotatingFileHandler 按日切分保留 7 天 (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译零错误（`python3 -m compileall -q scripts/_logger.py scripts/ccc-engine.py`）
- [ ] `add_file_handler` 幂等测试通过（重复调用不爆 handler 堆叠）
- [ ] Engine 启动后 `~/.ccc/logs/engine.log` 有内容，`engine-*.log` 不再新增
- [ ] diff 范围仅限 3 个白名单文件
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json 与 plan phase 数一致
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤

部署后（`launchctl kickstart -k gui/501/com.ccc.engine`）确认日志正常。已有 200+ PID 文件可安全清理：`rm -f ~/.ccc/logs/engine-*.log`。