# 任务卡 mx024 · quick-xml 安全债升级（OpenCode 执行）

> 关联：ccc-plan: medio-0 打磨第四批：质量门禁与安全债、架构暴露 · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：mx · 日期：2026-08-08

## 目标

quick-xml 安全债升级（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `Cargo.toml / Cargo.lock（quick-xml 依赖版本）`
- `使用 quick-xml 的相关源码（适配 API 变化）`
- `相关测试文件`

## 步骤

1. 在 Mac2017 进入 `cd /Users/fan/program/apps/medio-0`，跑 `cargo tree -i quick-xml`（或 grep Cargo.lock）确认 quick-xml 的直接/间接依赖链与当前版本（0.36）。
2. 升级至 0.41+（或当前最新稳定），适配 breaking changes（quick-xml 0.36→0.41 有 API 变化，如 writer/reader API）；如 quick-xml 仅被某处使用，评估是否可用既有 atom_syndication 替代从而彻底移除（回写区说明选择与理由）。
3. `cargo check` / `cargo test` 全量通过；`cargo audit` 确认该 RUSTSEC 项不再报。
4. 若升级涉及 RUSTSEC 忽略清单（`.cargo/audit.toml` 或 ci 配置），同步移除对应 ignore。
5. 回写区记录：升级前后版本、API 适配点、audit 结果。
6. 探针：`git -C /Users/fan/program/apps/medio-0 status -sb` 只有白名单改动；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
7. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. quick-xml 从 0.36 升级至 0.41+（消除已知 DoS 风险），适配 breaking changes；升级后全仓编译/测试通过
2. 如 quick-xml 已无直接依赖或已被替代，核实并说明（cargo tree 证据）；cargo audit 该漏洞不再报
3. 只动白名单；不直推 main

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
