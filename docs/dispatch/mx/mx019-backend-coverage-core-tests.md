# 任务卡 mx019 · 后端覆盖率收窄与核心服务单测（OpenCode 执行）

> 关联：mx-plan-001 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：mx · 日期：2026-08-08

## 目标

后端覆盖率收窄与核心服务单测（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `测试配置文件（tarpaulin 配置/排除清单）`
- `src/backend/core/src/ 下新增单测（核心服务）`
- `Cargo.toml（如补测试依赖）`

## 步骤

1. 在 Mac2017 进入 `cd /Users/fan/program/apps/medio-0`，读当前 tarpaulin 配置（`.github/workflows/ci.yml` 中 coverage job 或 tarpaulin 参数）与 `exclude-files` 排除清单。
2. 收窄排除：将 websub_service / scan_scheduler / rss_service 等核心服务从 exclude 移入统计；识别暴露的未覆盖代码面。
3. 为覆盖率最低/核心服务补单测（SQLite 内存库）：覆盖主要路径与错误分支；**真实断言**（不注水、非空壳）。
4. 跑覆盖率：`cargo tarpaulin --out html`（或 CI 同款命令），记录数值；目标真实整体覆盖率 ≥80%。
5. `cargo test` / `cargo clippy` 通过；确认无业务逻辑改动（纯测试+配置）。
6. 回写区记录：覆盖率前后数值对比 + 命令；CI 配置改动说明。
7. 探针：`git -C /Users/fan/program/apps/medio-0 status -sb` 只有白名单改动；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
8. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. tarpaulin exclude-files 收窄（websub_service / scan_scheduler / rss_service 等核心服务纳入统计），补 SQLite 内存库单测，真实整体覆盖率 ≥80%
2. 新增测试为真实断言（非空壳/无注水）；cargo test / clippy 通过
3. 覆盖率报告数据回写（数值 + 命令）；只动白名单；不直推 main

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

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
