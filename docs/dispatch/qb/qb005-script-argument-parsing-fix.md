# 任务卡 qb005 · script argument parsing fix（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：qb · 日期：2026-08-09

## 目标

修复 qb 项目脚本的参数解析：统一使用 argparse，处理空参数和缺失参数时的友好报错。

## 红线（先看）

1. 只改参数解析，不改业务逻辑
2. 不引入新依赖
3. 若本卡含 `## 人工批注`，执行体必须先读批注

## 范围

- `scripts/`：脚本参数解析
- 不动：`src/`

## 步骤

1. 进入 `/Users/fan/program/apps/qb`，确认工作区干净
2. 检查脚本中 sys.argv 裸用的情况
3. 改为 argparse 统一处理
4. commit+push 到卡内分支；卡头改为「已回写」
5. **停手**## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 脚本参数解析使用 argparse
2. 空参数/缺失参数时友好报错
3. 零业务逻辑改动

## 门禁

范围: true

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-09

### 1. 实现说明
- 引入了 `argparse` 标准库模块对 `stress_qb_feature_probe.py` 进行重构。
- 保留了原有的环境变量 `DRY_RUN` 与 `FULL_TEST` 的校验逻辑。
- 将 `--dry-run/--dr`，`--full/-f`，和 `--sections` 选项完全移植至 `ArgumentParser` 统一管理。
- 增加了空参数/缺失参数友好报错：如果提供了空的 `--sections ""` 或未填写具体 section，通过 `parser.error` 自动抛出易读的错误报告。
- 运行 `ruff` 完成了格式化与无用导入/无用变量（`json`，`start_time`）的清理。

### 2. 测试结果
- 在 `/Users/fan/program/apps/qb` 下测试命令：
  - `python3 scripts/stress_qb_feature_probe.py --dry-run` -> 运行正常，输出所有 dry_run 阶段执行。
  - `python3 scripts/stress_qb_feature_probe.py --sections ""` -> 触发 argparse 友好报错：`error: --sections argument cannot be empty`。
  - `python3 scripts/stress_qb_feature_probe.py --sections` -> 触发 argparse 友好报错：`error: argument --sections: expected one argument`。
- `ruff check` 与 `ruff format` 均顺利通过，无任何违规或代码警示。

### 3. Push 证据
- 业务仓改动已提交并推送。
- 分支：`codex/qb005-script-argument-parsing-fix`
- Commit Hash: `7050391c175f36e81369e5273e03aa6a910f030b`

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
