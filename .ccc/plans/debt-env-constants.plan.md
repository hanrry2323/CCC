# Plan: debt-env-constants — 硬编码路径收口到 _config.py

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

`.ccc/prompts/`、`.ccc/board/`、`.ccc/reports/` 等路径散落在 `ccc-engine.py`、`ccc-board.py`、`ccc-board-server.py` 中用字面量引用。修改项目目录结构时需要改多处。

## 范围

- **目标**: 所有 `.ccc/` 子目录路径收口到 `_config.py`
- **只改文件**: `scripts/_config.py`, `scripts/ccc-engine.py`, `scripts/ccc-board.py`, `scripts/ccc-board-server.py`

## 改动

1. `_config.py` 添加 `PROMPTS_DIR`, `BOARD_DIR`, `PLANS_DIR`, `PHASES_DIR`, `REPORTS_DIR`, `VERDICTS_DIR`
2. 3 个脚本用 `config.PROMPTS_DIR` 替代硬编码 `".ccc/prompts/"`
3. `Config.__init__` 接受 `workspace` 参数，路径动态构造
4. 向后兼容：默认值不变

## 验收

- [0 硬编码] `grep -rn '"\.ccc/' scripts/ccc-engine.py scripts/ccc-board.py scripts/ccc-board-server.py` 返回 0
- [test] `python3 -m pytest tests/scripts/test_config.py -q` → PASS
- [行为不变] Engine 启动后 paths 和文件读写正常
