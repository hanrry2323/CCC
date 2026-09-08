# 2026-09-04 flowfix Batch1 报告

## 结论

批次改动已完成，定向测试与全量 pytest 通过；全量 Ruff 未通过，但失败项均在本批未修改文件，按指令红线未扩大范围修复。引擎已按要求重启并确认新 PID 与心跳。

## 改动与证据

1. `server/engine/card_state_store.py:503-543`
   - 新增 `CardStateStore.write_audit_verdict()`。
   - 机审区写入经既有 `update_card()`，继续使用卡锁、版本 CAS、原子写、Git 写锁与提交/推送复核；未增加旁路直写。
2. `server/engine/phase2.py:315-575`
   - 机审前置改为主仓卡状态（store snapshot）必须为「已回写」，并要求 `EXECUTOR_LOG_DIR/<work_id>-ccc-result.md` 存在。
   - auditor 输入固定为主仓卡，空 worktree 参数仅用于兼容参数位；不再检查/创建业务 worktree，旧 `_ensure_audit_worktree` 已删除。
   - verdict 从 `EXECUTOR_LOG_DIR/<work_id>-audit-verdict.md` 读取，整行 `机审：通过/不通过`；exit 2 且工件含结论按 REJECT 处理。
   - 审计基础设施失败写入 audit sidecar 冷却信息；连续失败达到 `PHASE2_AUDIT_MAX_STRIKES`（默认 3）后走熔断打回并记 `phase2_audit_circuit_open` ledger；冷却期跳过计数。
3. `scripts/dsh-auditor.sh:7-159`
   - 三重 worktree/卡副本守卫改为主仓卡只读契约。
   - verdict 统一写 `EXECUTOR_LOG_DIR/<work_id>-audit-verdict.md`；机械前置失败写 REJECT 工件并 exit 2；DSH exit 2 且未产出工件时写兜底 REJECT 工件。
   - prompt 明确禁止写卡文件与业务 worktree。
4. `server/tests/test_phase2.py:50-107, 394-421`
   - 增加新前置工件、空 worktree 调用与 verdict 工件测试；更新旧 worktree 假设测试。

## 定向测试

复现命令：

```text
python3 -m pytest server/tests/test_phase2.py server/tests/test_phase2_engine_cas_interop.py server/tests/test_card_state_store_cas.py server/tests/test_dsh_gateway.py -q
```

结果：`54 passed`。

修改文件 Ruff：

```text
python3 -m ruff check server/engine/phase2.py server/engine/card_state_store.py server/tests/test_phase2.py
```

结果：`All checks passed!`

## 全量门禁

全量 pytest：

```text
python3 -m pytest server/tests/ -q
```

结果：通过，输出进度 100%，退出码 0。

全量 Ruff：

```text
python3 -m ruff check server/ scripts/
```

结果：未通过，13 个既有错误，均不在本批改动文件：

- `scripts/tests/regression_v028.py`：6 个 `F541`
- `server/engine/main.py:707`：`UP038`
- `server/kb/indexer.py:112,133`：`UP038`
- `server/tests/test_http_api.py:957`：`UP038`
- `server/tests/test_server.py:292,940`：`UP038`

按指令“只改本清单范围”红线，未修改这些既有问题；本批涉及 Python 文件的 Ruff 已独立通过。

## 逐笔 commit / push

每笔均已推送 `origin/main`：

1. `88b593ef2` — `fix(card): add audit verdict store facade`
2. `21a92f533` — `fix(card): align phase2 audit contract`
3. `853e63976` — `fix(card): cool down repeated audit failures`
4. `90ad78c94` — `fix(card): preserve mock audit error semantics`
5. `4a10f940d` — `fix(card): audit preflight before gateway + cooldown guard`
6. `28128dd41` — `fix(card): honor audit verdict exit contract`
7. `92c2a8eec` — `fix(card): write audit verdict artifacts`

最终本地 HEAD 与 `origin/main` 均为：`92c2a8eec68f785501d87596b68c842d6e44715`。

## 引擎重启核验

执行时间（UTC）：`2026-09-04T07:43:08Z`。

执行动作：`launchctl kickstart -k gui/$(id -u)/com.ccc.engine`。

独立核验：

- 重启前匹配 PID：`95332`
- 重启后 PID：`58797`
- `launchctl print`：`state = running`，`pid = 58797`
- 进程工作目录：`/Users/fan/program/CCC`
- 重启后日志出现新的 `heartbeat`，且 `scanned=0`、`audit_failed=0`、`audit_failed_infra=0`。

重启前遗留日志尾部仍包含 `tst905` 旧 worktree 卡缺失告警；该告警属于重启前旧代码输出。重启后的新心跳已由 PID `58797` 产生并确认运行。
