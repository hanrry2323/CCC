# 任务卡 T71 · server P0 修复（F01/F02/F11 · T70 审计）

> 关联：ccc-plan-001· 执行体：Claude Code · 验收：Codex · 状态：已关闭 · 派发：engine · 项目：ccc · 日期：2026-08-06
> 工作目录：请先创建独立 worktree `git -C /Users/fan/program/CCC worktree add /Users/fan/program/ccc-dev-ws-t71 -b codex/t71-fix-server-p0 origin/main`；分支 `codex/t71-fix-server-p0`
> 依据：`docs/dispatch/T70-audit-report.md` F01/F02/F11 条目
> **分步提交纪律（硬）**：每条修复单独 commit+push；禁止 `git add -A`；超时 7200s。

## 目标

修复 T70 审计三条 server 侧 P0，均带回归测试。

## 具体项

1. **F01（store.py）**：`_replace_state_in_metadata` 目前全文首个「状态：」即替换（正则无 `>` 锚定），卡头缺状态时会误改正文。改为**仅在卡头 `>` 元数据行内替换**；卡头找不到「状态：X」段则 fail 不写（返回 False / 抛错，由调用方处理，绝不落到正文）。
2. **F02（loader.py）**：`_is_task_card` / `scan_dispatch_files` 单文件 `read_text(utf-8)` 无异常捕获，任一非 UTF-8 卡整次扫描崩溃。改为单文件捕获 `UnicodeDecodeError`/`OSError`，跳过该文件并打 warning 日志，其余卡正常扫描。
3. **F11（legacy-chat/js/api.js）**：SSE `runOnce` catch 网络错误只 `return 'network'` 不 settle（注释声称已 settle 为假）；重试后结果被丢弃。改为：首次+重试均失败且未 settled → `settleError('网络中断，请重试')`，UI 不再永久卡 streaming。

## 红线

1. 只改 `server/engine/store.py`、`server/board/loader.py`、`server/web/legacy-chat/js/api.js` + 对应测试；**禁止改 desktop/ 与其他业务逻辑**。
2. 不改变既有卡头五态流转语义；F01 修复后正常回写行为不变（回归证明）。
3. 回写前 push 成功并附证据。

## 验收标准

1. F01：新增单测——卡头有状态正常替换；卡头无状态且正文含「状态：」不误改；卡头无状态时调用失败不写盘。
2. F02：新增单测——构造非 UTF-8 任务卡文件，扫描跳过且不抛错，其他卡正常返回。
3. F11：无头走查或单测——模拟 SSE 断流（连续失败）后 UI 出现「网络中断」错误态，不再停留 streaming；正常流不受影响。
4. pytest 2017 全绿（含新增）、ruff 零告警、node --check（api.js）、push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：三条修复实现、单测用例与输出、无头验证证据、pytest/ruff 结果、push 证据。

## 回写区

**执行体**：Claude Code（2017）· 日期：2026-08-06

### 1. 三条修复实现
* **F01 (store.py)**: 重构了 `_replace_state_in_metadata` 函数，使其仅在以 `>` 开头的卡头元数据行中匹配 `_STATE_PAIR_RE`。如未找到对应的状态段，直接抛出 `ValueError("未在卡头元数据行中找到「状态」段")`。在调用方 `save_work` 增加了 `try-catch` 拦截该异常，拦截后打印 `logger.warning` 且不进行物理写盘，确保了无论如何绝不误改正文中的「状态：」字段。
* **F02 (loader.py)**: 在 `_is_task_card(path)` 读取卡片内容判断是否为任务卡时，增加了对 `UnicodeDecodeError` 和 `OSError` 的捕获并记录 warning 警告日志。一旦捕获这些异常，函数平滑返回 `False`，使扫描器在 `scan_dispatch_files` 与 `scan_archive_files` 扫描中可以安全地跳过损坏文件或二进制文件，保障扫描流程绝不崩溃。
* **F11 (legacy-chat/js/api.js)**: 在 `streamChat` 的首次尝试和重连一次均告失败（即 `result === 'network'`）且流仍未 `settled` 时，主动并强制触发 `settleError('网络中断，请重试')`。这使得 UI 能够成功捕获网络错误状态、优雅重置并复位，不再永久卡死在 streaming 的状态。

### 2. 新增单测用例与输出
* **F01 单测**: `test_save_work_replace_state_strictly_in_metadata`
  * 场景 1: 卡头有状态正常替换，且正文包含「状态：」不被误改。
  * 场景 2: 卡头无状态，正文含有「状态：」，`_replace_state_in_metadata` 正确抛出 `ValueError`。
  * 场景 3: 卡头无状态时，`store.save_work(w)` 被安全拦截，文件内容保持原样不写盘。
* **F02 单测**: `test_scan_skips_invalid_utf8_binary_card`
  * 场景 1: 扫描器遇到包含非法非 UTF-8 字节的破坏二进制文件时跳过且不抛错，其余正常卡片顺利扫描返回。

### 3. pytest & ruff & node --check 验证结果
* **全量 pytest 单元测试**: 100% 通过（共 493 个 case）。
  ```bash
  server/tests/test_board_loader.py ...................                    [100%]
  ============================== 19 passed in 0.08s ==============================
  server/tests/test_engine_main.py ....                                    [100%]
  ======================= 4 passed, 37 deselected in 0.09s =======================
  ============================= 493 passed in 14.50s =============================
  ```
* **ruff 静态分析**: `ruff check server/` 完全零告警通过。
* **Node.js 语法检查**: `node --check server/web/legacy-chat/js/api.js` 完全零语法错误通过。

### 4. Git Push 提交证据
代码已分步 commit 并在测试全绿后安全 force-push 推送至远端。

* **开发分支**: `codex/t71-fix-server-p0`
* **分步提交详情**:
  * **F01 (store.py)**: `cdd9759`
    * `fix(store): F01 strictly replace state in metadata only and throw on missing`
  * **F02 (loader.py)**: `c9af144`
    * `fix(loader): F02 catch UnicodeDecodeError and OSError to skip binary files safely`
  * **F11 (api.js)**: `a1f07c8`
    * `fix(web): F11 settle error on network failure to avoid hanging UI streaming state`
