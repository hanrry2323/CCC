# xianyu M6.1 计划激活报告

日期：2026-09-05

## 事实对账

- `docs/projects/registry.yaml`：项目 `xianyu`，前缀 `xy`，`taskable: true`，`status: active`；业务仓路径为 `/Users/fan/program/apps/xianyu`。
- `docs/projects/xy/README.md`：确认 xianyu 为 2017 上的独立业务仓，CCC 前缀为 `xy`。
- `docs/projects/xy/roadmap.md`：M6「前端展示台」关联 `xy-plan-009`；6.1–6.4 均挂在该方案下；M5 为「计划中」，M7 为「起草（等 Cookie 前置）」。
- `docs/projects/xy/plans/009-frontend-showcase.md`：方案包含 6.1 内容库 API、6.2 工作流 API、6.3 视频/图文预览页面、6.4 工作流可视化页面；方案原状态为「待验收」。
- 工作区核验：CCC 仓在更新后干净；xianyu 业务仓原工作区干净，本次未修改业务仓。

## 本次改动

- `docs/projects/xy/roadmap.md`：仅将 6.1「内容库 API」状态从「待验收」改为「计划中」。采用仓库现有方案状态词；该状态表达计划已确认、尚未进入执行。
- `docs/projects/xy/plans/009-frontend-showcase.md`：新增「本次激活子项目」段，仅说明 6.1 的最小范围、无代码级依赖、只读验收边界，并明确 6.2、6.3、6.4 未激活。
- 未修改 M1–M3、M5、M7 或 6.2–6.4。

## 未激活项与流程边界

- 6.2「工作流 API」、6.3「视频/图文预览页面」、6.4「工作流可视化页面」均未激活。
- 未创建 `docs/dispatch/xy/` 新卡，未调用转卡脚本，未启动 DSH，未开发 xianyu 代码。
- 本次明确停在老板节点②之前，不进入验收、合入、部署或其他后续动作。

## 校验

- `scripts/validate-plans.sh`：全量校验通过；既有历史兼容项仅产生 WARN，未新增失败。
- `git diff --check`：通过。

## Git 状态快照

- CCC：本次变更仅限本报告、xianyu roadmap 和 xy-plan-009 三类文档；提交前将复核状态并推送 `origin/main`。
- xianyu 业务仓：`main` 工作区保持干净；无文件改动。
