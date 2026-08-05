# 任务卡 T67 · 部署窗口误派防线（卡头纪律 + Engine/放行双保险）（Claude Code 执行）

> 关联：T60 误派复盘（2026-08-05 部署窗口：已验收卡因卡头未同步被 Engine 重新拉起）· 执行体：Claude Code · 验收：Codex · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-05
> 工作目录：请先创建独立 worktree `git -C /Users/fan/program/CCC worktree add /Users/fan/program/ccc-dev-ws-t67 -b codex/t67-deploy-race-guard origin/main`；分支 `codex/t67-deploy-race-guard`
> **分步提交纪律（硬）**：每块完成立即 commit+push；超时 7200s。

## 目标

防止「已验收完成的卡被 Engine 误派」与「部署窗口中断在途执行体」，三条防线落地：

1. **卡头纪律校验（validate.py）**：卡文件含 Codex 验收区（`## 验收区` 且含 `✅` 判定）但卡头状态 ≠ 已关闭 → 报 error 阻断（CI/pre-commit 双闸）。本次 T60 事故即此形态：验收区已写、卡头仍待分派，部署后被 Engine 当新卡拉起。
2. **Engine 派发防误（server/engine/main.py）**：派发前检查卡文件是否含验收区标记（`## 验收区` + `✅`），命中则跳过并记录「已验收卡不派发」（防御性，防 1 尚未覆盖的旧卡/漏网）。
3. **放行窗口防中断（deploy/release.sh）**：生产模式在 git fetch/checkout 前先优雅停 Engine（`launchctl bootout`），等当前在途执行体进程退出或确认无在途（超时上限 300s）后再 checkout + kickstart 三服务；启动后扫描的是最终态，杜绝 checkout 窗口误扫 + kickstart 杀在途执行体。

## 具体项

1. validate.py：新增验收区-状态一致性检查（读卡正文 `## 验收区` 后 20 行内含 `✅`/`判定：通过` 即视为已验收），与五态/必填字段同级的 error 级规则；单测覆盖 3 类（验收区+已关闭=通过 / 验收区+待分派=error / 无验收区不触发）。
2. main.py：派发决策前读卡文件做验收区预检（缓存文件路径与 mtime，避免每轮全量读盘）；命中 → `logger.warning("已验收卡不派发: work=%s", ...)` 并跳过（保持原状态）。
3. release.sh：生产模式新增 `stop_engine()` / `start_engine()`；`--no-pull`/模拟模式跳过；在途执行体检测用 `pgrep -f 'claude -p'`（或 Engine 心跳 API，取实现最简者），等待期间每 10s 打点，300s 超时则警告并继续（不阻塞部署）。
4. 复盘文档：`docs/dispatch/T60-console-cockpit.md` 验收区补一行复盘说明（2026-08-05 误派根因 + 本卡防线），正文其他语义不动。
5. 回归：pytest server/tests 全绿；release.sh `--simulate` 跑通；validate 对现存 75 张卡零新增 error（旧卡宽容规则不变）。

## 红线

1. 只改 server/board/validate.py、server/engine/main.py、deploy/release.sh、server/tests/、docs/dispatch/T60-console-cockpit.md；**禁止改前端与桌面**。
2. 不改变现有五态流转语义；Engine 对正常待分派卡行为不变（回归证明）。
3. 回写前 push 成功并附证据。

## 验收标准

1. validate 新增规则单测通过；对现有 75 卡零新增 error。
2. Engine 单测覆盖「已验收卡不派发」；真实 or 模拟验证：含验收区卡不拉起执行体。
3. release.sh 模拟模式通过；生产模式改动在 M1 测试环境（临时目录）验证 stop/start 逻辑不破坏既有流程。
4. pytest 全绿、ruff 零告警、push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：三条防线实现、单测用例、release.sh 验证、pytest/ruff 结果、push 证据。

## 回写区

**执行体**：Claude Code（2017）· 日期：2026-08-05

三条防线全部落地（分支 `codex/t67-deploy-race-guard`，远端 HEAD `8531d439`）：

1. **卡头纪律校验**（`server/board/validate.py`）：新增 `_is_accepted()`——读卡正文 `## 验收区` 后 20 行内 `✅`/`判定：通过` 即视为已验收，与五态/必填字段同级 error 规则（验收区命中但状态 ≠ 已关闭 → 报错阻断）。单测 3 类：验收区+已关闭=通过 / 验收区+待分派=error / 超 20 行不触发。
2. **Engine 派发防误**（`server/engine/main.py`）：`is_card_accepted()` 按 mtime 缓存做派发前验收区预检；命中 → `logger.warning("已验收卡不派发: work=%s", ...)` 跳过保持原状态（并行/串行两派发路径接入）。单测 4 类：已验收不派发 / 正常卡照常派发 / 并行混合 / mtime 缓存判定。
3. **放行窗口防中断**（`deploy/release.sh`）：生产模式 checkout 前 `stop_engine()`（launchctl bootout + `pgrep -f 'claude -p'` 在途检测，10s 打点，300s 超时警告不阻塞）；checkout 后 `start_engine()`（已卸载 → bootstrap 恢复 / 未卸载 → kickstart -k）。`--no-pull`/`--simulate` 跳过。规避 bash 3.2 `$VAR` 紧邻全角字符解析缺陷（统一 `${VAR}`）。
4. **复盘文档**：`docs/dispatch/T60-console-cockpit.md` 验收区补 2026-08-05 误派根因 + 本卡防线一行。

### 验证证据

- **pytest**：`server/tests/` 490 passed（validate 17 → 20 用例、engine main 40 用例含 4 新）
- **ruff 0.8.6**：本次改动的 4 个文件 0 告警；`server/` 基线既有 UP038×3（`server/kb/indexer.py`×2 属红线外、`server/tests/test_http_api.py`×1）非本次引入
- **validate 现存卡**：76 卡零新增 error（验收区命中 47 张状态均已关闭）
- **release.sh**：`bash -n` 通过；隔离 harness（mock launchctl/pgrep/sleep）11 项断言全过（无在途/在途退出/超时不阻塞/bootout 失败继续/kickstart/bootstrap）；`--simulate` 放行通过（2 PASS / 8 SKIP / 0 FAIL）exit 0
- **push 证据**：`9881e27b`（validate）· `7eaa2100`（engine）· `f89285c5`（release.sh）· `f2ce3341`（T60 复盘）
