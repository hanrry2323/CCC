---
name: ccc-verify
description: >-
  CCC platform pre-submit verification: py_compile, ruff, pytest server suite.
  Use when finishing CCC platform edits, before commit,
  or user says 自检 / 跑测 / verify / 提交前检查.
---

# CCC 平台自检（ccc-verify）

> **2026-08-02 重构定稿后**：本 skill 已切换到 `server/` 新栈；旧 `scripts/` 命令已退役。
> 不启用 Engine invent，不修改运行面配置。

## 默认顺序（由快到慢）

改了哪些就跑哪些；全量提交前尽量跑完 1–3。

```bash
# 1) 语法（改过的 server/*.py）
python3 -m py_compile server/engine/main.py
# 按需追加其它改动文件

# 2) Lint（CI 级，覆盖 server/）
ruff check server/ tests/

# 3) 新栈单测
pytest server/tests/ -q --tb=short

# 4) 可选：HTTP API 烟测
curl -s http://192.168.3.116:7788/health
```

Shell 脚本改动时额外：`bash -n path/to/script.sh`。

## 单点排查

```bash
pytest server/tests/test_engine_main.py -v --tb=short
pytest server/tests/test_http_api.py -v -k test_conversation
```

## 报告口径

- 先报：命令 + 退出码 + 失败用例名（勿只说「有问题」）。
- 修测试失败时只动与本次改动相关的断言/实现；勿顺手大扫除。
- 版本 SSOT：`VERSION`；勿在 verify 流程里擅自 bump。

## 权威巡查（平台维护）

提交前或每日维护：

```bash
# 仓内 grep 自检（排除归档区与 CHANGELOG 历史条目）
rg -n 'scripts/ccc-engine|Hub :7777|6\+1 列|能力包|M1 Desktop \+ sidecar|角色分层' \
  --glob '!docs/archive/**' --glob '!.ccc/archive/**' --glob '!CHANGELOG.md'
```

- 退出 0：绿，可继续绿灯自动维护（不问老板）。
- 退出非 0：有旧口径残留，**停止改红线**；等人话告警拍板。
- 权威链：`docs/INDEX.md` §0（重构决策定稿 + 契约 v1 最高优先级）。
