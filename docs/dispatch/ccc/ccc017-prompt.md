# 任务卡 ccc017 · 引擎 prompt 注入审计日志（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-09

## 目标

为引擎 prompt 注入添加审计日志：每次注入时记录（卡号、阶段、注入字符数、时间戳）到结构化日志，便于追踪注入效果。

## 红线（先看）

1. **只加日志，不改注入逻辑**：在 `_dispatch_and_collect` 中注入点后追加日志写入，不改变注入行为。
2. **零硬编码**：日志路径从配置读取。
3. 若本卡含 `## 人工批注`，执行体必须先读批注。

## 范围

- `server/engine/main.py`：`_dispatch_and_collect()` 注入点后追加审计日志
- `server/tests/test_engine_main.py`：新增审计日志测试用例

## 步骤

1. 在 `_dispatch_and_collect()` 的注入点后，追加写入 `prompt_inject.jsonl`。
2. 日志格式：`{"ts":"...","card_id":"...","phase":"run|audit","section":"执行提示|机审提示","chars":N}`
3. 日志路径：`{EXECUTOR_LOG_DIR}/prompt_inject.jsonl`。
4. 新增测试用例：执行后检查 `prompt_inject.jsonl` 存在且内容合法。
5. 运行 `python3 -m pytest server/tests/test_engine_main.py -v` 全绿。
6. commit+push 到卡内分支；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 执行体派发后 `prompt_inject.jsonl` 含注入记录（card_id + phase + chars）
2. `python3 -m pytest server/tests/test_engine_main.py` 全绿，新增用例通过
3. 零硬编码：日志路径从 EXECUTOR_LOG_DIR 配置读取

## 门禁

测试: python3 -m pytest server/tests/test_engine_main.py -v

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

- 项目：ccc（自动化任务编排平台：薄驱动 Engine + Markdown 任务卡 + 看板/HTTP + 2017 单端生产。）

- 仓库路径：/Users/fan/program/CCC（Mac2017）

- 开发技能与命令：
  - [domains::projects::常用命令] 常用命令 - 运行测试： 全量 - 单模块测试： - 代码检查：
  - [domains::projects::常用命令] 常用命令 - 运行测试： - 单模块测试： - 代码检查： - 编译检查： - 出卡： - 看板：
  - [domains::projects::常用命令] 常用命令 - 编译检查： - 运行测试： - 后端单测： - 前端测试： - 端到端测试： - 构建： - 代码检查：

- 禁区：- 不在本仓写 QuantHive 业务；不把双轨混成一个项目
- 2017 生产副本不手改；不恢复 Hub :7777 / 旧 scripts 编排
- 项目注册只改 [`../registry.yaml`](../registry.yaml)，禁止只改 `PREFIXES` 或 KB seed

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：ccc（自动化任务编排平台：薄驱动 Engine + Markdown 任务卡 + 看板/HTTP + 2017 单端生产。）

- 审查重点：代码实现质量、边界条件、异常处理、架构隐患

- 架构约束/红线：- 不在本仓写 QuantHive 业务；不把双轨混成一个项目
- 2017 生产副本不手改；不恢复 Hub :7777 / 旧 scripts 编排
- 项目注册只改 [`../registry.yaml`](../registry.yaml)，禁止只改 `PREFIXES` 或 KB seed

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭
