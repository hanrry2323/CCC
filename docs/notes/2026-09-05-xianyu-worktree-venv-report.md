# xianyu 业务 worktree `.venv` 挂载记录

日期：2026-09-05

## 改动

- `server/engine/main.py` 在业务仓 worktree 创建或复用后检查业务仓根 `.venv`。
- 业务仓根存在 `.venv` 且 worktree 没有同名路径时，创建 `worktree/.venv -> business_repo/.venv` 符号链接；不复制、不新建虚拟环境。
- worktree 已存在 `.venv`（实体或符号链接）时跳过。
- 业务仓根没有 `.venv` 时保持原行为，并记录 `WARN worktree venv unavailable`。
- worktree 强重建和终态清理前移除 worktree 内符号链接，不删除业务仓根 `.venv`。
- 重置工作树时使用 `git clean -fd -e .venv` 与排除 `.venv` 的状态检查，避免链接被误判为脏文件或被清理。

## 验证

- `./.venv-hub/bin/pytest -q server/tests/test_engine_main.py -k 'business_worktree or worktree_branch_seed or retryable_worktree'`：11 passed。
- `./.venv-hub/bin/pytest -q server/tests/test_engine_main.py server/tests/test_worktree_lifecycle.py server/tests/test_engine_task.py`：全部通过（122 tests）。
- `./.venv-hub/bin/ruff check server/`：All checks passed。
- 独立临时 git worktree 实验确认 `git clean -fd -e .venv` 保留 `.venv` 符号链接，pathspec exclude 不将其报告为脏改动。

## 范围

仅修改 CCC Engine 的业务 worktree 创建/清理逻辑、相关测试和本记录；未修改业务仓、任务卡或运行配置，未手动启动 DSH。
