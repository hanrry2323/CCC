# Plan: ccc-cleanup-dead-code — 清除 scripts/ 下未使用 import 和 dead code

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/` 下共 23 个 Python 源文件（不含 `scripts/tests/`）
- **当前结构要点**：
  - 8 个文件存在 16 处未使用 import，均为标准库模块（`sys`、`os`、`time`、`json`、`html`、`re`、`tarfile`、`datetime`/`timezone`、`Optional`、`Any`、`Mapping`），移除无运行时影响
  - 3 个文件存在 8 处 dead code：`_board_store.py`（5 处：`_HAS_FLOCK`、`VALID_ID_CHARS`、`_acquire_ro`、`quarantines_cleanup_task`、`quarantines_harvesting_index`）、`_logger.py`（1 处：`_format` 方法从未被调用）、`ccc-board.py`（2 处：`STALE_CHECK_INTERVAL` 常量、`_task_all_phases_terminal` 函数）
  - `_board_store.py` 中的 `quarantines_cleanup_task` 和 `quarantines_harvesting_index` 仅被 `tests/` 引用——产品代码中无调用者
  - `ccc-board.py` 的 `_task_all_phases_terminal` 仅被 `tests/` 引用——产品代码中已由 phase 依赖解析替代
- **待改动点**：`scripts/_board_store.py`、`scripts/_build_prompt.py`、`scripts/_logger.py`、`scripts/_review_validator.py`、`scripts/_stats_aggregator.py`、`scripts/phase_lint.py`、`scripts/ccc-cockpit.py`、`scripts/ccc-chat-server.py`、`scripts/ccc-board.py`

---

## 范围

- **目标**：清除 scripts/ 下所有未使用的 import 和产品代码中无用的定义/常量，消除 ruff/lint 噪音
- **只改文件**：
  - `scripts/_board_store.py`
  - `scripts/_build_prompt.py`
  - `scripts/_logger.py`
  - `scripts/_review_validator.py`
  - `scripts/_stats_aggregator.py`
  - `scripts/phase_lint.py`
  - `scripts/ccc-cockpit.py`
  - `scripts/ccc-chat-server.py`
  - `scripts/ccc-board.py`
- **不改文件**：`scripts/tests/` 下任何文件、`.ccc/` 配置文件、`templates/`、`docs/`
- **执行方式**：`manual`
- **Phase 数**：2

---

## Phase 1：移除全部 16 处未使用 import

### 做什么

删除 8 个文件中经 AST 分析确认的未使用 import。标准库 import 移除是零风险的机械操作——运行时 import 开销被省去，无行为变化。

### 怎么做

逐文件删除以下行：

| 文件 | 行号 | 删除的 import |
|------|------|---------------|
| `_board_store.py` | 13 | `import sys` |
| `_board_store.py` | 14 | `import tarfile` |
| `_build_prompt.py` | 14 | `import json` |
| `_build_prompt.py` | 16 | `Mapping`（从 `from typing import Final, Mapping` 中移除） |
| `_logger.py` | 30 | `from typing import Optional`（整行） |
| `_review_validator.py` | 8 | `import os` |
| `_review_validator.py` | 11 | `Any`（从 `from typing import Any` 中移除——整行） |
| `_stats_aggregator.py` | 18 | `import os` |
| `_stats_aggregator.py` | 19 | `import time` |
| `phase_lint.py` | 19 | `import os` |
| `phase_lint.py` | 20 | `import re` |
| `phase_lint.py` | 22 | `from datetime import datetime, timezone`（整行） |
| `phase_lint.py` | 24 | `Any`（从 `from typing import Any, Dict, List, Set, Tuple` 中仅移除 `Any`） |
| `ccc-cockpit.py` | 16 | `import sys` |
| `ccc-cockpit.py` | 17 | `import time` |
| `ccc-chat-server.py` | 16 | `import html` |

### 验收清单

- [ ] 8 个文件中总计 16 个未使用 import 被移除
- [ ] 每个文件移除后 `python3 -c "compileall.compile_file(...)"` 零错误
- [ ] 移除后全局搜索未发现误删（被删除符号在新 import 列表下确实未使用）
- [ ] 所有测试仍然通过：`uv run pytest tests/scripts/ -q --ignore=tests/e2e`
- [ ] `_build_prompt.py` 的 `from typing import Final` 保留（`Final` 在 `__all__` 中被使用）
- [ ] `_logger.py` 的 `from typing import Optional` 已移除（`Optional` 在该文件中未被任何代码使用；`_board_store.py` 有自己的 `from typing import Optional`，不受影响）

### 验收

- 语法检查通过（参考：`cd scripts && for f in _board_store.py _build_prompt.py _logger.py _review_validator.py _stats_aggregator.py phase_lint.py ccc-cockpit.py ccc-chat-server.py; do python3 -c "import ast; ast.parse(open('$f').read()); print(f'$f: syntax OK')"; done`）
- 测试通过（参考：`cd /Users/apple/program/CCC && uv run pytest tests/scripts/ -q --ignore=tests/e2e`）
- ruff 检查：移除后 import 不应再出现（参考：`ruff check scripts/_board_store.py scripts/_build_prompt.py scripts/_logger.py scripts/_review_validator.py scripts/_stats_aggregator.py scripts/phase_lint.py scripts/ccc-cockpit.py scripts/ccc-chat-server.py --select F401`）

---

## Phase 2：移除 8 处死定义

### 做什么

删除产品代码中已定义但从未被任何产品代码调用的函数/方法/常量。

### 怎么做

#### A. `_board_store.py`

1. **第 29-30 行 `_HAS_FLOCK = False`**：删除整行。注释"保留 _HAS_FLOCK 仅作历史索引"——纯历史标记，无法读取，无保留价值。历史已在 git 中。

2. **第 83 行 `VALID_ID_CHARS = re.compile(...)`**：删除整行。校验已委托 `_utils_sanitize_id()` 实现，该正则常量未被任何代码引用。

3. **第 413-415 行 `_acquire_ro` 方法**：删除整个方法体。读锁占位方法，从未被任何调用方引用。（`_board_store.py` 自己的 `from typing import Optional` 中 `Optional` 仍被其他方法使用，保留）。

4. **第 847 行 `quarantines_cleanup_task` 函数**：删除整个函数定义（及其调用者在文件内部的引用）。仅被 `tests/` 引用。

5. **第 968 行 `quarantines_harvesting_index` 函数**：删除整个函数定义。仅被 `tests/` 引用。

#### B. `_logger.py`

6. **第 89-93 行 `_format` 方法**：删除整个方法。日志方法（`debug`/`info`/`warning`/`error`/`exception`）全部通过标准 logging Formatter 格式化，`_format` 从未被调用。

#### C. `ccc-board.py`

7. **第 91 行 `STALE_CHECK_INTERVAL = 6`**：删除整行。ops_role 扫描间隔常量，但 ops_role 已内联硬编码超时，该常量未在任何地方被读取。

8. **第 492-505 行 `_task_all_phases_terminal` 函数**：删除整个函数定义。Phase 依赖解析已在 `_resolve_phase_dependencies()` 实现，该函数仅被 `tests/` 引用。

删除后更新 `ccc-board.py` 的所有引用：搜索 `_task_all_phases_terminal(` 确保无残留产品代码调用。

### 验收清单

- [ ] `_HAS_FLOCK` 常量已删除
- [ ] `VALID_ID_CHARS` 正则已删除
- [ ] `_acquire_ro` 方法已删除
- [ ] `quarantines_cleanup_task` 函数已删除
- [ ] `quarantines_harvesting_index` 函数已删除
- [ ] `_format` 方法已删除
- [ ] `STALE_CHECK_INTERVAL` 常量已删除
- [ ] `_task_all_phases_terminal` 函数已删除
- [ ] 全局搜索每个被删除符号，确认无产品代码引用残留
- [ ] 所有测试通过：`uv run pytest tests/scripts/ -q --ignore=tests/e2e`

### 验收

- 删除后语法检查通过（参考：`cd scripts && for f in _board_store.py _logger.py ccc-board.py; do python3 -c "import ast; ast.parse(open('$f').read()); print(f'$f: syntax OK')"; done`）
- 确认测试通过（参考：`cd /Users/apple/program/CCC && uv run pytest tests/scripts/ -q --ignore=tests/e2e`）
- 全局搜索确认被删符号不再出现（参考：`grep -rn '_HAS_FLOCK\|VALID_ID_CHARS\|_acquire_ro\|quarantines_cleanup_task\|quarantines_harvesting_index\|def _format\|STALE_CHECK_INTERVAL\|_task_all_phases_terminal' scripts/ --include='*.py'`，预期只有 `scripts/tests/` 下的引用，产品代码无匹配）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 移除 8 个文件中 16 处未使用的 import | `chore(scripts): 清除未使用的 import (phase 1/2)` |
| 2 | 移除 3 个文件中 8 处死定义 | `chore(scripts): 清除 dead code 定义 (phase 2/2)` |

规则：每个 phase 一个独立 commit，message 含 phase 编号。

---

## 全局验收清单

- [ ] Python 语法检查零错误
- [ ] 全部测试通过（`uv run pytest tests/scripts/ -q --ignore=tests/e2e`）
- [ ] diff 范围仅限"只改文件"列表（9 个文件）
- [ ] ruff F401 无残留（unused import）
- [ ] 每个 phase 对应一个 commit
- [ ] 被删除符号的产品代码引用全部清理
- [ ] `_build_prompt.py` 保留 `Final`（已使用），`_board_store.py` 保留 `from typing import Optional`（仍被其他方法使用）

---

## 后续步骤

Phase 3（可选）：清理 `tests/` 中引用已删除函数 (`quarantines_cleanup_task`、`quarantines_harvesting_index`、`_task_all_phases_terminal`) 的测试用例，但超出当前 scope 范围，建议单独提 card。
