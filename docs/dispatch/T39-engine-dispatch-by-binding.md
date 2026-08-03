# 任务卡 T39 · Engine 派发按卡头执行体绑定优先（M4 观察项落地）（Trae GLM5.2 执行）

> 关联：INT-120 关闭后新阶段 · M4 主档 `__archive__/decisions/ccc-refactor-M4-移交-2026-08-03.md` §三 观察项
> 依据：T38 插曲——`状态：待分派` 管理卡被 2017 生产 Engine 自动派发（卡头执行体 Trae=手动 GUI，但角色「开发执行体」注册表含 OpenCode CLI 行 → `decide()` 返回 AUTO → 错误拉起并打回）
> 执行体：Trae（GLM5.2）· 验收：Codex（严格）· 状态：已关闭 · 日期：2026-08-03

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

**执行体**：Trae（GLM5.2）· 日期：2026-08-03

### 实现要点

1. `server/engine/task.py`：`Work` dataclass 新增 `executor: str = ""` 字段（卡头「执行体」绑定名，去括号后；空串表示卡未指定，回退 role-based 决策）。
2. `server/engine/dispatch.py`：
   - `ExecutorRegistry` 新增 `rows_for_binding(tool_name)`（按 binding 名返回全部注册行）+ `cli_entry_for_binding(tool_name)`（首个 CLI 行）。
   - 新增 `decide_work(work, registry)`：有 `work.executor` 时按 binding 找注册表行 → CLI→AUTO / 手动 GUI→MANUAL / 「—」→NONE / 未命中→回退 `decide(role)`；无 executor → 回退 `decide(role)`。`decide()` 原语义不变（兼容既有调用）。
3. `server/engine/store.py`：`FileBoardStore._parse_card_to_work` 填充 `work.executor`（复用已解析的 `executor_name`；`UNKNOWN` → 空串以触发回退）。
4. `server/engine/main.py`：`run_once` 决策改用 `decide_work(work, registry)`；MANUAL/NONE 日志补 `executor=` 字段；AUTO 路径不变（entry 仍经 `cli_entry_for_role`，因 role 已由 store 从 executor 反查）。
5. `server/config/executors.example.json`：Trae 行备注改为「Engine 按卡头绑定识别为手动，挂起等人，不自动拉起（T39）」。
6. `server/engine/README.md`：派发管道图/约定/实现表同步 T39 绑定优先。

### 6 类单测结果（server/tests/test_engine_dispatch.py::TestDecideWork + test_engine_main.py::TestRunOnceDispatchByBinding）

| # | 用例 | 期望 | 结果 |
|---|------|------|------|
| ① | 卡头 Trae（手动 GUI）但角色含 OpenCode CLI 行 | MANUAL、无拉起日志 | PASS（`test_trae_manual_gui_even_if_role_has_cli` + `test_trae_card_manual_even_if_role_has_cli` 端到端：dispatched=1/collected=0/in_flight=1，无 T90.log）|
| ② | 卡头 OpenCode（CLI） | AUTO 真实拉起收单 | PASS（`test_opencode_binding_auto` + `test_opencode_card_auto_real_dispatch` 端到端：collected=1，T91.log 存在）|
| ③ | 卡头 Codex（分类「—」） | NONE 不派发 | PASS（`test_codex_staff_binding_none` + `test_codex_card_none_not_dispatched` 端到端：dispatched=0，留待分派）|
| ④ | 无 executor（空串） | 回退角色 AUTO | PASS（`test_no_executor_falls_back_to_role_auto` + `test_no_executor_unknown_role_none`）|
| ⑤ | 未知 executor（不在注册表） | 回退角色决策 | PASS（`test_unknown_executor_falls_back_to_role`：role=开发执行体→AUTO / role=管理席→NONE / role=空→NONE）|
| ⑥ | 现有派发/收单/超时用例不回归 | 全绿 | PASS（`test_decide_work_consistent_with_decide_when_no_executor` 五角色一致 + 全套 306 passed）|

补充：`TestFileBoardStore` 新增 `test_list_work_fills_executor_empty_for_unknown`（未知执行体 → role 空、executor 保留卡头名供回退）+ 原 `test_list_work_reads_card_headers` 补 `w.executor == "demo"` 断言。

### 本地端到端演示（/tmp/t39-demo，已清理）

注册表：开发执行体含 Trae(手动 GUI) + OpenCode(CLI) + 管理席 Codex(—)。两张卡同放 `dispatch/`：

- T90 `执行体：Trae` → `挂起等人接单: work=T90 role=开发执行体 executor=Trae` → 状态：执行中（挂起），**无 T90.log**。
- T91 `执行体：OpenCode` → `拉起执行体: work=T91 cmd=['echo','work=T91',...]` → 状态：已回写，**T91.log 存在**（真实收单）。

`run_once` 统计：`{"scanned":2, "dispatched":2, "in_flight":1, "collected":1, "timed_out":0}`。

### pytest / ruff 结果

- `pytest server/tests/ --tb=short` → **306 passed in 4.59s**（含 11 个 T39 新增用例：7 决策 + 3 端到端 + 1 store 填充）。
- `ruff check server/` → **All checks passed!**（零告警）。
- `python -m py_compile server/engine/{task,dispatch,store,main}.py` → OK。

### 三扫描零命中（仅本次改动 8 文件）

- 硬编码 IP/端口/路径（`192\.168\.|127\.0\.0\.1|:7788|:6100|:6102|/Users/apple`）：零命中。
- 密钥/token 字面量：零命中。
- 外脑引用（`qx-map|hp-kb|hp_kb`）：零命中（`cluster.py:1` 旧注释「不依赖 qx-map」非本次改动，不在范围）。

### push 证据

- commit：`6c185e6 feat(engine): T39 Engine 派发按卡头执行体绑定优先——修复 T38 插曲`（8 files, +286/-22）。
- push：`539cbb7..6c185e6 main -> main`（origin/main = `6c185e652316fff146773de8dff7c82082f3ad38`）。
- 工作树：仅余 `.ccc/agent-mind/decided.json` 预存项（非本次改动）。

### 2017 部署（待 Codex 放行）

红线 #5：本卡 M1 实现 + 单测；2017 部署（pull → engine 重启 → 一张 Trae 卡验证「挂起不拉起」）由 Codex 验收放行后执行。

---

## 验收区（Codex 独立取证 · 严格 · 2026-08-03）

**判定：✅ 通过（含 2017 生产验证）。** T38 插曲根因修复闭环。

### 对照承诺表

| 验收标准 | 实际 | 判定 |
|----------|------|------|
| 1. 6 类用例单测全绿；pytest 全绿；ruff 零告警 | 实测 306 collected 0 失败（含 7 个 dispatch 决策用例 + 4 个 main 端到端用例）；ruff server/ All checks passed | ✅ 做到 |
| 2. 本地端到端：Trae 卡挂起无拉起；CLI 卡真实拉起收单 | 执行体演示记录 + 测试 `test_trae_card_manual_even_if_role_has_cli` / `test_opencode_card_auto_real_dispatch` 覆盖；Codex 抽查断言（Trae+角色含 CLI → MANUAL）真实有效 | ✅ 做到 |
| 3. 回退路径与 T32 现状一致（无执行体/未知执行体不回归） | `decide_work` 无 executor / binding 未命中 → 回退 `decide(role)`；测试含未知执行体回退、无执行体回退、一致性断言 | ✅ 做到 |
| 4. 三扫描零命中；工作树干净；真实提交 + push 证据 | 改动 8 文件无硬编码/密钥/外脑；工作树干净；6c185e6+0a93644 已 push（origin 实测 = 0a93644） | ✅ 做到 |
| 5. 2017 部署验证（Codex 放行后） | Codex 独立执行：2017 pull → engine 重启（PID 89733）→ T99-Trae-test 卡实测：待分派→执行中（挂起）约 75s，exec 日志目录零新增（未拉起）；清理测试卡 + 看板重导出 48 卡 + health ok | ✅ 做到 |

### 备注

- MANUAL 路径语义保持「挂起等人」：Engine 将卡置为执行中并回写卡头，不拉起任何执行体（T39 目标）。
- 生产验证卡为临时 untracked 文件，已移出 `/tmp/T99-Trae-test.md`，看板无残留。
