# 批次 2 执行指令 · CCC 系统化升级（A 闭环：合入自动收口 + sidecar 同步 + 修 P2）

> 来源：qx-map/__archive__/decisions/ccc-系统化升级方案-2026-08-08.md（commit d4f463e）· 批次 2「A 闭环」
> 角色：OpenCode CCC 窗口（出指令 Agent）发出 · 你（Claude Code）是执行 Agent，**只执行本指令，不自行扩方向**
> 工作目录：/Users/apple/program/CCC（main 分支，批次 1 已完成 eac78da4）

## 一、目标（一句话）

让「合入批准」自动收口：卡关闭后 **runtime sidecar 与磁盘真值一致**（P2 撕裂消除）、无僵尸机审、approve-merge 一键化（含 sidecar 同步 + 已合入分支清理）。

## 二、基线事实（先核对再动手）

- 批次 1 已修 P6（`machine_audit_passed_text` 结构化结论判定）——本批**不得回退**
- P2 现场已复现：
  - 磁盘真值：hp009/xy024/xy026=打回、mx026=待分派、已关闭 156
  - runtime sidecar `/Users/fan/.ccc/logs/exec/state/cards.jsonl`：hp009/xy024/xy026/mx026 残留「已回写」，mx024/hp016（已关闭）也残留「已回写」
  - 看板合成被 sidecar 覆盖 → 显示「已回写 4」而非真值
- 涉及代码：
  - `server/engine/store.py:146-152`：`raw_state = str(rt["state"])` 无脑覆盖磁盘卡状态
  - `server/web/server.py:1049-1053`（`_compose_board_items`）：非已关闭卡被 runtime 覆盖
  - `scripts/approve-merge.sh`：合入关闭后**不同步 sidecar**、**不清理已合入分支**
  - `server/engine/runtime_state.py`：read/write_card_state（append-only last-wins）

## 三、任务（严格按序执行）

### 任务 1：修 P2 撕裂（核心）

原则：**磁盘卡文件是唯一真值源；sidecar 只承载「执行/机审进行时」的流程态**（待分派→执行中→已回写→打回），一旦磁盘状态为「已关闭/打回/待分派」，sidecar 对应条目**必须失效**（视为不存在）。

1. `server/engine/store.py`（Engine 派发队列）：
   - 读状态时，若磁盘卡状态是「已关闭」「打回」「待分派」，**忽略 sidecar 状态**（不用 rt 覆盖 raw_state）
   - 即：sidecar 状态仅在磁盘为「已回写」/「执行中」时参与判定
2. `server/web/server.py` `_compose_board_items`（看板合成）：
   - 对齐同一规则：磁盘「已关闭」→ 显示已关闭（现有已做）；磁盘「打回/待分派」→ 也用磁盘状态（**修掉 `rt["state"]` 覆盖**）
   - 修改后：看板对 hp009/xy024/xy026 显示「打回」，mx026 显示「待分派」
3. `server/engine/runtime_state.py`：新增 `clear_card_state(log_dir, card_id)`（追加一条 state=None 哨兵或删除条目？**注意 append-only 语义**——采用追加「失效」记录：`{"id":..., "ts":..., "state": null}`，read 时 last-wins 遇 null 视为无状态），并让 `read_card_state` 支持 null 失效语义（保持向后兼容，无 null 时行为不变）。

### 任务 2：approve-merge 一键化（合入自动收口）

`scripts/approve-merge.sh` 的 `approve_one()` 在「close_card 写验收区+已关闭」之后、push 之前，追加：

1. **sidecar 同步**：调用 `server.engine.runtime_state.clear_card_state`（或等价方式）清除该卡的 sidecar 流程态（已关闭卡不再被 sidecar 覆盖）
2. **分支清理**：已 ff 合入 main 的分支删除已有；补：close-only 场景若卡已关闭且分支已合入/无独立 diff，也清理本地+远端分支（若分支分叉保留，加日志）
3. 输出「收口完成：card=<id> 已关闭 + sidecar 已同步」日志

### 任务 3：存量 sidecar 收敛（一次性清理）

1. 写一次性收敛：对**所有** `cards.jsonl` 中「磁盘已关闭/打回/待分派」但 sidecar 残留流程态的卡，追加失效记录（用任务 1 的 clear 机制），使 sidecar 与磁盘一致
2. 收敛后核验：`read_card_state` 输出中 mx024/hp016 等已关闭卡**不再有**「已回写」残留
3. 该收敛脚本放 `scripts/` 下（如 `scripts/sync-runtime-state.py`），可重复执行（幂等）

### 任务 4：单测补齐

1. `server/tests/`（找现有 runtime_state / store 测试文件，或新建）补：
   - `read_card_state` 遇 null 失效记录 → 该卡无状态
   - `store` 派发队列：磁盘已关闭+sidecar已回写 → 忽略 sidecar
   - `_compose_board_items`（若可测）：磁盘打回+sidecar已回写 → 显示打回
2. 跑 `pytest server/tests/` 全绿（**注意**：test_t53_console_roadmap.py 3 个失败为批次 1 已确认的存量问题，与本批无关，允许除外并注明）

## 四、红线（违反即停）

1. **禁止触碰**：`server/config/`；2017 任何 worktree/运行面；本批不改任何 `docs/dispatch/` 卡文件（问题卡处置已完成）
2. **禁止** commit/push 含密钥文件；禁 `git add -A`
3. **禁止** 回退批次 1 的 P6 修改（`machine_audit_passed_text` 新语义必须保留）
4. sidecar 修改必须保持 append-only 兼容（read 端 last-wins），不得破坏已有事件流
5. 测试不过/发现歧义 → 停手记录，不猜着改

## 五、验证（写完必须跑）

1. `pytest server/tests/` 全绿（存量 3 失败除外）
2. 本地模拟：构造「磁盘已关闭 + sidecar 已回写」→ 确认 read_card_state / store 队列 / compose 三者均显示磁盘真值
3. `scripts/sync-runtime-state.py` 幂等跑两次，输出一致
4. `git status` 干净

## 六、交付（执行完输出）

1. 改动文件清单 + diff 摘要（含行数）
2. 单测结果（跑通输出）
3. sidecar 收敛前后对照（4 张问题卡 + mx024/hp016 等已关闭卡）
4. approve-merge 收口改动说明
5. push commit hash
6. 未决项 / 遗留（如有）

## 七、验收条件（OpenCode 窗口复核用）

1. 磁盘「打回/待分派/已关闭」卡不再被 sidecar 覆盖（store + compose 双路径一致）
2. `clear_card_state` / null 失效语义生效，read 端 last-wins 兼容
3. approve-merge 合入后 sidecar 无该卡流程态残留
4. 存量收敛幂等（跑两次结果一致）
5. 单测全绿（存量 3 失败除外）；push 后 origin/main 含改动；工作区干净
6. 不碰 2017 / config / 卡文件
