# Plan: test-validate-jsonl-edge — task JSONL 校验边界测试

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

`test_validate_task_jsonl.py` 已有基础用例，但缺少边界场景：超长字符串、unicode 字符、空数组、超大数值、未知字段等。

## 范围

- **目标**: 补充 validate_task_jsonl 的边界测试
- **只改文件**: `tests/scripts/test_validate_task_jsonl.py`

## 改动

1. `test_validate_task_jsonl.py` 新增用例：
2. `test_unicode_title` — title 含中文和 emoji，通过
3. `test_max_length_title` — title 500 字符，通过；501 字符，失败
4. `test_empty_tags` — tags=[] 通过
5. `test_negative_complexity` — complexity="huge" 失败
6. `test_unknown_fields_strict` — strict=True 时未知字段拒绝
7. `test_null_assignee` — assignee=null 通过

## 验收

- [pass] `python3 -m pytest tests/scripts/test_validate_task_jsonl.py -q` → 全部 PASS
- [新增] 至少 6 个新 test 函数
- [无侵入] 功能代码无改动
