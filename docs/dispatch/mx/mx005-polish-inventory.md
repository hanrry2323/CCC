# 任务卡 mx005 · polish inventory for code and UI（OpenCode 执行）

> 关联：mx-plan-001 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：mx · 日期：2026-08-07

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

**执行体**：OpenCode · 日期：2026-08-07

### 实现说明
1. **代码质量摸底**：深入审计了 `medio-0` 的 `.github/workflows/ci.yml`、`Cargo.toml` / `Cargo.lock`、`eslint.config.js` / `.prettierrc` 以及 `tests/` 结构与覆盖率情况。识别出：后端格式化 CI/Hook 检查缺失、tarpaulin 覆盖率排除范围过大、前端测试覆盖率未在 CI 门禁中运行、历史依赖漏洞等代码质量缺陷。
2. **功能细节摸底**：通过 `lessons.md` 梳理了 iOS 视频播放权限、随机 refill 串文件夹和网络盘抖动误删等核心教训，并对 `issues.jsonl` 台账进行了全面扫描，发掘了设置页前端校验、认证暴破、敏感操作无速率限制等痛点。
3. **UI/UX 细节摸底**：分析了 Tailwind 4 / shadcn 的 CSP 兼容现状，以及移动端大操作触控、确认弹窗等细节。
4. **打磨点输出**：整理归纳出 9 项具体打磨点（3类，含现状、建议动作与预估成本 S/M/L），全量追加到 `docs/roadmap.md` 的「业务线路（mx）」打磨点清单子段中。
5. **项目 README 更新**：同步更新 `docs/projects/mx/README.md`「线路 / 近况」为 “打磨盘点完成，清单挂 roadmap（mx005）”。

### 测试与自检结果
1. **业务仓零改动校验**：运行 `git -C /Users/fan/program/apps/medio-0 status -sb`，确认本地未对业务仓进行任何修改，符合只读红线。
2. **本地卡头自检**：运行 `python3 -m server.board.validate docs/dispatch`，卡头及格式校验 100% 通过。

### push 证据
- Commit Hash: `b56fa4e5d753cd249a7bcbb8dbb0befc121fa449`

## 机审区

机审：通过


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
