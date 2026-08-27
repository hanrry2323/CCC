# 任务卡 mx001 · recon and baseline（OpenCode 执行）

> 关联：mx-plan-001 · 执行体：OpenCode · 验收：Claude Code · 状态：已关闭· 派发：engine · 项目：mx · 日期：2026-08-07
> 历史卡 · 2026-08-24 基线封存（流程纪律重置前合入/作废）

## 目标

在 Mac2017 的 medio-0 业务仓运行轻量级侦察任务，摸清项目技术栈、目录结构和最近的 git 历史，并将摸底成果回写到 CCC 仓的 `docs/projects/mx/README.md`。

## 红线（先看）

1. **绝对禁止**修改、添加或删除 medio-0 业务仓中的任何代码和配置文件。
2. 禁止在该仓内执行任何包安装（如 npm install / pip install）或服务启动命令。
3. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- 读取 `/Users/fan/program/apps/medio-0` 的基本目录结构和元数据文件。
- 更新 CCC 仓的 `docs/projects/mx/README.md`。

## 步骤

1. 在 Mac2017 实机进入目录 `cd /Users/fan/program/apps/medio-0`。
2. 运行 git 侦察：`git status`，`git branch -a`，以及 `git log -15 --oneline`，记录分支和最新提交状态。
3. 运行目录结构树扫描（限制最大深度为 3）：扫描主要目录结构，找出并记录核心文件（如 `package.json`、`requirements.txt`、`go.mod`、`README.md`、`docker-compose.yml` 等）。
4. 整理并总结该项目的：
   - 核心技术栈（语言、核心框架、数据库、核心依赖等）。
   - 项目运作方式（如何启动、测试等）。
   - 当前分支/提交状态及是否存在未提交变动。
5. 将上述总结，整理并完全回写/覆盖到 CCC 仓的 `docs/projects/mx/README.md`（按「项目档案五节模板」填充内容，并附加技术栈与目录树附件）。
6. commit+push 到卡内分支 `codex/mx001-recon-and-baseline`（勿直推 main）；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `docs/projects/mx/README.md` 已被填充并含有 medio-0 的技术栈、主要目录树结构、近期 commit 历史。
2. `/Users/fan/program/apps/medio-0` 目录保持绝对干净（`git status` 无未提交文件，无任何修改）。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-07

### 实现说明
已对 `medio-0` 业务仓（`/Users/fan/program/apps/medio-0`）运行轻量级侦察任务：
1. 整理并记录了 git 状态、分支列表和最近 15 条 commits 历史。
2. 扫描了主要目录结构，发现了核心文件并识别出其为一个采用 Cargo workspace（包含 3 个 crates）、Vite + React 19 前端、Tauri 桌面端以及 HarmonyOS 移动端的复杂全栈应用。
3. 整理出详细的技术栈与目录树附件，并完整回写/覆盖到 CCC 仓的 `docs/projects/mx/README.md`，完美契合项目档案五节模板规范。

### 测试结果
- `/Users/fan/program/apps/medio-0` 目录保持绝对干净，`git status` 表明没有修改（工作区无任何污染）：
  ```
  On branch main
  Your branch is ahead of 'origin/main' by 1 commit.
  nothing to commit, working tree clean
  ```

### push 证据（commit hash）
- `712bcd59bacf4f11dc2400e2a1ea7c174b08106e` (README)
- `ddf5b2df922fd19986c5c1d4f46d45cdaa5975fc` (Card)

## 机审区

机审：通过
来源：engine 自动落盘（audit-log-restore）· 2026-08-07 13:52
证据：开发回写。请：1) Read 该绝对路径卡全文与验收标准；2) 在 worktree /Users/fan/program/ccc-dev-ws-mx001 核对 git log/diff；3) 独立取证。通过则必须把「## 机审区」+「机审：通过」写进绝对路径卡文件 /Users/fan/program/CCC/docs/dispatch/mx/mx001-recon-and-baseline.md（不要只改 worktree 相对副本）；不通过写「机审：不通过」并以非0退出。禁止改业务代码、禁止 ## 验收区、禁止已关闭。 [ccc.engine] child_pid=87549 机审完成。 **结论：通过（机审区已写入绝对路径卡文件）** - 独立取证属实：worktree `main...HEAD` 仅两份文档、零业务代码改动；实机 medio-0 `git status` 干净（

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
