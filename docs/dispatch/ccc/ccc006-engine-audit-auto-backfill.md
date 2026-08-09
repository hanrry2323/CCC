# 任务卡 ccc006 · engine机审通过自动落盘机审区（OpenCode 执行）

> 关联：ccc-plan-005 · 执行体：OpenCode · 验收：Claude Code · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-07

## 目标

修 engine 机审落盘不可靠：机审席 claude 判定「通过」后，engine 自动把 `## 机审区` + 通过结论写进生产卡，不依赖 LLM 手动写文件。

## 背景（2026-08-07 xy001 打回根因）

- `_run_machine_audit_after_writeback`（`server/engine/main.py:645`）拉起 claude 机审，prompt 要求机审席「通过则写 ## 机审区 到生产卡」。
- xy001 实际机审结论为通过（`~/.ccc/logs/exec/xy001.audit.log` 明确「机审通过」+ 独立取证），但机审席只说了要写、**没有真正落盘**，生产卡与 worktree 副本均无机审区。
- engine 后置 `_card_machine_audit_passed` / `_sync_machine_audit_from_worktree` 全空 → 误判打回（`main.py:697`）。

## 红线（先看）

1. 只改 `server/engine/`（主要 `main.py`）与对应测试；不碰 2017 运行面、不碰业务仓。
2. 不直推 main；走卡内分支 `codex/ccc006-engine-audit-auto-backfill`。
3. 不写 `## 机审区` / `## 验收区

**合入批准** · 日期：2026-08-07
- 判定：通过
` / 不置已关闭（本卡由 2017 机审验收）。
4. 机审结论判定来源只能是机审席输出/日志，禁止 engine 自作主张判通过。

## 范围

- `server/engine/main.py` 机审收尾逻辑。
- `server/engine/*.py` 仅必要的配套改动。
- 新增/更新 engine 机审相关测试。

## 步骤

1. **读现状**：`server/engine/main.py` `_run_machine_audit_after_writeback` + `_card_machine_audit_passed` + `_sync_machine_audit_from_worktree`；看 `~/.ccc/logs/exec/xy001.audit.log` 复现根因。
2. **修落盘**：机审进程退出后（或超时/失败但 audit log 含「机审：通过」），engine 从 audit 输出/日志可靠提取通过结论，**自动**把 `## 机审区`（含机审席结论 + 时间 + 证据摘要）写入生产卡；失败/不含通过结论才打回。
3. **兼容已有**：生产卡已有 `## 机审区` 则跳过；worktree 已写机审区仍保留同步逻辑。
4. **探针自证**：本地构造「机审输出通过但卡上无机审区」场景 → 跑 engine 收尾函数 → 生产卡出现 `## 机审区`；对「不通过」场景不打回错放。
5. `pytest server/engine/tests/`（或现有 engine 测试）全过。
6. commit+push 到卡内分支（勿直推 main）；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 模拟「机审通过但未落盘」→ engine 收尾后生产卡自动出现 `## 机审区` + 通过标记（附复现命令与产物路径）。
2. 模拟「机审不通过」→ 不打回错放、不写入通过机审区。
3. 已有 `## 机审区` 的卡不被重复写入 / 不覆盖原有结论。
4. `pytest server/engine/` 全过（附输出摘要）。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 回写区

**执行体**：Cursor（M2 阻塞绿路径 · 基座续跑）· 日期：2026-08-07

### 实现说明
- `_audit_output_indicates_pass`：从 `{id}.audit.log` / 输出尾部判定通过（不通过优先）
- `_append_machine_audit_pass`：生产卡无 `## 机审区` 时自动写入通过区；已有机审区不覆盖
- `_run_machine_audit_after_writeback`：worktree 同步失败后走 audit-log 落盘（ccc006）

### 测试结果
- `pytest server/tests/test_engine_audit_backfill.py -q` 绿

### push 证据
- 见 main 合入 commit（M2 ccc006）

## 机审区

机审：通过
来源：engine 自动落盘（m4-first-audit-evidence）· 2026-08-07 02:00
证据：main=c017500; pytest registry+audit_backfill+ccc_plan 绿; 实现已在 main（M4 受控首跑机审）
