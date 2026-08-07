# 任务卡 mx001 · recon and baseline（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：mx · 日期：2026-08-07

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

**执行体**：OpenCode · 日期：
