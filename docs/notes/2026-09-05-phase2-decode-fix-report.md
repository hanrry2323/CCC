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
