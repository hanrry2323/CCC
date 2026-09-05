# phase2 验收席非 UTF-8 解码修复

日期：2026-09-05

## 结论

`server/engine/phase2.py` 的 `_run_dsh_auditor` 已改为以 bytes 捕获验收席 stdout/stderr，再以 UTF-8 `errors="replace"` 显式解码。返回签名仍为 `(rc, out: str, err: str)`，超时、启动异常、分支漂移和返回码语义未改动。

## 验证

- 定向测试：`.venv-hub/bin/python -m pytest server/tests/test_phase2.py -q`，35 passed。
- 静态检查：`.venv-hub/bin/ruff check server/engine/phase2.py`，通过。
- 空白检查：`git diff --check`，通过。
- 新增测试覆盖非法 UTF-8 stdout/stderr，确认输出含替换字符且 `PHASE2_VERDICT: PASS` 仍可解析。

## 变更范围

- `server/engine/phase2.py`
- `server/tests/test_phase2.py`
- 本报告

未修改 xianyu 业务代码、任务卡或机审区。

## 追加：cc-auditor UTF-8 shell 变量边界修复

- `scripts/cc-auditor.sh` 中紧邻中文/全角标点的变量引用已改为显式 `${AUDIT_CARD}`、`${WORK_ID}`、`${ROLE}`、`${rc}`，避免 Bash UTF-8 locale + `set -u` 将全角标点及后续文字并入变量名。
- `bash -n scripts/cc-auditor.sh`：通过。
- UTF-8 locale + `set -u` 等价 echo：通过，输出 `审查对象：卡片.md（work xy060，角色 验收席）`。
- `$CCC_BRAIN_CLAUDE_BIN` 与 `$HOME` 仅出现在反斜杠转义的错误提示文本中，不属于实际展开引用，未改动。

未修改任务卡、xianyu 业务代码、状态机或 DSH。

## 追加：roadmap 级联回写后自然消费观察

- `chore(xianyu): record M6.1 cascade progress` 已提交并推送：`ace8ca69e53e2f176c4feef40e0b9d088ea1bf0f`。
- 未重启 engine（PID 8545 仍存活）；`/Users/fan/.ccc/logs/engine-pipeline.json` 在 2026-09-05 19:07:16 显示 `git_sync_ok=true`、`probe_skips=0`、`audit_failed=0`、`in_flight=0`。
- 现有 phase2 已自然消费 `xy060`，未再因 `docs/projects/xy/roadmap.md` 脏状态跳过；随后独立收口结果为 `rejected`，原因是维护区完成钩子只找到 `0/4` 问，并由 engine 生成提交 `93590aca85ea5d9e6729ac084e72123c841ff6f3`（`chore(card): xy060 已回写 → 打回`）。
- 该次消费路径未出现此前的 UTF-8 解码异常或 `AUDIT_CARD…: unbound variable`；历史错误仍保留在旧日志中，不能作为本次回归失败证据。

本观察未重启 engine，未修改业务仓或任务卡正文。
