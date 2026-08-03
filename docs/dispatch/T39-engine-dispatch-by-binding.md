# 任务卡 T39 · Engine 派发按卡头执行体绑定优先（M4 观察项落地）（Trae GLM5.2 执行）

> 关联：INT-120 关闭后新阶段 · M4 主档 `__archive__/decisions/ccc-refactor-M4-移交-2026-08-03.md` §三 观察项
> 依据：T38 插曲——`状态：待分派` 管理卡被 2017 生产 Engine 自动派发（卡头执行体 Trae=手动 GUI，但角色「开发执行体」注册表含 OpenCode CLI 行 → `decide()` 返回 AUTO → 错误拉起并打回）
> 执行体：Trae（GLM5.2）· 验收：Codex（严格）· 状态：待分派 · 日期：2026-08-03

## 目标

Engine 派发决策以「卡头执行体绑定」为优先：卡指定手动 GUI 执行体（如 Trae）→ 一律挂起等人（MANUAL），不再因角色含 CLI 行而自动拉起；卡指定 CLI 执行体 → AUTO；无执行体或绑定未命中 → 回退现有角色决策。

## 红线（先看）

1. 只改 server/engine/（task.py、dispatch.py、store.py、main.py）+ server/config/executors.example.json 备注 + server/tests/ + server/engine/README.md；**不碰 2017 运行面**（本卡 M1 实现 + 单测）。
2. **回退兼容**：无执行体 / 绑定未命中时必须保持现有 role-based 行为，不得破坏 AUTO 决策（T32 已验收行为不回归）。
3. 状态机不变（契约 §2）；无新第三方依赖；零硬编码。
4. 回写前必须 push 成功并在回写区附证据（P2-4 纪律）。
5. 2017 部署（pull + engine 重启 + 一张 Trae 卡验证挂起）由 Codex 验收放行后执行。

## 范围

server/engine/task.py（Work.executor 字段）、server/engine/dispatch.py（decide_work 绑定优先决策）、server/engine/store.py（FileBoardStore 填充 executor）、server/engine/main.py（run_once 改用 decide_work）、server/config/executors.example.json（Trae 行备注口径）、server/tests/（新增用例）、server/engine/README.md。

## 步骤

1. task.py：`Work` 增加 `executor: str = ""` 字段（卡头「执行体」名，去括号后，如 Trae / OpenCode / Claude Code / Codex）。
2. dispatch.py：新增 `decide_work(work, registry)`：
   - 有 `work.executor` 时按 binding 找注册表行：可后台 CLI → AUTO；手动 GUI → MANUAL；分类「—」（管理/验收席）→ NONE；未命中 → 回退 `decide(work.role, registry)`。
   - 无 executor → 回退 `decide(work.role, registry)`（现行为不变）。
   - `decide()` 保持原语义（兼容既有测试/调用）。
3. store.py：`_parse_card_to_work` 填充 executor（复用已解析的 executor_name）。
4. main.py：run_once 决策改用 `decide_work`（MANUAL 路径保持「挂起等人」语义不变）。
5. 单测（≥6 类）：① 卡头 Trae（手动 GUI）但角色含 OpenCode CLI 行 → MANUAL、无拉起日志；② 卡头 OpenCode → AUTO 真实拉起；③ 卡头 Codex（分类「—」）→ NONE 不派发；④ 无执行体卡 → 回退角色 AUTO；⑤ 未知执行体 → 回退角色决策；⑥ 现有派发/收单/超时用例不回归。
6. 本地端到端演示：echo 注册表 + 手动 GUI 卡 → run_once 后状态=执行中（挂起）且无执行日志；CLI 卡 → 真实拉起收单。
7. README/example 同步（Trae 行备注改「Engine 按绑定识别为手动，挂起等人，不自动拉起」）。
8. 提交 + push（附证据）。

## 验收标准

1. 6 类用例单测全绿；`pytest server/tests -q` 全绿；ruff server/ 零告警。
2. 本地端到端演示：手动 GUI 卡（角色含 CLI 行）→ 执行中（挂起）且无拉起；CLI 卡 → 真实拉起收单。
3. 回退路径与 T32 现状一致（无执行体 / 未知执行体行为不回归）。
4. 三扫描零命中（硬编码/密钥/外脑）；工作树干净；真实提交 + push 证据。
5. 验收通过后 Codex 放行 2017 部署：pull → engine 重启 → 一张 Trae 卡验证「挂起不拉起」。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现要点、6 类用例结果、本地端到端演示记录、pytest/ruff 结果、push 证据。

## 回写区

**执行体**：Trae（GLM5.2）· 日期：
