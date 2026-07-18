# Plan: debt-import-cleanup — 清理未使用 import

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

`ruff check` 周期性发现 F401（import 未使用）警告。当前 `fix-lint-2026-07-14` 已清理部分，但新增代码可能引入新的未使用 import。

## 范围

- **目标**: 运行 `ruff check --fix --select F401 scripts/ tests/` 清理全部未使用 import
- **只改文件**: 自动修复的文件

## 改动

1. `cd ~/program/CCC && ruff check --fix --select F401 scripts/ tests/`
2. `ruff check --select F401 scripts/ tests/` 确认 0 残留
3. commit

## 验收

- [0] `ruff check --select F401 scripts/ tests/` → 0 errors
- [build] `python3 -m compileall scripts/ tests/` → 0 errors
