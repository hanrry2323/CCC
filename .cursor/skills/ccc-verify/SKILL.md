---
name: ccc-verify
description: >-
  CCC platform pre-submit verification: py_compile, ruff, pytest scripts suite,
  optional self-check. Use when finishing CCC platform edits, before commit,
  or user says 自检 / 跑测 / verify / 提交前检查.
---

# CCC 平台自检（ccc-verify）

只用于 **本仓（orch）平台改动**。不启用 Engine invent，不改 `~/.ccc/control.json`。

## 默认顺序（由快到慢）

改了哪些就跑哪些；全量提交前尽量跑完 1–3。

```bash
# 1) 语法（改过的 scripts/*.py）
python3 -m py_compile scripts/ccc-engine.py
# 按需追加其它改动文件

# 2) Lint（CI 级）
ruff check scripts/ tests/

# 3) 核心单测
pytest tests/scripts/ -q --tb=short

# 4) 可选：完整自检（较慢）
bash scripts/ccc-self-check.sh
```

Shell 脚本改动时额外：`bash -n path/to/script.sh`。

## 单点排查

```bash
pytest tests/scripts/test_board_store.py -v --tb=short
pytest tests/scripts/test_engine.py -v -k test_phase_dependencies
```

## 报告口径

- 先报：命令 + 退出码 + 失败用例名（勿只说「有问题」）。
- 修测试失败时只动与本次改动相关的断言/实现；勿顺手大扫除。
- 版本 SSOT：`VERSION`；勿在 verify 流程里擅自 bump。

## 权威巡查（平台维护）

提交前或每日维护：

```bash
python3 scripts/ccc-authority-patrol.py --dry-run   # CI/本地安静
python3 scripts/ccc-authority-patrol.py              # 违规才桌面通知 + ~/.ccc/alerts
```

- 退出 0：绿，可继续绿灯自动维护（不问老板）。
- 退出 2：红，**停止改红线**；等人话告警拍板。
- 卡片：`references/authority-patrol.jsonl`（机读）。
- 单测：`pytest tests/scripts/test_authority_patrol.py -q`
