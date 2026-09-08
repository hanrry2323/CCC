# 后段验收证据工作目录收口报告

日期：2026-09-05

## 结论

已完成后段验收 wrapper 的业务 worktree 传递修复并重启 Engine。独立证据确认前段 xy060 自测在业务 worktree 内通过；后段本轮未能启动，原因是 Engine 网关配额预检返回 `PROBE_UNAVAILABLE`，因此不伪造后段 PASS，不合入、不部署。

## 平台修复

- `server/engine/phase2.py:_run_dsh_auditor`：第 3 位保持卡对象原始 `worktree`；第 5 位新增 `BIZ_WORKTREE`，优先使用卡 worktree，卡为空时按项目隔离根 `_worktree_for(project, work_id)` 推导，仍为空才传 `__CCC_EMPTY__`。
- `scripts/cc-auditor.sh`：保留 `BIZ_WORKTREE → WORKTREE → REPO_ROOT` 选择顺序；目标目录不存在时回落主仓并输出 WARN，再把 `TEST_WORKDIR` 传给 `test-evidence.sh`。
- 测试补充 phase2 argv 第 5 位和脚本回落门禁。

## 验证证据

- `pytest server/tests/test_phase2.py -q`：36 passed（使用 `.venv-hub/bin/pytest`）。
- `.venv-hub/bin/ruff check server/`：通过。
- `bash -n scripts/cc-auditor.sh`：通过。
- `git diff --check`：通过。
- `pytest server/tests/test_skeleton.py -q`：28 passed。
- 提交：`81edb2ba5d46becbb5b7cd46ca2e6e06794736cf`，已推送 `origin/main`。
- Engine 重启后 pid：`97693`；launchd 状态 running。

## xy060 正规重派与独立运行证据

- 使用 `/Users/fan/.ccc/web-auth.txt` 凭据在内存中向 `POST /session` 换取短期 token；token 未写入文件、日志或报告。
- 使用 `CCC_BOARD_TOKEN` 调用 `scripts/redispatch-card.sh xy060`；返回 `from=待分派,to=待分派`，说明此前已是待分派状态，未改卡正文、未手工启动 DSH。
- 独立读取 `/Users/fan/.ccc/logs/exec/xy060.test-evidence.log`：`rootdir=/Users/fan/program/apps/.ccc-wt/xy/xy060`，收集 98 项，末行 `98 passed`，退出码 0。
- 独立读取 `/Users/fan/.ccc/logs/exec/xy060-ccc-result.md`：结果工件记录业务 worktree `/Users/fan/program/apps/.ccc-wt/xy/xy060`，前段自测 98 passed。
- 业务 worktree 实体存在：`/Users/fan/program/apps/.ccc-wt/xy/xy060`，分支 `codex/xy060-content-library-api`。

## 当前边界

- 看板核验：xy060 当前 `待分派`，`/board/ready_for_merge` 为空。
- Engine 日志显示网关配额预检：`dsh-key-check: 探针不可用（PROBE_UNAVAILABLE）`，本轮未拉起新的 DSH/后段验收。
- 既有 `xy060-audit-verdict.md` 为此前测试真实失败记录；本次未用它证明通过。
- 未修改 xianyu 业务代码、未修改 xy060 卡正文、未手工写卡回写区/机审区、未合入、未部署。
