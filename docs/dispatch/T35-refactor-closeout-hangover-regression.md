# 任务卡 T35 · 重构收口：挂账清零 + 全量回归 + 双端验收（Trae 执行）

> 关联：INT-120（CCC 重构收口）· 契约：CCC 重构契约 v1（§5 安全三件套 / §6 验收）
> 依据：Codex 2026-08-03 全新取证重评——INT-120 挂账：patrol 2 失败（引用已归档 brief）、cluster DEFAULT_SERVICES 硬编码（T33 处理）、W292×16、2017 config.env.bak.T29、docs/REFACTOR-INDEX.md 验收清单未勾
> 执行体：Trae · 验收：Codex · 状态：待分派 · 日期：2026-08-03
> ⚠ 2026-08-03 T32 验收登记新增子项（P1-1）：Engine 接真实看板——文件/卡驱动 BoardStore（读 docs/dispatch → 回写卡头状态行）+ scheduler 扫真实卡 + 真实卡端到端演示；补完 Codex 复验 M2。
> ⚠ 2026-08-03 T33 验收附注：T31 P2 修正项并入本卡——P2-1 修正 CLAUDE.md/README.md/CHANGELOG.md 三处 scripts 归档路径（`.ccc/archive/...` → `docs/archive/...`）；P2-2 恢复 tests/ F401/F841/E402/I001 忽略（或 CLAUDE.md ruff 命令改 `server/`）使文档命令真实可绿。

## 目标

全部已知挂账清零，全量测试/扫描回归绿，双端部署复测通过，重构收口状态有据可查。

## 红线（先看）

1. 测试修复必须修根因（路径/断言随新结构更新），禁止跳过、禁止改语义凑绿。
2. 不碰 2017 运行面；2017 侧清理/验证如无 SSH 权限则登记「待核」并说明，不硬编。
3. 只动清单内文件；真实提交；验收标准不可自行解释。

## 范围

tests/scripts/test_authority_patrol.py、server/（W292×16 尾换行）、docs/dispatch/（卡头状态校对）、docs/REFACTOR-INDEX.md、docs/archive/ccc-legacy-2026-08-02/RETENTION-LIST.md（如需同步）、2017 config.env.bak.T29（如可及）、server/deploy/（双端 kickstart 验证记录）、**server/engine/（P1-1 接真实看板：文件/卡驱动 BoardStore + 卡头状态回写 + scheduler 扫真实卡 + 真实卡端到端演示）**、**CLAUDE.md/README.md/CHANGELOG.md（P2-1 归档路径修正）+ pyproject.toml/CLAUDE.md（P2-2 ruff 命令可绿）**。

## 步骤

0. **P1-1 Engine 接真实看板**：实现文件/卡驱动 BoardStore（读 `docs/dispatch/*.md` 卡头元数据 → 构造 Work → 状态流转后回写卡头「状态」行）；main.py 生产路径改用该实现；scheduler 定时扫真实卡；用一张真实格式任务卡做端到端演示（派发 → 执行体 → 卡头状态更新 → board/export 派生可见）。同时处理 P2-3（EXECUTOR_LOG_DIR 改必填或删代码默认路径）。
0.1. **P2-1**：CLAUDE.md:22 / README.md:109 / CHANGELOG.md:14 的 scripts 归档路径 `.ccc/archive/legacy-retired-2026-08-02/` → 改为 `docs/archive/legacy-retired-2026-08-02/`（3 处）。
0.2. **P2-2**：pyproject.toml 恢复 tests/scripts+tests/integration 的 F401/F841/E402/I001 忽略（或 CLAUDE.md ruff 命令收窄为 `ruff check server/`），使文档命令真实可绿；server/ 存量债（W292×16 + F821×6 + F401×3 等）清零。
1. patrol 2 失败：定位引用 `docs/briefs/2026-07-22-opencode-lifecycle-stall.md` 的用例，路径更新到归档区（docs/archive/ccc-legacy-2026-08-02/briefs/…）或按新目录结构调整断言，跑绿。
2. server/ 16 处 W292 补尾换行；`ruff check server/` 全绿。
3. 卡头状态校对：全量 docs/dispatch/*.md 卡头「状态」与回写区/实际一致（T18–T22、T29 等逐卡核对），不一致修正。
4. docs/REFACTOR-INDEX.md 验收清单按实际勾选；RETENTION-LIST 如有归档新增（T34 的 src-tauri 等）同步补录。
5. 2017 config.env.bak.T29：如有 SSH 权限删除并记录；无权限登记「待核」。
6. 双端 kickstart 复测（M1 本地 + 2017 可及则实测）：登录门 → 对话（大脑 Agent 回复）→ 看板/线路图/集群/运维 → 控制台；记录各端结果。
7. 全量回归：`pytest server/tests -q` + `pytest tests/scripts -q` 全绿；三扫描零命中；提交。

## 验收标准

1. 全量测试绿（server/tests + tests/scripts 含 patrol）；`ruff check server/ --select W292` 零命中。
2. REFACTOR-INDEX.md 验收清单全部勾选且有依据；卡头状态全量一致。
3. 双端实测记录完整（登录/对话/看板/运维/线路图/集群）；无法覆盖的项明确标「待核」。
4. 工作树干净（仅许可预存项）；真实提交。

## 回写要求

卡头状态更新为「已回写」；回写区填：patrol 修复根因、W292 清零统计、卡头校对清单、双端实测输出、pytest/ruff 结果、commit hash。

## 回写区

**执行体**：Trae · 日期：
