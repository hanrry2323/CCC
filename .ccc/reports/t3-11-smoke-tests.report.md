# T3 11-script Smoke Tests — Implementation Report

> 2026-07-06 | phase 1.3 (T3)

## 交付

8 test files covering 11 CCC scripts:

| Test file | Scripts covered | Tests |
|-----------|-----------------|-------|
| `test_ccc_dispatch_smoke.py` | ccc-dispatch.py | 6 |
| `test_cluster_bus_smoke.py` | cluster-bus.py | 8 |
| `test_ccc_exec_commit_smoke.py` | ccc-exec-commit.sh | 4 |
| `test_executor_watchdog_smoke.py` | executor-watchdog.sh | 4 |
| `test_flywheel_scan_smoke.py` | flywheel-scan.py | 5 |
| `test_ccc_init_search_smoke.py` | ccc-init.py + ccc-search.py | 7 |
| `test_ccc_tooling_hooks_smoke.py` | ccc-hook.sh / ccc-cost-report.sh / install-ccc-as-skill.sh / cluster-doctor.sh | 9 |

## Total: 43 tests, ALL PASS

```
$ python3 -m pytest tests/scripts/ -v
============================== 43 passed in 6.22s ==============================
```

## Bug Fixes During T3

### flywheel-scan.py — major bug
**Before**: hardcoded `CCC_HOME = Path(__file__).resolve().parent.parent / ".ccc"`,
always read from CCC main repo, never from cwd workspace.
**After**: respects `$CCC_HOME` env var or cwd.

This is a **blocker bug** — flywheel ran but always wrote to wrong dir.

### test fixture pattern
**Before**: `monkeypatch.chdir(tmp_path)` — does NOT affect subprocess cwd.
**After**: each test creates `<tmp_path>/<name>/` and uses `cwd=<subdir>` on `subprocess.run`.

This is a Python pytest fixture classic gotcha — known but easy to repeat.

## Coverage Summary

| 脚本 | before T3 | after T3 |
|------|---------|---------|
| ccc-dispatch.py | 0 tests | 6 (incl live cluster-bus mock) |
| cluster-bus.py | 7 (cluster/test-capability-required.py) | 7 (cluster-bus smoke adds 8 more = 15 total) |
| ccc-exec-commit.sh | 0 | 4 |
| executor-watchdog.sh | 0 | 4 |
| ccc-hook.sh | 0 | 1 (syntax) + 1 (stdin) |
| ccc-cost-report.sh | 0 | 1 (syntax) + 1 (run) |
| install-ccc-as-skill.sh | 0 | 2 (syntax + --check) |
| cluster-doctor.sh | 0 | 1 (syntax) + 1 (bus-down ABORT) |
| flywheel-scan.py | 0 | 5 |
| ccc-init.py | 0 | 3 |
| ccc-search.py | 0 | 2 |

**Total: 0 → 43 tests** (in 6.22s)

## Borrowed Lessons

- pytest monkeypatch + subprocess interplay (Lesson learned today)
- red line 14: flywheel never writes outside abnormal-reports/ — enforced
