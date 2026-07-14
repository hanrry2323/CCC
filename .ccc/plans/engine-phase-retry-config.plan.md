# Plan: engine-phase-retry-config — phase 重试策略可配置化

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

Engine phase 重试次数和超时值散落在 `ccc-engine.py` 和 `ccc-board.py` 中硬编码。`phases.json` 的 `retry` 字段已存在但 Engine 未全面读取；超时值部分从 CLI 传，部分硬编码 600s。

## 范围

- **目标**: phase 重试次数和超时从 phases.json 读取，不存在时用 _config.py 默认值
- **只改文件**: `scripts/ccc-engine.py`, `scripts/ccc-board.py`, `scripts/_config.py`

## 改动

1. `_config.py` 添加 `DEFAULT_RETRY=3`, `DEFAULT_TIMEOUT=600`
2. Engine `_load_phases()` 解析 phase 时读取 `retry` 和 `timeout` 字段
3. `dev_role_launch()` 传参不再硬编码，从 phase 配置读取
4. 日志输出标明 "retry 2/3, timeout 300s"

## 验收

- [默认] phases.json 无 retry/timeout 时使用 _config.py 默认值
- [覆盖] phases.json 指定 retry: 5 时实际重试 5 次
- [日志] 日志行含 "retry 2/3, timeout 600s" 字样
- [回滚] `git revert` 可一键回退
