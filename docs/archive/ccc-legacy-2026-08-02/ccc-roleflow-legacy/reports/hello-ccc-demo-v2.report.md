# hello-ccc-demo-v2 — Executor Report

> **task**: hello-ccc-demo-v2
> **executor**: CCC Executor
> **scope**: scripts/ccc-status.sh + scripts/ccc-cost.sh + tests/scripts/test_ccc_status_smoke.py + 本报告

---

## 改动文件清单

| # | 文件 | 行数 | 类型 |
|---|------|------|------|
| 1 | `scripts/ccc-status.sh` | 105 | 新建 |
| 2 | `scripts/ccc-cost.sh` | 85 | 新建 |
| 3 | `tests/scripts/test_ccc_status_smoke.py` | 55 | 新建 |
| 4 | `.ccc/reports/hello-ccc-demo-v2.report.md` | — | 本报告 |

> Phase 1 提交在 `49aa249 ccc-task-id=hello-ccc-demo phase=1` 中已含 `scripts/ccc-status.sh`。
> 本次改动新增 3 个文件 (`ccc-cost.sh` / 测试 / 报告)。

---

## 自验证结果

### Phase 2 — ccc-cost.sh

```
$ bash -n scripts/ccc-cost.sh
syntax: OK

$ bash scripts/ccc-cost.sh --task hello-ccc-demo
task: hello-ccc-demo
commits: 1
files: 2
report: /Users/apple/program/CCC/.ccc/reports/hello-ccc-demo.report.md
exit=0

$ bash scripts/ccc-cost.sh --task nonexistent
ERROR: report not found: /Users/apple/program/CCC/.ccc/reports/nonexistent.report.md
exit=2

$ bash scripts/ccc-cost.sh            # 缺 --task
ERROR: --task <name> is required
exit=2

$ chmod +x scripts/ccc-cost.sh        # OK
```

### Phase 3 — pytest

```
$ python3 -m pytest tests/scripts/test_ccc_status_smoke.py -v
tests/scripts/test_ccc_status_smoke.py::test_status_text_output          PASSED [ 33%]
tests/scripts/test_ccc_status_smoke.py::test_status_json_output          PASSED [ 66%]
tests/scripts/test_ccc_status_smoke.py::test_status_handles_missing_verdict PASSED [100%]
============================== 3 passed in 0.05s ===============================
```

---

## 验收结果表

| 验收项 | 命令 / 标准 | 结果 |
|--------|------------|------|
| ccc-cost.sh syntax | `bash -n scripts/ccc-cost.sh` | OK |
| ccc-cost.sh 正常路径 | `bash scripts/ccc-cost.sh --task hello-ccc-demo` | exit 0, commits=1 |
| ccc-cost.sh 错误路径 | `bash scripts/ccc-cost.sh --task nonexistent` | exit 2 |
| ccc-cost.sh 缺参数 | `bash scripts/ccc-cost.sh` | exit 2 |
| ccc-cost.sh 可执行 | `chmod +x scripts/ccc-cost.sh` | OK |
| pytest 文本输出 | `test_status_text_output` | PASS |
| pytest JSON 输出 | `test_status_json_output` (4 keys) | PASS |
| pytest 含 ok | `test_status_handles_missing_verdict` | PASS |
| pytest 全通过 | `pytest -v` | 3/3 PASS |
| 文件数约束 | ≤ 4 文件 | ✓ (3 + 本报告) |

---

## 红线遵守

- ✅ 不 git add / commit
- ✅ 不写 verdict.md (Verifier 专属)
- ✅ 未超出 4 文件白名单

---

> VERDICT: .ccc/verdicts/hello-ccc-demo-v2.verdict.md