# Plan: fix-executor-log-tuple — 修 _executor.py _log 元组 bug

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/_executor.py`（241 行，Executor 抽象和 OpenCodeExecutor 实现）
- **当前结构要点**：
  - `_logger.py`（v0.28.0+）提供 `get_logger(name)` → 返回标准 logger 实例
  - `_config.py` 重导出 `get_logger`，在 `_executor.py` 行 12 导入
  - 行 14 写为 `_log = get_logger("executor"), get_logger` — 末尾 `, get_logger` 导致 `_log` 是**元组** `(logger_instance, get_logger_function)` 而非 logger 实例
  - 文件中 5 处使用 `_log.warning(...)`（行 196、204、213、217、237）—— 元组无 `.warning` 方法，会在运行时报 `AttributeError` 或静默吞掉异常
- **待改动点**：仅 `scripts/_executor.py:14` 一行

---

## 范围

- **目标**：修复 `_executor.py` 行 14 的赋值 bug，使 `_log` 指向正确的 logger 实例
- **只改文件**：`scripts/_executor.py`
- **不改文件**：`.ccc/` 下任何文件、其他脚本、测试文件、`_logger.py`、`_config.py`
- **执行方式**：`manual`
- **Phase 数**：1

---

## Phase 1：修 _log 赋值

### 做什么

行 14 的 `_log = get_logger("executor"), get_logger` 是**构造元组**——Python 中逗号就是元组构造器。`_log` 实际值为 `(<logger>, <function>)`，不是 logger 实例。所有后续 `_log.warning()` 调用都会报 `AttributeError: 'tuple' object has no attribute 'warning'`。

删掉 `, get_logger`，使 `_log = get_logger("executor")` 拿到正确的 logger 实例。

### 怎么做

- `scripts/_executor.py:14`：去掉逗号和 `get_logger`

### 验收清单

- [ ] `_log` 类型为 logger 而非 tuple
- [ ] `_log.warning()` 可正常调用
- [ ] 仅改这 1 行，无其它改动

### 验收

- `python3 -c "exec(open('scripts/_executor.py').read()); print(type(_log).__name__)"` 输出 `Logger`（而非 `tuple`）
- `python3 -c "from scripts._executor import _log; _log.warning('test ok')"` 不抛 `AttributeError`

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 删 `_log` 赋值行尾的 `, get_logger` | `fix(_executor): 修 _log 元组 bug，第 14 行尾缀 , get_logger 导致 _log 是 tuple (phase 1/1)` |

---

## 全局验收清单

- [ ] `python3 -m py_compile scripts/_executor.py` 语法通过
- [ ] diff 仅限 `scripts/_executor.py`，且仅 1 行改动
- [ ] 1 个 phase 对应 1 个 commit
- [ ] phases.json 与 plan phase 数一致
- [ ] 所有验收意图全部达成

---

## 后续步骤

无。此 bug 修复后 `_executor.py` 的日志调用恢复正常。