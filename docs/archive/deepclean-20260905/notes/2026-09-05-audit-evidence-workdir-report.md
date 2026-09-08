# 后段 test-evidence 使用业务 worktree 修复报告

日期：2026-09-05
状态：已完成

## 1. 根因与范围

- 根因：`phase2.py:_run_dsh_auditor` 在 CCC 主仓 cwd 启动后段 `cc-auditor.sh`，旧调用未传业务 worktree；wrapper 使用 `$(pwd)` 调 `test-evidence.sh`，导致业务测试命令在 CCC 主仓执行并产生假失败。
- 修复范围：仅修改后段验收证据执行目录选择和对应回归测试；未修改 xianyu 业务代码、任务卡正文或业务仓。

## 2. 实现

- `server/engine/phase2.py`：验收席 wrapper argv 第 3 位传 `card.get("worktree")`；空值保持 `__CCC_EMPTY__` 哨兵，保留既有 argv 签名。
- `scripts/cc-auditor.sh`：保留主仓 cwd 读取主仓卡；机械测试证据工作目录按 `BIZ_WORKTREE` → `WORKTREE` → 主仓根目录选择，并输出 `test_workdir` 日志；调用 `test-evidence.sh` 时传入该目录，不再默认使用 `$(pwd)`。
- `server/tests/test_phase2.py`：断言注册表 wrapper 收到卡的业务 worktree。
- `server/tests/test_skeleton.py`：增加 workdir 选择和 `test-evidence` 参数静态契约断言。

## 3. 独立验证证据

- `.venv-hub/bin/python -m pytest server/tests/test_phase2.py -q`：通过（35 passed）。
- `.venv-hub/bin/python -m pytest server/tests/test_skeleton.py -q`：通过（28 passed）。
- `.venv-hub/bin/python -m pytest tests/test_test_evidence.py -q`：通过（6 passed）。
- `.venv-hub/bin/ruff check server/`：`All checks passed!`。
- `bash -n scripts/cc-auditor.sh scripts/test-evidence.sh`：通过。
- 未访问真实 xy060 卡，未修改业务仓。

## 4. 收口

修复提交并推送后，已通过 launchctl 重启 Engine；实测 `com.ccc.engine` 状态为 `running`，日志出现 heartbeat。尝试用本机鉴权文件获取 Bearer token 并正规 redispatch `xy060`，`POST /session` 返回 401（凭证与当前服务配置不匹配），因此未伪造成功、未手工改状态；xy060 重派待有效 `CCC_BOARD_TOKEN` 后由正规脚本执行。未绕过 `test-evidence`，未修改业务实现。
