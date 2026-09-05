# DSH 权限协商修复报告（2026-09-05）

## 根因

`dsh-executor.sh` 已通过 `DSH_PERMISSION_MODE=danger-full-access` 预先授予当前会话完整权限，但执行体仍在工具调用中重复发送 `sandbox_permissions: "danger-full-access"`。宿主将其视为重复权限升级，并返回「sandbox escalation ... is not strictly wider than this call's current `danger-full-access` mode」。问题是重复 escalation，不是权限不足。

## 改动

- 在 `scripts/dsh-executor.sh` 的执行 prompt 授权段明确声明：当前会话已预授予 `danger-full-access`；工具调用不得传 `sandbox_permissions`、不得请求权限升级、不得以 `danger-full-access` 作为重复升级参数；若 schema 要求权限字段则省略或使用当前上下文。
- 补充测试约束：缺少 pytest 时优先使用业务仓已有入口/解释器；不要用带 `danger-full-access` escalation 参数的 uvx/临时安装；确实无法测试时记录原始失败并继续写 `.ccc-result.md`，不要无限重试。
- 在 `server/tests/test_skeleton.py` 增加静态契约测试，读取 wrapper 源文本检查上述 prompt 语义并执行 `bash -n`；不启动真实 DSH。

## 验证

- `bash -n scripts/dsh-executor.sh`：通过。
- `.venv-hub/bin/pytest -q server/tests/test_skeleton.py server/tests/test_result_report_api.py`：通过（45 passed）。
- `.venv-hub/bin/ruff check server/`：通过（All checks passed）。
- `git diff --check`：通过。

## 回滚

撤销本次新增 prompt 约束和对应静态测试即可；不需重启 Engine，也不手动终止 xy060。下次 Engine 重派时 wrapper 自动使用新提示。
