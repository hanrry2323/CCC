# 任务卡 T35 · 重构收口：挂账清零 + 全量回归 + 双端验收（Trae 执行）

> 关联：INT-120（CCC 重构收口）· 契约：CCC 重构契约 v1（§5 安全三件套 / §6 验收）
> 依据：Codex 2026-08-03 全新取证重评——INT-120 挂账：patrol 2 失败（引用已归档 brief）、cluster DEFAULT_SERVICES 硬编码（T33 处理）、W292×16、2017 config.env.bak.T29、docs/REFACTOR-INDEX.md 验收清单未勾
> 执行体：Trae · 验收：Codex · 状态：待分派 · 日期：2026-08-03

## 目标

全部已知挂账清零，全量测试/扫描回归绿，双端部署复测通过，重构收口状态有据可查。

## 红线（先看）

1. 测试修复必须修根因（路径/断言随新结构更新），禁止跳过、禁止改语义凑绿。
2. 不碰 2017 运行面；2017 侧清理/验证如无 SSH 权限则登记「待核」并说明，不硬编。
3. 只动清单内文件；真实提交；验收标准不可自行解释。

## 范围

tests/scripts/test_authority_patrol.py、server/（W292×16 尾换行）、docs/dispatch/（卡头状态校对）、docs/REFACTOR-INDEX.md、docs/archive/ccc-legacy-2026-08-02/RETENTION-LIST.md（如需同步）、2017 config.env.bak.T29（如可及）、server/deploy/（双端 kickstart 验证记录）。

## 步骤

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
