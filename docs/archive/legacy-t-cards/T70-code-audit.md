# 任务卡 T70 · 全项目代码 bug 检查（Cursor 测试卡 2 · M1 只读审计）

> 关联：ccc-plan-001· 执行体：Cursor（M1 测试接手）· 验收：Codex（独立复核）· 状态：已关闭 · 派发：manual · 项目：ccc · 日期：2026-08-06
> 工作目录：M1 `/Users/apple/program/CCC`；分支 `codex/cursor-t02-code-audit`（从 main 新建）
> 背景交接：`docs/cursor-code-check-handoff.md`（先读）
> **分步提交纪律（硬）**：清单分批 commit+push；禁止 `git add -A` 全量提交。

## 目标

对 CCC 全项目做一次只读代码 bug 检查，输出 ≥15 条有证据的问题清单（每条含位置/现象/证据/影响/严重级 P0-P3/修复建议），供后续修复卡使用。

## 范围与维度

- 范围：`server/`（engine/board/web/kb/config）+ `desktop/Sources/CCCDesktop/` + `server/web/legacy-chat/` 前端
- 维度：正确性（逻辑/边界/空值/竞态/异常/资源泄漏/死代码）、前后端契约一致性、健壮性（超时/重试/降级/错误提示/轮询）、双壳行为差异、安全（低优先）
- 已知问题对照：`docs/cursor-code-check-handoff.md` §三 清单优先标记「已登记」，不重复发明

## 红线

1. **只读检查，不擅自改代码**（修复走正式卡）；问题清单文档除外
2. 只检查 `/Users/apple/program/CCC`；禁止 SSH 改 2017 生产
3. 不碰 QuantHive / qb；不碰 docs/archive/
4. 不伪造证据——每条问题给真实命令输出或代码引用

## 验收标准（Codex 独立复核，不采信自述）

1. 清单 ≥15 条，条条有位置（文件:行）+ 证据 + 严重级 + 修复建议
2. 至少覆盖 server/ 与 前端 两块；desktop 有结论（查了或说明受限原因）
3. pytest 全量真实输出附上；能补 swift build/test 更好
4. 分支分步提交、工作树干净、push 成功

## 回写要求

卡头状态更新为「已回写」；回写区填：清单全文或文件路径、检查方法、pytest/swift 输出、push 证据。

## 回写区

**执行体**：Cursor（M1）· **日期**：2026-08-05

### 清单

完整问题清单：[`docs/dispatch/T70-audit-report.md`](T70-audit-report.md)

- 新发现 **21** 条（F01–F21）：覆盖 engine/board、web/kb/前端、desktop
- 已登记 **5** 条（K1–K5）对照交接文档 §三
- P0×6 / P1×11 / P2×4

### 检查方法

1. 读 CURSOR.md / handoff / T70 / INDEX §0
2. 从 main 建分支 `codex/cursor-t02-code-audit`
3. 代码走读 server/engine|board|web|kb + legacy-chat + desktop；关键缺陷本地脚本复现
4. 不改业务代码；只写报告与本卡回写

### pytest（真实输出）

```text
$ .venv-hub/bin/python -m pytest server/tests --tb=no
7 failed, 484 passed in 13.50s
```

失败 7 例均 `test_engine_main.py`，探活 `http://127.0.0.1:6100/` Connection refused（M1 无中继，环境正常）。样例：

```text
WARNING  ccc.engine:main.py:118 探活失败: URL http://127.0.0.1:6100/ … Connection refused
WARNING  ccc.engine:main.py:348 探活失败，跳过该卡（保持待分派）
```

### swift

```text
$ cd desktop && swift build
Build complete! (exit 0)
```

### push 证据

- 分支：`codex/cursor-t02-code-audit`（已 push `origin`）
- commits：`37f0283`（清单）→ `1ecc28c`（本卡回写）
- HEAD：`1ecc28c0fedfc4a78d14cb45eec11d5f327782b2`

---

## 验收区（Codex 独立取证 · 2026-08-06）

**判定：✅ 通过。** 独立复核：① 范围守界（仅报告+卡，零业务代码改动）；② 抽查 8 条 P0/P1（F01/F02/F10/F11/F18/F19/F20/F04）全部属实——F01 正则确无 `>` 锚定、F02 read_text 无异常捕获、F11 SSE catch 确未 settleError（注释与代码不符）、F19 Kanban 确留英文旧列、F20 StreamBody 确缺 thread_id/model、F10 threads 路由确在 auth 前；③ pytest 7 failed/484 passed 与自述一致（7 失败均 M1 无中继环境性）；④ 严重级分级合理、修复建议可执行。
**评级**：Cursor 试运行表现合格（T68 首测 + T70 审计均独立验证无编造）。**修复排期**：P0 组（F01/F02/F11/F18/F19/F20）转修复卡；P1/P2 随整体联调消化。

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
