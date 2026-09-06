# P1 verdict JSON 化报告

日期：2026-09-07（按 2026-09-06 指令续跑收口）
提交：`98a28aabc`

## 改动清单

- `scripts/cc-auditor.sh`
  - Claude prompt 要求用 Write 写 `<work_id>-audit-verdict.json`；正文写 `.md`。
  - Python schema 校验 `verdict` / `reason` / `findings` / `severity`。
  - JSON 缺失、解析失败或 schema 非法统一 fail-closed 为 exit 2，并写 markdown protocol REJECT。
  - 保留 BASE_URL 归一、PATH 兜底、参数解包、BIZ_WORKTREE、维护区和 test-evidence 门禁、3 次重试/30 秒间隔。
- `server/board/audit_verdict.py`
  - 新增单源 `parse_json_verdict`、`parse_markdown_verdict`、`read_verdict`。
  - JSON 优先，旧 markdown 仅兼容 fallback；解析失败不推断 PASS。
- `server/engine/phase2.py`
  - 消费结构化 verdict；P0/P1 阻断、P2 留档不阻断。
  - 新增 REJECT 预算 sidecar：默认同卡 3 次耗尽后置「打回（REJECT 预算耗尽，待人工）」并写 `reject_budget_exhausted` ledger。
  - protocol REJECT 走基础设施冷却，不调用业务预算。
  - 删除 `_claude_verdict_from_output`、`PHASE2_VERDICT` 与 marker prompt。
- `server/engine/main.py`
  - 改用 `server.board.audit_verdict.read_verdict`，删除 `_audit_verdict_from_artifact`。
  - protocol verdict 作为 infra；P0/P1 业务 finding 阻断；保留旧 worktree wrapper 兼容链。
- `server/engine/runtime_state.py` / `server/web/server.py`
  - sidecar 增加 `reject_count` / `reject_budget_exhausted`；人工 redispatch 清零。
- `server/tests/fixtures/verdict-corpus/`
  - 2 个合法样本 + 6 个畸形样本：前导空白、fenced、截断、prose 混排、markdown 加粗、编码污染。
- 测试更新：结构化 JSON 矩阵、severity 阈值、预算耗尽、protocol 与人工重派清零、shell wrapper 合同。

## 验证矩阵

| 检查 | 结果 | 复现命令 |
|---|---|---|
| 全量 Python 测试 | 通过（含 2 skipped） | `.venv-hub/bin/pytest server/tests/ -q` |
| focused verdict/phase2/ledger 测试 | 通过 | `.venv-hub/bin/pytest -q server/tests/test_audit_verdict.py server/tests/test_phase2.py server/tests/test_engine_pass_ledger.py` |
| auditor shell 合同 | 通过 | `bash scripts/tests/test-cc-auditor-verdict.sh` |
| Ruff | 通过 | `.venv-hub/bin/ruff check server/` |
| Python 编译 | 通过 | `python3 -m py_compile server/board/audit_verdict.py server/engine/phase2.py server/engine/main.py server/engine/runtime_state.py server/web/server.py` |
| Shell 语法 | 通过 | `bash -n scripts/cc-auditor.sh scripts/tests/test-cc-auditor-verdict.sh` |
| 旧口径 grep | 归零 | `grep -R "_claude_verdict_from_output\\|PHASE2_VERDICT" -n server scripts` |
| diff whitespace | 通过 | `git diff --check` |

## 影子双跑（只读）

对象：`/Users/fan/.ccc/logs/exec/xy060-audit-verdict.md`（未写生产状态）。

- 旧整行正则：`PASS`，reason 为空。
- 新 `parse_markdown_verdict`：`PASS`，reason 为空。
- 结论一致；xy060 卡和工件均未修改。

## 提交/推送

- `98a28aabc feat(audit): add structured JSON verdict contract`
- 已推送 `origin/main`。

## 部署记录

- 重启前：engine PID `86815`，web PID `86818`；`GET http://192.168.3.116:7788/health` → `{"status":"ok","auth_required":false,"auth_configured":true}`。
- 执行：`launchctl kickstart -k gui/$(id -u)/com.ccc.engine`、`launchctl kickstart -k gui/$(id -u)/com.ccc.web-server`。
- 重启后：engine PID `28519`，web PID `28522`；同一 `/health` 返回 ok。
- `xy060` 卡/工件未修改。
