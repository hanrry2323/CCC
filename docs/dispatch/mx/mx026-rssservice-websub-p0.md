# 任务卡 mx026 · RssService WebSub 联动断链修复（P0）（OpenCode 执行）

> 关联：mx025 架构问题清单 #1 P0 · WebSub 实时推送功能断链 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：mx · 日期：2026-08-09

## 目标

修复 medio-0 中 RssService 的 WebSub 联动被注释禁用的断链问题（P0），恢复 WebSub 实时推送功能。

## 红线（先看）

1. **只修断链**：仅恢复 `src/backend/core/src/rss/service.rs:94` 附近 WebSub 联动的路径引用并重新启用；不改动其他业务逻辑与行为。
2. **不引入新依赖**：禁止新增 crate/第三方依赖，除非编译无法通过且为最小必要改动。
3. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src/backend/core/src/rss/service.rs`（WebSub 联动段，约 :94）
- 关联的 WebSub/推送相关模块（如需恢复编译必需的最小范围）
- 后端编译与测试验证

业务仓路径：`/Users/fan/program/apps/medio-0`（Mac2017）。

## 步骤

1. 进入 `/Users/fan/program/apps/medio-0`，`git status -sb` 确认工作区干净、基于最新 main。
2. 定位 `src/backend/core/src/rss/service.rs:94` 附近被注释禁用的 WebSub 联动代码（mx025 审计确认：路径重构致编译错误后被注释）。
3. 恢复路径引用并重新启用 WebSub 联动；确认编译通过（`cargo check` / `cargo build`）。
4. 若该模块已有单测，运行相关测试；确认无回归。
5. 回写区记录：断链根因、改动 diff 要点、编译/测试输出尾部。
6. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `src/backend/core/src/rss/service.rs` WebSub 联动已恢复并重新启用（不再被注释禁用），路径引用正确
2. `cargo check`（或 `cargo build`）通过，无编译错误；若有相关单测，运行通过
3. 探针：`git -C /Users/fan/program/apps/medio-0 status -sb` 只含白名单范围改动；不直推 main

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-09

### 实现说明
1. **定位并解决问题**：在 `medio-0` 项目的 `src/backend/core/src/service/rss/service.rs` 中定位了由于重构引起路径引用错误（原 `crate::service::websub_service::WebSubService` 无法被解析）而被注释禁用的 WebSub 链接检测联动代码。
2. **修复路径引用**：经代码上下文库查找，确认正确的模块路径应该为 `crate::service::rss::WebSubService::detect_websub_links`。已将其恢复并重新启用，并将 `_content` 变量改为 `content` 以正确传递给检测函数，从而彻底消除了断链，使 WebSub 实时推送功能能成功联动。
3. **安全与依赖**：没有引入任何新依赖、新 crate，也未改动其他的业务逻辑。

### 测试结果
1. **编译检查**：在 `medio-0` 中执行 `cargo check` 以及 `cargo check --tests -p medio-core`，一切编译通过，无任何错误或警告。
2. **单元测试**：成功运行 `cargo test -p medio-core --lib` 所有的库单元测试，全部 423 个测试全部 PASS（其中包含了 `service::rss::websub` 模块下的所有测试，确保联动和 SSRF 验证逻辑均工作正常且无回归）。

### push 证据（commit hash）
- **业务仓 (medio-0) 提交分支**：`codex/mx026-rssservice-websub-p0`
- **提交哈希 (commit hash)**：`d8377d00bb94a0b583223cdf750196c5a024c220`
