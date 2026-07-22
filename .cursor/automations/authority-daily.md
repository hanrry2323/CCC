# CCC 平台每日权威巡查 + 绿灯维护（Cursor Automation 说明）

触发：每天一次（建议本地上午）。
仓库：本仓 CCC（platform）。

## 硬原则

1. **未违背权威 → 直接维护，不要问老板。**
2. **违背权威 → 只报警，不擅自改红线。** 人话通知已由 `scripts/ccc-authority-patrol.py` 发出。
3. 经验进 `loop-engineer-authority` / `.cursor/rules` / `hub_voice` / `references/authority-patrol.jsonl`，禁止另堆给人看的 brief。

## 必做步骤

1. 在仓库根执行：
   `python3 scripts/ccc-authority-patrol.py`
   - 退出码 0：绿，继续绿灯维护。
   - 退出码 2：红，停止改权威相关实现；确认 `~/.ccc/alerts/` 最新 L3 文件后人话摘要即可结束（勿长文档）。
2. 若绿，可做绿灯维护（有则做，无则安静结束）：
   - `pytest tests/scripts/test_authority_patrol.py -q`
   - 版本号三处是否一致（`VERSION` / badge / package）——不一致只修对齐，不擅自 bump。
   - 仓内是否又出现「用 Claude Code/Trae/Zed 改平台」现行指引 → 标史或删（这是绿灯清理，不算改红线）。
3. 不要启用 invent，不要对 CCC orch 投业务 epic，不要改 `~/.ccc/control.json` 降控制面。

## 对老板可见输出

- 绿：一句话「巡查绿，无事」。
- 红：一句话复述告警人话标题 +「已通知，等拍板」。
