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
