# 任务卡 mx006 · CI 补后端 Rust 格式门禁（OpenCode 执行）

> 关联：ccc-plan: mx 打磨第一批：后端格式门禁 + 设置页路径校验 · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：mx · 日期：2026-08-07

## 目标

medio-0 打磨第一批（按 mx005 清单第 1 项）：后端 Rust 代码格式门禁落地——CI backend 步骤补 `cargo fmt --all -- --check`，本地 husky/lint-staged 覆盖 Rust 文件，先统一现有代码格式再上门禁。

## 红线（先看）

1. **格式化即格式化**：`cargo fmt --all` 只允许纯格式改动，**禁止夹带任何逻辑/重构**；格式化后必须自查 diff 确认。
2. 只动白名单文件（CI 配置、husky/lint-staged 配置、rustfmt 配置、被格式化的现有 Rust 文件）；**禁止**改业务逻辑代码、数据库、前端业务代码。
3. 禁止 `cargo build`/`npm install` 装包；CI 配置改动本地以 yaml 语法校验 + 逻辑核对为准。
4. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `.github/workflows/ci.yml`（backend 步骤加 fmt 门禁）
- `package.json` / husky / lint-staged 配置（本地 Rust 文件格式化校验）
- `rustfmt.toml`（如需新增，保持默认风格即可）
- 现有 Rust 文件（仅 cargo fmt 格式化产生）

## 步骤

1. 在 Mac2017 进入 `cd /Users/fan/program/apps/medio-0`，先读现状：
   - `.github/workflows/ci.yml` 的 backend job（确认现有 clippy/fmt 步骤）
   - `package.json` 的 husky / lint-staged 配置（确认当前只覆盖前端）
   - `cargo fmt --all -- --check` 当前结果（确认存量未格式化文件范围）
2. 先统一存量格式：`cargo fmt --all`，然后 `git diff` 自查 **diff 中只有格式变化、零逻辑改动**（必要时 `git diff -w` 对比确认）。
3. CI 门禁：`.github/workflows/ci.yml` backend job 增加 `cargo fmt --all -- --check` 步骤（放在 check/clippy 之前或并行）。
4. 本地钩子：在 lint-staged/husky 中为 `**/*.rs` 增加 rustfmt 校验（如 `cargo fmt --all -- --check` 或 rustfmt --check），配置方式与现有前端配置风格一致。
5. 自测：人为在某个 .rs 文件制造一处未格式化改动 → 触发本地钩子应拦截（exit 非 0）→ **立即还原**；回写区记录自测过程与还原证据。
6. 探针：`cargo fmt --all -- --check` 退出码 0；`git -C /Users/fan/program/apps/medio-0 status -sb` 只有白名单改动；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
7. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. CI backend 步骤含 cargo fmt --all -- --check 门禁；本地 husky/lint-staged 覆盖 Rust 文件（人为制造未格式化文件能拦截，自测后还原并记录）
2. 现有代码经 cargo fmt --all 统一后 cargo fmt --check 通过；diff 中无业务逻辑改动（仅格式化）
3. 只动白名单文件；不直推 main

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
