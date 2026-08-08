# 任务卡 qb003 · 代码规范与 lint 自动化（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：qb · 日期：2026-08-09

## 目标

为 qb 项目配置代码规范自动化：添加 ruff/pre-commit 配置，确保每次提交前自动检查代码质量。

## 红线（先看）

1. **只加配置，不修代码**：仅添加 `.pre-commit-config.yaml` 和 `pyproject.toml` 中的 lint 配置，不修改业务代码。
2. 若本卡含 `## 人工批注`，执行体必须先读批注。

## 范围

- `pyproject.toml`：添加 ruff 配置
- `.pre-commit-config.yaml`：新增 pre-commit 钩子
- 不动：`src/`、`tests/`

## 步骤

1. 进入 `/Users/fan/program/apps/qb`，`git status -sb` 确认工作区干净。
2. 检查现有 `pyproject.toml` 是否有 lint 配置。
3. 添加 ruff 配置到 `pyproject.toml`。
4. 创建 `.pre-commit-config.yaml`：ruff + basic checks。
5. 安装 pre-commit hooks：`pre-commit install`。
6. 验证：`pre-commit run --all-files` 通过。
7. commit+push 到卡内分支；卡头改为「已回写」。
8. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `pre-commit run --all-files` 通过
2. `.pre-commit-config.yaml` 含 ruff hook
3. `pyproject.toml` 含 ruff 配置
4. 零业务代码改动

## 门禁

测试: pre-commit run --all-files

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

## 执行提示

- 项目：qb（CCC 自动化开发测试用业务仓（挂 Engine 出卡）。）

- 仓库路径：/Users/fan/program/apps/qb（Mac2017）

- 开发技能与命令：
  - [domains::projects::常用命令] 常用命令 - 运行测试： 全量 - 单模块测试： - 代码检查：
  - [domains::projects::常用命令] 常用命令 - 运行测试： - 单模块测试： - 代码检查： - 编译检查： - 出卡： - 看板：
  - [domains::projects::常用命令] 常用命令 - 编译检查： - 运行测试： - 后端单测： - 前端测试： - 端到端测试： - 构建： - 代码检查：

- 禁区：- 禁止在 CCC 建 `docs/qb/` 深文档树
- 禁止把 M1 错误路径当工作区

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：qb（CCC 自动化开发测试用业务仓（挂 Engine 出卡）。）

- 审查重点：代码实现质量、边界条件、异常处理、架构隐患

- 架构约束/红线：- 禁止在 CCC 建 `docs/qb/` 深文档树
- 禁止把 M1 错误路径当工作区

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭
