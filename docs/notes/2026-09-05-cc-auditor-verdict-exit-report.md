# cc-auditor verdict 退出语义修复记录

日期：2026-09-05

## 结论

`scripts/cc-auditor.sh` 现在以 verdict 工件中的当前裁决为业务退出语义，不再把 Claude CLI 的非零退出码覆盖成基础设施失败：

- 可解析 `机审：通过` → exit 0；
- 可解析 `机审：不通过（原因）` → exit 2；
- 工件存在但没有可解析裁决行 → exit 1；
- 无 verdict 工件 → 保留 Claude CLI 原始退出码，stdout 仍包含 CLI 输出（含 stderr 重定向内容）。

当 Claude CLI 返回 rc=1 但已写入 `机审：不通过` 时，wrapper 返回 exit 2，phase2 可进入 REJECT 打回路径；CLI rc 仅记录在 stderr 诊断中。

## 证据

- 改动：`scripts/cc-auditor.sh`
- 隔离测试：`scripts/tests/test-cc-auditor-verdict.sh`
- 测试场景：mock 通过 + CLI rc=1 → 0；mock 不通过 + CLI rc=1 → 2；无 verdict + CLI rc=1 → 1。
- 语法：`bash -n scripts/cc-auditor.sh` 通过。
- 相关回归：`python3 -m pytest -q server/tests/test_phase2.py server/tests/test_skeleton.py server/tests/test_audit_format_contract.py`，结果 `81 passed`。
- 既有 shell 测试：`scripts/tests/test-card-resolve.sh`、`scripts/tests/test-redispatch-default.sh` 均通过。

## 是否需要重启 Engine

不需要重启。`server/engine/phase2.py` 的 `_dsh_auditor_path()` 每次 `_run_dsh_auditor()` 调用时从 `EXECUTOR_REGISTRY_PATH` 读取「验收席」命令；代码中没有缓存 `_dsh_auditor_path` 结果。当前注册表指向 `/Users/fan/program/CCC/scripts/cc-auditor.sh`，因此下一轮 phase2 自然调用即使用新脚本。此次未重启 engine，也未访问真实 xy060。

## 边界保持

维护区四问、`test-evidence.sh` 真实性门禁、结果工件缺失前置失败均未改动；无 verdict 时不伪造业务裁决。
