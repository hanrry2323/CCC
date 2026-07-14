# Plan: debt-docstring-sweep — 各模块补 docstring

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

scripts/ 下多个 Python 模块缺少模块级 docstring：`opencode-exec.py`、`ccc-exec-launcher.sh`（shell）、`_exceptions.py`、`_review_validator.py`、`_stats_aggregator.py`。

## 范围

- **目标**: 所有 Python 脚本补全模块级 docstring 和公共函数 docstring
- **只改文件**: `scripts/_exceptions.py`, `scripts/_review_validator.py`, `scripts/_stats_aggregator.py`, `scripts/opencode-exec.py`

## 改动

1. 每个文件添加模块级 docstring（1-3 行，中文，说明用途）
2. 公共函数（def 前有类型注解的）补 `"""..."""` docstring
3. 私有函数（`_` 开头）不做要求
4. docstring 风格：首行简要，换行后详述

## 验收

- [模块] 4 个文件都新增模块级 docstring
- [函数] 每个公共函数有 docstring
- [不改变功能] `python3 -m compileall scripts/` → 0 errors
