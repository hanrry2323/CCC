# CCC 平台每日权威巡查 + 绿灯维护（Cursor Automation 说明）

触发：每天一次（建议本地上午）。
仓库：本仓 CCC（platform）。

## 硬原则

1. **未违背权威 → 直接维护，不要问老板。**
2. **违背权威 → 只报警，不擅自改红线。** 以新栈门禁（validate）与文档权威链为准。
3. 经验进 `.cursor/rules` / `docs/lessons.md`，禁止另堆给人看的 brief。

## 必做步骤

1. 在仓库根执行新栈门禁：
   - `python -m server.board.validate docs/dispatch`（卡头门禁，exit 0 = 绿）
   - `bash scripts/verify-shell.sh --skip-conversation`（壳六场景 API 复验）
   - 绿：继续绿灯维护；红：只报警不改红线，人话摘要结束。
2. 若绿，可做绿灯维护（有则做，无则安静结束）：
   - `pytest server/tests -q`（回归）
   - 版本号三处是否一致（`VERSION` / badge / package）——不一致只修对齐，不擅自 bump。
   - 仓内是否又出现旧栈指引（Hub :7777 / Board :7775 / sidecar / OpenCode 主线写码 / 6+1 列 jsonl / 能力包）→ 标史或改指 `CURSOR.md`（绿灯清理）。
   - HP 记忆若捞到 Hub 时期「现状」→ 以 `/codex/topics/ccc/current-state-v070` 为准。
3. 不要对 CCC 投业务 epic；不改生产配置（2017 `server/config/config.env` 由部署流程管理）。
4. **禁止**再调用已退役的 `scripts/ccc-authority-patrol.py`。

## 对老板可见输出

- 绿：一句话「巡查绿，无事」。
- 红：一句话复述告警人话标题 +「已通知，等拍板」。
