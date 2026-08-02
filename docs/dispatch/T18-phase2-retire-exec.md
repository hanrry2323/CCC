# 任务卡 T18 · 退役第二阶段执行（scripts/templates 归档 + 2017 旧引擎停止 + relay/dist 清理）

> 关联：INT-120（CCC 重构收尾）· 依据：`docs/legacy-phase2-plan.md`（放行条件已全部满足）· 管理席：Codex
> 执行体：Trae · 验收：Codex · 状态：待分派 · 日期：2026-08-02
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

（执行后填写）

### 执行明细

（执行后填写：步骤 A–E 各步结果）

### 验收自检

（执行后填写：对照验收标准逐条勾选）
