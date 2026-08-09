# 任务卡 mx013 · 整体架构文档与开发指南（OpenCode 执行）

> 关联：mx-plan-001 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：mx · 日期：2026-08-07

## 目标

medio-0 框架文档地基（工程框架优化第一批）：在 medio-0 仓 `docs/` 新增整体架构文档（汇总 ADR-001~013 成系统架构总览）+ 开发指南（环境/启动/测试/构建/发布/规范），补齐"能用的功能堆叠但有框架感"的文档缺口。

## 红线（先看）

1. **零代码改动**：只动 medio-0 仓 `docs/` 下新增 ≤2 篇文档；**禁止**改任何 src/、scripts/、配置文件。
2. **文档必须与现状一致**：命令、模块路径、配置名逐一与 `scripts/`、`src/`、`config.toml` 核对，**禁止臆造**；与既有 `docs/deployment.md`、`adr/` 口径一致。
3. 禁止在 CCC 仓新建业务深文档目录（回写只走本卡文件）。
4. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- medio-0 仓 `docs/` 下新增 ≤2 篇文档（架构总览 + 开发指南）
- 既有文档链接修订（如引用需要，最小更新）

## 步骤

1. 在 Mac2017 进入 `cd /Users/fan/program/apps/medio-0`，只读收集素材：`adr/`（ADR-001~013 标题与关键决策）、`Cargo.toml`（workspace 三 crate 职责）、`src/` 目录结构（backend core/server/tauri + frontend 页面组件）、`scripts/` 命令清单（build/deploy/test 等实际命令）、`docs/deployment.md`、`config.toml` 配置字段。
2. 撰写**整体架构文档**（如 `docs/architecture.md`）：系统架构总览——三 crate 分层与职责、前后端关系与 API 面、核心模块（RSS 爬虫/调度/扫描/媒体库/播放/鉴权）、关键数据流（抓取→解析→落库→前端展示）、引用对应 ADR 编号。
3. 撰写**开发指南**（如 `docs/developer-guide.md`）：环境搭建（Rust/Node）、启动（后端/前端）、测试（cargo test / vitest / pytest 命令与范围）、构建与发布（build/bump-version 流程）、代码规范（fmt/clippy 门禁、lint-staged）、目录地图（src/frontend 页面 ↔ src/backend 模块）。
4. 一致性抽查：≥3 处命令/路径/配置名与代码核对一致（回写区列出抽查项与结果）。
5. 探针：`git -C /Users/fan/program/apps/medio-0 status -sb` 只有白名单改动；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
6. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. medio-0 仓 docs/ 新增整体架构文档：系统架构总览（三 crate 分层、前后端关系、核心模块 RSS/扫描/媒体库/播放、数据流），引用既有 ADR 决策
2. 新增开发指南：环境搭建/启动/测试/构建/发布命令（与 scripts/ 实际一致）、代码规范（fmt/clippy 门禁）、目录地图
3. 文档与代码现状一致（抽查 ≥3 处：模块路径/命令/配置名对得上）；零代码改动；不直推 main

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
