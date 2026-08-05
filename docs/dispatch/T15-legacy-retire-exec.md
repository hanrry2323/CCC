# 任务卡 T15 · 旧系统退役执行（第一阶段 + 第二阶段清单）（Trae 执行）

> 关联：INT-120（CCC 重构收尾）· 依据：`docs/legacy-retirement-list.md`（T12-R 版）· 管理席：Codex
> 执行体：Trae（手动）· 验收：Codex · 状态：已关闭 · 日期：2026-08-02 · 派发：manual · 项目：ccc
> 运行面提示：本卡执行**第一阶段（安全项）**；第二阶段（`scripts/` 归档 + 2017 旧引擎停止）只产出执行清单与回滚方案，**不执行**——停止 2017 旧引擎会停掉 qb 产线，须新栈接管 qb 确认后另行放行。

## 目标

执行退役清单第一阶段：清理构建产物（relay/node_modules、desktop/.build）+ 归档小模块（app/lib/db/skills）；产出第二阶段（scripts/ 退役）执行清单（含 2017 旧引擎停止/切换步骤与回滚）。

## 红线（先看）

1. **只动第一阶段明确项**：`scripts/`、`desktop/` 源码、`templates/` 一律不动（暂留）。
2. **不碰运行面**：2017 旧引擎/launchd/qb 产线零接触；M1 运行服务（7788/7777/7775/4100/4102 等）零接触。
3. 归档用 `git mv`（可追溯）；删除仅限可重建产物（node_modules/.build），删除前确认 gitignore/可重建。
4. 不落密钥；不读写外脑；验收标准不可自行解释；完成必须提交（真实 commit）。
5. 工作树只允许预存 1 个无关改动（`_update_handoff.py`）。

## 范围

- 清理：`relay/node_modules`（78MB）、`desktop/.build`（1.3GB，若存在）。
- 归档（git mv 至 `docs/archive/legacy-retired-2026-08-02/`）：`app/`、`lib/`、`db/`、`skills/`。
- 只读参考：`docs/legacy-retirement-list.md`。

## 步骤

1. 构建产物清理：确认 gitignore 覆盖后删除本地 `relay/node_modules`、`desktop/.build`；`git status` 无意外删除。
2. 归档小模块：`app/`、`lib/`、`db/`、`skills/` → `git mv` 到 `docs/archive/legacy-retired-2026-08-02/`（保留原相对路径）。
3. 更新 `docs/legacy-retirement-list.md`：标记第一阶段已完成项。
4. 产出第二阶段执行清单（文档内或独立 `docs/legacy-phase2-plan.md`）：`scripts/` 归档步骤 + 2017 旧引擎停止/切换步骤（含确认命令）+ 回滚方案 + 放行条件（新栈接管 qb 确认）。
5. 提交 `chore(retire):`，回写真实 commit hash。

## 验收标准（Codex 按此验收）

1. 构建产物清理干净（relay/desktop 体积下降实测），git 无意外删除、无被跟踪产物丢失。
2. 小模块已归档（git mv 可追溯，内容零丢失）。
3. `scripts/`、运行服务、2017 零改动零接触。
4. 第二阶段清单含放行条件与回滚，可直接作为后续卡输入。
5. `server/` 测试不回归；真实提交；工作树仅剩 1 个预存项。

## 回写要求

结果摘要（人话一句）、清理/归档统计、git mv 列表、第二阶段清单路径、commit hash；按契约 §3 同步更新本卡卡头状态。

## 回写区

**结果摘要**：第一阶段清理/归档完成（构建产物已删除，小模块已 git mv 归档），第二阶段执行清单（含回滚方案）已产出至 `docs/legacy-phase2-plan.md`。

**清理/归档统计**：
- 删除：`relay/node_modules/`（78MB 构建产物，gitignored）、`desktop/.build/`（1.3GB 构建产物，gitignored）
- 归档（git mv → `docs/archive/legacy-retired-2026-08-02/`）：`app/`（6 文件）、`lib/`（2 文件）、`db/`（1 文件）、`skills/`（9 文件），合计 18 文件 ~76KB
- 保留：`relay/dist/`（188KB，待执行）

**git mv 列表**：`app/`、`lib/`、`db/`、`skills/` → `docs/archive/legacy-retired-2026-08-02/`（已提交 `88cf04a`）

**第二阶段清单路径**：`docs/legacy-phase2-plan.md`

**commit hash**：`88cf04a`（git mv 归档）+ `65c4640`（本卡回写 + 退役清单 + 第二阶段计划）
