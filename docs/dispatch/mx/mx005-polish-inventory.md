# 任务卡 mx005 · polish inventory for code and UI（OpenCode 执行）

> 关联：ccc-plan: mx 打磨线启动：服务健康巡检 + 打磨盘点 · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：mx · 日期：2026-08-07

## 目标

medio-0 打磨线启动摸底（纯只读，不开发）：盘点现有代码质量缺口（CI/审计/lint/测试）、功能细节打磨点（已知痛点/边界 bug/TODO）、UI 优化点（组件与体验细节），输出 ≥8 项打磨点清单（分代码质量/功能细节/UI 优化三类，每项现状+建议）回写 `docs/roadmap.md`「业务线路（mx）」段，作为后续打磨卡拆分依据。老板方向：暂不开发新功能，聚焦现有功能打磨 + 代码优化 + 界面优化。

## 红线（先看）

1. **绝对禁止**修改、添加、删除 medio-0 业务仓（`/Users/fan/program/apps/medio-0`）任何文件；只读 `ls`/`cat`/`git log`/`rg`；禁止 `cargo build`/`npm install`/启服务/改配置。
2. 文档改动**只允许**在 CCC 仓本机：`docs/roadmap.md`、`docs/projects/mx/README.md`、本任务卡。
3. 禁止在 CCC 仓新建业务深文档目录（如 `docs/projects/mx/xxx.md` 业务详文）。
4. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- 只读侦察：`/Users/fan/program/apps/medio-0`（CI 工作流与告警、cargo audit 配置与 RUSTSEC 忽略清单、ESLint/Prettier 配置、`tests/` 结构与覆盖、`docs/lessons.md` 已知痛点、`adr/` 决策、源码 TODO/FIXME、前端组件与 UI 细节）
- 回写：`docs/roadmap.md`「业务线路（mx）」段追加打磨点清单；`docs/projects/mx/README.md`「线路 / 近况」≤3 行同步一句

## 步骤

1. 在 Mac2017 进入 `cd /Users/fan/program/apps/medio-0`，只读侦察代码质量面：
   - `.github/workflows/ci.yml`：CI 实际跑哪些检查（fmt/clippy/audit/test/build）、有无挂起/降级项
   - `cargo audit` 相关配置与 3 个已知 risk-accepted RUSTSEC 的具体项与原因（`git log` 找 `ignore` 提交）
   - `eslint.config.js` / `.prettierrc`（若存在）：lint 规则与是否接入 husky/lint-staged
   - `tests/`：pytest 用例数与覆盖面（`tests/test_probe.py`、`test_api_smoke.py` 等）
2. 只读侦察功能细节面：`docs/lessons.md` 已知痛点清单、`adr/` 关键决策、`rg -n "TODO|FIXME|HACK|XXX" src/` 残留标记。
3. 只读侦察 UI 面：`src/frontend/src` 组件结构（页面/组件数、共享组件复用度）、Tailwind 4 主题与暗色默认、无障碍与细节（确认弹窗/toast/加载态/封面渲染）。
4. 整理打磨点清单（≥8 项）：分三类（代码质量/功能细节/UI 优化），每项写「现状 + 建议动作 + 预估成本 S/M/L」。
5. 回写 `docs/roadmap.md`「业务线路（mx）」段：追加「打磨点清单」子段；`docs/projects/mx/README.md`「线路 / 近况」≤3 行同步一句（如「打磨盘点完成，清单挂 roadmap」）。
6. 探针自检：`git -C /Users/fan/program/apps/medio-0 status -sb` clean（业务仓零改动）；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
7. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 打磨点清单（≥8 项，分代码质量/功能细节/UI 优化三类，每项现状+建议）回写 docs/roadmap.md「业务线路（mx）」段
2. medio-0 业务仓零改动（git status clean），纯只读侦察
3. python3 -m server.board.validate docs/dispatch 通过

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
