# 任务卡 T71 · server P0 修复（F01/F02/F11 · T70 审计）

> 关联：T70 审计 P0（F01 卡头替换误改正文 / F02 非 UTF-8 卡拖垮扫描 / F11 SSE 断流不 settle）· 执行体：Claude Code · 验收：Codex · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-06
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

**执行体**：Claude Code（2017）· 日期：
