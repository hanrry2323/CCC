# Plan: debt-config-unify-timeout — 超时参数统一到 _config.py

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

3 处硬编码超时散落在不同脚本：`ccc-engine.py` 600s, `ccc-board.py` 600s, `opencode-exec.py` 300s。修改超时需要改 3 个文件，容易遗漏。

## 范围

- **目标**: 所有超时参数收口到 `_config.py` 的 `Config` 类
- **只改文件**: `scripts/_config.py`, `scripts/ccc-engine.py`, `scripts/ccc-board.py`, `scripts/opencode-exec.py`

## 改动

1. `_config.py` 添加 `PHASE_TIMEOUT = 600`, `EXEC_TIMEOUT = 300`, `ENGINE_TICK_INTERVAL = 5`
2. 3 个脚本 import `from _config import config` 替换硬编码
3. `_config.py` 支持 `CCC_PHASE_TIMEOUT` 环境变量覆盖
4. 日志输出当前超时值（方便调试）

## 验收

- [无硬编码] `grep -n 'timeout=600\|timeout=300\|sleep(5)' scripts/ccc-engine.py scripts/ccc-board.py scripts/opencode-exec.py` 返回空
- [环境变量] `CCC_PHASE_TIMEOUT=1200 python3 scripts/ccc-engine.py` 实际使用 1200s
- [向后兼容] 不设环境变量时用默认值
