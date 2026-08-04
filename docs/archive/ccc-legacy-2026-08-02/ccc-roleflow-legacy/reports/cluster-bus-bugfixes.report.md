# cluster-bus-bugfixes — Phase 1 Report

**Task**: 修 `ccc-exec-commit.sh` JSONL 解析 bug
**Phase**: 1 (fix-jsonl-commit-bug)
**Date**: 2026-07-06
**Executor**: claude (independent session)

---

## 改动清单

### 1. `scripts/ccc-exec-commit.sh` — Python heredoc 解析逻辑 (L82-104)

**Before** (单 JSON 文档解析,JSONL 触发 `Extra data`):
```python
with open(fp) as f:
    data = json.load(f)
```

**After** (兼容 3 种格式:空 / JSON 数组 / JSONL / 单 JSON 对象):
```python
with open(fp) as f:
    content = f.read().strip()

# 兼容 3 种格式: 单 JSON 对象 / JSON 数组 / JSONL (每行一个对象)
if not content:
    data = {}
elif content.startswith('['):
    # JSON 数组格式
    data = {"phases": json.loads(content)}
elif '\n' in content:
    # JSONL 格式(每行一个独立 JSON 对象)— 优先判定(单行 JSONL 不可能存在)
    phases = [json.loads(line) for line in content.splitlines() if line.strip()]
    data = {"phases": phases}
else:
    # 单 JSON 对象
    data = json.loads(content)
```

下游 `data.get('phases', [data])` 已支持两种 schema(顶层 `phases` key 或整个对象即单 phase)。

### 2. `tests/scripts/test_ccc_exec_commit_jsonl_smoke.py` — 新建回归测试 (6 cases)

覆盖:
1. `test_phases_jsonl_format_accepted` — JSONL 格式 phases.json 不报 JSONDecodeError
2. `test_phases_jsonl_format_task_id_injected` — JSONL 无 task_id 时自动注入 uuid
3. `test_phases_json_array_format_accepted` — JSON 数组格式(legacy)
4. `test_phases_single_object_format_accepted` — 单 JSON 对象格式
5. `test_phases_empty_file_handled` — 空文件不挂
6. `test_real_cluster_bus_bugfixes_phases_jsonl` — 实际 `cluster-bus-bugfixes.phases.json` 解析校验

---

## 自验证 (pytest)

```
$ python3 -m pytest tests/scripts/test_ccc_exec_commit_jsonl_smoke.py -v
============================= test session starts ==============================
platform darwin -- Python 3.14.6, pytest-9.0.3, pluggy-1.6.0
rootdir: /Users/apple/program/CCC
collected 6 items

tests/scripts/test_ccc_exec_commit_jsonl_smoke.py::test_phases_jsonl_format_accepted PASSED [ 16%]
tests/scripts/test_ccc_exec_commit_jsonl_smoke.py::test_phases_jsonl_format_task_id_injected PASSED [ 33%]
tests/scripts/test_ccc_exec_commit_jsonl_smoke.py::test_phases_json_array_format_accepted PASSED [ 50%]
tests/scripts/test_ccc_exec_commit_jsonl_smoke.py::test_phases_single_object_format_accepted PASSED [ 66%]
tests/scripts/test_ccc_exec_commit_jsonl_smoke.py::test_phases_empty_file_handled PASSED [ 83%]
tests/scripts/test_ccc_exec_commit_jsonl_smoke.py::test_real_cluster_bus_bugfixes_phases_jsonl PASSED [100%]

============================== 6 passed in 0.91s ===============================
```

**结果**: 6/6 PASS,0.91s

---

## 验收红线

| 红线 | 状态 |
|------|------|
| Bug 修复(`json.load` → 多格式兼容) | ✅ |
| 回归测试覆盖 3+ case | ✅ (实际 6 case) |
| 实际 `cluster-bus-bugfixes.phases.json` 可解析 | ✅ |
| 不 commit / 不写 verdict | ✅ |

---

> VERDICT: .ccc/verdicts/cluster-bus-bugfixes.verdict.md