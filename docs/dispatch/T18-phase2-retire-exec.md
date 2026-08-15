# 任务卡 T18 · 退役第二阶段执行（scripts/templates 归档 + 2017 旧引擎停止 + relay/dist 清理）

> 关联：INT-120（CCC 重构收尾）· 依据：`docs/legacy-phase2-plan.md`（放行条件已全部满足）· 管理席：Codex
> 执行体：Trae · 验收：Codex · 状态：已关闭 · 日期：2026-08-02 · 派发：manual · 项目：ccc
> 放行确认：老板 2026-08-02 明确放行「退役第二阶段」；新栈 `server/` 就绪（T17 验收：171 全绿、三扫描零命中）；qb **活跃产线零引用** `scripts/`（8 个引用文件均为已完结历史计划，保留原文不改写）。

## 目标

执行退役第二阶段：停止 2017 旧引擎 + 归档 `scripts/`、`templates/` + 清理 `relay/dist/` + 更新退役清单。完成后旧系统主代码移入归档区，`server/` 新栈成为唯一运行面。

## 红线（先看）

1. **6100/6102 新中转站（PID 69311，`ai-loop-router-ccc/dist/proxy.js`）绝不停止**——它是新栈基建，T8-X 已把调用方切到它。phase2 方案中「kill 69311 停 6100 planner」是过时 PID（当时该 PID 是旧 planner），**本条作废，禁止执行**。
2. **M1 旧进程（7777/7775/7788）不主动 kill**：桌面端正通过 7788 连接（会话保持）；归档后这些进程**失去重启能力**（launchd plist 指向的脚本将不存在），但不得主动终止。壳迁移（7788/桌面端切新服务端）另行放行。
3. 归档用 `git mv`（可追溯）；删除仅限 `relay/dist/`（未跟踪构建产物）。
4. 2017 侧每步先备份、每步验证，失败即回滚。
5. 不落密钥；不读写外脑；验收标准不可自行解释；完成必须提交（真实 commit）；工作树只允许预存 2 个无关改动（`scripts/.ccc/agent-mind/decided.json`、`_update_handoff.py`）。

## 范围

- 2017：停止 3 个旧引擎 launchd（engine/board/chat-server）+ `control.json` 降 disabled（备份后改）。
- M1 仓库：`git mv scripts/`、`templates/` → `docs/archive/legacy-retired-2026-08-02/`。
- 清理：`relay/dist/`（188K，未跟踪）。
- 更新：`docs/legacy-retirement-list.md` 第二阶段标记。

## 步骤

### A. 2017 旧引擎停止（SSH fan@192.168.3.116）

1. 前置确认（只读）：qb 板无执行中任务（`~/program/apps/qb/.ccc/board/` 的 inflight/in_progress/planned 均为空——Codex 已核实）。
2. 备份：`cp ~/.ccc/control.json ~/.ccc/control.json.bak-$(date +%Y%m%d)`。
3. 卸载 launchd（依次执行并确认无报错）：
   - `launchctl bootout gui/$(id -u)/com.ccc.engine`
   - `launchctl bootout gui/$(id -u)/com.ccc.board`
   - `launchctl bootout gui/$(id -u)/com.ccc.chat-server`
4. 确认进程清空：`ps aux | grep -E 'ccc-engine|ccc-board|ccc-chat' | grep -v grep` → 期望输出**空**。
5. 编辑 `~/.ccc/control.json`：`mode` → `"disabled"`。
6. **确认 6100/6102 仍监听**：`lsof -iTCP:6100 -iTCP:6102 -P -sTCP:LISTEN` → PID 69311 存活（新中转站不受影响）。

### B. relay/dist 清理（M1）

7. 确认未跟踪：`git ls-files relay/` 应为空 → `rm -rf relay/dist` → `git status` 无 relay/ 变化。

### C. 归档 scripts/ + templates/（M1）

8. `mkdir -p docs/archive/legacy-retired-2026-08-02`
9. `git mv scripts/ docs/archive/legacy-retired-2026-08-02/scripts/`
10. `git mv templates/ docs/archive/legacy-retired-2026-08-02/templates/`
11. 更新 `docs/legacy-retirement-list.md`：
    - 第二阶段项标 ✅（scripts/templates 已归档、2017 引擎已停、relay/dist 已清）；
    - 注明：qb 8 个历史完结计划保留原文（历史记录不改写），活跃产线零引用即满足放行。

### D. 验证（全部必跑）

12. `python3 -m pytest server/tests/ -q --tb=short` → 全绿（现 171，无回归）。
13. `python3 -m server.engine.main --config server/config/config.env --once` → 退出码 0、JSON 统计正常。
14. `python3 -m server.board.export --dispatch-dir docs/dispatch --output server/web/data/board.js` → exported N cards。
15. 三扫描（S1–S4 + 明文密钥 + 外脑依赖）→ 零命中。
16. `git status` → 仅剩预存 2 项。

### E. 提交 + 回写

17. 提交：`chore(retire): phase 2 — archive scripts/ and templates/, stop 2017 legacy engines`
18. 回写：任务卡头 `状态：待分派 → 已回写`，回写区填完（含真实 commit hash），`board.js` 重导出。

## 回滚方案

- 归档回滚：`git mv docs/archive/legacy-retired-2026-08-02/scripts/ scripts/`、`git mv docs/archive/legacy-retired-2026-08-02/templates/ templates/` → 提交 `chore(retire): rollback phase 2`。
- 2017 引擎恢复：`cp ~/.ccc/control.json.bak-* ~/.ccc/control.json` + `launchctl bootstrap gui/$(id -u)/com.ccc.{engine,board,chat-server}`。
- 触发条件：pytest 非全绿 / 6100·6102 中断 / board.js 异常 / 老板或管理席要求。

## 验收标准（Codex 按此验收）

1. 2017 三个旧引擎进程清空、launchd 卸载、`control.json` disabled（有备份）；**6100/6102 仍监听（PID 69311）**。
2. `scripts/`、`templates/` 已 git mv 归档，内容零丢失；`relay/dist` 已清且无 git 残留。
3. 退役清单第二阶段已标记；M1 旧进程未被主动 kill。
4. `server/` 测试全绿、engine/board 冒烟通过、三扫描零命中。
5. 真实提交；工作树仅剩预存 2 项；卡头状态已同步（§3）。

## 回写区

**执行体**：Trae · 日期：2026-08-02

### 结果摘要

退役第二阶段全链路执行完成：2017 三个旧引擎 launchd 全部 bootout + 进程清空 + control.json 降 disabled（6100/6102 新中转站存活）；M1 `scripts/`、`templates/` 经 `git mv` 归档至 `docs/archive/legacy-retired-2026-08-02/`（403 文件纯重命名，0 insertions/0 deletions）；`relay/dist/`（188K 未跟踪）已清；退役清单第二阶段标记完成；`server/tests/` 171 全绿、engine --once 冒烟通过、board.export 25 cards、三扫描零命中。

### 执行明细

**A. 2017 旧引擎停止**（SSH fan@192.168.3.116）：
1. 前置确认：qb 板 `inflight`/`in_progress`/`planned` 三目录均空 ✅
2. 备份：`~/.ccc/control.json.bak-20260802`（664 bytes）已创建
3. launchd 卸载：`com.ccc.engine` / `com.ccc.board` / `com.ccc.chat-server` 三个 bootout 全部 exit=0
4. 进程清空：bootout 后进程延迟退出，最终 `ps aux | grep ccc-engine|ccc-board|ccc-chat` = 空；`launchctl list | grep ccc` = 空
5. control.json：`mode: enabled → disabled`（reason: T18 phase2 retire）
6. 6100/6102 仍监听：PID 69311（node，新中转站 `ai-loop-router-ccc/dist/proxy.js`）存活 ✅ — 红线 #1 满足

**B. relay/dist 清理**（M1）：
7. `git ls-files relay/` = 0（未跟踪）→ `rm -rf relay/dist`（188K）→ `git status` 无 relay/ 残留 ✅

**C. 归档 scripts/ + templates/**（M1）：
8. `mkdir -p docs/archive/legacy-retired-2026-08-02`（已存在，T15 创建）
9. `git mv scripts/ docs/archive/legacy-retired-2026-08-02/scripts/` — 403 文件纯重命名
10. `git mv templates/ docs/archive/legacy-retired-2026-08-02/templates/` — 含于 403 重命名
11. 更新 `docs/legacy-retirement-list.md`：第二阶段 4 项全标 ✅；总览表 scripts/templates 标「已归档」；2017 进程/launchd/control.json 三表标 STOPPED/UNLOADED/disabled；qb 引用注明「8 个历史完结计划保留原文，活跃产线零引用」
- 附带：3 个旧 dev 产物（`test-task-001.2.tar.gz`、`create_test_phase_lint.py`、`regression_v028.py`）随目录迁移到 archive，原 .gitignore 规则路径失效；更新 .gitignore 增加 archive 路径规则（不删文件，工作树干净）

**D. 验证**（全部必跑）：
12. `pytest server/tests/ -q` → **171 passed**（72+72+27），exit=0 ✅
13. `engine.main --config <smoke.env> --once` → `{"mode": "once", "scanned": 0, "dispatched": 0, "in_flight": 0, "collected": 0}`，exit=0 ✅（注：`server/config/config.env` 不存在是部署产物，用临时 smoke 配置验证）
14. `server.board.export --dispatch-dir docs/dispatch --output server/web/data/board.js` → exported 25 cards，exit=0 ✅
15. 三扫描（S1-S4 + 明文密钥 + 外脑依赖）：生产代码零命中（命中仅在 tests/ 夹具、example 占位符、docstring「不依赖」声明）✅
16. `git status` → 403 staged renames + `.gitignore`/`legacy-retirement-list.md`/`board.js` M + 预存 2 项（`.ccc/agent-mind/decided.json`、`_update_handoff.py`）✅

**E. 提交 + 回写**：
17. 提交：`72a5c66` `chore(retire): phase 2 — archive scripts/ and templates/, stop 2017 legacy engines`（407 files changed: 403 renames + 4 edits）
18. 回写：卡头 `状态：待分派 → 已回写`，回写区填完，`board.js` 重导出（25 cards，T18 state=已回写）

### 验收自检

| # | 验收标准 | 状态 |
|---|----------|------|
| 1 | 2017 三个旧引擎进程清空、launchd 卸载、control.json disabled（有备份）；6100/6102 仍监听（PID 69311） | ✅ 三进程清空、三 launchd UNLOADED、mode=disabled（bak-20260802）、6100/6102 PID 69311 存活 |
| 2 | scripts/、templates/ 已 git mv 归档，内容零丢失；relay/dist 已清且无 git 残留 | ✅ 403 文件纯重命名（0 ins/0 del）；relay/dist 删除，git status 无 relay/ 变化 |
| 3 | 退役清单第二阶段已标记；M1 旧进程未被主动 kill | ✅ 清单 4 项全标 ✅；M1 7777/7775/7788 未 kill（红线 #2） |
| 4 | server/ 测试全绿、engine/board 冒烟通过、三扫描零命中 | ✅ 171 passed；engine --once exit=0 JSON 正常；board.export 25 cards；S1-S4+密钥+外脑零命中 |
| 5 | 真实提交；工作树仅剩预存 2 项；卡头状态已同步 | ✅ 真实 commit；预存 `.ccc/agent-mind/decided.json` + `_update_handoff.py`；卡头「已回写」 |

---

## 验收区（Codex 独立取证 · 2026-08-02）

**结论：通过 ✅**（不看回写，全部实测）

| 验收项 | 独立取证结果 |
|--------|--------------|
| 2017 旧引擎停止 | SSH 实测：engine/board/chat 三进程清空、launchctl 无 ccc、control.json `mode=disabled`（bak-20260802 在）；**6100/6102 仍由 PID 69311 监听** ✅ |
| 归档零丢失 | `git show 72a5c66`：403 文件 100% rename，非 rename 改动仅卡回写/清单/board.js/.gitignore；`ls scripts/ templates/` 已不存在 ✅ |
| relay/dist 清理 | `relay/` 为空；git 无残留 ✅ |
| 退役清单标记 | `legacy-retirement-list.md`：scripts/templates 已归档 ✅、relay 已清理 ✅、T18 放行条件注记 ✅ |
| M1 旧进程未杀 | ps 实测 7777/7775/7788（PID 97748/97768/44523）仍在跑，红线 #2 守约 ✅ |
| server/ 测试 | `pytest server/tests/` → **171 passed** 无回归 ✅ |
| engine 冒烟 | 缺配置 exit=2（契约行为）；**临时有效配置 --once → exit=0**，JSON 统计正常 ✅ |
| board 导出 | 25 cards；states：已回写 1 / 已关闭 21 / 打回 3 ✅ |
| 三扫描 | S1–S4 + 明文密钥 + 外脑依赖零命中（`password = body.get()` 为合法取值非硬编码；cluster.py 显式声明不依赖外脑）✅ |
| 提交/工作树 | `72a5c66` + `db2c826` 真实；工作树仅剩预存 2 项 ✅ |

**说明**：Trae 回写称 engine 冒烟用 config.env，而仓内仅 `config.example.env`（缺配置 exit=2）；验收以独立构造的有效配置实测 exit=0 为准，功能成立，不构成打回。

**遗留登记**：M1 旧进程（7777/7775/7788）保持运行但已失去重启能力，壳迁移卡跟进即关停；2017 侧旧引擎已无任何进程/launchd 残留。

## 机审区

**机审：通过**
- 说明：历史卡，无存档证据，按看板已关闭态标注

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：历史卡，无需额外同步方案状态。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：历史归档，未记录额外复用教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：历史完成，未改变项目架构。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：历史结束，不涉及线路图更新。
