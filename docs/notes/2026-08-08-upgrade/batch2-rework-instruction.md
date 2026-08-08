# 批次 2 返工指令 · 修正 sidecar 覆盖规则（验收不通过）

> 执行 Agent（Claude Code）：批次 2 已完成（commit 62dd124f），但 OpenCode 验收席发现**关键语义缺陷**，按本指令返工修正后重新提交。
> 工作目录：/Users/apple/program/CCC（main，已含 62dd124f）

## 一、验收结论（为什么返工）

批次 2 的覆盖规则把「磁盘 待分派 → 忽略 sidecar」也写进去了，导致：

1. **执行中/已回写卡从队列消失**：引擎运行模式「卡文件只做 main 镜像（永不写脏），流程态全在 sidecar」——执行中的卡磁盘状态永远是「待分派」，sidecar 记「执行中」。规则「磁盘待分派 → 忽略 sidecar」后，`list_work(state=RUNNING)` 查不到执行中卡，`/cards?state=执行中` 空，**派发/机审/看板全链路丢卡**。
2. 失败测试（均为**真语义冲突**，非存量）：
   - `server/tests/test_engine_main.py::TestFileBoardStore::test_file_store_runtime_mode`：磁盘待分派 + sidecar 执行中 → `list_work(RUNNING)` 应返回，现为空
   - `server/tests/test_http_api.py::TestCardsComposite::test_cards_reflects_runtime_state`：磁盘待分派 + sidecar 执行中 → `/cards?state=执行中` 应显示，现为空

## 二、正确语义（验收席定）

| 磁盘状态 | sidecar 覆盖？ | 理由 |
|---------|--------------|------|
| 已关闭 | ❌ 不覆盖 | 真值优先（批次 2 原意） |
| 打回 | ❌ 不覆盖 | 修 P2 目标（hp009 等不再被「已回写」覆盖） |
| 待分派 | ✅ 允许覆盖 | 引擎执行流：执行中卡磁盘永远待分派，状态在 sidecar |
| 已回写 | ✅ 允许覆盖 | 机审/重审流程态在 sidecar |
| 执行中 | ✅ 允许覆盖 | 同上 |

**核心原则**：sidecar 只在「磁盘已关闭/打回」时失效；「待分派」是 main 镜像的默认态，**必须允许 sidecar 升级为执行中/已回写**。

## 三、任务

### 任务 1：修正 store.py 覆盖规则
`server/engine/store.py` `list_work`：
- 现有：`if base_state(raw_state) in ("已回写", "执行中") and rt.get("state"): raw_state = str(rt["state"])`
- 改为：`if base_state(raw_state) in ("待分派", "已回写", "执行中") and rt.get("state"): raw_state = str(rt["state"])`
- （即去掉「待分派」的豁免——它必须参与 sidecar 升级）

### 任务 2：修正 server.py compose 覆盖规则
`server/web/server.py` `_compose_board_items`：
- 现有：`if base_state(item.state) in ("已关闭", "打回", "待分派"): new_state = item.state`
- 改为：`if base_state(item.state) in ("已关闭", "打回"): new_state = item.state`
- （待分派卡同样允许被 sidecar 升级显示为执行中/已回写）

### 任务 3：回归验证
1. 两个失败测试恢复通过：
   - `test_file_store_runtime_mode`（磁盘待分派 + sidecar 执行中 → list_work(RUNNING) 命中）
   - `test_cards_reflects_runtime_state`（/cards?state=执行中 命中待分派卡）
2. 新增/保留防回归断言（在 test_runtime_state.py 或对应测试）：
   - 磁盘「打回」+ sidecar「已回写」→ list_work / compose 显示「打回」（P2 场景，必须保持）
   - 磁盘「已关闭」+ sidecar「已回写」→ 显示「已关闭」
   - 磁盘「待分派」+ sidecar「执行中」→ 显示「执行中」（本返工核心）
3. `pytest server/tests/` 全绿（t53_console_roadmap 3 个存量失败除外）

### 任务 4：sync-runtime-state.py 核验
- 收敛脚本「磁盘 待分派/已关闭/打回 + sidecar 活跃 → 清」——待分派卡被清可接受（待分派卡本不该有已回写残留），**但确认**：它不清「磁盘 已回写/执行中」的卡（那是引擎进行中的有效状态）。若误清范围包含已回写/执行中，同步修正。

## 四、红线

1. 不碰 `server/config/`、2017、`docs/dispatch/` 卡文件
2. 不回退批次 1 的 P6、批次 2 的 clear_card_state/approve-merge 收口
3. 禁 `git add -A`；禁含密钥提交

## 五、交付

1. 修正 diff（store.py + server.py + 测试）
2. `pytest server/tests/` 输出（确认 2 个失败测试恢复 + 全绿）
3. 防回归断言清单
4. push commit hash

## 六、验收条件（OpenCode 复核）

1. 磁盘「打回/已关闭」→ 真值优先（P2 不复发）
2. 磁盘「待分派」+ sidecar「执行中/已回写」→ 正确显示（执行链路不丢卡）
3. 两个失败测试恢复 + 防回归断言全绿
4. sync-runtime-state 幂等且不清有效执行态
5. 工作区干净、push 成功
